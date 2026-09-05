"""
AI reasoning engine.

The primary recommendation path uses a hosted LLM through OpenRouter.
A deterministic keyword parser remains as a reliability fallback.

Agent responsibility:
- interpret user intent
- select from backend-provided catalog candidates
- generate recommendation reasoning

Backend responsibility:
- validate selected product
- fetch authoritative price
- create proposal
- enforce policy
- authorize payment
"""

import json
import logging
import os
from typing import Optional, Set, Tuple

import httpx
from sqlalchemy.orm import Session

from backend.db.models import Product

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
REQUEST_TIMEOUT_SECONDS = 12.0

SYSTEM_PROMPT = (
    "You are an AI product recommendation agent for SentinelCart.\n"
    "Your job is to interpret the user's purchase intent and select the single best matching product "
    "from the provided catalog candidates.\n"
    "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
    "{\n"
    '  "product_id": <integer product id from candidates>,\n'
    '  "reasoning": "<concise explanation of why this product fits the intent>"\n'
    "}\n"
    "CRITICAL RULES:\n"
    "1. Choose ONLY a product_id from the provided candidate list.\n"
    "2. Do NOT include any price fields or keys in your response.\n"
    "3. Output pure JSON without markdown code blocks or surrounding text.\n"
)


class IntentParser:
    """
    Deterministic fallback product matcher used when the AI provider
    is unavailable or returns unusable output.
    """

    KEYWORD_MAP = {
        # Audio
        "headphones": 1,
        "earbuds": 1,
        "wireless": 1,
        "audio": 1,

        # Cables
        "cable": 2,
        "charging": 2,
        "usb": 2,

        # Power
        "battery": 3,
        "power bank": 3,
        "charger": 3,

        # Desk
        "stand": 4,
        "laptop": 4,
        "desk": 4,

        # Keyboard
        "keyboard": 5,
        "typing": 5,
        "rgb": 5,

        # Mouse
        "mouse": 6,
        "pointer": 6,
        "wireless mouse": 6,

        # Webcam
        "camera": 7,
        "webcam": 7,
        "4k": 7,
        "video": 7,

        # Lighting
        "lamp": 8,
        "light": 8,
        "desk lamp": 8,

        # Phone
        "phone": 9,
        "mount": 9,
        "mobile": 9,

        # HDMI
        "hdmi": 10,
        "display": 10,

        # Cooling
        "cooling": 11,
        "fan": 11,
        "heat": 11,

        # Cable organizer
        "organizer": 12,
        "organization": 12,
        "cable": 12,
    }

    @staticmethod
    def parse_intent(intent_text: str, db: Session) -> int:
        """
        Parse user intent and return suggested product ID.
        
        Process:
        1. Extract keywords from intent
        2. Search for matching products
        3. Return best match
        
        Args:
            intent_text: User's natural-language intent
            db: Database session
            
        Returns:
            Product ID
            
        Raises:
            ValueError: If no matching product found
        """
        intent_lower = intent_text.lower()

        # Simple keyword matching
        for keyword, product_id in IntentParser.KEYWORD_MAP.items():
            if keyword in intent_lower:
                # Verify product exists
                product = db.query(Product).filter_by(id=product_id).first()
                if product:
                    return product_id

        # Fallback: return first product if no keywords match
        product = db.query(Product).order_by(Product.id).first()
        if product:
            return product.id

        raise ValueError("No products available in catalog")


def format_candidates(candidates: list[Product]) -> str:
    """Format candidate products for LLM context (id, name, description, price)."""
    lines = []
    for p in candidates:
        price_inr = f"₹{p.current_price / 100:.2f}"
        desc = p.description or "No description"
        lines.append(f"- ID: {p.id} | Name: {p.name} | Price: {price_inr} | Description: {desc}")
    return "\n".join(lines)


def parse_llm_response(raw_text: str, candidate_ids: Set[int]) -> Tuple[int, str]:
    """
    Parse and validate LLM output.
    
    Trust boundary:
    - Only extracts product_id and reasoning
    - Validates product_id is an integer belonging to candidate_ids
    - Never accepts or uses any price field from LLM
    """
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON dictionary")

    if "product_id" not in data:
        raise ValueError("Missing required 'product_id' key in response")

    raw_id = data["product_id"]
    if type(raw_id) is not int:
        try:
            raw_id = int(raw_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid product_id type: {type(raw_id)}")

    if raw_id not in candidate_ids:
        raise ValueError(f"Product ID {raw_id} not found in catalog candidates")

    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        reasoning = f"Recommended product {raw_id} based on intent."

    # Trust Boundary: return only validated candidate product_id and reasoning text.
    # No price field is parsed, accepted, or returned.
    return raw_id, reasoning


class AIProductRecommender:
    """
    AI product recommendation engine using OpenRouter.
    
    Architecture:
    User intent -> OpenRouter recommendation -> Backend validation ->
    DB-authoritative price -> Deterministic policy -> Razorpay
    """

    @staticmethod
    def recommend_product(intent_text: str, db: Session) -> Tuple[int, str]:
        """
        Recommend a product matching the user's intent.
        
        Attempts OpenRouter LLM recommendation with candidate catalog.
        Falls back to deterministic IntentParser on any failure or timeout.
        """
        candidates = db.query(Product).order_by(Product.id).all()
        if not candidates:
            raise ValueError("No products available in catalog")

        candidate_ids = {p.id for p in candidates}

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or not api_key.strip():
            logger.info("OPENROUTER_API_KEY not configured; using deterministic IntentParser fallback")
            return AIProductRecommender._fallback(intent_text, db)

        model = os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sentinelcart.local",
            "X-Title": "SentinelCart",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User Purchase Intent: \"{intent_text}\"\n\n"
                        f"Available Catalog Candidates:\n"
                        f"{format_candidates(candidates)}\n\n"
                        "Select the single best matching candidate product_id and provide concise reasoning."
                    ),
                },
            ],
            "temperature": 0.1,
        }

        try:
            response = httpx.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code != 200:
                logger.warning(
                    "OpenRouter API returned status %s; falling back to IntentParser",
                    response.status_code,
                )
                return AIProductRecommender._fallback(intent_text, db)

            resp_data = response.json()
            choices = resp_data.get("choices", [])
            if not choices:
                logger.warning("OpenRouter returned empty choices; falling back to IntentParser")
                return AIProductRecommender._fallback(intent_text, db)

            raw_content = choices[0].get("message", {}).get("content", "")
            product_id, reasoning = parse_llm_response(raw_content, candidate_ids)
            return product_id, reasoning

        except (httpx.TimeoutException, httpx.HTTPError) as e:
            logger.warning("OpenRouter network error (%s); falling back to IntentParser", type(e).__name__)
            return AIProductRecommender._fallback(intent_text, db)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("OpenRouter response parsing error (%s); falling back to IntentParser", str(e))
            return AIProductRecommender._fallback(intent_text, db)
        except Exception as e:
            logger.warning("Unexpected error during AI recommendation (%s); falling back to IntentParser", type(e).__name__)
            return AIProductRecommender._fallback(intent_text, db)

    @staticmethod
    def _fallback(intent_text: str, db: Session) -> Tuple[int, str]:
        """Deterministic keyword fallback when AI is unavailable or fails."""
        product_id = IntentParser.parse_intent(intent_text, db)
        product = db.query(Product).filter_by(id=product_id).first()
        product_name = product.name if product else f"Product {product_id}"
        reasoning = f"Deterministic match: Selected {product_name} based on intent '{intent_text}'"
        return product_id, reasoning

