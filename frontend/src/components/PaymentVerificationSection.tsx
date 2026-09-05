import React from 'react';
import type { PaymentVerificationResponse } from '../types/api';
import { formatPaise } from '../utils/formatters';

interface PaymentVerificationSectionProps {
  verification: PaymentVerificationResponse | null;
  isVerifying: boolean;
  verificationError: string | null;
  onRetryCheckout?: () => void;
  onNewSearch: () => void;
}

export const PaymentVerificationSection: React.FC<PaymentVerificationSectionProps> = ({
  verification,
  isVerifying,
  verificationError,
  onRetryCheckout,
  onNewSearch,
}) => {
  // Case 1: Verifying in progress
  if (isVerifying) {
    return (
      <section className="journey-card payment-verify-section">
        <div className="section-header">
          <div className="step-indicator">
            <span className="step-number">4</span>
            <span className="step-label">Settlement &amp; Verification</span>
          </div>
          <div className="verifying-hero">
            <div className="spinner-md"></div>
            <div>
              <h2 className="section-title">Verifying Payment Cryptographically...</h2>
              <p className="section-description">
                Validating HMAC-SHA256 signature against server-side secret.
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Case 2: Verification Error or Failure
  if (verificationError) {
    return (
      <section className="journey-card payment-verify-section verify-failed" role="alert">
        <div className="section-header">
          <div className="step-indicator blocked-indicator">
            <span className="step-number">4</span>
            <span className="step-label">Verification Failed</span>
          </div>
          <div className="status-hero blocked-hero">
            <div className="status-hero-icon blocked-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <div>
              <h2 className="section-title blocked-title">Payment Verification Unsuccessful</h2>
              <p className="blocked-subtitle">{verificationError}</p>
            </div>
          </div>
        </div>

        <div className="action-row">
          {onRetryCheckout && (
            <button type="button" className="btn btn-secondary" onClick={onRetryCheckout}>
              Try Again
            </button>
          )}
          <button type="button" className="btn btn-text" onClick={onNewSearch}>
            Start New Search
          </button>
        </div>
      </section>
    );
  }

  // Case 3: Verified Success
  if (verification && verification.success) {
    const amountPaise = verification.details?.amount_paise;

    return (
      <section className="journey-card payment-verify-section verify-success">
        <div className="section-header">
          <div className="step-indicator allowed-indicator">
            <span className="step-number">4</span>
            <span className="step-label">Payment Settled &amp; Verified</span>
          </div>
          <div className="status-hero allowed-hero">
            <div className="status-hero-icon allowed-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <polyline points="9 12 11 14 15 10" />
              </svg>
            </div>
            <div>
              <h2 className="section-title">Payment verified</h2>
              <p className="status-hero-subtitle">
                Cryptographic signature verified server-side. Order completed successfully.
              </p>
            </div>
          </div>
        </div>

        <div className="decision-details-box allowed-box">
          <div className="policy-summary-row">
            <div className="meta-item">
              <span className="meta-label">Payment ID</span>
              <span className="meta-val font-mono">{verification.payment_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Razorpay Order ID</span>
              <span className="meta-val font-mono">{verification.order_id}</span>
            </div>
            {amountPaise && (
              <div className="meta-item">
                <span className="meta-label">Amount Paid</span>
                <span className="meta-val font-bold">{formatPaise(amountPaise)}</span>
              </div>
            )}
            <div className="meta-item">
              <span className="meta-label">Status</span>
              <span className="meta-val text-success font-bold">COMPLETED</span>
            </div>
          </div>

          <div className="verification-badge-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>Verified with Razorpay server-side HMAC-SHA256 signature check.</span>
          </div>

          <div className="action-row">
            <button type="button" className="btn btn-primary" onClick={onNewSearch}>
              Start Another Search
            </button>
          </div>
        </div>
      </section>
    );
  }

  return null;
};
