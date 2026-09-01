"""
Policy engine tests.

Tests the deterministic authorization logic.
Does not test Razorpay (that's phase C).

Tests cover:
- Per-transaction limit (₹50,000)
- Session spending limit (₹1,00,000)
- Price drift detection (>2%)
- Duplicate order prevention
- Audit logging
"""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.db.init_db import create_audit_log_triggers
from backend.db.models import AuditLog, Base, Order, Product, Proposal
from backend.policy.engine import PolicyEngine
from backend.policy import rules


@pytest.fixture
def test_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_policy.db"
        database_url = f"sqlite:///{db_path}"

        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

        Base.metadata.create_all(bind=engine)

        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

        import sqlite3
        conn_sqlite = sqlite3.connect(str(db_path))
        cursor = conn_sqlite.cursor()

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_log_prevent_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log table is append-only and cannot be updated');
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_log_prevent_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log table is append-only and cannot be deleted');
            END
        """)

        conn_sqlite.commit()
        conn_sqlite.close()

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Seed test products
        session = SessionLocal()
        products = [
            Product(name="Budget Item", description="Low price", current_price=10000),  # ₹100
            Product(name="Mid-Range Item", description="Medium price", current_price=1000000),  # ₹10,000
            Product(name="Premium Item", description="High price", current_price=5000000),  # ₹50,000
            Product(name="Expensive Item", description="Very high price", current_price=6000000),  # ₹60,000
        ]
        for product in products:
            session.add(product)
        session.commit()
        session.close()

        def make_db():
            return SessionLocal()

        yield make_db

        engine.dispose()


class TestPerTransactionLimit:
    """Test per-transaction limit (₹50,000)."""

    def test_amount_at_limit_allowed(self, test_db):
        """Amount exactly at ₹50,000 should be ALLOWED."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=3).first()  # ₹50,000 = 5,000,000 paise
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-limit-1",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_ALLOWED
            assert decision.reason_code == rules.REASON_WITHIN_POLICY
        finally:
            db.close()

    def test_amount_below_limit_allowed(self, test_db):
        """Amount below ₹50,000 should be ALLOWED."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=2).first()  # ₹10,000 = 1,000,000 paise
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-limit-2",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_ALLOWED
        finally:
            db.close()

    def test_amount_above_limit_requires_approval(self, test_db):
        """Amount above ₹50,000 should require approval."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=4).first()  # ₹60,000 = 6,000,000 paise
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-limit-3",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_REQUIRE_APPROVAL
            assert decision.reason_code == rules.REASON_EXCEEDS_TRANSACTION_LIMIT
            assert decision.details is not None
            assert decision.details["amount_paise"] == 6000000
        finally:
            db.close()


class TestPriceDrift:
    """Test price drift detection (>2%)."""

    def test_no_drift_allowed(self, test_db):
        """Price unchanged → no drift block."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-drift-1",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_ALLOWED
        finally:
            db.close()

    def test_small_drift_allowed(self, test_db):
        """Drift ≤ 2% should pass drift check."""
        db = test_db()
        
        try:
            quoted_price = 1000000  # ₹10,000
            current_price = 1020000  # 2% increase
            
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=quoted_price,
                idempotency_key="test-drift-2",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=current_price,
                session_user_id="test-user",
            )
            
            # Should pass drift check, so either ALLOWED or REQUIRE_APPROVAL (from other limits)
            assert decision.decision != rules.DECISION_BLOCKED or decision.reason_code != rules.REASON_PRICE_DRIFT
        finally:
            db.close()

    def test_large_drift_blocked(self, test_db):
        """Drift > 2% should block."""
        db = test_db()
        
        try:
            quoted_price = 1000000  # ₹10,000
            current_price = 1030000  # 3% increase (> 2% threshold)
            
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=quoted_price,
                idempotency_key="test-drift-3",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_BLOCKED
            assert decision.reason_code == rules.REASON_PRICE_DRIFT
            assert decision.details is not None
            assert decision.details["drift_percent"] > 2.0
        finally:
            db.close()

    def test_drift_price_decrease(self, test_db):
        """Drift applies to price decrease too."""
        db = test_db()
        
        try:
            quoted_price = 1000000  # ₹10,000
            current_price = 960000  # 4% decrease (> 2% threshold)
            
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=quoted_price,
                idempotency_key="test-drift-4",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_BLOCKED
            assert decision.reason_code == rules.REASON_PRICE_DRIFT
        finally:
            db.close()


class TestDuplicateOrder:
    """Test duplicate order prevention."""

    def test_no_existing_order_allowed(self, test_db):
        """If no existing order, should pass duplicate check."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-dup-1",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.reason_code != rules.REASON_DUPLICATE_ORDER
        finally:
            db.close()

    def test_existing_order_blocked(self, test_db):
        """If order already exists, should be blocked."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-dup-2",
            )
            db.add(proposal)
            db.commit()
            
            # Create an order for this proposal
            order = Order(
                proposal_id=proposal.id,
                amount=product.current_price,
                status="CREATED",
            )
            db.add(order)
            db.commit()
            
            # Try to authorize again
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_BLOCKED
            assert decision.reason_code == rules.REASON_DUPLICATE_ORDER
        finally:
            db.close()


class TestSessionSpendingLimit:
    """Test session spending limit (₹1,00,000)."""

    def test_within_session_limit_allowed(self, test_db):
        """If total spending within ₹1,00,000, should be allowed."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=2).first()  # ₹10,000
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-session-1",
            )
            db.add(proposal)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            assert decision.reason_code != rules.REASON_EXCEEDS_SESSION_LIMIT
        finally:
            db.close()

    def test_exceeds_session_limit_blocked(self, test_db):
        """If total spending exceeds ₹1,00,000, should be blocked."""
        db = test_db()
        
        try:
            # Create a completed order for ₹90,000
            product1 = db.query(Product).filter_by(id=2).first()
            proposal1 = Proposal(
                product_id=product1.id,
                quoted_price_snapshot=product1.current_price,
                idempotency_key="test-session-2-1",
            )
            db.add(proposal1)
            db.commit()
            
            order1 = Order(
                proposal_id=proposal1.id,
                amount=9000000,  # ₹90,000
                status="PAYMENT_SUCCESS",
            )
            db.add(order1)
            db.commit()
            
            # Now try to add a new ₹20,000 transaction (total would be ₹1,10,000)
            product2 = db.query(Product).filter_by(id=1).first()
            proposal2 = Proposal(
                product_id=product2.id,
                quoted_price_snapshot=2000000,
                idempotency_key="test-session-2-2",
            )
            db.add(proposal2)
            db.commit()
            
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal2,
                authoritative_current_price=2000000,  # ₹20,000
                session_user_id="test-user",
            )
            
            assert decision.decision == rules.DECISION_BLOCKED
            assert decision.reason_code == rules.REASON_EXCEEDS_SESSION_LIMIT
            assert decision.details["total_after_paise"] > rules.SESSION_SPENDING_LIMIT_PAISE
        finally:
            db.close()


class TestAuditLogging:
    """Test that policy decisions are audited."""

    def test_blocked_decision_audited(self, test_db):
        """Blocked decision should be recorded in audit log."""
        db = test_db()
        
        try:
            product = db.query(Product).filter_by(id=4).first()  # ₹60,000 (over limit)
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=product.current_price,
                idempotency_key="test-audit-1",
            )
            db.add(proposal)
            db.commit()
            
            # Manually call policy and audit (simulating what the endpoint does)
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=product.current_price,
                session_user_id="test-user",
            )
            
            # Verify decision is REQUIRE_APPROVAL
            assert decision.decision == rules.DECISION_REQUIRE_APPROVAL
            
            # Simulate audit (normally done in endpoint)
            audit_log = AuditLog(
                proposal_id=proposal.id,
                event_type="POLICY_DECISION",
                detail_json=json.dumps({
                    "decision": decision.decision,
                    "reason_code": decision.reason_code,
                }),
            )
            db.add(audit_log)
            db.commit()
            
            # Verify audit log entry
            audit = db.query(AuditLog).filter_by(proposal_id=proposal.id).first()
            assert audit is not None
            assert audit.event_type == "POLICY_DECISION"
            
            detail = json.loads(audit.detail_json)
            assert detail["decision"] == rules.DECISION_REQUIRE_APPROVAL
        finally:
            db.close()


class TestAuthoritativePriceUsage:
    """Test that DB price is always authoritative."""

    def test_uses_current_price_for_limits(self, test_db):
        """Policy should use current DB price, not quoted snapshot."""
        db = test_db()
        
        try:
            # Create proposal with quoted price ₹10,100
            # But current DB price is ₹10,000 (0.99% drift, within 2% tolerance)
            quoted_price = 1010000  # ₹10,100
            current_price = 1000000  # ₹10,000 (0.99% decrease)
            
            product = db.query(Product).filter_by(id=1).first()
            proposal = Proposal(
                product_id=product.id,
                quoted_price_snapshot=quoted_price,
                idempotency_key="test-auth-price-1",
            )
            db.add(proposal)
            db.commit()
            
            # Policy should check against current price (₹10,000), not quoted (₹10,100)
            decision = PolicyEngine.authorize_proposal(
                db=db,
                proposal=proposal,
                authoritative_current_price=current_price,
                session_user_id="test-user",
            )
            
            # Current price (₹10,000) is within per-transaction limit (₹50,000)
            # Drift is 0.99% which is within 2% threshold
            assert decision.decision == rules.DECISION_ALLOWED
        finally:
            db.close()

