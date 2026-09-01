"""
AI reasoning engine.

For MVP: simple keyword-based product search.
In phase 2, this will use actual LLM for NLU and ranking.

Agent's responsibility: search/rank products
Backend's responsibility: validate, fetch authoritative price, create proposal
"""

from sqlalchemy.orm import Session

from backend.db.models import Product


class IntentParser:
    """
    Parse user intent and suggest products.
    
    MVP: Simple keyword matching
    Phase 2: LLM-based NLU and ranking
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

