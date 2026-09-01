# SentinelCart Backend - Setup and Development

## Overview

SentinelCart is a single-merchant, single-user AI shopping agent backend. The user enters natural-language purchase intent. The AI may understand the intent, search/rank products, and generate reasoning. A deterministic policy engine authorizes (or blocks) the purchase. Razorpay then executes the payment.

**Core principle:** LLM PROPOSES. DETERMINISTIC BACKEND AUTHORIZES. RAZORPAY EXECUTES.

## Architecture

```
backend/
├── __init__.py
├── main.py              # FastAPI application
├── schemas.py           # Pydantic request/response schemas
├── db/
│   ├── __init__.py
│   ├── models.py        # SQLAlchemy ORM models
│   ├── session.py       # Database configuration
│   ├── init_db.py       # Database initialization & triggers
│   └── seed.py          # Seed data population
├── agent/               # AI reasoning (stub)
├── policy/              # Authorization engine (stub)
├── payments/            # Razorpay integration (stub)
├── audit/               # Audit logging (stub)
└── tests/
    ├── __init__.py
    └── test_db.py       # Database tests
```

## Database

**Tables:**
- `products`: Product catalog (id, name, description, current_price in paise, created_at, updated_at)
- `proposals`: AI-generated purchase proposals with unique idempotency keys
- `orders`: Razorpay orders (one per proposal max)
- `audit_log`: Append-only audit trail (protected by SQLite triggers)

**Monetary values:** All prices/amounts stored as integer paise (100 paise = 1 rupee).

**Constraints:** Foreign-key enforcement enabled. Audit log is append-only (UPDATE/DELETE rejected by triggers).

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Database

Creates tables and audit log triggers:

```bash
python -m backend.db.init_db
```

### 4. Seed Database

Populates with ~12 realistic products (idempotent):

```bash
python -m backend.db.seed
```

### 5. Run Tests

```bash
pytest backend/tests/test_db.py -v
```

### 6. Start Development Server

```bash
uvicorn backend.main:app --reload
```

Then visit http://localhost:8000/docs for interactive API documentation.

## Key Design Decisions

- **Paise everywhere:** All monetary values are integers. No floats for money.
- **Idempotency keys:** Proposals use unique idempotency keys to prevent duplicate submissions.
- **Price snapshots:** Proposals capture the authoritative product price at proposal time; LLM's own price estimate is never used.
- **One order per proposal:** Retry reuses the existing order; no new Razorpay orders for retries.
- **Append-only audit log:** SQLite triggers prevent UPDATE/DELETE; compliance-critical.
- **Deterministic authorization:** Policy engine (not implemented yet) will make authorization decisions, never the LLM.

## State Machine

### Proposal States
```
PROPOSAL_CREATED → POLICY_CHECK → (APPROVED | BLOCKED | REQUIRE_APPROVAL)
   ↓
ORDER_CREATED → PAYMENT_PENDING → (PAYMENT_SUCCESS | PAYMENT_FAILED)
   ↓
(COMPLETED | ABORTED)
```

### Order States
```
CREATED → PAYMENT_PENDING → (PAYMENT_SUCCESS | PAYMENT_FAILED)
```

## Testing

All tests use isolated temporary SQLite databases and verify:
- ✓ Product insertion
- ✓ Proposal-to-product references
- ✓ Idempotency key uniqueness
- ✓ One order per proposal
- ✓ Audit log insertion
- ✓ Audit log immutability (triggers)
- ✓ Integer monetary values
- ✓ Foreign-key enforcement

Run tests after setup:

```bash
pytest backend/tests/test_db.py -v
```

## Next Steps

Phase 2 will add:
- Agent: natural-language understanding and product search
- Policy engine: spending limits, fraud checks, approval rules
- Razorpay integration: order creation and payment handling
- Frontend: React UI for user interaction
