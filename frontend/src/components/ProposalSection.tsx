import React from 'react';
import type { ProposalResponse } from '../types/api';
import { formatDateTime, formatPaise } from '../utils/formatters';

interface ProposalSectionProps {
  proposal: ProposalResponse;
  onCheckout: () => Promise<void>;
  isCheckingOut: boolean;
  checkoutCompleted: boolean;
}

export const ProposalSection: React.FC<ProposalSectionProps> = ({
  proposal,
  onCheckout,
  isCheckingOut,
  checkoutCompleted,
}) => {
  return (
    <section className="journey-card proposal-section">
      <div className="section-header">
        <div className="step-indicator">
          <span className="step-number">2</span>
          <span className="step-label">Agent Proposal</span>
        </div>
        <h2 className="section-title">Here&apos;s what SentinelCart found.</h2>
        <p className="section-description">
          The agent proposed this item matching your criteria with an immutable price snapshot.
        </p>
      </div>

      <div className="proposal-card">
        <div className="proposal-main">
          <div className="product-meta">
            <span className="product-badge">Product #{proposal.product_id}</span>
            <span className="proposal-id">Proposal #{proposal.proposal_id}</span>
          </div>

          <h3 className="product-name">{proposal.product_name}</h3>
          {proposal.description && (
            <p className="product-description">{proposal.description}</p>
          )}

          <div className="price-container">
            <div className="price-block">
              <span className="price-label">Authoritative Price</span>
              <span className="price-value">
                {formatPaise(proposal.quoted_price_snapshot)}
              </span>
            </div>

            <div className="trust-badge">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
              <div>
                <strong>Price verified from merchant data</strong>
                <span className="trust-sub">Database snapshot taken at proposal creation</span>
              </div>
            </div>
          </div>

          {proposal.reasoning_text && (
            <div className="reasoning-bubble">
              <div className="reasoning-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span>Agent Reasoning</span>
              </div>
              <p className="reasoning-text">{proposal.reasoning_text}</p>
            </div>
          )}

          <div className="proposal-footer-meta">
            <span>Created: {formatDateTime(proposal.created_at)}</span>
            <span className="meta-divider">•</span>
            <span className="idempotency-display" title={proposal.idempotency_key}>
              Idempotency: {proposal.idempotency_key.slice(0, 22)}...
            </span>
          </div>
        </div>

        <div className="proposal-actions">
          {!checkoutCompleted ? (
            <button
              type="button"
              className="btn btn-primary btn-checkout"
              onClick={onCheckout}
              disabled={isCheckingOut}
            >
              {isCheckingOut ? (
                <span className="btn-loading-content">
                  <span className="spinner-sm"></span>
                  <span>Evaluating policy &amp; authorizing...</span>
                </span>
              ) : (
                <span>Proceed to Checkout</span>
              )}
            </button>
          ) : (
            <div className="checkout-status-pill">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>Policy Evaluated</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
