"""
Database seed data.

Populates the database with a deterministic, realistic product catalog.
Idempotent - safe to run multiple times.

Run with: python -m backend.db.seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Product
from backend.db.session import SessionLocal


# Seed data: realistic products with prices in paise (100 paise = 1 rupee)
PRODUCTS = [
    {
        "name": "Wireless Bluetooth Headphones",
        "description": "High-quality wireless headphones with noise cancellation",
        "current_price": 299900,  # ₹2,999
    },
    {
        "name": "USB-C Charging Cable",
        "description": "Durable 2-meter USB-C cable for fast charging",
        "current_price": 49900,  # ₹499
    },
    {
        "name": "Portable Power Bank 20000mAh",
        "description": "Fast-charging power bank with LED display",
        "current_price": 149900,  # ₹1,499
    },
    {
        "name": "Laptop Stand Adjustable",
        "description": "Ergonomic aluminum laptop stand for desk setup",
        "current_price": 199900,  # ₹1,999
    },
    {
        "name": "Mechanical Keyboard RGB",
        "description": "Compact mechanical keyboard with programmable RGB lighting",
        "current_price": 449900,  # ₹4,499
    },
    {
        "name": "Wireless Mouse Silent",
        "description": "Quiet wireless mouse with precision tracking",
        "current_price": 89900,  # ₹899
    },
    {
        "name": "4K USB Webcam",
        "description": "Professional 4K webcam with auto-focus and stereo microphone",
        "current_price": 399900,  # ₹3,999
    },
    {
        "name": "Desk Lamp LED Dimmable",
        "description": "Adjustable LED desk lamp with USB charging port",
        "current_price": 129900,  # ₹1,299
    },
    {
        "name": "Phone Mount Magnetic",
        "description": "Magnetic phone mount for car dashboard or desk",
        "current_price": 34900,  # ₹349
    },
    {
        "name": "HDMI Cable 2.1 Premium",
        "description": "High-speed HDMI 2.1 cable for 8K and gaming",
        "current_price": 74900,  # ₹749
    },
    {
        "name": "Laptop Cooling Pad",
        "description": "Active cooling pad with 5 quiet fans",
        "current_price": 179900,  # ₹1,799
    },
    {
        "name": "Cable Organizer Kit",
        "description": "Complete cable management kit with clips and ties",
        "current_price": 24900,  # ₹249
    },
]


def seed_products() -> None:
    """
    Insert seed products into the database.
    
    Idempotent: checks if products already exist before inserting.
    """
    db = SessionLocal()
    try:
        # Check if products already exist
        existing_count = db.query(Product).count()
        if existing_count > 0:
            print(f"✓ Database already seeded ({existing_count} products exist). Skipping seed.")
            return

        # Insert all products
        for product_data in PRODUCTS:
            product = Product(**product_data)
            db.add(product)

        db.commit()
        print(f"✓ Seeded {len(PRODUCTS)} products\n")

    except Exception as e:
        db.rollback()
        print(f"✗ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding SentinelCart database...")
    seed_products()
