"""
API routes for SentinelCart.

Endpoints:
- POST /intent: Receive user intent, return proposal (Phase A)
- GET /proposal/{id}: Get proposal details (Phase A)
- POST /proposal/{id}/checkout: Proceed to checkout with policy + Razorpay order creation (Phase B+C)
- POST /payment/verify: Verify Razorpay payment signature and update DB (Phase C)
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agent.proposal_service import ProposalService
from backend.agent.reasoning import IntentParser
from backend.db.models import AuditLog, Order, Product, Proposal
from backend.db.session import get_db
from backend.payments.razorpay_client import get_razorpay_client
from backend.policy.engine import PolicyEngine
from backend.schemas import (
    CheckoutPaymentResponse,
    CheckoutResponse,
    IntentRequest,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PolicyDecisionResponse,
    ProposalResponse,
)

router = APIRouter(prefix="/api/v1", tags=["proposals", "payments"])


@router.post("/intent", response_model=ProposalResponse, status_code=201)
async def create_intent_proposal(
    request: IntentRequest,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    """
    Handle user purchase intent.
    
    Flow:
    1. Parse natural-language intent to product search
    2. Fetch authoritative price from DB
    3. Create proposal with DB price snapshot
    4. Generate idempotency_key
    5. Audit proposal creation
    
    Request:
    {
        "user_intent": "I want wireless headphones",
        "idempotency_key": "user-session-123-intent-1"
    }
    
    Response:
    {
        "proposal_id": 1,
        "product_id": 1,
        "product_name": "Wireless Bluetooth Headphones",
        "description": "...",
        "quoted_price_snapshot": 299900,  # paise
        "reasoning_text": "...",
        "idempotency_key": "...",
        "status": "PROPOSAL_CREATED",
        "created_at": "2026-09-01T..."
    }
    
    Note: quoted_price_snapshot is the authoritative price from DB.
    LLM's own price estimate is never used.
    """
    try:
        # Parse intent to get product ID
        product_id = IntentParser.parse_intent(request.user_intent, db)
        
        # Create proposal with DB's authoritative price
        proposal = ProposalService.create_proposal_from_intent(
            db=db,
            idempotency_key=request.idempotency_key,
            product_id=product_id,
            reasoning_text=f"Interpreted intent: {request.user_intent}",
        )
        
        # Fetch product for response
        product = db.query(Product).filter_by(id=product_id).first()
        
        return ProposalResponse(
            proposal_id=proposal.id,
            product_id=proposal.product_id,
            product_name=product.name,
            description=product.description,
            quoted_price_snapshot=proposal.quoted_price_snapshot,
            reasoning_text=proposal.reasoning_text,
            idempotency_key=proposal.idempotency_key,
            status=proposal.status,
            created_at=proposal.created_at,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/proposal/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    """
    Fetch a proposal by ID.
    
    Returns the full proposal with product details.
    """
    proposal = ProposalService.get_proposal(db, proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    product = db.query(Product).filter_by(id=proposal.product_id).first()
    
    return ProposalResponse(
        proposal_id=proposal.id,
        product_id=proposal.product_id,
        product_name=product.name,
        description=product.description,
        quoted_price_snapshot=proposal.quoted_price_snapshot,
        reasoning_text=proposal.reasoning_text,
        idempotency_key=proposal.idempotency_key,
        status=proposal.status,
        created_at=proposal.created_at,
    )


@router.post("/proposal/{proposal_id}/checkout")
async def checkout_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
):
    """
    Checkout a proposal with deterministic policy authorization.
    
    Flow for BLOCKED/REQUIRE_APPROVAL:
    1. Load proposal and product
    2. Run policy engine
    3. Audit decision
    4. Return CheckoutResponse (no order created, no Razorpay call)
    
    Flow for ALLOWED:
    1. Load proposal and product
    2. Verify no existing order (prevent duplicates)
    3. Run policy engine again (safety check)
    4. Create Razorpay order (server-side)
    5. Create Order DB row with PAYMENT_PENDING status
    6. Audit order creation
    7. Return CheckoutPaymentResponse with order_id and public key_id
       (secret NEVER sent to frontend)
    
    Response types:
    - BLOCKED/REQUIRE_APPROVAL: CheckoutResponse (policy_decision object)
    - ALLOWED: CheckoutPaymentResponse (order ready for Razorpay)
    """
    try:
        # Load proposal from DB
        proposal = ProposalService.get_proposal(db, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Load product from DB
        product = db.query(Product).filter_by(id=proposal.product_id).first()
        if not product:
            raise HTTPException(status_code=400, detail="Product not found")
        
        # Get authoritative current price from DB
        authoritative_current_price = product.current_price
        
        # Run deterministic policy engine
        session_user_id = "anonymous"  # Placeholder for MVP
        
        policy_decision = PolicyEngine.authorize_proposal(
            db=db,
            proposal=proposal,
            authoritative_current_price=authoritative_current_price,
            session_user_id=session_user_id,
        )
        
        # Audit the policy decision
        _audit_policy_decision(
            db=db,
            proposal_id=proposal_id,
            decision=policy_decision,
            authoritative_current_price=authoritative_current_price,
        )
        
        # If policy blocked or requires approval, return early
        if policy_decision.decision != "ALLOWED":
            return CheckoutResponse(
                proposal_id=proposal.id,
                product_id=proposal.product_id,
                product_name=product.name,
                authoritative_current_price_paise=authoritative_current_price,
                policy_decision=PolicyDecisionResponse(
                    decision=policy_decision.decision,
                    reason_code=policy_decision.reason_code,
                    message=policy_decision.message,
                    details=policy_decision.details,
                ),
            )
        
        # Policy ALLOWED: proceed to create Razorpay order
        
        # Check if an order already exists for this proposal
        existing_order = db.query(Order).filter_by(proposal_id=proposal_id).first()
        if existing_order:
            # Reuse existing order (prevents duplicate Razorpay orders)
            razorpay_client = get_razorpay_client()
            return CheckoutPaymentResponse(
                status="PAYMENT_READY",
                proposal_id=proposal.id,
                order_id=existing_order.razorpay_order_id,
                key_id=razorpay_client.key_id,
                amount=existing_order.amount,
                currency="INR",
            )
        
        # Create Razorpay order server-side
        razorpay_client = get_razorpay_client()
        receipt = f"proposal-{proposal_id}-{int(__import__('time').time())}"
        razorpay_order = razorpay_client.create_order(
            amount_paise=authoritative_current_price,
            receipt=receipt,
            description=f"Payment for {product.name}",
        )
        
        # Create Order DB row
        order = Order(
            proposal_id=proposal_id,
            razorpay_order_id=razorpay_order["razorpay_order_id"],
            amount=authoritative_current_price,
            status="PAYMENT_PENDING",
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # Audit order creation
        _audit_payment_event(
            db=db,
            proposal_id=proposal_id,
            event_type="ORDER_CREATED",
            details={
                "razorpay_order_id": razorpay_order["razorpay_order_id"],
                "amount_paise": authoritative_current_price,
                "currency": "INR",
            },
        )
        
        # Return payment ready response
        return CheckoutPaymentResponse(
            status="PAYMENT_READY",
            proposal_id=proposal.id,
            order_id=razorpay_order["razorpay_order_id"],
            key_id=razorpay_client.key_id,
            amount=authoritative_current_price,
            currency="INR",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout error: {str(e)}")


@router.post("/payment/verify", response_model=PaymentVerificationResponse)
async def verify_payment(
    request: PaymentVerificationRequest,
    db: Session = Depends(get_db),
) -> PaymentVerificationResponse:
    """
    Verify Razorpay payment signature and update DB state.
    
    Critical security flow:
    1. Load order from DB using proposal_id
    2. Verify client-supplied order_id matches DB order_id
    3. Verify signature using DB-stored order_id (never trust client)
    4. On success:
       - Mark order PAYMENT_SUCCESS
       - Mark proposal PAYMENT_SUCCESS -> COMPLETED
       - Audit verified payment
    5. On failure:
       - Do NOT mark payment successful
       - Audit verification failure
       - Return error
    
    Request body NEVER contains the secret key.
    Signature verification happens server-side with secret.
    """
    try:
        # Load proposal
        proposal = ProposalService.get_proposal(db, request.proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Load order for this proposal
        order = db.query(Order).filter_by(proposal_id=request.proposal_id).first()
        if not order:
            _audit_payment_event(
                db=db,
                proposal_id=request.proposal_id,
                event_type="PAYMENT_VERIFICATION_FAILED",
                details={
                    "reason": "No order found for proposal",
                    "proposal_id": request.proposal_id,
                },
            )
            raise HTTPException(status_code=404, detail="Order not found for proposal")
        
        # Critical: verify client-supplied order_id matches DB order_id
        if order.razorpay_order_id != request.razorpay_order_id:
            _audit_payment_event(
                db=db,
                proposal_id=request.proposal_id,
                event_type="PAYMENT_VERIFICATION_FAILED",
                details={
                    "reason": "Order ID mismatch",
                    "db_order_id": order.razorpay_order_id,
                    "client_order_id": request.razorpay_order_id,
                },
            )
            raise HTTPException(status_code=400, detail="Order ID mismatch")
        
        # Verify signature using server-side secret and DB order_id
        razorpay_client = get_razorpay_client()
        signature_valid = razorpay_client.verify_payment_signature(
            razorpay_order_id=order.razorpay_order_id,  # Use DB order, not client's
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_signature=request.razorpay_signature,
        )
        
        if not signature_valid:
            _audit_payment_event(
                db=db,
                proposal_id=request.proposal_id,
                event_type="PAYMENT_VERIFICATION_FAILED",
                details={
                    "reason": "Invalid signature",
                    "razorpay_order_id": order.razorpay_order_id,
                    "razorpay_payment_id": request.razorpay_payment_id,
                },
            )
            raise HTTPException(status_code=400, detail="Invalid payment signature")
        
        # Signature valid: update order and proposal state
        order.status = "PAYMENT_SUCCESS"
        db.add(order)
        
        # Update proposal status
        proposal.status = "COMPLETED"
        db.add(proposal)
        db.commit()
        
        # Audit successful verification
        _audit_payment_event(
            db=db,
            proposal_id=request.proposal_id,
            event_type="PAYMENT_VERIFIED",
            details={
                "razorpay_order_id": order.razorpay_order_id,
                "razorpay_payment_id": request.razorpay_payment_id,
                "amount_paise": order.amount,
            },
        )
        
        return PaymentVerificationResponse(
            success=True,
            proposal_id=proposal.id,
            order_id=order.razorpay_order_id,
            payment_id=request.razorpay_payment_id,
            message="Payment verified and order completed successfully.",
            details={
                "amount_paise": order.amount,
            },
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # Unexpected error: audit and return
        _audit_payment_event(
            db=db,
            proposal_id=request.proposal_id,
            event_type="PAYMENT_VERIFICATION_FAILED",
            details={
                "reason": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=f"Verification error: {str(e)}")





def _audit_policy_decision(
    db: Session,
    proposal_id: int,
    decision,
    authoritative_current_price: int,
) -> None:
    """
    Audit the policy decision for this checkout attempt.
    
    Records: decision, reason, details (prices, drift, limits).
    """
    audit_log = AuditLog(
        proposal_id=proposal_id,
        event_type="POLICY_DECISION",
        detail_json=json.dumps({
            "decision": decision.decision,
            "reason_code": decision.reason_code,
            "message": decision.message,
            "authoritative_current_price_paise": authoritative_current_price,
            "details": decision.details or {},
        }),
    )
    db.add(audit_log)
    db.commit()


def _audit_payment_event(
    db: Session,
    proposal_id: int,
    event_type: str,
    details: dict,
) -> None:
    """
    Audit a payment event (order creation, verification success/failure).
    
    Event types: ORDER_CREATED, PAYMENT_VERIFIED, PAYMENT_VERIFICATION_FAILED, PAYMENT_FAILED
    """
    audit_log = AuditLog(
        proposal_id=proposal_id,
        event_type=event_type,
        detail_json=json.dumps(details),
    )
    db.add(audit_log)
    db.commit()

