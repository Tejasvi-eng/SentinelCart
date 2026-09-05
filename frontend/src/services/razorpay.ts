import type { CheckoutPaymentResponse, RazorpayHandlerResponse } from '../types/api';

/**
 * Ensures Razorpay Checkout script is loaded in the DOM.
 */
export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window !== 'undefined' && window.Razorpay) {
      resolve(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export interface OpenRazorpayOptions {
  paymentData: CheckoutPaymentResponse;
  productName: string;
  onSuccess: (response: RazorpayHandlerResponse) => void;
  onDismiss: () => void;
  onFailure: (errorDetails: { code?: string; description?: string; reason?: string }) => void;
}

/**
 * Launches official Razorpay Standard Checkout in the browser.
 * Only public key_id and order_id are used.
 */
export async function launchRazorpayCheckout({
  paymentData,
  productName,
  onSuccess,
  onDismiss,
  onFailure,
}: OpenRazorpayOptions): Promise<void> {
  const loaded = await loadRazorpayScript();
  if (!loaded || !window.Razorpay) {
    throw new Error('Unable to load Razorpay payment gateway. Please check your internet connection.');
  }

  const options = {
    key: paymentData.key_id,
    amount: paymentData.amount,
    currency: paymentData.currency || 'INR',
    name: 'SentinelCart',
    description: productName ? `Payment for ${productName}` : `Order #${paymentData.order_id}`,
    order_id: paymentData.order_id,
    handler: (response: RazorpayHandlerResponse) => {
      onSuccess(response);
    },
    modal: {
      ondismiss: () => {
        onDismiss();
      },
      escape: true,
      backdropclose: false,
    },
    theme: {
      color: '#0F172A',
    },
    prefill: {
      name: 'Demo Shopper',
      email: 'shopper@example.com',
      contact: '9999999999',
    },
    notes: {
      proposal_id: String(paymentData.proposal_id),
      order_id: paymentData.order_id,
    },
  };

  const rzp = new window.Razorpay(options);

  rzp.on('payment.failed', (response: any) => {
    const err = response?.error || {};
    onFailure({
      code: err.code,
      description: err.description || 'Payment was declined or cancelled.',
      reason: err.reason,
    });
  });

  rzp.open();
}
