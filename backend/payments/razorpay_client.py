"""
Razorpay payment client.

Handles:
- Order creation (server-side only)
- Payment signature verification
- No credentials ever sent to frontend

Uses Razorpay REST API directly (simple, no external SDK dependency).
"""

import hashlib
import hmac
import json
import os
from typing import Optional

import httpx


class RazorpayClient:
    """Razorpay integration for Test Mode."""
    
    BASE_URL = "https://api.razorpay.com/v1"
    
    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        currency: str = "INR",
    ):
        """
        Initialize Razorpay client.
        
        Args:
            key_id: Razorpay Key ID (from environment or parameter)
            key_secret: Razorpay Key Secret (from environment or parameter)
            currency: Payment currency (default: INR)
        """
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
        self.currency = currency or os.getenv("RAZORPAY_CURRENCY", "INR")
        
        if not self.key_id or not self.key_secret:
            raise ValueError(
                "Razorpay credentials not configured. "
                "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env"
            )
    
    def create_order(
        self,
        amount_paise: int,
        receipt: str,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a Razorpay order.
        
        Args:
            amount_paise: Amount in integer paise (100 paise = 1 rupee)
            receipt: Unique receipt identifier
            description: Optional order description
            
        Returns:
            Order data: {id, amount, currency, receipt, created_at}
            
        Raises:
            Exception: If Razorpay API returns error
        """
        payload = {
            "amount": amount_paise,
            "currency": self.currency,
            "receipt": receipt,
        }
        if description:
            payload["description"] = description
        
        auth = (self.key_id, self.key_secret)
        
        try:
            response = httpx.post(
                f"{self.BASE_URL}/orders",
                auth=auth,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            order_data = response.json()
            return {
                "razorpay_order_id": order_data["id"],
                "amount": order_data["amount"],
                "currency": order_data["currency"],
                "receipt": order_data["receipt"],
                "created_at": order_data["created_at"],
            }
        except httpx.HTTPError as e:
            raise Exception(f"Razorpay API error: {str(e)}")
    
    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """
        Verify Razorpay payment signature.
        
        This is the critical security check. The signature is computed as:
            HMAC-SHA256(order_id|payment_id, key_secret)
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
            
        Returns:
            True if signature is valid, False otherwise
            
        Important:
            - The order_id used here MUST be the one we stored in DB.
            - Never trust order_id from the client for signature verification.
            - The client's provided order_id should be compared against DB,
              but verification uses the server-stored order_id.
        """
        payload = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            self.key_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, razorpay_signature)


# Singleton instance (lazy-loaded)
_razorpay_client: Optional[RazorpayClient] = None


def get_razorpay_client() -> RazorpayClient:
    """Get or create Razorpay client singleton."""
    global _razorpay_client
    if _razorpay_client is None:
        _razorpay_client = RazorpayClient()
    return _razorpay_client
