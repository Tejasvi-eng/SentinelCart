"""
AI recommendation layer tests.

Tests cover:
1. Valid structured AI response parsing and recommendation
2. Invalid JSON from AI -> graceful fallback to IntentParser
3. Unknown product ID from AI -> graceful fallback to IntentParser
4. API failure (500 / 429) -> graceful fallback to IntentParser
5. Timeout from OpenRouter -> graceful fallback to IntentParser
6. Trust Boundary: Model output cannot influence authoritative DB price
7. Missing API key -> deterministic fallback without network calls
"""

import json
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.agent.reasoning import AIProductRecommender, IntentParser
from backend.db.models import Base, Product
from backend.db.session import get_db
from backend.main import app


@pytest.fixture
def test_db_session():
    """Create a temporary SQLite database session for unit tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_ai.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        products = [
            Product(id=1, name="Wireless Bluetooth Headphones", description="Noise cancellation headphones", current_price=299900),
            Product(id=2, name="USB-C Charging Cable", description="Durable fast charge cable", current_price=49900),
            Product(id=3, name="Portable Power Bank 20000mAh", description="Long flight battery pack", current_price=149900),
        ]
        for p in products:
            session.add(p)
        session.commit()

        yield session

        session.close()
        engine.dispose()


@pytest.fixture
def client_with_db():
    """FastAPI test client with temporary database override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_client_ai.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        products = [
            Product(id=1, name="Wireless Bluetooth Headphones", description="Noise cancellation headphones", current_price=299900),
            Product(id=2, name="USB-C Charging Cable", description="Durable fast charge cable", current_price=49900),
        ]
        for p in products:
            session.add(p)
        session.commit()
        session.close()

        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        yield client

        app.dependency_overrides.clear()
        engine.dispose()


class TestAIRecommendationLayer:
    """Mocked tests for OpenRouter AI recommendation flow."""

    def test_valid_structured_ai_response(self, test_db_session, monkeypatch):
        """Valid JSON from OpenRouter should recommend the chosen product with reasoning."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")
        monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")

        captured_request = {}

        def mock_post(url, **kwargs):
            captured_request["url"] = url
            captured_request["headers"] = kwargs.get("headers", {})
            captured_request["json"] = kwargs.get("json", {})
            mock_body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "product_id": 1,
                                "reasoning": "The wireless headphones are under ₹5,000 and offer noise cancellation."
                            })
                        }
                    }
                ]
            }
            return httpx.Response(200, json=mock_body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "Find me wireless headphones under ₹5,000",
            test_db_session,
        )

        assert product_id == 1
        assert "noise cancellation" in reasoning
        assert captured_request["headers"]["Authorization"] == "Bearer mock-openrouter-key"
        assert captured_request["json"]["model"] == "openrouter/free"

    def test_invalid_json_fallback(self, test_db_session, monkeypatch):
        """Malformed JSON from model should trigger deterministic fallback."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

        def mock_post(url, **kwargs):
            mock_body = {
                "choices": [
                    {
                        "message": {
                            "content": "I recommend product 1 because it's good (not JSON format)"
                        }
                    }
                ]
            }
            return httpx.Response(200, json=mock_body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "wireless headphones",
            test_db_session,
        )

        # Falls back to IntentParser keyword match for 'headphones' -> Product 1
        assert product_id == 1
        assert "Deterministic match" in reasoning

    def test_unknown_product_id_fallback(self, test_db_session, monkeypatch):
        """Product ID outside candidate catalog should be rejected and fall back."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

        def mock_post(url, **kwargs):
            mock_body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "product_id": 99999,
                                "reasoning": "Hallucinated product ID"
                            })
                        }
                    }
                ]
            }
            return httpx.Response(200, json=mock_body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "wireless headphones",
            test_db_session,
        )

        # 99999 rejected, falls back to IntentParser -> Product 1
        assert product_id == 1
        assert "Deterministic match" in reasoning

    def test_api_failure_fallback(self, test_db_session, monkeypatch):
        """HTTP error (e.g. 500 or 429 rate limit) should gracefully fall back."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

        def mock_post_500(url, **kwargs):
            return httpx.Response(500, content=b"Internal Server Error", request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post_500)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "power bank",
            test_db_session,
        )

        assert product_id == 3  # Keyword match for 'power bank'
        assert "Deterministic match" in reasoning

        # Test 429 rate limit
        def mock_post_429(url, **kwargs):
            return httpx.Response(429, content=b"Rate limited", request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post_429)

        product_id2, reasoning2 = AIProductRecommender.recommend_product(
            "power bank",
            test_db_session,
        )

        assert product_id2 == 3
        assert "Deterministic match" in reasoning2

    def test_timeout_fallback(self, test_db_session, monkeypatch):
        """Network timeout should gracefully fall back without breaking the app."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

        def mock_post_timeout(url, **kwargs):
            raise httpx.TimeoutException("Read timeout after 12 seconds")

        monkeypatch.setattr(httpx, "post", mock_post_timeout)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "power bank",
            test_db_session,
        )

        assert product_id == 3  # Keyword match for 'power bank'
        assert "Deterministic match" in reasoning

    def test_missing_api_key_uses_fallback(self, test_db_session, monkeypatch):
        """When OPENROUTER_API_KEY is empty or unset, fall back directly with no network calls."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "")

        call_count = 0
        def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post)

        product_id, reasoning = AIProductRecommender.recommend_product(
            "wireless headphones",
            test_db_session,
        )

        assert product_id == 1
        assert call_count == 0  # No HTTP call was made
        assert "Deterministic match" in reasoning

    def test_model_cannot_influence_authoritative_db_price(self, client_with_db, monkeypatch):
        """
        Critical Trust Boundary Test:
        Model attempting to inject a modified price must have zero effect on
        quoted_price_snapshot or the product's database price.
        """
        monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

        def mock_post_with_fake_price(url, **kwargs):
            mock_body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "product_id": 1,
                                "price": 100,
                                "quoted_price": 50,
                                "current_price": 10,
                                "reasoning": "Attempting to force price to ₹1"
                            })
                        }
                    }
                ]
            }
            return httpx.Response(200, json=mock_body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", mock_post_with_fake_price)

        response = client_with_db.post(
            "/api/v1/intent",
            json={
                "user_intent": "I want headphones",
                "idempotency_key": "test-security-price-shield-1",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["product_id"] == 1
        # Authoritative price from DB MUST be preserved (299900 paise = ₹2,999)
        assert data["quoted_price_snapshot"] == 299900
        assert data["quoted_price_snapshot"] != 100
        assert data["quoted_price_snapshot"] != 50
        assert data["quoted_price_snapshot"] != 10
