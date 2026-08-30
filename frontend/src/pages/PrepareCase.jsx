import React, { useState, useEffect, useMemo } from 'react';
import { ArrowLeft, Download, Share2, AlertCircle, CheckSquare, Shield, Info } from 'lucide-react';
import { downloadEvidencePackage, getInspection } from '../services/api';

const translateEnum = (val) => {
  if (!val) return '—';
  const mapping = {
    GENERIC_RETAIL_PACKAGE: 'Generic Retail Package',
    FOOD: 'Food Product',
    COSMETIC: 'Cosmetic Product',
    DRUG: 'Drug / Medical Product',
    DRAFT: 'Draft Case',
    IN_PROGRESS: 'In Progress',
    READY_FOR_REVIEW: 'Awaiting Review',
    FINALIZED: 'Finalized',
    VIOLATIONS_FOUND: 'Possible Violations Found',
    REVIEW_REQUIRED: 'Needs Review',
    NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE: 'No Violations Detected',
    INCOMPLETE_INSPECTION: 'More Package Evidence Needed',
  };
  return mapping[val] || val.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

export const PrepareCase = ({ inspectionId, onBack, externalPortalUrl }) => {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [officerNotes, setOfficerNotes] = useState('');
  const [complaintDraft, setComplaintDraft] = useState('');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState({});
  const [draftInitialized, setDraftInitialized] = useState(false);
  const [submissionConfirmed, setSubmissionConfirmed] = useState(false);
  const [showSubmissionModal, setShowSubmissionModal] = useState(false);

  useEffect(() => {
    if (inspectionId) {
      setLoading(true);
      getInspection(inspectionId)
        .then((data) => {
          setSession(data);
        })
        .catch(() => {
          setError('Could not load the complaint details. Check the connection and try again.');
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [inspectionId]);

  const allViolations = useMemo(() => [
    ...(session?.rule_evaluations?.filter(r => r.status === 'FAIL') || []),
    ...(session?.food_label_evaluations?.filter(r => r.status === 'FAIL') || []),
    ...(session?.visual_rule_evaluations?.filter(r => r.status === 'FAIL') || []),
  ], [session]);

  const draftStorageKey = inspectionId ? `drishti_complaint_draft_${inspectionId}` : null;

  useEffect(() => {
    if (session) {
      if (draftStorageKey) {
        try {
          const savedDraft = JSON.parse(localStorage.getItem(draftStorageKey));
          if (savedDraft?.complaintDraft) {
            setComplaintDraft(savedDraft.complaintDraft);
            setOfficerNotes(savedDraft.officerNotes || '');
            setDraftInitialized(true);
            return;
          }
        } catch {
          localStorage.removeItem(draftStorageKey);
        }
      }

      const dateStr = session.reference_date || new Date().toISOString().split('T')[0];
      const category = session.product_category || 'packaged commodity';
      const genericName = session.aggregated_candidates?.find(c => c.field === 'COMMON_GENERIC_NAME')?.raw_value || '';
      
      let draft = `OFFICIAL INSPECTION COMPLAINT DRAFT\n`;
      draft += `--------------------------------------------------\n`;
      draft += `Date of Inspection: ${dateStr}\n`;
      draft += `Commodity Name: ${genericName || 'Not detected'} (${translateEnum(category)})\n\n`;
      draft += `During the official inspection of the packaged commodity, the following possible statutory non-compliance issue(s) were observed under the Legal Metrology Act and Packaged Commodity Rules:\n\n`;
      
      allViolations.forEach((rule, idx) => {
        const name = rule.field ? rule.field.replace(/_/g, ' ') : rule.rule_id.replace(/_/g, ' ');
        draft += `${idx + 1}. DECLARATION ISSUE: ${name}\n`;
        draft += `   - Detail: ${rule.reason}\n`;
        draft += `   - Applicable statutory provision: ${rule.legal_reference || 'Legal Metrology Rules'}\n\n`;
      });
      
      draft += `The supporting package photographs, inspection report, and evidence record have been prepared for officer review.`;
      setComplaintDraft(draft);
      setDraftInitialized(true);
    }
  }, [session, allViolations, draftStorageKey]);

  useEffect(() => {
    if (!draftInitialized || !draftStorageKey) return;
    localStorage.setItem(draftStorageKey, JSON.stringify({ complaintDraft, officerNotes }));
  }, [complaintDraft, officerNotes, draftInitialized, draftStorageKey]);

  const handleExportPackage = async () => {
    setIsExporting(true);
    setError('');
    setSuccess(false);
    setSubmissionConfirmed(false);
    try {
      await downloadEvidencePackage(session.inspection_id, {
        complaint_draft: complaintDraft,
        officer_notes: officerNotes
      });
      setSuccess(true);
    } catch (err) {
      console.error(err);
      setError('Could not prepare the evidence package. Check the connection and try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleContinueToPortal = () => {
    if (!externalPortalUrl || !success || !submissionConfirmed) return;
    setShowSubmissionModal(true);
  };

  const handleConfirmedPortalHandoff = () => {
    window.open(externalPortalUrl, '_blank', 'noopener,noreferrer');
    setShowSubmissionModal(false);
  };

  const toggleTechnical = (id) => {
    setShowTechnicalDetails(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4 text-xs font-semibold text-slate-500">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        <span>Loading case evidence...</span>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-sm font-bold text-slate-855 dark:text-slate-200">Error Loading Case</h2>
        <p className="text-xs text-slate-500">{error || 'Case inspection record could not be resolved.'}</p>
        <button onClick={onBack} className="px-4 py-2 bg-slate-100 dark:bg-slate-700 text-xs font-bold rounded-lg border border-slate-250 hover:bg-slate-200 transition-all cursor-pointer">
          Back
        </button>
      </div>
    );
  }

  return (
    <main className="portal-page space-y-6 py-6 sm:py-8">
      {/* Back CTA */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-lg transition-colors cursor-pointer border border-slate-200 dark:border-slate-600"
      >
        <ArrowLeft size={14} /> Back to Inspection
      </button>

      {/* Header Banner */}
      <div className="bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700/80 rounded-xl p-5 shadow-sm space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-black text-slate-900 dark:text-slate-50 tracking-tight flex items-center gap-2">
              <Shield className="text-rose-600 dark:text-rose-400" size={20} />
              Prepare complaint
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
              Review the reasons for non-compliance, edit the complaint draft, and prepare supporting evidence from the finalized inspection record.
            </p>
          </div>
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-300">
            Finalized inspection
          </span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 rounded-xl border border-rose-200 dark:border-rose-800 flex items-start gap-3 text-xs">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {success && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-300 rounded-xl border border-emerald-200 dark:border-emerald-800 flex items-start gap-3 text-xs">
          <CheckSquare className="w-5 h-5 shrink-0" />
          <p>Evidence package prepared and downloaded. Review it before continuing to an external portal.</p>
        </div>
      )}

      {/* Layout Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Side: Findings and Inputs (2 cols) */}
        <div className="md:col-span-2 space-y-6">
          
          {/* Confirmed Violations List */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm space-y-4">
            <h3 className="text-xs font-extrabold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 pb-2">
              Reasons for non-compliance ({allViolations.length})
            </h3>
            
            {allViolations.length === 0 ? (
              <p className="text-sm text-slate-500 italic">No non-compliant finding is available for complaint preparation.</p>
            ) : (
              <div className="space-y-3.5">
                {allViolations.map((violation, vIdx) => {
                  const isTechOpen = showTechnicalDetails[`v-${vIdx}`];
                  const name = violation.field ? violation.field.replace(/_/g, ' ') : violation.rule_id.replace(/_/g, ' ');
                  return (
                    <div key={vIdx} className="border border-rose-200/40 dark:border-rose-900/30 rounded-lg p-4 bg-rose-50/10 dark:bg-rose-950/5 space-y-3 text-xs">
                      <div className="flex items-center justify-between gap-2 border-b border-rose-100/30 pb-2">
                        <span className="font-bold text-rose-700 dark:text-rose-300">
                          {name}
                        </span>
                        <span className="text-[10px] text-slate-500 font-semibold px-2 py-0.5 bg-slate-100 dark:bg-slate-850 rounded">
                          {violation.legal_reference || 'Legal Metrology Rules, 2011'}
                        </span>
                      </div>
                      
                      <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-0.5">Reason for non-compliance</div>
                        <p className="text-slate-750 dark:text-slate-300 leading-relaxed">
                          {violation.reason}
                        </p>
                      </div>

                      <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-750">
                        <button
                          onClick={() => toggleTechnical(`v-${vIdx}`)}
                          className="inline-flex items-center gap-1 font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                        >
                          <Info className="w-3.5 h-3.5" />
                          <span>{isTechOpen ? 'Hide details' : 'View details'}</span>
                        </button>
                      </div>

                      {isTechOpen && (
                        <div className="bg-slate-50 dark:bg-slate-900/40 border border-slate-250 dark:border-slate-800 rounded p-2.5 space-y-1.5 font-mono text-[10px] text-slate-650 dark:text-slate-400">
                          <div>Rule code: {violation.rule_id}</div>
                          <div>Status code: {violation.status}</div>
                          {violation.evidence_ids?.length > 0 && (
                            <div>Supporting evidence is retained in the inspection record.</div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Officer notes & Complaint Draft */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm space-y-5">
            <h3 className="text-xs font-extrabold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 pb-2">
              Review before submission
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-350 mb-1.5">
                  Officer notes
                </label>
                <textarea
                  value={officerNotes}
                  onChange={(e) => {
                    setOfficerNotes(e.target.value);
                    setSuccess(false);
                    setSubmissionConfirmed(false);
                  }}
                  placeholder="Enter custom remarks regarding package condition, distributor details, or inspection context..."
                  rows={3}
                  className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-xs leading-relaxed focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-350 mb-1.5">
                  Complaint draft
                </label>
                <textarea
                  value={complaintDraft}
                  onChange={(e) => {
                    setComplaintDraft(e.target.value);
                    setSuccess(false);
                    setSubmissionConfirmed(false);
                  }}
                  rows={10}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-3 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
                <p className="mt-1.5 text-xs text-slate-500">Draft changes are saved on this device so the review can continue after an interruption.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Case Info & Action Buttons (1 col) */}
        <div className="space-y-6">
          {/* Metadata Card */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm space-y-3.5">
            <h3 className="text-xs font-extrabold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 pb-2">
              Inspection details
            </h3>
            
            <div className="space-y-3 text-xs leading-relaxed">
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Reference Date:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{session.reference_date}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Package Type:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{translateEnum(session.product_category)}</span>
              </div>
              {session.regulatory_product_class && (
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Context:</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">{translateEnum(session.regulatory_product_class)}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Product Name:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 text-right max-w-[150px] truncate">
                  {session.aggregated_candidates?.find(c => c.field === 'COMMON_GENERIC_NAME')?.raw_value || 'Not detected'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Box */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm space-y-4">
            <h3 className="text-xs font-extrabold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 pb-2">
              Prepare evidence and submit
            </h3>
            
            <button
              onClick={handleExportPackage}
              disabled={isExporting || allViolations.length === 0}
              className="w-full flex items-center justify-center gap-1.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg transition-all shadow-sm hover:shadow-md cursor-pointer border border-indigo-700 disabled:opacity-50"
            >
              <Download size={14} />
              {isExporting ? 'Preparing evidence package...' : 'Prepare evidence package'}
            </button>

            <label className={`flex items-start gap-3 rounded-xl border p-3 text-sm ${success ? 'cursor-pointer border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-900/30' : 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400 dark:border-slate-700 dark:bg-slate-900/20'}`}>
              <input
                type="checkbox"
                checked={submissionConfirmed}
                disabled={!success}
                onChange={(event) => setSubmissionConfirmed(event.target.checked)}
                className="mt-0.5 h-5 w-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>I have reviewed the complaint draft and downloaded evidence package.</span>
            </label>

            <button
              type="button"
              onClick={handleContinueToPortal}
              disabled={!externalPortalUrl || !success || !submissionConfirmed}
              className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 dark:disabled:bg-slate-700"
            >
              <Share2 size={17} /> Review before submission
            </button>

            {!externalPortalUrl && (
              <p className="text-center text-xs text-slate-500">Official portal link is not configured.</p>
            )}

            <div className="p-3 bg-indigo-50/50 dark:bg-indigo-950/15 rounded-lg border border-indigo-100/50 dark:border-indigo-900/30 text-[11px] text-slate-500 dark:text-slate-450 leading-relaxed flex gap-2">
              <Shield size={16} className="text-indigo-500 shrink-0 mt-0.5" />
              <p>
                DRISHTI prepares the draft and evidence only. The officer decides whether to continue and completes any external submission personally.
              </p>
            </div>
          </div>
        </div>
      </div>

      {showSubmissionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" role="presentation">
          <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-800" role="dialog" aria-modal="true" aria-labelledby="submission-confirm-title">
            <div>
              <h2 id="submission-confirm-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">Officer confirmation required</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                This will open the configured official portal. DRISHTI will not submit the complaint. Review all information again before completing submission on the portal.
              </p>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setShowSubmissionModal(false)}
                className="min-h-12 rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
              >
                Go back
              </button>
              <button
                type="button"
                onClick={handleConfirmedPortalHandoff}
                className="min-h-12 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
              >
                Confirm and open official portal
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default PrepareCase;
