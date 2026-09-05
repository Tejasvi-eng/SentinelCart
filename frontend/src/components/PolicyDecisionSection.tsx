import React from 'react';
import type {
  CheckoutBlockedResponse,
  CheckoutPaymentResponse,
} from '../types/api';
import { formatPaise, formatPercent } from '../utils/formatters';

interface PolicyDecisionSectionProps {
  decisionData:
    | { type: 'PAYMENT_READY'; data: CheckoutPaymentResponse }
    | { type: 'POLICY_DECISION'; data: CheckoutBlockedResponse };
  onOpenCheckout?: () => void;
  isOpeningRazorpay?: boolean;
  isPaymentVerified?: boolean;
}

export const PolicyDecisionSection: React.FC<PolicyDecisionSectionProps> = ({
  decisionData,
  onOpenCheckout,
  isOpeningRazorpay = false,
  isPaymentVerified = false,
}) => {
  // Case 1: ALLOWED -> Razorpay order ready
  if (decisionData.type === 'PAYMENT_READY') {
    const payment = decisionData.data;
    return (
      <section className="journey-card policy-section policy-allowed">
        <div className="section-header">
          <div className="step-indicator allowed-indicator">
            <span className="step-number">3</span>
            <span className="step-label">Policy Decision: ALLOWED</span>
          </div>
          <div className="status-hero allowed-hero">
            <div className="status-hero-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
            <div>
              <h2 className="section-title">Purchase approved</h2>
              <p className="status-hero-subtitle">
                Within spending and price policies.
              </p>
            </div>
          </div>
        </div>

        <div className="decision-details-box allowed-box">
          <div className="policy-summary-row">
            <div className="meta-item">
              <span className="meta-label">Razorpay Order ID</span>
              <span className="meta-val font-mono">{payment.order_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Authorized Amount</span>
              <span className="meta-val font-bold">{formatPaise(payment.amount)}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Public Key</span>
              <span className="meta-val font-mono">{payment.key_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Currency</span>
              <span className="meta-val">{payment.currency}</span>
            </div>
          </div>

          <div className="execution-callout">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
              <line x1="1" y1="10" x2="23" y2="10"></line>
            </svg>
            <span>
              {isPaymentVerified
                ? 'Payment completed and verified. Order finalized.'
                : 'Razorpay Test Mode checkout initiated. Complete the payment in the gateway modal.'}
            </span>
          </div>

          {!isPaymentVerified && onOpenCheckout && (
            <div className="action-row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={onOpenCheckout}
                disabled={isOpeningRazorpay}
              >
                {isOpeningRazorpay ? 'Opening Razorpay...' : 'Proceed to secure payment'}
              </button>
            </div>
          )}
        </div>
      </section>
    );
  }

  // Case 2: BLOCKED or REQUIRE_APPROVAL
  const { policy_decision, authoritative_current_price_paise, product_name } = decisionData.data;
  const isBlocked = policy_decision.decision === 'BLOCKED';
  const isPriceDrift = policy_decision.reason_code === 'PRICE_DRIFT';
  const details = policy_decision.details || {};

  // PRICE DRIFT BLOCKED: PRIMARY FAILURE DEMO
  if (isBlocked && isPriceDrift) {
    const quotedPrice = details.quoted_price_paise ?? 0;
    const currentPrice = details.current_price_paise ?? authoritative_current_price_paise;
    const allowedDrift = details.threshold_percent ?? 2.0;
    const actualDrift = details.drift_percent ?? 0;

    return (
      <section className="journey-card policy-section policy-drift-blocked" role="alert">
        <div className="section-header">
          <div className="step-indicator blocked-indicator">
            <span className="step-number">3</span>
            <span className="step-label">Policy Decision: BLOCKED</span>
          </div>
          <div className="status-hero blocked-hero">
            <div className="status-hero-icon blocked-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <div>
              <h2 className="section-title blocked-title">TRANSACTION BLOCKED</h2>
              <p className="blocked-subtitle">The merchant price changed before checkout.</p>
            </div>
          </div>
        </div>

        <div className="drift-metrics-container">
          <div className="drift-grid">
            <div className="drift-card">
              <span className="drift-label">Quoted price</span>
              <span className="drift-value font-mono">{formatPaise(quotedPrice)}</span>
              <span className="drift-sub">Captured at proposal creation</span>
            </div>

            <div className="drift-card drift-current">
              <span className="drift-label">Current price</span>
              <span className="drift-value font-mono text-danger">{formatPaise(currentPrice)}</span>
              <span className="drift-sub">Verified from merchant catalog</span>
            </div>

            <div className="drift-card">
              <span className="drift-label">Allowed drift</span>
              <span className="drift-value font-mono">{formatPercent(allowedDrift)}</span>
              <span className="drift-sub">System policy threshold</span>
            </div>

            <div className="drift-card drift-highlight">
              <span className="drift-label">Actual drift</span>
              <span className="drift-value font-mono text-danger font-bold">
                {formatPercent(actualDrift)}
              </span>
              <span className="drift-sub">Deviation exceeded tolerance</span>
            </div>

            <div className="drift-card">
              <span className="drift-label">Policy</span>
              <span className="drift-value font-mono">{policy_decision.reason_code}</span>
              <span className="drift-sub">Deterministic rule triggered</span>
            </div>
          </div>

          <div className="zero-order-notice">
            <div className="notice-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <div className="notice-content">
              <strong className="notice-heading">No Razorpay order was created.</strong>
              <p className="notice-text">
                SentinelCart intercepted the price modification and halted execution before any
                charge could be authorized.
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // OTHER BLOCKED REASONS (DUPLICATE_ORDER, EXCEEDS_SESSION_LIMIT, etc.)
  if (isBlocked) {
    return (
      <section className="journey-card policy-section policy-blocked" role="alert">
        <div className="section-header">
          <div className="step-indicator blocked-indicator">
            <span className="step-number">3</span>
            <span className="step-label">Policy Decision: BLOCKED</span>
          </div>
          <div className="status-hero blocked-hero">
            <div className="status-hero-icon blocked-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <div>
              <h2 className="section-title blocked-title">TRANSACTION BLOCKED</h2>
              <p className="blocked-subtitle">{policy_decision.message}</p>
            </div>
          </div>
        </div>

        <div className="decision-details-box">
          <div className="policy-summary-row">
            <div className="meta-item">
              <span className="meta-label">Policy Rule</span>
              <span className="meta-val font-mono">{policy_decision.reason_code}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Product</span>
              <span className="meta-val">{product_name}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Authoritative Price</span>
              <span className="meta-val">{formatPaise(authoritative_current_price_paise)}</span>
            </div>
          </div>

          <div className="zero-order-notice">
            <div className="notice-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div className="notice-content">
              <strong className="notice-heading">No Razorpay order was created.</strong>
              <p className="notice-text">
                The transaction failed compliance verification and was rejected.
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // REQUIRE_APPROVAL
  return (
    <section className="journey-card policy-section policy-approval" role="alert">
      <div className="section-header">
        <div className="step-indicator warning-indicator">
          <span className="step-number">3</span>
          <span className="step-label">Policy Decision: REQUIRE_APPROVAL</span>
        </div>
        <div className="status-hero warning-hero">
          <div className="status-hero-icon warning-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </div>
          <div>
            <h2 className="section-title">Your approval is required</h2>
            <p className="warning-subtitle">{policy_decision.message}</p>
          </div>
        </div>
      </div>

      <div className="decision-details-box">
        <div className="policy-summary-row">
          <div className="meta-item">
            <span className="meta-label">Transaction Amount</span>
            <span className="meta-val font-bold">{formatPaise(authoritative_current_price_paise)}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Per-Transaction Limit</span>
            <span className="meta-val">₹50,000</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Reason Code</span>
            <span className="meta-val font-mono">{policy_decision.reason_code}</span>
          </div>
        </div>

        <div className="zero-order-notice">
          <div className="notice-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="notice-content">
            <strong className="notice-heading">No Razorpay order was created.</strong>
            <p className="notice-text">
              Purchases exceeding ₹50,000 require manual administrative approval before payment execution.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
