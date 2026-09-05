# SentinelCart

### Policy-Authorized AI Commerce

> **The agent proposes. The policy engine decides. Razorpay executes.**

SentinelCart is a single-merchant, single-user commerce prototype designed around a simple question:

**What should happen when an AI-assisted purchase recommendation becomes unsafe before money is authorized?**

Instead of allowing an AI system to directly control checkout, SentinelCart separates **recommendation** from **authorization**.

The recommendation layer can suggest a product and explain why it fits the user's request. The backend then independently validates the product and retrieves its authoritative price before a deterministic policy engine decides whether the transaction can proceed.

Only an approved transaction can reach Razorpay.

---

## Why SentinelCart?

Traditional AI shopping experiences optimize for recommendation:

```text
User → AI → Product → Checkout
```

The missing layer is often the boundary between:

**"the agent thinks this is a good purchase"**

and

**"the system is authorized to move money."**

SentinelCart introduces that boundary explicitly:

```text
Natural-language intent
        ↓
Recommendation / proposal
        ↓
Database validation
        ↓
Deterministic policy engine
        ↓
┌────────────┬──────────────────┐
│            │                  │
BLOCKED   REQUIRE APPROVAL    ALLOWED
│                               │
No order                       ↓
                              Razorpay
                                 ↓
                              Payment
                                 ↓
                         Server verification
                                 ↓
                              Audit trail
```

The model or recommendation layer never becomes the payment authority.

---

## Core Principle

### The agent proposes. The policy engine decides.

The recommendation layer is intentionally constrained.

### Recommendation layer may

* understand the user's natural-language request
* identify a suitable product
* provide concise reasoning

### Recommendation layer may not

* set the authoritative price
* approve a transaction
* modify policy rules
* create a Razorpay order
* determine the amount charged
* verify a payment
* modify the audit trail

The backend re-fetches the product directly from the database and obtains the authoritative price independently of recommendation output.

This keeps the money-control path deterministic.

---

# Product Journey

SentinelCart is designed as a consumer-facing journey rather than an administrative dashboard.

### 1. Intent

The user describes what they want in natural language.

Example:

> "Find me wireless headphones under ₹5,000."

The frontend sends the request to:

```http
POST /api/v1/intent
```

The backend creates a proposal using a product from the merchant catalog and snapshots its database price.

### 2. Proposal

The user sees:

* product
* description
* authoritative price
* recommendation reasoning

The price shown to the user is derived from merchant data rather than being treated as an LLM-provided value.

### 3. Policy

When checkout is requested, the backend performs a deterministic policy evaluation.

Possible outcomes:

```text
ALLOWED
BLOCKED
REQUIRE_APPROVAL
```

### 4. Razorpay

Only an `ALLOWED` decision can proceed to Razorpay.

The backend creates the Razorpay order server-side and returns only the public checkout information required by the browser:

```json
{
  "status": "PAYMENT_READY",
  "proposal_id": 7,
  "order_id": "order_...",
  "key_id": "rzp_test_...",
  "amount": 299900,
  "currency": "INR"
}
```

The Key Secret never goes to the frontend.

### 5. Verification

After Razorpay Checkout returns:

* `razorpay_payment_id`
* `razorpay_order_id`
* `razorpay_signature`

the frontend sends those values to:

```http
POST /api/v1/payment/verify
```

The backend verifies the signature using the server-side secret before marking the transaction successful.

### 6. Audit

The entire journey is visible through an append-only audit trail:

```text
Intent received
      ↓
Proposal created
      ↓
Policy evaluated
      ↓
Order created
      ↓
Payment verified
```

---

# The Main Failure: Price Drift

The centerpiece of the SentinelCart demo is a deterministic failure that happens **before payment authorization**.

### Scenario

A product is proposed at:

```text
₹74,999
```

The merchant subsequently changes the price to:

```text
₹79,000
```

The policy engine compares:

```text
Quoted price
Current price
Allowed drift
Actual drift
```

If the change exceeds the configured tolerance:

```text
PRICE_DRIFT
→ BLOCKED
→ no Razorpay order created
```

The UI makes the reason explicit:

```text
TRANSACTION BLOCKED

Quoted price       ₹74,999
Current price      ₹79,000
Allowed drift      2%
Actual drift       5.33%

Policy              PRICE_DRIFT

No Razorpay order was created.
```

This is important because SentinelCart does not merely report an error after payment. It prevents the payment order from being created in the first place.

---

# Trust Boundary

The system intentionally separates probabilistic reasoning from deterministic authorization.

```text
┌─────────────────────────────────────────┐
│ Recommendation layer                   │
│                                         │
│ Understand intent                       │
│ Select candidate product                │
│ Explain recommendation                  │
└──────────────────┬──────────────────────┘
                   │
                   │ product_id only
                   ▼
┌─────────────────────────────────────────┐
│ Backend validation                      │
│                                         │
│ Product exists?                         │
│ Current price from DB                   │
│ Price snapshot                          │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│ Deterministic policy engine             │
│                                         │
│ Transaction limit                       │
│ Session limit                           │
│ Price drift                             │
│ Duplicate-order protection              │
└──────────────────┬──────────────────────┘
                   │
              ALLOWED only
                   ▼
┌─────────────────────────────────────────┐
│ Razorpay                                │
│                                         │
│ Order creation                          │
│ Checkout                                │
│ Payment                                 │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│ Server-side verification                │
│                                         │
│ HMAC-SHA256 signature verification      │
└──────────────────┬──────────────────────┘
                   ▼
             Audit trail
```

---

# Architecture

SentinelCart uses a modular monolith intentionally.

```text
SentinelCart/
│
├── backend/
│   ├── agent/
│   │   ├── reasoning.py
│   │   └── proposal_service.py
│   │
│   ├── policy/
│   │   ├── engine.py
│   │   └── rules.py
│   │
│   ├── payments/
│   │   └── razorpay_client.py
│   │
│   ├── audit/
│   │   └── log.py
│   │
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── init_db.py
│   │   ├── seed.py
│   │   └── set_price.py
│   │
│   ├── main.py
│   ├── routes.py
│   └── schemas.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── types/
│   │   └── utils/
│   └── ...
│
└── README.md
```

The architecture deliberately avoids unnecessary distributed infrastructure.

No microservices, Kafka, Redis, Kubernetes, or message queues are required for the prototype.

---

# Database

SentinelCart currently uses four tables.

### `products`

The authoritative merchant catalog.

Stores the canonical product price in **integer paise**.

### `proposals`

Stores what the recommendation layer suggested.

Important fields include:

* product ID
* quoted price snapshot
* reasoning
* idempotency key
* proposal status

### `orders`

Stores the payment order created after authorization.

`proposal_id` is unique so a proposal cannot produce multiple application-level orders.

### `audit_log`

Stores the immutable event trail.

SQLite triggers prevent updates and deletes to preserve append-only behavior.

---

# Policy Rules

The policy engine is deterministic and independent of the payment provider.

Current rules include:

### Per-transaction limit

Transactions above the configured threshold require approval rather than silently proceeding.

### Session spending limit

Cumulative completed spending is checked before another transaction is authorized.

### Price drift

A proposal is blocked when the merchant price changes beyond the configured tolerance.

### Duplicate order protection

A proposal cannot produce more than one application-level order.

---

# Money Handling

All monetary values are stored and transmitted internally as integer **paise**.

Example:

```text
₹2,999.00
→ 299900 paise
```

This avoids floating-point rounding issues in payment amounts and price comparisons.

The frontend converts paise to human-readable INR for display.

---

# Razorpay Integration

SentinelCart uses **Razorpay Test Mode**.

The flow is:

```text
Backend
   ↓
Create Razorpay Order
   ↓
Return public Key ID + Order ID
   ↓
Browser opens Standard Checkout
   ↓
Razorpay payment response
   ↓
Backend signature verification
   ↓
Payment marked successful
```

The Razorpay Key Secret remains server-side.

The frontend never receives:

```text
RAZORPAY_KEY_SECRET
```

Only the public Key ID and server-created Order ID are exposed to the browser.

This project is a **Test Mode prototype** and does not process real production payments.

---

# Security Model

Important security decisions include:

### Authoritative pricing

The backend never trusts a price supplied by the recommendation layer or browser.

### Server-side payment authorization

The browser cannot decide whether a transaction is approved.

### Server-side Razorpay order creation

The Razorpay Key Secret is not present in browser code.

### Signature verification

A successful browser callback is not enough to mark a payment successful. The backend verifies the Razorpay signature first.

### Database-level constraints

Idempotency and proposal/order uniqueness are enforced at the schema level.

### Immutable audit trail

The audit table rejects update and delete operations.

### Environment separation

Secrets are stored in environment variables and excluded from Git.

---

# API

## Submit intent

```http
POST /api/v1/intent
```

Creates a proposal.

## Get proposal

```http
GET /api/v1/proposal/{proposal_id}
```

Returns proposal and product information.

## Checkout

```http
POST /api/v1/proposal/{proposal_id}/checkout
```

Runs policy evaluation and, when allowed, creates a Razorpay order.

Possible paths:

```text
ALLOWED
BLOCKED
REQUIRE_APPROVAL
PAYMENT_READY
```

## Approve proposal

```http
POST /api/v1/proposal/{proposal_id}/approve
```

Handles the scoped human approval path.

## Verify payment

```http
POST /api/v1/payment/verify
```

Verifies Razorpay payment signature server-side.

## Audit trail

```http
GET /api/v1/audit/{proposal_id}
```

Returns chronological audit events for a proposal.

---

# Frontend

The frontend is built with:

* React
* TypeScript
* Vite
* CSS
* Razorpay Standard Checkout

The application presents the product as a progressive journey:

```text
Intent
  ↓
Proposal
  ↓
Policy Decision
  ↓
Payment
  ↓
Verification
  ↓
Audit
```

The UI deliberately avoids an "AI robot dashboard" aesthetic.

It uses a restrained fintech-style interface focused on:

* trust
* clarity
* status
* decision reasoning
* transaction safety

The price-drift state is the primary failure experience.

---

# Testing

The current backend test suite covers:

* API proposal flow
* database constraints
* policy behavior
* audit immutability
* monetary value handling
* foreign-key enforcement
* payment verification paths

Current validation:

```text
31 backend tests passed
Frontend production build passed
Frontend lint passed
```

Frontend validation:

```bash
cd frontend
npm.cmd run build
npm.cmd run lint
```

Backend validation:

```bash
.\venv\Scripts\python.exe -m pytest backend/tests/ -q
```

---

# Running Locally

## Backend

From the repository root:

```powershell
python -m venv venv
```

Activate the environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Initialize the database:

```powershell
python -m backend.db.init_db
```

Seed the catalog:

```powershell
python -m backend.db.seed
```

Start FastAPI:

```powershell
.\venv\Scripts\uvicorn backend.main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The Vite server may choose an available port such as:

```text
http://localhost:5173
```

or

```text
http://localhost:5174
```

---

# Environment Variables

Backend `.env`:

```env
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_CURRENCY=INR
```

Frontend `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Never commit real credentials.

Only the `.env.example` templates belong in the repository.

---

# Demo Scenarios

## Happy Path

```text
User intent
→ Proposal
→ ALLOWED
→ Razorpay Test Checkout
→ Test payment
→ Server-side verification
→ COMPLETED
→ Audit trail
```

## Require Approval

A transaction above the configured per-transaction threshold produces:

```text
REQUIRE_APPROVAL
```

without automatically creating a payment order.

## Price Drift

```text
Proposal created
→ Merchant price changed
→ Checkout requested
→ PRICE_DRIFT
→ BLOCKED
→ No Razorpay order created
→ Audit recorded
```

The price-drift scenario is intentionally reproducible using the local development price utility.

---

# Current Scope

SentinelCart is deliberately scoped as a prototype.

### Included

* natural-language purchase intent
* product proposal flow
* authoritative database pricing
* deterministic transaction policy
* price-drift protection
* Razorpay Test Mode Checkout
* server-side payment verification
* append-only audit trail
* human-readable decision interface

### Intentionally excluded

* production authentication
* multi-user accounts
* multi-merchant support
* multi-currency
* refunds
* subscriptions
* webhooks
* advanced fraud detection
* distributed services
* production-scale infrastructure

These are deliberately out of scope for the current prototype.

---

# AI Architecture

SentinelCart uses a hosted LLM only for the recommendation layer.

The model receives the user's natural-language request together with a small set of candidate products retrieved from the merchant database.

It returns:

```json
{
  "product_id": 1,
  "reasoning": "The headphones match the requested use case and budget."
}
```

The model does **not** provide the authoritative price, authorization decision, payment amount, or payment action.

The backend validates the selected product ID against the candidate catalog and then re-fetches the product directly from SQLite. The quoted price snapshot therefore comes exclusively from the authoritative database.

```text
User intent
     ↓
OpenRouter LLM
     ↓
product_id + reasoning
     ↓
Backend validation
     ↓
SQLite authoritative price
     ↓
Deterministic policy engine
     ↓
ALLOWED / BLOCKED / REQUIRE_APPROVAL
     ↓
Razorpay
```

## AI Failure Safety

The AI layer is intentionally non-authoritative.

If the hosted model:

* times out
* rate-limits
* returns malformed data
* returns an unknown product
* encounters an API failure
* is not configured

SentinelCart falls back to the existing deterministic product matcher.

This ensures that an AI provider failure cannot bypass or corrupt the transaction-control layer.

### Trust Boundary

The LLM can:

* understand natural-language intent
* choose a product from supplied candidates
* explain the recommendation

The LLM cannot:

* set the authoritative price
* approve or block a transaction
* modify policy limits
* create a Razorpay order
* determine the amount charged
* verify a payment

The financial control path remains deterministic and independently testable.

# Design Trade-offs

### Why SQLite?

The prototype prioritizes simplicity, portability and deterministic local testing.

A production multi-user deployment would likely move to managed PostgreSQL for stronger concurrency and operational characteristics.

### Why modular monolith?

The prototype has a small number of logical boundaries but does not require distributed deployment.

The most important boundary is **authorization**, not service networking.

### Why price snapshots?

Without a proposal-time snapshot, the system cannot objectively determine whether a merchant price changed before checkout.

### Why deterministic policy?

Authorization decisions affect money. They should be reproducible and independently testable.

---

# What We Learned

The interesting engineering problem is not simply:

> "Can an AI recommend a product?"

It is:

> **"Where should probabilistic AI stop and deterministic authorization begin?"**

SentinelCart treats recommendation as a judgment problem and payment authorization as a control problem.

That distinction is the core of the system.

---

# Status

**Prototype status: working**

```text
Database                       ✅
Proposal flow                  ✅
Deterministic policy           ✅
Price-drift protection         ✅
Razorpay Test Mode order       ✅
Razorpay Test Checkout         ✅
Test payment verification      ✅
Immutable audit trail           ✅
React frontend                 ✅
Backend tests                  ✅
Frontend build/lint            ✅
```

> **Test Mode only. Not production-ready.**
> No real production payments are processed by this prototype.

---

# License

Add the project's chosen license here before publishing if required.
