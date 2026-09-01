"""
Database tests.

Comprehensive verification of:
- Product insertion
- Proposal references to products
- Duplicate idempotency_key rejection
- Duplicate order per proposal rejection
- Audit log insertion
- Audit log UPDATE rejection
- Audit log DELETE rejection
- Monetary values as integers
- Foreign-key enforcement

Uses isolated temporary SQLite database.

Run with: pytest backend/tests/test_db.py -v
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.db.init_db import create_audit_log_triggers, enable_foreign_keys
from backend.db.models import AuditLog, Base, Order, Product, Proposal


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database_url = f"sqlite:///{db_path}"

        # Create engine
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

        # Create tables
        Base.metadata.create_all(bind=engine)

        # Enable foreign keys
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

        # Create audit log triggers
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
        session = SessionLocal()

        yield session, engine

        session.close()
        engine.dispose()  # Close all connections and release file locks


class TestProductInsertion:
    """Test product insertion."""

    def test_product_insertion_works(self, temp_db):
        """Verify product insertion works."""
        session, _ = temp_db

        product = Product(
            name="Test Product",
            description="A test product",
            current_price=99900,  # ₹999 in paise
        )
        session.add(product)
        session.commit()

        # Verify insertion
        retrieved = session.query(Product).filter_by(name="Test Product").first()
        assert retrieved is not None
        assert retrieved.current_price == 99900
        assert retrieved.description == "A test product"


class TestProposalReferences:
    """Test proposal product references."""

    def test_proposal_references_product(self, temp_db):
        """Verify proposal correctly references a product."""
        session, _ = temp_db

        # Create product
        product = Product(
            name="Test Product",
            current_price=99900,
        )
        session.add(product)
        session.commit()

        # Create proposal
        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            reasoning_text="Test proposal",
            idempotency_key="test-key-123",
            status="PROPOSAL_CREATED",
        )
        session.add(proposal)
        session.commit()

        # Verify relationship
        retrieved_proposal = session.query(Proposal).filter_by(id=proposal.id).first()
        assert retrieved_proposal is not None
        assert retrieved_proposal.product_id == product.id
        assert retrieved_proposal.product.name == "Test Product"


class TestIdempotencyKey:
    """Test idempotency key uniqueness."""

    def test_duplicate_idempotency_key_rejected(self, temp_db):
        """Verify duplicate idempotency_key is rejected."""
        session, _ = temp_db

        product = Product(name="Test Product", current_price=99900)
        session.add(product)
        session.commit()

        # Create first proposal
        proposal1 = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="unique-key-1",
        )
        session.add(proposal1)
        session.commit()

        # Attempt to create second proposal with same idempotency_key
        proposal2 = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="unique-key-1",  # Duplicate!
        )
        session.add(proposal2)

        with pytest.raises(IntegrityError):
            session.commit()


class TestOrderUniqueness:
    """Test order uniqueness constraints."""

    def test_duplicate_order_for_same_proposal_rejected(self, temp_db):
        """Verify duplicate order for the same proposal is rejected."""
        session, _ = temp_db

        # Create product and proposal
        product = Product(name="Test Product", current_price=99900)
        session.add(product)
        session.commit()

        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="test-key-unique",
        )
        session.add(proposal)
        session.commit()

        # Create first order
        order1 = Order(
            proposal_id=proposal.id,
            amount=99900,
            status="CREATED",
        )
        session.add(order1)
        session.commit()

        # Attempt to create second order for same proposal
        order2 = Order(
            proposal_id=proposal.id,
            amount=99900,
            status="CREATED",
        )
        session.add(order2)

        with pytest.raises(IntegrityError):
            session.commit()


class TestAuditLog:
    """Test audit log functionality."""

    def test_audit_log_insertion_works(self, temp_db):
        """Verify audit log insertion works."""
        session, _ = temp_db

        product = Product(name="Test Product", current_price=99900)
        session.add(product)
        session.commit()

        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="test-key",
        )
        session.add(proposal)
        session.commit()

        # Create audit log entry
        audit_log = AuditLog(
            proposal_id=proposal.id,
            event_type="PROPOSAL_CREATED",
            detail_json=json.dumps({"product_id": product.id}),
        )
        session.add(audit_log)
        session.commit()

        # Verify insertion
        retrieved = session.query(AuditLog).filter_by(id=audit_log.id).first()
        assert retrieved is not None
        assert retrieved.event_type == "PROPOSAL_CREATED"

    def test_audit_log_update_fails(self, temp_db):
        """Verify audit log UPDATE fails."""
        session, _ = temp_db

        product = Product(name="Test Product", current_price=99900)
        session.add(product)
        session.commit()

        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="test-key",
        )
        session.add(proposal)
        session.commit()

        audit_log = AuditLog(
            proposal_id=proposal.id,
            event_type="PROPOSAL_CREATED",
            detail_json="{}",
        )
        session.add(audit_log)
        session.commit()

        # Attempt update - should fail due to trigger
        audit_log.event_type = "MODIFIED"
        session.merge(audit_log)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_audit_log_delete_fails(self, temp_db):
        """Verify audit log DELETE fails."""
        session, _ = temp_db

        product = Product(name="Test Product", current_price=99900)
        session.add(product)
        session.commit()

        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,
            idempotency_key="test-key",
        )
        session.add(proposal)
        session.commit()

        audit_log = AuditLog(
            proposal_id=proposal.id,
            event_type="PROPOSAL_CREATED",
            detail_json="{}",
        )
        session.add(audit_log)
        session.commit()

        # Attempt delete - should fail due to trigger
        session.delete(audit_log)

        with pytest.raises(IntegrityError):
            session.commit()


class TestMonetaryValues:
    """Test that monetary values are stored as integers."""

    def test_monetary_values_are_integers(self, temp_db):
        """Verify monetary values are stored as integers (paise)."""
        session, _ = temp_db

        product = Product(
            name="Test Product",
            current_price=99900,  # Integer paise
        )
        session.add(product)
        session.commit()

        retrieved = session.query(Product).filter_by(id=product.id).first()
        assert isinstance(retrieved.current_price, int)
        assert retrieved.current_price == 99900

        # Create proposal with integer price
        proposal = Proposal(
            product_id=product.id,
            quoted_price_snapshot=99900,  # Integer paise
            idempotency_key="test-key",
        )
        session.add(proposal)
        session.commit()

        retrieved_proposal = session.query(Proposal).filter_by(id=proposal.id).first()
        assert isinstance(retrieved_proposal.quoted_price_snapshot, int)
        assert retrieved_proposal.quoted_price_snapshot == 99900

        # Create order with integer amount
        order = Order(
            proposal_id=proposal.id,
            amount=99900,  # Integer paise
        )
        session.add(order)
        session.commit()

        retrieved_order = session.query(Order).filter_by(id=order.id).first()
        assert isinstance(retrieved_order.amount, int)
        assert retrieved_order.amount == 99900


class TestForeignKeyEnforcement:
    """Test foreign-key constraint enforcement."""

    def test_foreign_key_enforcement_works(self, temp_db):
        """Verify foreign-key constraints are enforced."""
        session, _ = temp_db

        # Attempt to create proposal with non-existent product_id
        proposal = Proposal(
            product_id=9999,  # Non-existent product
            quoted_price_snapshot=99900,
            idempotency_key="test-key",
        )
        session.add(proposal)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_foreign_key_order_to_proposal(self, temp_db):
        """Verify order foreign-key to proposal is enforced."""
        session, _ = temp_db

        # Attempt to create order with non-existent proposal_id
        order = Order(
            proposal_id=9999,  # Non-existent proposal
            amount=99900,
        )
        session.add(order)

        with pytest.raises(IntegrityError):
            session.commit()
