"""
Proposal service.

Handles the intent -> proposal flow:
1. LLM understands intent and searches products
2. Backend fetches authoritative price from DB
3. Backend creates proposal with DB price (never LLM price)
4. Backend generates idempotency_key
5. Backend audits the proposal creation
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from backend.db.models import AuditLog, Proposal, Product


class ProposalService:
    """Service for creating and managing proposals."""

    @staticmethod
    def create_proposal_from_intent(
        db: Session,
        idempotency_key: str,
        product_id: int,
        reasoning_text: Optional[str] = None,
    ) -> Proposal:
        """
        Create a proposal from intent.
        
        Process:
        1. Check if proposal already exists (idempotency)
        2. Validate product exists in DB
        3. Fetch authoritative price from DB
        4. Create proposal with DB price snapshot
        5. Audit the proposal creation
        
        Args:
            db: SQLAlchemy session
            idempotency_key: Unique identifier for idempotency
            product_id: Product ID to propose
            reasoning_text: Optional LLM reasoning
            
        Returns:
            Created Proposal object
            
        Raises:
            ValueError: If product doesn't exist or idempotency key already used
        """
        # Check for duplicate idempotency key (idempotent)
        existing = db.query(Proposal).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing

        # Fetch product from DB
        product = db.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found in catalog")

        # IMPORTANT: Use authoritative price from DB, not any LLM-supplied price
        authoritative_price = product.current_price

        # Create proposal with DB price snapshot
        proposal = Proposal(
            product_id=product_id,
            quoted_price_snapshot=authoritative_price,
            reasoning_text=reasoning_text,
            idempotency_key=idempotency_key,
            status="PROPOSAL_CREATED",
        )

        db.add(proposal)
        db.commit()
        db.refresh(proposal)

        # Audit the proposal creation
        ProposalService._audit_proposal_creation(
            db=db,
            proposal=proposal,
            product=product,
        )

        return proposal

    @staticmethod
    def _audit_proposal_creation(
        db: Session,
        proposal: Proposal,
        product: Product,
    ) -> None:
        """
        Audit proposal creation event.
        
        Records:
        - proposal ID
        - product ID
        - product name
        - authoritative price used
        """
        audit_log = AuditLog(
            proposal_id=proposal.id,
            event_type="PROPOSAL_CREATED",
            detail_json=json.dumps({
                "proposal_id": proposal.id,
                "product_id": product.id,
                "product_name": product.name,
                "authoritative_price_paise": product.current_price,
                "idempotency_key": proposal.idempotency_key,
            }),
        )
        db.add(audit_log)
        db.commit()

    @staticmethod
    def get_proposal(db: Session, proposal_id: int) -> Optional[Proposal]:
        """Fetch a proposal by ID."""
        return db.query(Proposal).filter_by(id=proposal_id).first()
