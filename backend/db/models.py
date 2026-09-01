"""
SQLAlchemy models for SentinelCart.

All monetary values are stored as integer paise (100 paise = 1 rupee).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Product(Base):
    """
    Product catalog entry.
    
    current_price is authoritative and stored in paise (integer).
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    current_price: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    proposals: Mapped[list["Proposal"]] = relationship("Proposal", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name}, current_price={self.current_price})>"


class Proposal(Base):
    """
    AI-generated purchase proposal.
    
    quoted_price_snapshot captures the authoritative price at proposal creation.
    The LLM's own price is never used; snapshot is always from products.current_price.
    
    idempotency_key ensures duplicate requests are idempotent.
    
    Status transitions:
    PROPOSAL_CREATED -> POLICY_CHECK -> (APPROVED | BLOCKED | REQUIRE_APPROVAL) -> ORDER_CREATED -> PAYMENT_* -> COMPLETED | ABORTED
    """
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quoted_price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    reasoning_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PROPOSAL_CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="proposals")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="proposal")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="proposal")

    def __repr__(self) -> str:
        return f"<Proposal(id={self.id}, product_id={self.product_id}, status={self.status})>"


class Order(Base):
    """
    Razorpay order record.
    
    A proposal can produce at most one Order.
    A failed payment does NOT create another Order; retry uses the existing order.
    
    Status values: CREATED, PAYMENT_PENDING, PAYMENT_SUCCESS, PAYMENT_FAILED
    """
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_order_proposal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), nullable=False, unique=True)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    proposal: Mapped["Proposal"] = relationship("Proposal", back_populates="orders")

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, proposal_id={self.proposal_id}, status={self.status})>"


class AuditLog(Base):
    """
    Append-only audit log.
    
    Records all significant events for compliance and debugging.
    UPDATE and DELETE are rejected via SQLite triggers.
    """
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proposals.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    proposal: Mapped[Optional["Proposal"]] = relationship("Proposal", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type})>"
