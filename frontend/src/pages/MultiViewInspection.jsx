import { useState, useEffect, useRef } from 'react';
import {
  Camera, CheckCircle2, AlertCircle, RefreshCw, Layers,
  ChevronDown, ChevronRight, HelpCircle, Lock, FileText, Download,
  CheckSquare, AlertTriangle, ShieldCheck, ArrowLeft, WifiOff
} from 'lucide-react';
import {
  startInspection, uploadCapture, getActivePlan, updateInspectionContext,
  finalizeInspection, downloadReportPdf, downloadReportDocx, getInspection,
  getCaptureImage, confirmPackageInformation, correctDeclaration
} from '../services/api';
import {
  listPendingCaptures,
  removePendingCapture,
  savePendingCapture,
} from '../services/pendingCaptureStore';
import EvidenceImageViewer from '../components/ocr/EvidenceImageViewer';
import EvidenceInspectorPanel, { PackagePresentationChecks } from '../components/ocr/EvidenceInspectorPanel';
import DetectedPackageContextCard from '../components/inspection/DetectedPackageContextCard';
import OfficerResultSummary from '../components/inspection/OfficerResultSummary';
import PackageInformationCard from '../components/inspection/PackageInformationCard';
import DeclarationCorrectionModal from '../components/inspection/DeclarationCorrectionModal';

const LIFECYCLE_BADGES = {
  DRAFT: { label: 'New inspection', bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-700 dark:text-slate-300', border: 'border-slate-300 dark:border-slate-700' },
  IN_PROGRESS: { label: 'Inspection in progress', bg: 'bg-indigo-50 dark:bg-indigo-950/40', text: 'text-indigo-700 dark:text-indigo-300', border: 'border-indigo-200 dark:border-indigo-800' },
  READY_FOR_REVIEW: { label: 'Ready for review', bg: 'bg-amber-50 dark:bg-amber-950/40', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-200 dark:border-amber-800' },
  FINALIZED: { label: 'Inspection finalized', bg: 'bg-emerald-50 dark:bg-emerald-950/40', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800' }
};
const translateEnum = (val) => {
  if (!val) return '—';
  const mapping = {
    GENERIC_RETAIL_PACKAGE: 'Standard Retail Package',
    FOOD: 'Food Product (FSSAI Regime)',
    NON_FOOD: 'Non-Food Retail Product',
    COSMETIC: 'Cosmetic Product',
    DRUG: 'Drug / Medical Product',
    CERTIFIED_SEED: 'Certified Agricultural Seed',
    DRAFT: 'New Inspection',
    IN_PROGRESS: 'In Progress',
    READY_FOR_REVIEW: 'Ready for Review',
    FINALIZED: 'Finalized',
    VIOLATIONS_FOUND: 'Violations Detected',
    REVIEW_REQUIRED: 'Review Required',
    NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE: 'No Violations Detected',
    INCOMPLETE_INSPECTION: 'Incomplete Evidence',
    SUFFICIENT_FOR_ABSENCE_EVALUATION: 'Complete Evidence Captured',
    INSUFFICIENT_FOR_ABSENCE_EVALUATION: 'Incomplete Evidence (Absence Checks Deferred)',
    COMPLETE_EVIDENCE_CAPTURE: 'Complete Evidence Set',
    INCOMPLETE_EVIDENCE_CAPTURE: 'Incomplete Evidence Set',
    DOMESTIC: 'Domestic (Manufactured in India)',
    IMPORTED: 'Imported Commodity',
    ELECTRONIC: 'Electronic Product',
    NON_ELECTRONIC: 'Non-Electronic Product',
    UNKNOWN: 'Unspecified / Unknown',
    OBSERVATION_CLEAR: 'Observation Clear',
    PASS: 'Complies',
    FAIL: 'Possible Violation',
    NOT_APPLICABLE: 'Not Applicable',
    plan_software_1: 'Standard Retail Inspection Plan'
  };
  return mapping[val] || val.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

const getOfficerError = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && !/schema|json|ocr|gemini|database|sql|api/i.test(detail)) {
    return detail;
  }
  return fallback;
};

const MultiViewInspection = ({
  initialInspectionId = null,
  onBackToHistory = null,
  onPrepareCase = null,
  onInspectionStarted = null,
}) => {
  const [activePlan, setActivePlan] = useState(null);
  const [session, setSession] = useState(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [contextUpdating, setContextUpdating] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [showFinalizeModal, setShowFinalizeModal] = useState(false);
  const [reportApproved, setReportApproved] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);
  const [correctionItem, setCorrectionItem] = useState(null);
  const [correctionSaving, setCorrectionSaving] = useState(false);
  const [correctionError, setCorrectionError] = useState('');
  const [pendingUploads, setPendingUploads] = useState({});
  const [pendingStorageWarning, setPendingStorageWarning] = useState('');
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [guidance, setGuidance] = useState('');
  
  // Visual Evidence Traceability State
  const [imageUrls, setImageUrls] = useState({});
  const [imageLoadStates, setImageLoadStates] = useState({});
  const imageUrlsRef = useRef({});
  const [activeViewId, setActiveViewId] = useState('FRONT');
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState([]);
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [selectedFieldName, setSelectedFieldName] = useState(null);
  
  const [formData, setFormData] = useState({
    reference_date: new Date().toISOString().split('T')[0],
    product_category: 'GENERIC_RETAIL_PACKAGE',
    capture_plan_id: 'plan_software_1',
    product_origin: 'UNKNOWN',
    regulatory_product_class: 'UNKNOWN',
    date_regulatory_regime: 'UNKNOWN',
    date_package_exemption: 'UNKNOWN',
    is_electronic: 'UNKNOWN',
    package_structure: 'UNKNOWN',
    alcohol_context: 'UNKNOWN'
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadingView, setUploadingView] = useState(null);
  const hasUnsafePendingCapture = Object.values(pendingUploads).some(
    (item) => item.persisted === false,
  );

  const rememberImageUrl = (captureId, viewId, blob) => {
    const objectUrl = URL.createObjectURL(blob);
    setImageUrls((current) => {
      const previous = current[captureId];
      if (previous && previous !== objectUrl && previous.startsWith('blob:')) {
        URL.revokeObjectURL(previous);
      }
      const next = { ...current, [captureId]: objectUrl };
      if (viewId) next[viewId] = objectUrl;
      imageUrlsRef.current = next;
      return next;
    });
    return objectUrl;
  };

  const loadStoredCaptureImage = async (inspectionId, capture) => {
    setImageLoadStates((current) => ({ ...current, [capture.capture_id]: 'loading' }));
    try {
      const blob = await getCaptureImage(inspectionId, capture.capture_id);
      rememberImageUrl(capture.capture_id, capture.view_id, blob);
      setImageLoadStates((current) => ({ ...current, [capture.capture_id]: 'loaded' }));
    } catch {
      setImageLoadStates((current) => ({ ...current, [capture.capture_id]: 'unavailable' }));
    }
  };

  const restorePendingUploads = async (inspectionId) => {
    try {
      const records = await listPendingCaptures(inspectionId);
      const restored = {};
      const restoredImageUrls = {};
      records.forEach((record) => {
        const localUrl = URL.createObjectURL(record.file);
        restored[record.viewId] = { file: record.file, localUrl, persisted: true };
        restoredImageUrls[record.viewId] = localUrl;
      });
      setPendingUploads(restored);
      setImageUrls((current) => {
        const next = { ...current, ...restoredImageUrls };
        imageUrlsRef.current = next;
        return next;
      });
      if (records.length > 0) {
        setError(`${records.length} photograph${records.length === 1 ? '' : 's'} waiting to upload. Reconnect and retry.`);
      }
    } catch {
      setPendingStorageWarning('This device cannot preserve waiting photographs after the app closes. Keep this screen open or retake them later.');
    }
  };

  const queuePendingUpload = async (inspectionId, viewId, file, localUrl) => {
    const alreadyPersisted = pendingUploads[viewId]?.persisted === true;
    setPendingUploads((current) => ({
      ...current,
      [viewId]: { file, localUrl, persisted: alreadyPersisted },
    }));
    if (alreadyPersisted) return true;

    try {
      await savePendingCapture(inspectionId, viewId, file);
      setPendingUploads((current) => ({
        ...current,
        [viewId]: { file, localUrl, persisted: true },
      }));
      setPendingStorageWarning('');
      return true;
    } catch {
      setPendingStorageWarning('This waiting photograph will be lost if the app or browser is closed. Keep this screen open or retake it later.');
      return false;
    }
  };

  useEffect(() => {
    // Fetch the active prototype plan on mount
    getActivePlan().then(setActivePlan).catch(console.error);
  }, []);

  useEffect(() => () => {
    new Set(Object.values(imageUrlsRef.current)).forEach((url) => {
      if (url?.startsWith?.('blob:')) URL.revokeObjectURL(url);
    });
  }, []);

  useEffect(() => {
    if (!hasUnsafePendingCapture) return undefined;
    const warnBeforeLeaving = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeLeaving);
    return () => window.removeEventListener('beforeunload', warnBeforeLeaving);
  }, [hasUnsafePendingCapture]);

  useEffect(() => {
    const markOnline = () => setIsOnline(true);
    const markOffline = () => setIsOnline(false);
    window.addEventListener('online', markOnline);
    window.addEventListener('offline', markOffline);
    return () => {
      window.removeEventListener('online', markOnline);
      window.removeEventListener('offline', markOffline);
    };
  }, []);

  useEffect(() => {
    if (initialInspectionId) {
      setLoading(true);
      setError('');
      getInspection(initialInspectionId)
        .then((data) => {
          setSession(data);
          setLastSavedAt(new Date());
          data.captures?.forEach((capture) => loadStoredCaptureImage(data.inspection_id, capture));
          restorePendingUploads(data.inspection_id);
        })
        .catch((err) => {
          setError(getOfficerError(err, 'Could not load this inspection. Check the connection and try again.'));
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setSession(null);
      setPendingUploads({});
    }
  }, [initialInspectionId]);

  const handleStart = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const result = await startInspection(formData);
      setSession(result);
      setLastSavedAt(new Date());
      onInspectionStarted?.(result.inspection_id);
    } catch (err) {
      setError(getOfficerError(err, 'Could not start the inspection. Check the connection and try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (viewId, file) => {
    if (!file) return;
    if (session?.lifecycle_status === 'FINALIZED') {
      setError('This inspection has been finalized and its photographs are locked.');
      return;
    }
    const localUrl = rememberImageUrl(`pending-${viewId}`, viewId, file);
    setGuidance('');
    const persisted = await queuePendingUpload(
      session.inspection_id,
      viewId,
      file,
      localUrl,
    );

    if (!navigator.onLine) {
      setError(persisted
        ? 'No connection. The photograph is waiting safely on this device. Reconnect and tap “Retry photograph.”'
        : 'No connection. Keep this screen open and tap “Retry photograph” after reconnecting.');
      return;
    }

    setUploadingView(viewId);
    setError('');
    try {
      const result = await uploadCapture(session.inspection_id, viewId, file);
      
      const newCapture = result.captures?.filter(c => c.view_id === viewId).slice(-1)[0];
      if (newCapture) {
        setImageUrls((current) => {
          const next = { ...current, [viewId]: localUrl, [newCapture.capture_id]: localUrl };
          imageUrlsRef.current = next;
          return next;
        });
        setImageLoadStates((current) => ({ ...current, [newCapture.capture_id]: 'loaded' }));
      }
      
      setActiveViewId(viewId);
      setSession(result);
      setPendingUploads((current) => {
        const next = { ...current };
        delete next[viewId];
        return next;
      });
      try {
        await removePendingCapture(session.inspection_id, viewId);
      } catch {
        setPendingStorageWarning('The photograph is saved to the inspection, but its temporary device copy could not be cleared.');
      }
      setLastSavedAt(new Date());
    } catch (err) {
      setError(getOfficerError(
        err,
        persisted
          ? 'The photograph is waiting safely on this device. Check the connection and tap “Retry photograph.”'
          : 'The photograph could not be saved. Keep this screen open and retry.',
      ));
    } finally {
      setUploadingView(null);
    }
  };

  const handleRetryUpload = (viewId) => {
    const pending = pendingUploads[viewId];
    if (pending) handleUpload(viewId, pending.file);
  };

  const handleFileSelection = (viewId, event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) handleUpload(viewId, file);
  };

  const handleSelectEvidence = (evidenceIds, captureId, viewId, finding = null, fieldName = null) => {
    setSelectedEvidenceIds(evidenceIds || []);
    setSelectedFinding(finding);
    setSelectedFieldName(fieldName);
    if (viewId) {
      setActiveViewId(viewId);
    }
  };

  const handleUpdateContext = async (updates) => {
    if (session?.lifecycle_status === 'FINALIZED') {
      setError('This inspection has been finalized and its confirmed details are locked.');
      return;
    }
    setContextUpdating(true);
    setError('');
    try {
      const result = await updateInspectionContext(session.inspection_id, updates);
      setSession(result);
      setLastSavedAt(new Date());
    } catch (err) {
      setError(getOfficerError(err, 'Could not save the confirmed details. Check the connection and try again.'));
    } finally {
      setContextUpdating(false);
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setError('');
    try {
      const result = await finalizeInspection(session.inspection_id);
      setSession(result);
      setShowFinalizeModal(false);
      setReportApproved(false);
      setGuidance('');
      setLastSavedAt(new Date());
    } catch (err) {
      setError(getOfficerError(err, 'Could not finalize the report. Review the inspection and try again.'));
    } finally {
      setFinalizing(false);
    }
  };

  const handleConfirmPackageInformation = async () => {
    setReviewSaving(true);
    setError('');
    try {
      const result = await confirmPackageInformation(session.inspection_id);
      setSession(result);
      setLastSavedAt(new Date());
    } catch (err) {
      setError(getOfficerError(err, 'Could not save your confirmation. Check the connection and try again.'));
    } finally {
      setReviewSaving(false);
    }
  };

  const handleCorrectCandidate = (candidate, index) => {
    const captureId = candidate.capture_ids?.[0];
    const capture = session.captures?.find((item) => item.capture_id === captureId);
    const viewId = capture?.view_id || activeViewId;
    setActiveViewId(viewId);
    setCorrectionError('');
    const producingOverride = [...(session.officer_declaration_overrides || [])]
      .reverse()
      .find((override) => (
        override.field === candidate.field
        && override.confirmed_candidate?.raw_value === candidate.raw_value
      ));
    setCorrectionItem({
      candidate,
      originalCandidate: producingOverride?.observed_candidate || candidate,
      index,
    });
  };

  const handleSubmitCorrection = async (correction) => {
    setCorrectionSaving(true);
    setCorrectionError('');
    try {
      const result = await correctDeclaration(session.inspection_id, correction);
      setSession(result);
      setReportApproved(false);
      setCorrectionItem(null);
      setLastSavedAt(new Date());
      setGuidance('Correction saved. Please review the updated package information and assessment.');
    } catch (err) {
      setCorrectionError(getOfficerError(err, 'Could not save this correction. Check the visible value and try again.'));
    } finally {
      setCorrectionSaving(false);
    }
  };

  if (!session) {
    return (
      <div className="max-w-2xl mx-auto py-8 px-4 space-y-4">
        {onBackToHistory && (
          <button
            onClick={onBackToHistory}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to History
          </button>
        )}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-3 mb-6 border-b border-slate-100 dark:border-slate-700 pb-4">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg">
              <Layers size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Start inspection</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                Enter the inspection date, then photograph the package sides requested on the next screen.
              </p>
            </div>
          </div>
          
          {error && (
            <div className="mb-6 p-4 bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 rounded-lg flex items-start gap-3 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <form onSubmit={handleStart} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Reference Date</label>
              <input
                type="date"
                required
                value={formData.reference_date}
                onChange={(e) => setFormData({...formData, reference_date: e.target.value})}
                className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:text-slate-200"
              />
            </div>
            <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
              <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-300">View inspection setup</summary>
              <p className="mt-2 text-xs text-slate-500">Standard packaged commodity inspection • Requested views are selected automatically.</p>
            </details>
            
            <button
              type="submit"
              disabled={loading}
              className="mt-6 flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-base font-bold text-white transition-colors hover:bg-indigo-700"
            >
              {loading ? <RefreshCw className="animate-spin w-5 h-5" /> : 'Start Inspection'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- Session Active State ---
  const requiredViews = activePlan?.views.filter(v => v.required) || [];
  const capturedRequiredViews = session.captures.filter(c => 
    requiredViews.some(rv => rv.view_id === c.view_id)
  );
  const uniqueCapturedRequired = new Set(capturedRequiredViews.map(c => c.view_id)).size;

  const isFinalized = session.lifecycle_status === 'FINALIZED';
  const hasCaptures = session.captures && session.captures.length > 0;
  const hasAnalysis = session.rule_evaluations && session.rule_evaluations.length > 0;
  const canFinalize = !isFinalized && hasCaptures && hasAnalysis;
  const packageInfoReviewed = Boolean(session.package_information_review);
  const pendingUploadCount = Object.keys(pendingUploads).length;
  const allPendingPersisted = pendingUploadCount > 0
    && Object.values(pendingUploads).every((item) => item.persisted);
  const detectedContextDismissed = session.dismissed_clarifications?.includes('DETECTED_PACKAGE_CONTEXT');
  const needsDetectedContextConfirmation = Boolean(
    !isFinalized
    && !detectedContextDismissed
    && session.detected_package_context?.ready_for_confirmation
    && session.detected_package_context.suggestions?.some(
      (item) => !session[item.field] || session[item.field] === 'UNKNOWN',
    )
  );

  const currentBadge = LIFECYCLE_BADGES[session.lifecycle_status] || LIFECYCLE_BADGES.IN_PROGRESS;
  const hasNonCompliance = Boolean(
    session.rule_evaluations?.some((result) => result.status === 'FAIL')
    || session.food_label_evaluations?.some((result) => result.status === 'FAIL')
    || session.visual_rule_evaluations?.some((result) => result.status === 'FAIL'),
  );
  const readyToReviewReport = canFinalize && packageInfoReviewed && !needsDetectedContextConfirmation;

  // Process Progress Steps
  const steps = [
    { id: 'start', label: 'Started', done: true, active: false },
    { id: 'photos', label: 'Photographs', done: session.capture_status === 'COMPLETE_EVIDENCE_CAPTURE', active: session.capture_status !== 'COMPLETE_EVIDENCE_CAPTURE' },
    { id: 'confirm', label: 'Confirm details', done: packageInfoReviewed && !needsDetectedContextConfirmation, active: hasCaptures && (!packageInfoReviewed || needsDetectedContextConfirmation) },
    { id: 'assessment', label: 'Assessment', done: hasAnalysis, active: hasCaptures && !hasAnalysis },
    { id: 'report', label: 'Report', done: isFinalized, active: readyToReviewReport },
    { id: 'complaint', label: 'Complaint', done: isFinalized && !hasNonCompliance, active: isFinalized && hasNonCompliance },
  ];

  // Statutory Findings Counts
  const statutoryFindings = [
    ...(session.rule_evaluations || []),
    ...(session.food_label_evaluations || []),
  ];
  const passCount = statutoryFindings.filter(r => r.status === 'PASS').length;
  const failCount = statutoryFindings.filter(r => r.status === 'FAIL').length;
  const reviewCount = statutoryFindings.filter(r => r.status === 'REVIEW_REQUIRED').length;
  const notApplicableCount = statutoryFindings.filter(r => r.status === 'NOT_APPLICABLE').length;
  const visualReviewCount = (session.visual_rule_evaluations || []).filter((result) => (
    result.status === 'REVIEW_REQUIRED'
    || result.status === 'NEEDS_RECAPTURE'
    || result.status === 'NOT_EVALUABLE'
  )).length;
  const advisoryReviewCount = reviewCount + visualReviewCount;
  const firstPendingViewId = Object.keys(pendingUploads)[0] || null;
  const scrollToWorkflowSection = (sectionId) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const openFinalizeDialog = () => {
    setReportApproved(false);
    setShowFinalizeModal(true);
  };
  return (
    <main className="portal-page space-y-6 py-6 pb-40 lg:pb-8">
      
      {/* Top Inspector Journey Workflow Header */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded-lg">
              <ShieldCheck size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  Inspection Record
                </h1>
                <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${currentBadge.bg} ${currentBadge.text} ${currentBadge.border} flex items-center gap-1`}>
                  {isFinalized && <Lock size={12} />}
                  {currentBadge.label}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Inspection date: {session.reference_date}{session.regulatory_product_class && session.regulatory_product_class !== 'UNKNOWN' ? ` • ${translateEnum(session.regulatory_product_class)}` : ''}
              </p>
            </div>
          </div>

          {/* Action Area: Back to History, Finalize Button or Report Download Group */}
          <div className="flex flex-wrap items-center gap-2">
            {onBackToHistory && (
              <button
                onClick={onBackToHistory}
                className="flex min-h-11 items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
              >
                <ArrowLeft size={14} /> Back to History
              </button>
            )}
            {isFinalized ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={async () => {
                    try {
                      await downloadReportPdf(session.inspection_id);
                    } catch (err) {
                      console.error('Failed to download PDF report', err);
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  <Download size={14} /> Download PDF report
                </button>
                <button
                  onClick={async () => {
                    try {
                      await downloadReportDocx(session.inspection_id);
                    } catch (err) {
                      console.error('Failed to download DOCX report', err);
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                >
                  <FileText size={14} /> Download Word report
                </button>
              </div>
            ) : canFinalize ? (
              <button
                onClick={openFinalizeDialog}
                disabled={!readyToReviewReport}
                title={!packageInfoReviewed ? 'Confirm the detected package information first' : undefined}
                className="flex min-h-12 items-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <CheckSquare size={18} /> Review and finalize report
              </button>
            ) : null}
          </div>
        </div>

        {/* Process Progress Indicator */}
        <div className="flex gap-2 overflow-x-auto border-t border-slate-100 pt-4 text-xs dark:border-slate-700/60 sm:grid sm:grid-cols-6">
          {steps.map((st) => (
            <div
              key={st.id}
              className={`min-w-28 p-2.5 rounded-lg border flex items-center gap-2 transition-all duration-300 ${
                st.done
                  ? 'border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/15 text-emerald-700 dark:text-emerald-300 font-medium'
                  : st.active
                  ? 'border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300 font-semibold shadow-sm ring-1 ring-indigo-500/20'
                  : 'border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 bg-slate-50/40 dark:bg-slate-900/10'
              }`}
            >
              {st.done ? (
                <CheckCircle2 size={14} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
              ) : (
                <div className={`w-3 h-3 rounded-full border shrink-0 transition-colors duration-300 ${st.active ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300 dark:border-slate-600'}`} />
              )}
              <span className="truncate tracking-wide">{st.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Finalized Actions Panel */}
      {isFinalized && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200/85 dark:border-slate-700/85 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-105 dark:border-slate-700 pb-3">
            <Lock size={16} className="text-emerald-600 dark:text-emerald-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-50">
              Finalized inspection
            </h3>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-700 dark:bg-slate-900/20">
              <div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Inspection report
                </h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  Download the report approved and finalized by the officer.
                </p>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <button
                  onClick={async () => {
                    try { await downloadReportPdf(session.inspection_id); } catch (err) { console.error(err); }
                  }}
                  className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
                >
                  <Download size={18} /> Download PDF
                </button>
                <button
                  onClick={async () => {
                    try { await downloadReportDocx(session.inspection_id); } catch (err) { console.error(err); }
                  }}
                  className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
                >
                  <FileText size={18} /> Download Word
                </button>
              </div>
            </div>

            <div className={`flex flex-col justify-between rounded-xl border p-4 ${hasNonCompliance ? 'border-rose-200 bg-rose-50/50 dark:border-rose-800 dark:bg-rose-950/15' : 'border-slate-200 bg-slate-50/60 dark:border-slate-700 dark:bg-slate-900/20'}`}>
              <div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  {hasNonCompliance ? 'Prepare complaint' : 'Complaint not required'}
                </h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {hasNonCompliance
                    ? 'Review the reasons, edit the complaint draft, and prepare the evidence package. Nothing is submitted without officer confirmation.'
                    : advisoryReviewCount > 0
                      ? 'No confirmed non-compliance finding. No complaint has been generated. Documented officer-review or physical-verification limitations remain in the inspection record.'
                      : 'The finalized assessment does not contain a non-compliance finding.'}
                </p>
              </div>
              <div className="mt-4">
                {hasNonCompliance ? (
                  <button
                    onClick={() => onPrepareCase && onPrepareCase(session.inspection_id)}
                    className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-3 text-sm font-bold text-white shadow-sm hover:bg-rose-700"
                  >
                    <FileText size={18} /> Prepare complaint
                  </button>
                ) : (
                  <p className="rounded-lg bg-white/70 p-3 text-sm text-slate-500 dark:bg-slate-900/30 dark:text-slate-400">No external action is suggested.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {!isOnline && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-300" role="status">
          <WifiOff className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="font-bold">No connection</p>
            <p className="mt-1">The saved inspection remains available. Waiting photographs can be uploaded after reconnecting.</p>
          </div>
        </div>
      )}

      {pendingUploadCount > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-300" role="status">
          <p className="font-bold">{pendingUploadCount} photograph{pendingUploadCount === 1 ? '' : 's'} waiting to upload</p>
          <p className="mt-1">
            {allPendingPersisted
              ? 'Kept on this device until the inspection service confirms they are saved.'
              : 'Keep this screen open. At least one waiting photograph could not be preserved after closing.'}
          </p>
        </div>
      )}

      {pendingStorageWarning && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-950/25 dark:text-rose-300" role="alert">
          {pendingStorageWarning}
        </div>
      )}

      {lastSavedAt && isOnline && !isFinalized && (
        <p className="text-right text-xs font-medium text-slate-500 dark:text-slate-400" role="status">
          Inspection saved • {lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      )}

      {guidance && !isFinalized && (
        <div className="flex items-start gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/25 dark:text-indigo-300">
          <Camera className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{guidance}</p>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 rounded-xl border border-rose-200 dark:border-rose-800 flex items-start gap-3 text-xs">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Main Two-Column Workflow Workspace */}
      <div id="package-photo-section" className="inspection-workspace-grid">
        
        {/* Desktop left column: package photographs, legal assessment and officer context */}
        <div className="inspection-workspace-column">
          <div className="workspace-photographs space-y-6">
          {/* Interactive Evidence Image Viewer with Responsive SVG Overlay */}
          <EvidenceImageViewer
            views={activePlan?.views || []}
            captures={session.captures || []}
            activeViewId={activeViewId}
            onSelectView={setActiveViewId}
            selectedEvidenceIds={selectedEvidenceIds}
            selectedFinding={selectedFinding}
            selectedFieldName={selectedFieldName}
            imageUrls={imageUrls}
            imageLoadStates={imageLoadStates}
            onRetryImage={(capture) => loadStoredCaptureImage(session.inspection_id, capture)}
            onUploadCapture={handleUpload}
            isUploading={uploadingView !== null}
            onSelectEvidence={handleSelectEvidence}
          />

          {/* Capture Stepper & Progress */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Photograph package sides</h2>
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {uniqueCapturedRequired} of {requiredViews.length} requested sides photographed
              </div>
            </div>

            {session.capture_status !== 'COMPLETE_EVIDENCE_CAPTURE' && (
              <div className="mb-4 p-3.5 bg-amber-50 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-lg text-xs leading-relaxed flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Camera className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Photograph the requested sides. Information that cannot be read clearly will be sent for officer review, not treated as missing.</span>
                </div>
                {requiredViews.find(v => !session.captures.some(c => c.view_id === v.view_id)) && (
                  <button
                    type="button"
                    onClick={() => {
                      const nextMissing = requiredViews.find(v => !session.captures.some(c => c.view_id === v.view_id));
                      if (nextMissing) setActiveViewId(nextMissing.view_id);
                    }}
                    className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded text-[11px] shrink-0 cursor-pointer shadow-sm"
                  >
                    Photograph {requiredViews.find(v => !session.captures.some(c => c.view_id === v.view_id))?.display_name}
                  </button>
                )}
              </div>
            )}
            
            {/* Progress Bar */}
            <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2 mb-6">
              <div 
                className={`h-2 rounded-full transition-all duration-300 ${session.capture_status === 'COMPLETE_EVIDENCE_CAPTURE' ? 'bg-emerald-500' : 'bg-indigo-600'}`} 
                style={{ width: `${(uniqueCapturedRequired / Math.max(1, requiredViews.length)) * 100}%` }}
              ></div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {activePlan?.views.map(view => {
                const capturesForView = session.captures.filter(c => c.view_id === view.view_id);
                const latestCapture = capturesForView[capturesForView.length - 1];
                const isCurrentActive = view.view_id === activeViewId;
                
                return (
                  <div
                    key={view.view_id}
                    onClick={() => setActiveViewId(view.view_id)}
                    className={`border rounded-xl p-3.5 cursor-pointer transition-all ${
                      isCurrentActive
                        ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-indigo-50/20 dark:bg-indigo-950/20'
                        : latestCapture
                        ? 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/30'
                        : 'border-dashed border-slate-300 dark:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        {latestCapture ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-slate-300 dark:border-slate-600 border-dashed shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs text-slate-800 dark:text-slate-200 truncate">{view.display_name}</span>
                            {!view.required && <span className="text-[10px] bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.2 rounded-full">Opt</span>}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        {pendingUploads[view.view_id] && (
                          <button
                            type="button"
                            onClick={() => handleRetryUpload(view.view_id)}
                            disabled={!isOnline || uploadingView === view.view_id}
                            className="min-h-10 rounded-lg bg-amber-600 px-3 py-2 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-50"
                          >
                            Retry photograph
                          </button>
                        )}
                        {isFinalized ? (
                          <span className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-800 rounded-lg">
                            {latestCapture ? <><Lock size={12} /> Captured · Locked</> : 'Not captured'}
                          </span>
                        ) : (
                          <label className={`flex min-h-10 cursor-pointer items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${latestCapture ? 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-200' : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}>
                            {uploadingView === view.view_id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : latestCapture ? (
                              <><Camera className="w-3.5 h-3.5" /> Take again</>
                            ) : (
                              <><Camera className="w-3.5 h-3.5" /> Take photo</>
                            )}
                            <input
                              type="file"
                              accept="image/*"
                              capture="environment"
                              className="hidden"
                              onChange={(event) => handleFileSelection(view.view_id, event)}
                              disabled={uploadingView === view.view_id || isFinalized}
                            />
                          </label>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          </div>
          <div className="workspace-assessment space-y-6">
            {hasAnalysis && <OfficerResultSummary session={session} />}

            {/* Inspection Analysis Header & Clarification Box */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5">
              <div className="flex items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg">
                    <Layers size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">Legal assessment</h2>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {statutoryFindings.length} statutory requirements checked
                      {(session.active_clarification || needsDetectedContextConfirmation) && (
                        <span className="text-amber-600 dark:text-amber-400 font-medium"> • Officer confirmation required</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Categorical findings badge counters */}
                {hasAnalysis && (
                  <div className="flex flex-wrap items-center justify-end gap-1 text-[11px] font-semibold">
                    <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 rounded">
                      {passCount} Compliant
                    </span>
                    <span className="px-1.5 py-0.5 bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 rounded">
                      {failCount} Non-compliant
                    </span>
                    <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 rounded">
                      {reviewCount} Review
                    </span>
                    <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 rounded">
                      {notApplicableCount} Not applicable
                    </span>
                  </div>
                )}
              </div>
              
              {needsDetectedContextConfirmation ? (
                <DetectedPackageContextCard
                  session={session}
                  disabled={isFinalized}
                  saving={contextUpdating}
                  onSave={handleUpdateContext}
                />
              ) : session.active_clarification && !isFinalized ? (
                <div className="mt-3 p-3.5 bg-indigo-50/50 border border-indigo-200 dark:bg-indigo-950/30 dark:border-indigo-800/60 rounded-xl space-y-2.5">
                  <div className="flex items-start gap-2">
                    <div className="p-1 bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 rounded-lg shrink-0 mt-0.5">
                      <HelpCircle className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                         Officer confirmation required: {session.active_clarification.title}
                      </h3>
                      {session.active_clarification.description && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                          {session.active_clarification.description}
                        </p>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {session.active_clarification.options.map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() => handleUpdateContext(opt.context_updates)}
                        disabled={contextUpdating || isFinalized}
                        className={`px-3 py-1 text-xs font-medium rounded-lg border transition-all ${
                          opt.id === 'NOT_SURE'
                            ? 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700'
                            : 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 border-indigo-300 dark:border-indigo-700/80 hover:bg-indigo-600 hover:text-white dark:hover:bg-indigo-600 dark:hover:text-white shadow-sm'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : session.required_context?.length > 0 && !isFinalized ? (
                <div className="mt-3 p-2.5 bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 rounded-lg text-[11px] text-slate-500 dark:text-slate-400">
                    Take the remaining photographs or use “View additional context” if an officer correction is required.
                </div>
              ) : null}
              
              <div className="mt-4 border-t border-slate-100 dark:border-slate-700 pt-3">
                <button 
                  onClick={() => setAdvancedOpen(!advancedOpen)}
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                >
                  {advancedOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  Inspection context {isFinalized && '(Read-only)'}
                </button>
                
                {advancedOpen && (isFinalized ? (
                  <div className="mt-3 space-y-3">
                  <h3 className="text-sm font-bold text-slate-900">Inspection context</h3>
                  <dl className="mt-3 grid grid-cols-1 gap-px overflow-hidden border border-slate-200 bg-slate-200 text-xs sm:grid-cols-2">
                    {[
                      ['Officer-provided product origin classification', session.product_origin],
                      ['Regulatory category', session.regulatory_product_class],
                      ['Date regulatory regime', session.date_regulatory_regime],
                      ['Date exemption context', session.date_package_exemption],
                      ['Electronic status', session.is_electronic],
                      ['Package structure', session.package_structure],
                      ['Alcohol context', session.alcohol_context],
                    ].map(([label, value]) => (
                      <div key={label} className="bg-white p-3">
                        <dt className="text-[11px] font-semibold text-slate-500">{label}</dt>
                        <dd className="mt-1 font-bold text-slate-900">{translateEnum(value || 'UNKNOWN')}</dd>
                      </div>
                    ))}
                  </dl>
                  {session.package_information_review && (
                    <p className="text-xs text-slate-600">
                      Confirmed by <strong>{session.package_information_review.reviewed_by_username}</strong>
                      {session.package_information_review.reviewed_at
                        ? ` on ${new Date(session.package_information_review.reviewed_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`
                        : ''}. Finalized package record is immutable.
                    </p>
                  )}
                  </div>
                ) : (
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-50 dark:bg-slate-900/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700 text-xs">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Officer-provided Product Origin Classification</label>
                      <select 
                        value={session.product_origin} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ product_origin: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="DOMESTIC">Domestic Product</option>
                        <option value="IMPORTED">Imported Product</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Regulatory Category</label>
                      <select 
                        value={session.regulatory_product_class} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ regulatory_product_class: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="FOOD">Food Product</option>
                        <option value="NON_FOOD">Non-Food Product</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Date Regulatory Regime</label>
                      <select 
                        value={session.date_regulatory_regime} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ date_regulatory_regime: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="GENERAL">General</option>
                        <option value="FOOD">Food</option>
                        <option value="CERTIFIED_SEED">Certified Seed</option>
                        <option value="COSMETIC">Cosmetic</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Date Exemption Context</label>
                      <select 
                        value={session.date_package_exemption} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ date_package_exemption: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="NONE">None</option>
                        <option value="BIDI_OR_INCENSE">Bidi or Incense</option>
                        <option value="PSU_DOMESTIC_LPG_14_2_OR_5KG">PSU Domestic LPG (14.2kg or 5kg)</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Is Electronic</label>
                      <select 
                        value={session.is_electronic} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ is_electronic: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="ELECTRONIC">Electronic</option>
                        <option value="NON_ELECTRONIC">Non-Electronic</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Package Structure</label>
                      <select 
                        value={session.package_structure} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ package_structure: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="SINGLE">Single Package</option>
                        <option value="COMBINATION">Combination Package</option>
                        <option value="GROUP">Group Package</option>
                        <option value="MULTI_PIECE">Multi-Piece Package</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-500 mb-1">Alcohol Context</label>
                      <select 
                        value={session.alcohol_context} 
                        disabled={isFinalized}
                        onChange={(e) => handleUpdateContext({ alcohol_context: e.target.value })}
                        className="w-full px-2 py-1 bg-white dark:bg-slate-800 border rounded text-xs disabled:opacity-60"
                      >
                        <option value="ALCOHOLIC">Alcoholic</option>
                        <option value="NON_ALCOHOLIC">Non-Alcoholic</option>
                        <option value="UNKNOWN">Not Specified (Unknown)</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Desktop right column: package information, evidence and technical details */}
        <div className="inspection-workspace-column">
          
          {hasAnalysis && (
            <div id="package-information-section" className="workspace-package-information scroll-mt-24">
              <PackageInformationCard
                session={session}
                review={session.package_information_review}
                savingReview={reviewSaving}
                onReviewed={handleConfirmPackageInformation}
                onCorrect={handleCorrectCandidate}
                isFinalized={isFinalized}
              />
            </div>
          )}

          {/* Optional advanced evidence and technical traceability */}
          <details className="workspace-details rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-3 px-5 py-4 text-sm font-bold text-slate-800 dark:text-slate-100">
              <span>View details</span>
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Evidence and technical checks</span>
            </summary>
            <div className="border-t border-slate-200 p-4 dark:border-slate-700">
              <EvidenceInspectorPanel
                ruleEvaluations={session.rule_evaluations || []}
                aggregatedCandidates={session.aggregated_candidates || []}
                captures={session.captures || []}
                onSelectEvidence={handleSelectEvidence}
                regulatoryProductClass={session.regulatory_product_class || 'UNKNOWN'}
                productOrigin={session.product_origin || 'UNKNOWN'}
                foodLabelEvaluations={session.food_label_evaluations || []}
                referenceDate={session.reference_date}
              />
            </div>
          </details>
        </div>
      </div>

      <PackagePresentationChecks visualRuleEvaluations={session.visual_rule_evaluations || []} />

      <div
        id="mobile-primary-action"
        className="fixed inset-x-0 bottom-[68px] z-30 border-t border-slate-200 bg-white/95 p-3 shadow-[0_-8px_24px_rgba(15,23,42,0.12)] backdrop-blur dark:border-slate-700 dark:bg-slate-900/95 lg:hidden"
        role="region"
        aria-label="Primary inspection action"
      >
        <div className="mx-auto max-w-2xl">
          {isFinalized ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  await downloadReportPdf(session.inspection_id);
                } catch (err) {
                  setError(getOfficerError(err, 'Could not download the finalized report. Please retry.'));
                }
              }}
              className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-base font-bold text-white"
            >
              <Download size={19} /> Download finalized report
            </button>
          ) : readyToReviewReport ? (
            <button
              type="button"
              onClick={openFinalizeDialog}
              className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-base font-bold text-white"
            >
              <CheckSquare size={19} /> Review and finalize report
            </button>
          ) : firstPendingViewId && isOnline ? (
            <button
              type="button"
              onClick={() => handleRetryUpload(firstPendingViewId)}
              disabled={uploadingView === firstPendingViewId}
              className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-3 text-base font-bold text-white disabled:opacity-60"
            >
              <RefreshCw className={uploadingView === firstPendingViewId ? 'animate-spin' : ''} size={19} /> Retry waiting photograph
            </button>
          ) : hasAnalysis && !packageInfoReviewed ? (
            <button
              type="button"
              onClick={() => scrollToWorkflowSection('package-information-section')}
              className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-base font-bold text-white"
            >
              <CheckCircle2 size={19} /> Review package information
            </button>
          ) : (
            <button
              type="button"
              onClick={() => scrollToWorkflowSection('package-photo-section')}
              className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-base font-bold text-white"
            >
              <Camera size={19} /> Continue photographs
            </button>
          )}
        </div>
      </div>

      {correctionItem && (
        <DeclarationCorrectionModal
          item={correctionItem}
          captures={session.captures || []}
          saving={correctionSaving}
          error={correctionError}
          onClose={() => {
            if (!correctionSaving) setCorrectionItem(null);
          }}
          onSubmit={handleSubmitCorrection}
        />
      )}

      {/* Finalization Modal */}
      {showFinalizeModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4" role="presentation">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200 dark:border-slate-700 space-y-4" role="dialog" aria-modal="true" aria-labelledby="finalize-report-title">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 rounded-lg">
                <CheckSquare size={22} />
              </div>
              <div>
                <h3 id="finalize-report-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Review and finalize inspection report
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Confirm that you reviewed the package information, findings, photographs, and legal requirements.
                </p>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-3.5 text-xs space-y-2 border border-slate-200 dark:border-slate-700">
              <div className="flex justify-between">
                <span className="text-slate-500">Legal requirements checked:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{session.rule_evaluations?.length || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Non-compliant findings:</span>
                <span className={`font-semibold ${failCount > 0 ? 'text-rose-600' : 'text-slate-700 dark:text-slate-300'}`}>
                  {failCount}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Documented review / technical items:</span>
                <span className={`font-semibold ${advisoryReviewCount > 0 ? 'text-amber-600' : 'text-slate-700 dark:text-slate-300'}`}>
                  {advisoryReviewCount}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Package photographs:</span>
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  {session.capture_status === 'COMPLETE_EVIDENCE_CAPTURE' ? 'Requested sides photographed' : 'Additional photographs needed'}
                </span>
              </div>
            </div>

            {failCount > 0 && (
              <div className="p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-lg text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
                <AlertTriangle size={16} className="shrink-0 mt-0.5 text-rose-600" />
                <p>
                  This inspection contains non-compliant findings. Finalizing will create a locked non-compliance report for officer review and follow-up.
                </p>
              </div>
            )}

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Once finalized, the inspection is locked. Photographs and confirmed details cannot be changed.
            </p>

            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-300 bg-slate-50 p-4 text-sm dark:border-slate-600 dark:bg-slate-900/40">
              <input
                type="checkbox"
                checked={reportApproved}
                onChange={(event) => setReportApproved(event.target.checked)}
                className="mt-0.5 h-5 w-5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <span className="font-medium text-slate-800 dark:text-slate-200">
                I have reviewed this inspection report and approve it for finalization.
              </span>
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setReportApproved(false);
                  setShowFinalizeModal(false);
                }}
                disabled={finalizing}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleFinalize}
                disabled={finalizing || !reportApproved}
                className="flex min-h-12 items-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {finalizing ? <RefreshCw size={14} className="animate-spin" /> : <CheckSquare size={14} />}
                Approve and finalize report
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default MultiViewInspection;
