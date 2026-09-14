import { AlertTriangle, CheckCircle2, CircleMinus, XCircle } from 'lucide-react';

const RESULT_STYLES = {
  COMPLIANT: {
    label: 'Compliant',
    icon: CheckCircle2,
    panel: 'border-emerald-200 bg-gradient-to-br from-white to-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/25',
    iconClass: 'text-emerald-700 dark:text-emerald-300',
    iconSurface: 'bg-emerald-100/80 ring-emerald-200',
  },
  NON_COMPLIANT: {
    label: 'Non-compliant',
    icon: XCircle,
    panel: 'border-rose-200 bg-gradient-to-br from-white to-rose-50/75 dark:border-rose-800 dark:bg-rose-950/25',
    iconClass: 'text-rose-700 dark:text-rose-300',
    iconSurface: 'bg-rose-100/80 ring-rose-200',
  },
  NEEDS_REVIEW: {
    label: 'Needs Officer Review',
    icon: AlertTriangle,
    panel: 'border-amber-200 bg-gradient-to-br from-white to-amber-50/80 dark:border-amber-800 dark:bg-amber-950/25',
    iconClass: 'text-amber-700 dark:text-amber-300',
    iconSurface: 'bg-amber-100/80 ring-amber-200',
  },
  FINALIZED_REVIEW: {
    label: 'Finalized with documented review items',
    icon: CheckCircle2,
    panel: 'border-[#bfd3e2] bg-gradient-to-br from-white to-[#eef6f8] dark:border-indigo-800 dark:bg-indigo-950/25',
    iconClass: 'text-[#087f83] dark:text-indigo-300',
    iconSurface: 'bg-[#e8f6f5] ring-[#bfd3e2]',
  },
  NOT_APPLICABLE: {
    label: 'Not Applicable',
    icon: CircleMinus,
    panel: 'border-slate-200 bg-gradient-to-br from-white to-slate-50 dark:border-slate-700 dark:bg-slate-900/40',
    iconClass: 'text-slate-600 dark:text-slate-300',
    iconSurface: 'bg-slate-100 ring-slate-200',
  },
};

const getOfficerResult = (session) => {
  const findings = [
    ...(session.rule_evaluations || []),
    ...(session.food_label_evaluations || []),
    ...(session.visual_rule_evaluations || []),
  ];
  const failCount = findings.filter((item) => item.status === 'FAIL').length;
  const reviewCount = findings.filter((item) => (
    item.status === 'REVIEW_REQUIRED'
    || item.status === 'NEEDS_RECAPTURE'
    || item.status === 'NOT_EVALUABLE'
  )).length;
  const passCount = findings.filter((item) => (
    item.status === 'PASS' || item.status === 'OBSERVATION_CLEAR'
  )).length;
  const applicableCount = findings.filter((item) => item.status !== 'NOT_APPLICABLE').length;
  const needsMorePhotos = session.capture_status !== 'COMPLETE_EVIDENCE_CAPTURE';
  const needsContext = Boolean(session.active_clarification || session.required_context?.length);
  const isFinalized = session.lifecycle_status === 'FINALIZED';

  if (session.overall_disposition === 'VIOLATIONS_FOUND' || failCount > 0) {
    return {
      key: 'NON_COMPLIANT',
      reason: `${failCount} applicable legal requirement${failCount === 1 ? '' : 's'} did not comply. Review each reason and its supporting photograph below.`,
    };
  }

  if (isFinalized && reviewCount > 0) {
    return {
      key: 'FINALIZED_REVIEW',
      reason: `${reviewCount} legal or presentation review item${reviewCount === 1 ? '' : 's'} remain documented in the finalized inspection record. They are not confirmed non-compliance findings.`,
    };
  }

  if (isFinalized) {
    return {
      key: 'COMPLIANT',
      reason: 'The officer finalized this inspection with no confirmed non-compliance finding in the evaluated scope.',
    };
  }

  if (
    session.overall_disposition === 'REVIEW_REQUIRED'
    || (!isFinalized && session.overall_disposition === 'INCOMPLETE_INSPECTION')
    || reviewCount > 0
    || needsMorePhotos
    || needsContext
  ) {
    return {
      key: 'NEEDS_REVIEW',
      reason: needsMorePhotos
        ? 'More or clearer package photographs are required. Unreadable information has not been treated as legally absent.'
        : `${reviewCount || 1} item${reviewCount === 1 ? '' : 's'} require officer confirmation before the assessment can be completed.`,
    };
  }

  if (findings.length > 0 && applicableCount === 0) {
    return {
      key: 'NOT_APPLICABLE',
      reason: 'The evaluated requirements do not apply to the confirmed package context.',
    };
  }

  if (
    session.overall_disposition === 'NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE'
    || passCount > 0
  ) {
    return {
      key: 'COMPLIANT',
      reason: 'No non-compliance was found within the confirmed context and the package evidence that could be evaluated.',
    };
  }

  return {
    key: 'NEEDS_REVIEW',
    reason: 'Photograph the requested package sides to begin the legal assessment.',
  };
};

const OfficerResultSummary = ({ session }) => {
  const result = getOfficerResult(session);
  const style = RESULT_STYLES[result.key];
  const Icon = style.icon;

  return (
    <section className={`portal-result-reveal rounded-2xl border p-5 shadow-[0_8px_24px_rgba(16,42,67,0.05)] sm:p-6 ${style.panel}`} aria-live="polite">
      <div className="flex items-start gap-4">
        <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ring-1 ${style.iconSurface}`}>
          <Icon className={`h-6 w-6 ${style.iconClass}`} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">Inspection result</p>
          <h2 className={`mt-1.5 text-2xl font-extrabold tracking-tight ${style.iconClass}`}>{style.label}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700 dark:text-slate-300">{result.reason}</p>
        </div>
      </div>
    </section>
  );
};

export default OfficerResultSummary;
