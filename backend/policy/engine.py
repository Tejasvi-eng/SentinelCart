"""
Policy authorization engine.

Deterministic authorization logic.
Receives only trusted backend values.
Does not accept frontend or LLM decisions.

The engine is independent of FastAPI and Razorpay.
It returns structured policy decisions only.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from backend.db.models import Order, Proposal
from backend.policy import rules


@dataclass
class PolicyDecision:
    """
    Policy engine result.
    
    decision: ALLOWED | BLOCKED | REQUIRE_APPROVAL
    reason_code: Machine-readable reason (for logging/analytics)
    message: Human-readable explanation
    details: Optional dict with additional context (drift, limits, etc.)
    """

    decision: str
    reason_code: str
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dict for JSON response."""
        result = {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class PolicyEngine:
    """Deterministic authorization for purchases."""

    @staticmethod
    def authorize_proposal(
        db: Session,
        proposal: Proposal,
        authoritative_current_price: int,
        session_user_id: str,  # TODO: from auth in phase D
    ) -> PolicyDecision:
        """
        Authorize a proposal for checkout.
        
        Checks:
        1. Duplicate order prevention
        2. Price drift (>2%)
        3. Per-transaction limit (₹50,000)
        4. Session spending limit (₹1,00,000)
        
        Args:
            db: SQLAlchemy session
            proposal: Proposal object (from DB, trusted)
            authoritative_current_price: Current price from products table (trusted)
            session_user_id: User identifier (for session spending calculation)
            
        Returns:
            PolicyDecision with decision, reason, and message
        """
        # Check 1: Duplicate order
        duplicate_check = PolicyEngine._check_duplicate_order(db, proposal)
        if duplicate_check:
            return duplicate_check

        # Check 2: Price drift
        drift_check = PolicyEngine._check_price_drift(
            proposal.quoted_price_snapshot,
            authoritative_current_price,
        )
        if drift_check:
            return drift_check

        # Use authoritative current price for remaining checks
        amount = authoritative_current_price

        # Check 3: Per-transaction limit
        transaction_check = PolicyEngine._check_per_transaction_limit(amount)
        if transaction_check:
            return transaction_check

        # Check 4: Session spending limit
        session_check = PolicyEngine._check_session_spending_limit(
            db=db,
            session_user_id=session_user_id,
            new_amount=amount,
        )
        if session_check:
            return session_check

        # All checks passed
        return PolicyDecision(
            decision=rules.DECISION_ALLOWED,
            reason_code=rules.REASON_WITHIN_POLICY,
            message="Transaction satisfies all policy requirements.",
        )

    @staticmethod
    def _check_duplicate_order(db: Session, proposal: Proposal) -> Optional[PolicyDecision]:
        """
        Check if proposal already has an order.
        
        A proposal can produce at most one order.
        """
        existing_order = db.query(Order).filter_by(proposal_id=proposal.id).first()
        if existing_order:
            return PolicyDecision(
                decision=rules.DECISION_BLOCKED,
                reason_code=rules.REASON_DUPLICATE_ORDER,
                message=f"Proposal {proposal.id} already has an order.",
                details={"existing_order_id": existing_order.id},
            )
        return None

    @staticmethod
    def _check_price_drift(
        quoted_price: int,
        current_price: int,
    ) -> Optional[PolicyDecision]:
        """
        Check if price has drifted more than threshold.
        
        Drift = |current - quoted| / quoted * 100
        If drift > 2%, block.
        """
        if quoted_price == 0:
            # Edge case: if quoted price was 0, can't calculate drift
            return None

        drift_amount = abs(current_price - quoted_price)
        drift_percent = (drift_amount / quoted_price) * 100

        if drift_percent > rules.PRICE_DRIFT_THRESHOLD_PERCENT:
            return PolicyDecision(
                decision=rules.DECISION_BLOCKED,
                reason_code=rules.REASON_PRICE_DRIFT,
                message=(
                    f"Price has drifted {drift_percent:.2f}% "
                    f"(was ₹{quoted_price/100:.2f}, now ₹{current_price/100:.2f}). "
                    f"Threshold is {rules.PRICE_DRIFT_THRESHOLD_PERCENT}%."
                ),
                details={
                    "quoted_price_paise": quoted_price,
                    "current_price_paise": current_price,
                    "drift_percent": drift_percent,
                    "threshold_percent": rules.PRICE_DRIFT_THRESHOLD_PERCENT,
                },
            )
        return None

    @staticmethod
    def _check_per_transaction_limit(amount: int) -> Optional[PolicyDecision]:
        """
        Check if transaction amount exceeds per-transaction limit.
        
        If amount <= ₹50,000: allow
        If amount > ₹50,000: require approval
        """
        if amount > rules.PER_TRANSACTION_LIMIT_PAISE:
            return PolicyDecision(
                decision=rules.DECISION_REQUIRE_APPROVAL,
                reason_code=rules.REASON_EXCEEDS_TRANSACTION_LIMIT,
                message=(
                    f"Amount ₹{amount/100:.2f} exceeds per-transaction limit "
                    f"of ₹{rules.PER_TRANSACTION_LIMIT_PAISE/100:.2f}. "
                    f"Requires approval."
                ),
                details={
                    "amount_paise": amount,
                    "limit_paise": rules.PER_TRANSACTION_LIMIT_PAISE,
                },
            )
        return None

    @staticmethod
    def _check_session_spending_limit(
        db: Session,
        session_user_id: str,
        new_amount: int,
    ) -> Optional[PolicyDecision]:
        """
        Check if session spending would exceed limit.
        
        Limit: ₹1,00,000 per session
        
        Calculate total from completed orders in DB (never trust client).
        """
        # TODO: Add user_id to Proposal and Order tables in schema version 2
        # For MVP, use a simple session identifier
        # Query completed orders (we'll use all orders for now, pending proper auth)

        from backend.db.models import Proposal as ProposalModel

        completed_orders = db.query(Order).filter(
            Order.status.in_(["PAYMENT_SUCCESS", "COMPLETED"])
        ).all()

        total_spent = sum(order.amount for order in completed_orders)
        total_after = total_spent + new_amount

        if total_after > rules.SESSION_SPENDING_LIMIT_PAISE:
            return PolicyDecision(
                decision=rules.DECISION_BLOCKED,
                reason_code=rules.REASON_EXCEEDS_SESSION_LIMIT,
                message=(
                    f"Session spending of ₹{total_after/100:.2f} "
                    f"would exceed limit of ₹{rules.SESSION_SPENDING_LIMIT_PAISE/100:.2f}."
                ),
                details={
                    "total_spent_paise": total_spent,
                    "new_amount_paise": new_amount,
                    "total_after_paise": total_after,
                    "limit_paise": rules.SESSION_SPENDING_LIMIT_PAISE,
                },
            )
        return None

