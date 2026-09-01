"""
Development utility to change product prices for testing.

This is NOT a public API endpoint.
Use this only for testing price-drift scenarios.

Run with: python -m backend.db.set_price <product_id> <new_price_in_paise>

Example:
    python -m backend.db.set_price 1 350000  # Change headphones to ₹3,500
"""

import sys

from backend.db.models import Product
from backend.db.session import SessionLocal


def set_product_price(product_id: int, new_price_paise: int) -> None:
    """
    Change a product's current price.
    
    Args:
        product_id: ID of the product to update
        new_price_paise: New price in paise (integer)
    """
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(id=product_id).first()
        
        if not product:
            print(f"✗ Product {product_id} not found")
            sys.exit(1)
        
        old_price = product.current_price
        product.current_price = new_price_paise
        db.commit()
        
        print(f"✓ Updated Product {product_id}: {product.name}")
        print(f"  Old price: ₹{old_price/100:.2f} ({old_price} paise)")
        print(f"  New price: ₹{new_price_paise/100:.2f} ({new_price_paise} paise)")
        print(f"  Drift: {abs(new_price_paise - old_price) / old_price * 100:.2f}%")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m backend.db.set_price <product_id> <new_price_in_paise>")
        print()
        print("Examples:")
        print("  python -m backend.db.set_price 1 350000  # Headphones: ₹2999 -> ₹3500")
        print("  python -m backend.db.set_price 1 299900  # Restore to ₹2999")
        sys.exit(1)
    
    try:
        product_id = int(sys.argv[1])
        new_price = int(sys.argv[2])
        set_product_price(product_id, new_price)
    
    except ValueError:
        print("✗ Arguments must be integers")
        sys.exit(1)
