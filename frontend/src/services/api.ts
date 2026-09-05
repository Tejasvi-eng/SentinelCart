import type {
  AuditLogRead,
  CheckoutBlockedResponse,
  CheckoutPaymentResponse,
  CheckoutResult,
  IntentRequest,
  PaymentVerificationRequest,
  PaymentVerificationResponse,
  ProposalResponse,
} from '../types/api';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

export class ApiError extends Error {
  status: number;
  technicalDetails?: string;

  constructor(message: string, status: number, technicalDetails?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.technicalDetails = technicalDetails;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      let errorMessage = 'An unexpected error occurred';
      let technical = '';
      try {
        const errorData = await response.json();
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
          technical = JSON.stringify(errorData);
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
          technical = JSON.stringify(errorData.detail);
        } else if (errorData.message) {
          errorMessage = errorData.message;
          technical = JSON.stringify(errorData);
        }
      } catch {
        technical = `${response.status} ${response.statusText}`;
      }

      // Provide human-friendly default messages
      if (response.status === 404) {
        errorMessage = 'The requested resource was not found.';
      } else if (response.status >= 500) {
        errorMessage = 'Something went wrong while communicating with the server.';
      }

      throw new ApiError(errorMessage, response.status, technical);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : 'Network error';
    throw new ApiError(
      'Unable to connect to SentinelCart backend. Please verify the service is running.',
      0,
      message
    );
  }
}

/**
 * Send natural language intent to generate a purchase proposal.
 */
export async function createIntent(userIntent: string, idempotencyKey: string): Promise<ProposalResponse> {
  const body: IntentRequest = {
    user_intent: userIntent,
    idempotency_key: idempotencyKey,
  };

  return request<ProposalResponse>('/api/v1/intent', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Fetch proposal by ID.
 */
export async function getProposal(proposalId: number): Promise<ProposalResponse> {
  return request<ProposalResponse>(`/api/v1/proposal/${proposalId}`, {
    method: 'GET',
  });
}

/**
 * Run deterministic policy evaluation and attempt checkout.
 * Returns either:
 * - PAYMENT_READY with Razorpay order details (when ALLOWED)
 * - POLICY_DECISION with decision and drift details (when BLOCKED or REQUIRE_APPROVAL)
 */
export async function checkoutProposal(proposalId: number): Promise<CheckoutResult> {
  const raw = await request<CheckoutPaymentResponse | CheckoutBlockedResponse>(
    `/api/v1/proposal/${proposalId}/checkout`,
    {
      method: 'POST',
    }
  );

  if ('status' in raw && raw.status === 'PAYMENT_READY') {
    return {
      type: 'PAYMENT_READY',
      data: raw as CheckoutPaymentResponse,
    };
  }

  return {
    type: 'POLICY_DECISION',
    data: raw as CheckoutBlockedResponse,
  };
}

/**
 * Verify Razorpay payment signature server-side.
 */
export async function verifyPayment(
  payload: PaymentVerificationRequest
): Promise<PaymentVerificationResponse> {
  return request<PaymentVerificationResponse>('/api/v1/payment/verify', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch immutable audit trail for a proposal.
 */
export async function getAuditTrail(proposalId: number): Promise<AuditLogRead[]> {
  return request<AuditLogRead[]>(`/api/v1/audit/${proposalId}`, {
    method: 'GET',
  });
}
