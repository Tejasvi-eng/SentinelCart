"""
API routes for SentinelCart.

Endpoints:
- POST /intent: Receive user intent, return proposal
- GET /proposal/{id}: Get proposal details
- POST /proposal/{id}/checkout: Proceed to checkout (phase B)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agent.proposal_service import ProposalService
from backend.agent.reasoning import IntentParser
from backend.db.session import get_db
from backend.schemas import IntentRequest, ProposalResponse

router = APIRouter(prefix="/api/v1", tags=["proposals"])


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
        from backend.db.models import Product
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
    
    from backend.db.models import Product
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
