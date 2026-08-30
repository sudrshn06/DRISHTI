import { AlertTriangle, CheckCircle2, CircleMinus, XCircle } from 'lucide-react';

const RESULT_STYLES = {
  COMPLIANT: {
    label: 'Compliant',
    icon: CheckCircle2,
    panel: 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/25',
    iconClass: 'text-emerald-700 dark:text-emerald-300',
  },
  NON_COMPLIANT: {
    label: 'Non-compliant',
    icon: XCircle,
    panel: 'border-rose-200 bg-rose-50/70 dark:border-rose-800 dark:bg-rose-950/25',
    iconClass: 'text-rose-700 dark:text-rose-300',
  },
  NEEDS_REVIEW: {
    label: 'Needs Officer Review',
    icon: AlertTriangle,
    panel: 'border-amber-200 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/25',
    iconClass: 'text-amber-700 dark:text-amber-300',
  },
  FINALIZED_REVIEW: {
    label: 'Finalized with documented review items',
    icon: CheckCircle2,
    panel: 'border-indigo-200 bg-indigo-50/60 dark:border-indigo-800 dark:bg-indigo-950/25',
    iconClass: 'text-indigo-700 dark:text-indigo-300',
  },
  NOT_APPLICABLE: {
    label: 'Not Applicable',
    icon: CircleMinus,
    panel: 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/40',
    iconClass: 'text-slate-600 dark:text-slate-300',
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
    <section className={`portal-result-reveal rounded-xl border p-5 ${style.panel}`} aria-live="polite">
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-7 w-7 shrink-0 ${style.iconClass}`} aria-hidden="true" />
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Inspection result
          </p>
          <h2 className={`mt-1 text-2xl font-bold ${style.iconClass}`}>{style.label}</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
            {result.reason}
          </p>
        </div>
      </div>
    </section>
  );
};

export default OfficerResultSummary;
