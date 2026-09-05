import React from 'react';

interface HeaderProps {
  onReset: () => void;
  hasActiveProposal: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onReset, hasActiveProposal }) => {
  return (
    <header className="site-header">
      <div className="header-container">
        <div className="brand-group">
          <div className="brand-logo" onClick={onReset} role="button" tabIndex={0}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
            <span className="brand-title">SentinelCart</span>
          </div>
          <span className="brand-tagline">
            The agent proposes • The policy engine decides • Razorpay executes
          </span>
        </div>

        <div className="header-actions">
          <div className="mode-badge">
            <span className="mode-dot"></span>
            <span>Razorpay Test Mode</span>
          </div>
          {hasActiveProposal && (
            <button
              type="button"
              className="btn-text"
              onClick={onReset}
              title="Start a new search"
            >
              New Search
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
