/**
 * Formatting helpers for currency, timestamps, and numbers.
 */

/**
 * Formats amount in paise (100 paise = 1 INR) to standard Indian Rupee string.
 * e.g., 316200 -> "₹3,162", 49900 -> "₹499", 74999 -> "₹749.99"
 */
export function formatPaise(paise: number): string {
  const rupees = paise / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2,
    minimumFractionDigits: rupees % 1 === 0 ? 0 : 2,
  }).format(rupees);
}

/**
 * Formats a percentage with specified decimal places.
 */
export function formatPercent(percent: number, fractionDigits = 2): string {
  return `${percent.toFixed(fractionDigits)}%`;
}

/**
 * Formats an ISO datetime string into human-readable date & time.
 */
export function formatDateTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * Formats an ISO datetime string into just time (HH:MM:SS AM/PM).
 */
export function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * Generates a unique idempotency key for user actions.
 */
export function generateIdempotencyKey(prefix = 'intent'): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}
