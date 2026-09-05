import React, { useState, useCallback } from 'react';
import { Header } from './components/Header';
import { IntentSection } from './components/IntentSection';
import { ProposalSection } from './components/ProposalSection';
import { PolicyDecisionSection } from './components/PolicyDecisionSection';
import { PaymentVerificationSection } from './components/PaymentVerificationSection';
import { AuditTrailSection } from './components/AuditTrailSection';
import { DemoGuide } from './components/DemoGuide';
import type {
  AuditLogRead,
  CheckoutResult,
  PaymentVerificationResponse,
  ProposalResponse,
  RazorpayHandlerResponse,
} from './types/api';
import {
  createIntent,
  checkoutProposal,
  verifyPayment,
  getAuditTrail,
  ApiError,
} from './services/api';
import { launchRazorpayCheckout } from './services/razorpay';
import { generateIdempotencyKey } from './utils/formatters';
import './App.css';

export const App: React.FC = () => {
  // 1. Intent / Proposal state
  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [isGeneratingProposal, setIsGeneratingProposal] = useState(false);
  const [proposalError, setProposalError] = useState<{ message: string; technical?: string } | null>(null);

  // 2. Checkout / Policy state
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkoutResult, setCheckoutResult] = useState<CheckoutResult | null>(null);
  const [checkoutError, setCheckoutError] = useState<{ message: string; technical?: string } | null>(null);

  // 3. Payment verification state
  const [isVerifyingPayment, setIsVerifyingPayment] = useState(false);
  const [verificationResult, setVerificationResult] = useState<PaymentVerificationResponse | null>(null);
  const [verificationError, setVerificationError] = useState<string | null>(null);

  // 4. Razorpay modal open state
  const [isOpeningRazorpay, setIsOpeningRazorpay] = useState(false);

  // 5. Audit logs
  const [auditLogs, setAuditLogs] = useState<AuditLogRead[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);

  // Helper to fetch audit trail
  const fetchAudit = useCallback(async (proposalId: number) => {
    setIsLoadingAudit(true);
    try {
      const logs = await getAuditTrail(proposalId);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setIsLoadingAudit(false);
    }
  }, []);

  // 1. User submits intent
  const handleIntentSubmit = async (userIntent: string) => {
    setIsGeneratingProposal(true);
    setProposalError(null);
    setCheckoutResult(null);
    setCheckoutError(null);
    setVerificationResult(null);
    setVerificationError(null);
    setAuditLogs([]);

    try {
      const idempotencyKey = generateIdempotencyKey('intent');
      const response = await createIntent(userIntent, idempotencyKey);
      setProposal(response);
      // Fetch initial audit trail for proposal
      await fetchAudit(response.proposal_id);
    } catch (err) {
      if (err instanceof ApiError) {
        setProposalError({
          message: err.message,
          technical: err.technicalDetails,
        });
      } else {
        setProposalError({
          message: 'Unable to process your intent. Please try again.',
        });
      }
    } finally {
      setIsGeneratingProposal(false);
    }
  };

  // Callback when Razorpay succeeds
  const handleRazorpaySuccess = useCallback(
    async (response: RazorpayHandlerResponse) => {
      if (!proposal) return;

      setIsVerifyingPayment(true);
      setVerificationError(null);

      try {
        const verifyRes = await verifyPayment({
          proposal_id: proposal.proposal_id,
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
        });

        setVerificationResult(verifyRes);
        // Refresh audit to see PAYMENT_VERIFIED
        await fetchAudit(proposal.proposal_id);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Server signature verification failed.';
        setVerificationError(msg);
        await fetchAudit(proposal.proposal_id);
      } finally {
        setIsVerifyingPayment(false);
      }
    },
    [proposal, fetchAudit]
  );

  const handleRazorpayDismiss = useCallback(() => {
    // User closed modal
    setIsOpeningRazorpay(false);
  }, []);

  const handleRazorpayFailure = useCallback((err: { code?: string; description?: string; reason?: string }) => {
    setIsOpeningRazorpay(false);
    setVerificationError(err.description || 'Payment was declined or cancelled.');
  }, []);

  // Helper to open Razorpay modal
  const openRazorpay = useCallback(
    async (paymentData: any) => {
      if (!proposal) return;
      setIsOpeningRazorpay(true);
      try {
        await launchRazorpayCheckout({
          paymentData,
          productName: proposal.product_name,
          onSuccess: handleRazorpaySuccess,
          onDismiss: handleRazorpayDismiss,
          onFailure: handleRazorpayFailure,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to launch Razorpay gateway.';
        setVerificationError(msg);
      } finally {
        setIsOpeningRazorpay(false);
      }
    },
    [proposal, handleRazorpaySuccess, handleRazorpayDismiss, handleRazorpayFailure]
  );

  // 2. User clicks "Proceed to Checkout"
  const handleCheckout = async () => {
    if (!proposal || isCheckingOut) return;

    setIsCheckingOut(true);
    setCheckoutError(null);
    setVerificationResult(null);
    setVerificationError(null);

    try {
      const result = await checkoutProposal(proposal.proposal_id);
      setCheckoutResult(result);

      // Refresh audit trail
      await fetchAudit(proposal.proposal_id);

      // If ALLOWED, launch Razorpay Checkout automatically
      if (result.type === 'PAYMENT_READY') {
        await openRazorpay(result.data);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setCheckoutError({
          message: err.message,
          technical: err.technicalDetails,
        });
      } else {
        setCheckoutError({
          message: 'Something went wrong while preparing checkout.',
        });
      }
      await fetchAudit(proposal.proposal_id);
    } finally {
      setIsCheckingOut(false);
    }
  };

  // Reset to initial state
  const handleReset = () => {
    setProposal(null);
    setIsGeneratingProposal(false);
    setProposalError(null);
    setCheckoutResult(null);
    setCheckoutError(null);
    setIsVerifyingPayment(false);
    setVerificationResult(null);
    setVerificationError(null);
    setAuditLogs([]);
  };

  return (
    <div className="app-container">
      <Header onReset={handleReset} hasActiveProposal={Boolean(proposal)} />

      <main className="main-content">
        <div className="content-wrapper">
          {/* Top thesis banner */}
          <div className="thesis-banner">
            <div className="thesis-item">
              <span className="thesis-num">1</span>
              <span className="thesis-title">Agent Proposes</span>
              <span className="thesis-desc">Natural intent mapped to catalog snapshot</span>
            </div>
            <div className="thesis-separator">→</div>
            <div className="thesis-item">
              <span className="thesis-num">2</span>
              <span className="thesis-title">Policy Decides</span>
              <span className="thesis-desc">Deterministic drift &amp; limits verified</span>
            </div>
            <div className="thesis-separator">→</div>
            <div className="thesis-item">
              <span className="thesis-num">3</span>
              <span className="thesis-title">Razorpay Executes</span>
              <span className="thesis-desc">Cryptographic server-side settlement</span>
            </div>
          </div>

          {/* Demo Guide Drawer */}
          <DemoGuide />

          {/* Step 1: Intent Section */}
          <IntentSection
            onSubmit={handleIntentSubmit}
            isLoading={isGeneratingProposal}
            disabled={Boolean(proposal) && !checkoutResult}
          />

          {/* Proposal Error Alert */}
          {proposalError && (
            <div className="alert-box alert-error" role="alert">
              <div className="alert-content">
                <strong>Request Failed:</strong> {proposalError.message}
                {proposalError.technical && (
                  <details className="alert-technical">
                    <summary>Technical Details</summary>
                    <pre>{proposalError.technical}</pre>
                  </details>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Proposal Section */}
          {proposal && (
            <ProposalSection
              proposal={proposal}
              onCheckout={handleCheckout}
              isCheckingOut={isCheckingOut}
              checkoutCompleted={Boolean(checkoutResult)}
            />
          )}

          {/* Checkout Generic Error Alert */}
          {checkoutError && (
            <div className="alert-box alert-error" role="alert">
              <div className="alert-content">
                <strong>Checkout Error:</strong> {checkoutError.message}
                {checkoutError.technical && (
                  <details className="alert-technical">
                    <summary>Technical Details</summary>
                    <pre>{checkoutError.technical}</pre>
                  </details>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Policy Decision Section */}
          {checkoutResult && (
            <PolicyDecisionSection
              decisionData={checkoutResult}
              isPaymentVerified={Boolean(verificationResult?.success)}
              onOpenCheckout={
                checkoutResult.type === 'PAYMENT_READY' && !verificationResult?.success
                  ? () => openRazorpay(checkoutResult.data)
                  : undefined
              }
              isOpeningRazorpay={isOpeningRazorpay}
            />
          )}

          {/* Step 4: Payment Verification & Settlement Section */}
          {(isVerifyingPayment || verificationResult || verificationError) && (
            <PaymentVerificationSection
              verification={verificationResult}
              isVerifying={isVerifyingPayment}
              verificationError={verificationError}
              onRetryCheckout={
                checkoutResult?.type === 'PAYMENT_READY' && !verificationResult?.success
                  ? () => openRazorpay(checkoutResult.data)
                  : undefined
              }
              onNewSearch={handleReset}
            />
          )}

          {/* Audit Trail Section */}
          {proposal && (
            <AuditTrailSection
              logs={auditLogs}
              isLoading={isLoadingAudit}
              onRefresh={() => fetchAudit(proposal.proposal_id)}
              proposalId={proposal.proposal_id}
            />
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
