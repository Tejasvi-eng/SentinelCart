import React, { useState } from 'react';

export const DemoGuide: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="demo-guide-container">
      <button
        type="button"
        className="demo-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="demo-dot"></span>
        <span>{isOpen ? 'Close Demo Guide' : 'How to Test Price Drift & Authorization'}</span>
        <svg
          className={`demo-arrow ${isOpen ? 'rotated' : ''}`}
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

      {isOpen && (
        <div className="demo-guide-card">
          <div className="demo-guide-section">
            <h4 className="demo-guide-title">
              🧪 Scenario A: Test Price Drift (Primary Failure Demo)
            </h4>
            <ol className="demo-steps">
              <li>
                Search for <code>wireless headphones</code> above (Product #1, default price ₹2,999).
              </li>
              <li>
                Before clicking <strong>Proceed to Checkout</strong>, open a terminal and simulate merchant price change:
                <pre className="demo-code">python -m backend.db.set_price 1 350000</pre>
              </li>
              <li>
                Click <strong>Proceed to Checkout</strong>.
              </li>
              <li>
                Notice the instant <strong>TRANSACTION BLOCKED</strong> screen showing 16.71% drift (threshold: 2.00%) and confirming that <strong>no Razorpay order was created</strong>.
              </li>
              <li>
                Reset product price afterwards:
                <pre className="demo-code">python -m backend.db.set_price 1 299900</pre>
              </li>
            </ol>
          </div>

          <div className="demo-guide-section">
            <h4 className="demo-guide-title">
              💳 Scenario B: Standard Authorized Checkout
            </h4>
            <ol className="demo-steps">
              <li>Ensure product #1 price is restored to ₹2,999 (299900 paise).</li>
              <li>Search for <code>wireless headphones</code> and click <strong>Proceed to Checkout</strong>.</li>
              <li>Policy verifies drift is 0.00%, approves purchase, and opens Razorpay Test Mode modal.</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
};
