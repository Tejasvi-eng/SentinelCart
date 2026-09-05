import React, { useState } from 'react';
import type { AuditLogRead } from '../types/api';
import { formatDateTime, formatPaise, formatPercent } from '../utils/formatters';

interface AuditTrailSectionProps {
  logs: AuditLogRead[];
  isLoading: boolean;
  onRefresh: () => void;
  proposalId: number;
}

interface ParsedEventDetails {
  [key: string]: unknown;
}

export const AuditTrailSection: React.FC<AuditTrailSectionProps> = ({
  logs,
  isLoading,
  onRefresh,
  proposalId,
}) => {
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const toggleExpand = (id: number) => {
    setExpandedLogId((prev) => (prev === id ? null : id));
  };

  const parseDetailJson = (rawJson: string): ParsedEventDetails => {
    try {
      return JSON.parse(rawJson);
    } catch {
      return { raw: rawJson };
    }
  };

  const getEventMeta = (log: AuditLogRead) => {
    const details = parseDetailJson(log.detail_json);

    switch (log.event_type) {
      case 'PROPOSAL_CREATED':
        return {
          humanTitle: 'Proposal created',
          stage: 'Step 2: Proposal',
          status: 'CREATED',
          statusType: 'neutral',
          summary: details.product_name
            ? `Proposed "${details.product_name}" at ${
                typeof details.authoritative_price_paise === 'number'
                  ? formatPaise(details.authoritative_price_paise)
                  : ''
              }`
            : 'Product proposal created with DB price snapshot',
        };

      case 'POLICY_DECISION': {
        const decision = String(details.decision || '');
        const reason = String(details.reason_code || '');
        const isBlocked = decision === 'BLOCKED';
        const isApproval = decision === 'REQUIRE_APPROVAL';

        let summary = `Decision: ${decision} (${reason})`;
        if (reason === 'PRICE_DRIFT') {
          const drift = typeof details.details === 'object' && details.details !== null
            ? (details.details as any).drift_percent
            : null;
          summary = `Transaction BLOCKED due to price drift${
            typeof drift === 'number' ? ` (${formatPercent(drift)})` : ''
          }`;
        } else if (reason === 'EXCEEDS_TRANSACTION_LIMIT') {
          summary = 'Approval required: Amount exceeds ₹50,000 policy limit';
        } else if (decision === 'ALLOWED') {
          summary = 'All policy checks passed: Within transaction and drift limits';
        }

        return {
          humanTitle: 'Policy evaluated',
          stage: 'Step 3: Authorization',
          status: decision,
          statusType: isBlocked ? 'danger' : isApproval ? 'warning' : 'success',
          summary,
        };
      }

      case 'ORDER_CREATED':
        return {
          humanTitle: 'Order created',
          stage: 'Step 3: Gateway Execution',
          status: 'ORDER_READY',
          statusType: 'info',
          summary: details.razorpay_order_id
            ? `Razorpay Order ${details.razorpay_order_id} created for ${
                typeof details.amount_paise === 'number'
                  ? formatPaise(details.amount_paise)
                  : ''
              }`
            : 'Payment order created on Razorpay Test Mode',
        };

      case 'PAYMENT_VERIFIED':
        return {
          humanTitle: 'Payment verified',
          stage: 'Step 4: Settlement',
          status: 'VERIFIED',
          statusType: 'success',
          summary: details.razorpay_payment_id
            ? `Server-side HMAC-SHA256 signature verified for payment ${details.razorpay_payment_id}`
            : 'Payment cryptographically verified on server',
        };

      case 'PAYMENT_VERIFICATION_FAILED':
        return {
          humanTitle: 'Payment verification failed',
          stage: 'Step 4: Settlement Failure',
          status: 'FAILED',
          statusType: 'danger',
          summary: details.reason ? String(details.reason) : 'Signature verification failed',
        };

      default:
        return {
          humanTitle: log.event_type.replace(/_/g, ' '),
          stage: 'Audit Log',
          status: log.event_type,
          statusType: 'neutral',
          summary: 'Compliance audit log entry',
        };
    }
  };

  return (
    <section className="journey-card audit-section">
      <div className="section-header audit-header">
        <div>
          <div className="step-indicator">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span className="step-label">Immutable Audit Trail</span>
          </div>
          <h2 className="section-title">Compliance Timeline</h2>
          <p className="section-description">
            Append-only record of every proposal event, policy evaluation, and payment signature.
          </p>
        </div>

        <button
          type="button"
          className="btn-refresh"
          onClick={onRefresh}
          disabled={isLoading}
          title="Refresh audit events"
        >
          <svg
            className={isLoading ? 'spin' : ''}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          <span>Refresh</span>
        </button>
      </div>

      {logs.length === 0 ? (
        <div className="empty-audit-state">
          <span>No audit events recorded yet for Proposal #{proposalId}.</span>
        </div>
      ) : (
        <div className="timeline">
          {/* Virtual Initial Stage: Intent received */}
          <div className="timeline-item">
            <div className="timeline-marker marker-neutral">
              <span className="marker-dot"></span>
            </div>
            <div className="timeline-content">
              <div className="timeline-top">
                <div className="timeline-title-group">
                  <span className="timeline-title">Intent received</span>
                  <span className="badge badge-neutral">RECEIVED</span>
                </div>
                <span className="timeline-time">
                  {formatDateTime(logs[0].created_at)}
                </span>
              </div>
              <p className="timeline-summary">User search intent parsed and validated by agent</p>
            </div>
          </div>

          {/* Real Backend Events */}
          {logs.map((log) => {
            const meta = getEventMeta(log);
            const isExpanded = expandedLogId === log.id;
            const parsed = parseDetailJson(log.detail_json);

            return (
              <div key={log.id} className="timeline-item">
                <div className={`timeline-marker marker-${meta.statusType}`}>
                  <span className="marker-dot"></span>
                </div>

                <div className="timeline-content">
                  <div className="timeline-top">
                    <div className="timeline-title-group">
                      <span className="timeline-title">{meta.humanTitle}</span>
                      <span className={`badge badge-${meta.statusType}`}>
                        {meta.status}
                      </span>
                    </div>
                    <span className="timeline-time">{formatDateTime(log.created_at)}</span>
                  </div>

                  <p className="timeline-summary">{meta.summary}</p>

                  <div className="disclosure-wrap">
                    <button
                      type="button"
                      className="btn-disclosure"
                      onClick={() => toggleExpand(log.id)}
                      aria-expanded={isExpanded}
                    >
                      <span>{isExpanded ? 'Hide technical details' : 'View technical details'}</span>
                      <svg
                        className={`disclosure-arrow ${isExpanded ? 'rotated' : ''}`}
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </button>

                    {isExpanded && (
                      <div className="technical-details-panel">
                        <div className="tech-meta-grid">
                          <div className="tech-meta-row">
                            <span className="tech-key">Event Type:</span>
                            <span className="tech-val font-mono">{log.event_type}</span>
                          </div>
                          <div className="tech-meta-row">
                            <span className="tech-key">Audit ID:</span>
                            <span className="tech-val font-mono">#{log.id}</span>
                          </div>
                          <div className="tech-meta-row">
                            <span className="tech-key">Proposal ID:</span>
                            <span className="tech-val font-mono">#{log.proposal_id}</span>
                          </div>
                          <div className="tech-meta-row">
                            <span className="tech-key">Timestamp:</span>
                            <span className="tech-val font-mono">{log.created_at}</span>
                          </div>
                        </div>

                        <div className="json-viewer">
                          <span className="json-label">Event Payload (JSON):</span>
                          <pre className="json-code">
                            {JSON.stringify(parsed, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
