#!/usr/bin/env python3
"""Quick test for price drift scenario."""
import sys
sys.path.insert(0, '/c/Users/Asus/Desktop/SentinelCart')

from backend.db.session import SessionLocal
from backend.db.models import Product

db = SessionLocal()
product = db.query(Product).filter_by(id=1).first()
print(f"Current price: {product.current_price} paise (₹{product.current_price/100})")
print(f"Changing to 316200 paise (₹{316200/100})...")
product.current_price = 316200
db.commit()
print(f"New price: {product.current_price} paise (₹{product.current_price/100})")
print(f"This is {((316200 - 309000) / 309000 * 100):.2f}% increase from previous")
db.close()
