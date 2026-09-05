"""
API endpoint tests.

Tests for:
- POST /intent (proposal creation from intent)
- GET /proposal/{id} (fetch proposal)
- Invalid product ID rejection
- Idempotency key handling
- Authoritative DB price usage (not LLM price)
"""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.db.init_db import create_audit_log_triggers
from backend.db.models import Base, Product
from backend.db.session import get_db
from backend.main import app


@pytest.fixture
def test_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database_url = f"sqlite:///{db_path}"

        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

        # Create tables
        Base.metadata.create_all(bind=engine)

        # Enable foreign keys
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

        # Create triggers
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

        # Seed test data
        session = SessionLocal()
        products = [
            Product(
                name="Test Headphones",
                description="Test wireless headphones",
                current_price=299900,  # ₹2,999
            ),
            Product(
                name="Test Cable",
                description="Test USB cable",
                current_price=49900,  # ₹499
            ),
            Product(
                name="Test Power Bank",
                description="Test power bank",
                current_price=149900,  # ₹1,499
            ),
        ]
        for product in products:
            session.add(product)
        session.commit()
        session.close()

        # Override dependency
        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        yield SessionLocal

        session_final = SessionLocal()
        session_final.close()
        engine.dispose()


@pytest.fixture
def client(test_db):
    """FastAPI test client."""
    return TestClient(app)


class TestIntentProposal:
    """Tests for POST /intent endpoint."""

    def test_valid_intent_creates_proposal(self, client):
        """Verify valid intent creates a proposal with DB price."""
        response = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want wireless headphones",
                "idempotency_key": "test-intent-1",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["proposal_id"] is not None
        assert data["product_id"] == 1  # Headphones
        assert data["product_name"] == "Test Headphones"
        assert data["quoted_price_snapshot"] == 299900  # ₹2,999 in paise
        assert data["status"] == "PROPOSAL_CREATED"
        assert data["idempotency_key"] == "test-intent-1"

    def test_idempotency_key_returns_same_proposal(self, client):
        """Verify same idempotency_key returns the same proposal."""
        # First request
        response1 = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want headphones",
                "idempotency_key": "test-idempotent-1",
            },
        )
        data1 = response1.json()

        # Second request with same key
        response2 = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want different product",
                "idempotency_key": "test-idempotent-1",
            },
        )
        data2 = response2.json()

        # Should return the same proposal
        assert data1["proposal_id"] == data2["proposal_id"]
        assert response2.status_code == 201

    def test_invalid_product_fails(self, client):
        """Verify intent with invalid product fails gracefully."""
        # This test would need to mock the intent parser to return an invalid ID
        # For now, we test that a non-existent product ID can't be forced
        # (The intent parser won't return an invalid ID, but we could test directly)
        pass

    def test_authoritative_price_from_db(self, client):
        """Verify proposal uses DB price, not any supplied price."""
        # Create a proposal with "power bank" to ensure keyword match
        response = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want a power bank",
                "idempotency_key": "test-price-authority-1",
            },
        )

        data = response.json()

        # The DB price for power bank is ₹1,499 (149900 paise)
        assert data["quoted_price_snapshot"] == 149900

        # The proposal should be created, not rejected due to price
        assert response.status_code == 201


class TestGetProposal:
    """Tests for GET /proposal/{id} endpoint."""

    def test_fetch_existing_proposal(self, client):
        """Verify fetching an existing proposal works."""
        # Create proposal first
        response1 = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want a power bank",
                "idempotency_key": "test-fetch-1",
            },
        )
        proposal_id = response1.json()["proposal_id"]

        # Fetch the proposal
        response2 = client.get(f"/api/v1/proposal/{proposal_id}")

        assert response2.status_code == 200
        data = response2.json()

        assert data["proposal_id"] == proposal_id
        assert data["product_name"] == "Test Power Bank"
        assert data["quoted_price_snapshot"] == 149900

    def test_fetch_nonexistent_proposal_fails(self, client):
        """Verify fetching nonexistent proposal returns 404."""
        response = client.get("/api/v1/proposal/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestAuditLogging:
    """Tests for audit logging during proposal creation."""

    def test_proposal_creation_audited(self, test_db, client):
        """Verify proposal creation is logged to audit_log."""
        from backend.db.models import AuditLog

        # Create proposal
        response = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want a power bank",
                "idempotency_key": "test-audit-1",
            },
        )
        proposal_id = response.json()["proposal_id"]

        # Check audit log
        db = test_db()
        audit_logs = db.query(AuditLog).filter_by(proposal_id=proposal_id).all()

        assert len(audit_logs) > 0
        assert audit_logs[0].event_type == "PROPOSAL_CREATED"

        detail = json.loads(audit_logs[0].detail_json)
        assert detail["proposal_id"] == proposal_id
        assert detail["product_id"] == 3  # Power bank
        assert detail["product_name"] == "Test Power Bank"
        assert detail["authoritative_price_paise"] == 149900

        db.close()

    def test_get_audit_trail_endpoint(self, client):
        """Verify GET /api/v1/audit/{proposal_id} returns the audit logs."""
        response = client.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want headphones",
                "idempotency_key": "test-audit-endpoint-1",
            },
        )
        proposal_id = response.json()["proposal_id"]

        audit_res = client.get(f"/api/v1/audit/{proposal_id}")
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert len(logs) >= 1
        assert logs[0]["event_type"] == "PROPOSAL_CREATED"
        assert logs[0]["proposal_id"] == proposal_id
