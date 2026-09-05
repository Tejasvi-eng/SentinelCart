/**
 * SentinelCart API Types
 * Strictly aligned with backend schemas (backend/schemas.py).
 */

export interface IntentRequest {
  user_intent: string;
  idempotency_key: string;
}

export interface ProposalResponse {
  proposal_id: number;
  product_id: number;
  product_name: string;
  description: string | null;
  quoted_price_snapshot: number; // in paise (integer)
  reasoning_text: string | null;
  idempotency_key: string;
  status: string;
  created_at: string;
}

export type PolicyDecisionType = 'ALLOWED' | 'BLOCKED' | 'REQUIRE_APPROVAL';

export interface PolicyDecisionDetails {
  quoted_price_paise?: number;
  current_price_paise?: number;
  drift_percent?: number;
  threshold_percent?: number;
  amount_paise?: number;
  limit_paise?: number;
  total_spent_paise?: number;
  new_amount_paise?: number;
  total_after_paise?: number;
  existing_order_id?: number;
  [key: string]: unknown;
}

export interface PolicyDecisionResponse {
  decision: PolicyDecisionType;
  reason_code: string;
  message: string;
  details: PolicyDecisionDetails | null;
}

export interface CheckoutBlockedResponse {
  proposal_id: number;
  product_id: number;
  product_name: string;
  authoritative_current_price_paise: number;
  policy_decision: PolicyDecisionResponse;
}

export interface CheckoutPaymentResponse {
  status: 'PAYMENT_READY';
  proposal_id: number;
  order_id: string; // Razorpay order ID
  key_id: string;   // Razorpay public key ID
  amount: number;   // in paise
  currency: string;
}

export type CheckoutResult =
  | { type: 'PAYMENT_READY'; data: CheckoutPaymentResponse }
  | { type: 'POLICY_DECISION'; data: CheckoutBlockedResponse };

export interface PaymentVerificationRequest {
  proposal_id: number;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface PaymentVerificationResponse {
  success: boolean;
  proposal_id: number;
  order_id: string;
  payment_id: string;
  message: string;
  details: {
    amount_paise?: number;
    [key: string]: unknown;
  } | null;
}

export interface AuditLogRead {
  id: number;
  proposal_id: number | null;
  event_type: string;
  detail_json: string;
  created_at: string;
}

// Razorpay Checkout JS interface
export interface RazorpayHandlerResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  order_id: string;
  handler: (response: RazorpayHandlerResponse) => void;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  notes?: Record<string, string>;
  theme?: {
    color?: string;
  };
  modal?: {
    ondismiss?: () => void;
    escape?: boolean;
    backdropclose?: boolean;
  };
}

export interface RazorpayInstance {
  open: () => void;
  on: (event: string, callback: (response: { error: { code: string; description: string; source: string; step: string; reason: string; metadata: Record<string, string> } }) => void) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}
