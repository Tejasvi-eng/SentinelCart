import React, { useState } from 'react';

interface IntentSectionProps {
  onSubmit: (intent: string) => Promise<void>;
  isLoading: boolean;
  disabled?: boolean;
}

const SUGGESTIONS = [
  'Find me wireless headphones under ₹5,000',
  'Ergonomic aluminum laptop stand',
  'Mechanical keyboard with RGB',
  '4K USB webcam with auto-focus',
  'Portable power bank 20000mAh',
];

export const IntentSection: React.FC<IntentSectionProps> = ({
  onSubmit,
  isLoading,
  disabled = false,
}) => {
  const [intent, setIntent] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!intent.trim() || isLoading || disabled) return;
    onSubmit(intent.trim());
  };

  const handleSelectSuggestion = (suggestion: string) => {
    if (isLoading || disabled) return;
    setIntent(suggestion);
    onSubmit(suggestion);
  };

  return (
    <section className="journey-card intent-section">
      <div className="section-header">
        <div className="step-indicator">
          <span className="step-number">1</span>
          <span className="step-label">Agent Intent</span>
        </div>
        <h2 className="section-title">Tell us what you&apos;re looking for.</h2>
        <p className="section-description">
          Describe the product you need. The agent parses your intent, cross-references
          authoritative catalog data, and generates a verifiable purchase proposal.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="intent-form">
        <div className="input-group">
          <input
            type="text"
            className="intent-input"
            placeholder="e.g. Find me wireless headphones under ₹5,000"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            disabled={isLoading || disabled}
            aria-label="Product search intent"
            autoComplete="off"
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!intent.trim() || isLoading || disabled}
          >
            {isLoading ? (
              <span className="btn-loading-content">
                <span className="spinner-sm"></span>
                <span>Understanding your request...</span>
              </span>
            ) : (
              <span>Find the best match</span>
            )}
          </button>
        </div>
      </form>

      {!disabled && (
        <div className="suggestions-container">
          <span className="suggestions-label">Try an example:</span>
          <div className="suggestions-chips">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="chip-btn"
                onClick={() => handleSelectSuggestion(suggestion)}
                disabled={isLoading}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
