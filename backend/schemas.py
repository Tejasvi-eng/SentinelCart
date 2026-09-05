"""
Pydantic schemas for API request/response validation.

All monetary values in paise (integer).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    """Base product schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    current_price: int = Field(..., gt=0, description="Price in paise")


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class ProductRead(ProductBase):
    """Schema for reading a product."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProposalBase(BaseModel):
    """Base proposal schema."""
    product_id: int = Field(..., gt=0)
    quoted_price_snapshot: int = Field(..., gt=0, description="Price in paise")
    reasoning_text: Optional[str] = Field(None)
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="PROPOSAL_CREATED")


class ProposalCreate(BaseModel):
    """Schema for creating a proposal (backend use only)."""
    product_id: int
    quoted_price_snapshot: int
    reasoning_text: Optional[str] = None
    idempotency_key: str
    status: str = "PROPOSAL_CREATED"


class ProposalRead(ProposalBase):
    """Schema for reading a proposal."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    """Base order schema."""
    proposal_id: int = Field(..., gt=0)
    amount: int = Field(..., gt=0, description="Amount in paise")
    status: str = Field(default="CREATED")
    razorpay_order_id: Optional[str] = Field(None)


class OrderCreate(BaseModel):
    """Schema for creating an order."""
    proposal_id: int
    amount: int
    status: str = "CREATED"
    razorpay_order_id: Optional[str] = None


class OrderRead(OrderBase):
    """Schema for reading an order."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogBase(BaseModel):
    """Base audit log schema."""
    event_type: str = Field(..., min_length=1, max_length=100)
    detail_json: str
    proposal_id: Optional[int] = None


class AuditLogCreate(BaseModel):
    """Schema for creating an audit log entry."""
    event_type: str
    detail_json: str
    proposal_id: Optional[int] = None


class AuditLogRead(AuditLogBase):
    """Schema for reading an audit log entry."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class IntentRequest(BaseModel):
    """
    User's natural-language purchase intent.
    
    LLM receives this and proposes a product.
    """
    user_intent: str = Field(..., min_length=1, max_length=1000, description="Natural language purchase intent")
    idempotency_key: str = Field(..., min_length=1, max_length=255, description="Unique identifier for this intent")


class ProposalResponse(BaseModel):
    """
    API response: structured product proposal from the agent.
    
    Contains:
    - proposal DB record
    - product details
    - authoritative price (from DB, not LLM)
    - reasoning from LLM
    """
    proposal_id: int
    product_id: int
    product_name: str
    description: Optional[str]
    quoted_price_snapshot: int = Field(description="Authoritative price in paise from DB")
    reasoning_text: Optional[str] = Field(description="LLM reasoning for this proposal")
    idempotency_key: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PolicyDecisionResponse(BaseModel):
    """
    Response from policy engine authorization.
    
    Possible decisions:
    - ALLOWED: proceed with order
    - BLOCKED: transaction rejected, no order created
    - REQUIRE_APPROVAL: waiting for user approval, no order created
    """
    decision: str = Field(..., description="ALLOWED | BLOCKED | REQUIRE_APPROVAL")
    reason_code: str = Field(..., description="Machine-readable reason code")
    message: str = Field(..., description="Human-readable explanation")
    details: Optional[dict] = Field(None, description="Additional context (prices, drift %, limits, etc.)")


class CheckoutResponse(BaseModel):
    """
    Response for POST /proposal/{id}/checkout.
    
    Contains:
    - proposal details
    - current authoritative price
    - policy decision
    """
    proposal_id: int
    product_id: int
    product_name: str
    authoritative_current_price_paise: int = Field(description="Current price from DB in paise")
    policy_decision: PolicyDecisionResponse


class CheckoutPaymentResponse(BaseModel):
    """
    Response when policy decision is ALLOWED.
    
    Frontend uses this to open Razorpay Checkout.
    
    Important:
    - key_id is public (safe to send to frontend)
    - order_id is from Razorpay
    - amount must be used by frontend (authoritative value)
    - Secret is NEVER sent to frontend
    """
    status: str = Field(default="PAYMENT_READY", description="PAYMENT_READY")
    proposal_id: int
    order_id: str = Field(..., description="Razorpay order ID")
    key_id: str = Field(..., description="Razorpay public key (TEST mode)")
    amount: int = Field(..., description="Amount in paise")
    currency: str = Field(default="INR")


class PaymentVerificationRequest(BaseModel):
    """
    Request to verify a completed payment.
    
    Frontend sends this after Razorpay Checkout success handler.
    
    Important:
    - These values come from Razorpay's response, not user input
    - Backend will verify the signature using DB-stored order ID
    - Client-provided order_id must match DB order before verification
    """
    proposal_id: int = Field(..., description="Our proposal ID")
    razorpay_order_id: str = Field(..., description="Order ID from Razorpay response")
    razorpay_payment_id: str = Field(..., description="Payment ID from Razorpay")
    razorpay_signature: str = Field(..., description="Signature from Razorpay (not secret)")


class PaymentVerificationResponse(BaseModel):
    """
    Response after payment verification.
    
    Signature verification either succeeds or fails.
    Only on success do we mark the order PAYMENT_SUCCESS.
    """
    success: bool = Field(..., description="True if signature verified successfully")
    proposal_id: int
    order_id: str
    payment_id: str
    message: str
    details: Optional[dict] = None
