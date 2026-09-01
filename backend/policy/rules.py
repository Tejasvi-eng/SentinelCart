"""
Policy rules and constants.

All monetary values in paise (integer).
100 paise = 1 rupee.
"""

# Per-transaction limit
# ₹50,000 = 5,000,000 paise
PER_TRANSACTION_LIMIT_PAISE = 5_000_000

# Session spending limit
# ₹1,00,000 = 10,000,000 paise
SESSION_SPENDING_LIMIT_PAISE = 10_000_000

# Price drift threshold
# If |current - quoted| / quoted > 2%, block the transaction
PRICE_DRIFT_THRESHOLD_PERCENT = 2.0

# Policy decision constants
DECISION_ALLOWED = "ALLOWED"
DECISION_BLOCKED = "BLOCKED"
DECISION_REQUIRE_APPROVAL = "REQUIRE_APPROVAL"

# Reason codes (machine-readable)
REASON_WITHIN_POLICY = "WITHIN_POLICY"
REASON_EXCEEDS_TRANSACTION_LIMIT = "EXCEEDS_TRANSACTION_LIMIT"
REASON_EXCEEDS_SESSION_LIMIT = "EXCEEDS_SESSION_LIMIT"
REASON_PRICE_DRIFT = "PRICE_DRIFT"
REASON_DUPLICATE_ORDER = "DUPLICATE_ORDER"

