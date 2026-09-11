import { AlertTriangle, CheckCircle2, ChevronDown, Pencil } from 'lucide-react';

const FIELD_LABELS = {
  COMMON_GENERIC_NAME: 'Product name',
  BRAND_NAME: 'Brand or trade name',
  MRP: 'Maximum retail price',
  NET_QUANTITY: 'Net quantity',
  UNIT_SALE_PRICE: 'Unit sale price',
  MANUFACTURER_PACKER_IMPORTER: 'Business declaration',
  MONTH_YEAR: 'Date information',
  COUNTRY_OF_ORIGIN: 'Country of origin',
  CONSUMER_CARE: 'Consumer care details',
  FSSAI_LICENCE: 'FSSAI licence',
  FSSAI_INGREDIENTS: 'Ingredients',
  FSSAI_ALLERGENS: 'Allergen information',
  FSSAI_NUTRITION: 'Nutrition information',
  FSSAI_VEG_NONVEG: 'Vegetarian or non-vegetarian mark',
};

const getFieldLabel = (candidate) => {
  if (candidate.field === 'MANUFACTURER_PACKER_IMPORTER') {
    const role = candidate.normalized_value?.role;
    return role ? `Business declaration — ${role.replace(/_/g, ' ').toLowerCase()}` : FIELD_LABELS[candidate.field];
  }
  return FIELD_LABELS[candidate.field];
};

const formatValue = (candidate) => {
  if (candidate.status === 'REVIEW_REQUIRED') {
    return 'Could not read this declaration clearly';
  }
  if (candidate.status === 'NOT_DETECTED') {
    return 'Not identified in the available photographs';
  }
  return candidate.raw_value || 'Please review the supporting photograph';
};

const PackageInformationCard = ({ session, review, savingReview, onReviewed, onCorrect, isFinalized = false }) => {
  const candidates = (session.aggregated_candidates || [])
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => FIELD_LABELS[candidate.field]);
  const reviewed = Boolean(review);
  const reviewTime = review?.reviewed_at
    ? new Date(review.reviewed_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
    : null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_28px_rgba(16,42,67,0.06)] dark:border-slate-700 dark:bg-slate-800 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#e8f6f5] text-[#087f83]">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-slate-500">Officer verification</p>
            <h2 className="mt-1 text-lg font-extrabold tracking-tight text-[#102a43] dark:text-slate-100">
              {isFinalized ? 'Package information confirmed' : 'Package information detected'}
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-400">
              {isFinalized
                ? 'The officer-confirmed package information is preserved in the finalized record.'
                : 'Compare each detected value with the supporting photograph. Corrections preserve the original machine observation.'}
            </p>
          </div>
        </div>
        {reviewed && (
          <span className="hidden shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 sm:inline-flex">
            Reviewed
          </span>
        )}
      </div>

      {candidates.length === 0 ? (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-300">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-bold">Declarations could not be read clearly.</p>
              <p className="mt-1 leading-6">Take another photograph where possible. Unreadable information is kept for officer review and is not treated as legally absent.</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
          <div className="hidden grid-cols-[minmax(170px,0.8fr)_minmax(0,1.6fr)_auto] gap-4 bg-slate-50 px-4 py-2.5 text-[11px] font-extrabold uppercase tracking-[0.09em] text-slate-500 sm:grid">
            <span>Declaration</span><span>Recorded value</span><span>Officer action</span>
          </div>
          {candidates.slice(0, 5).map(({ candidate, index }) => (
            <div
              key={`${candidate.field}-${index}`}
              className={`grid gap-3 border-t border-slate-200 p-4 first:border-t-0 sm:grid-cols-[minmax(170px,0.8fr)_minmax(0,1.6fr)_auto] sm:items-start ${
                candidate.status === 'REVIEW_REQUIRED'
                  ? 'bg-amber-50/55 dark:bg-amber-950/20'
                  : 'bg-white dark:bg-slate-900/30'
              }`}
            >
              <div className="min-w-0">
                <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300">{getFieldLabel(candidate)}</p>
                <p className="mt-1 text-[11px] text-slate-400">Machine observation</p>
              </div>
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold leading-6 text-slate-900 dark:text-slate-100">{formatValue(candidate)}</p>
                {candidate.status === 'REVIEW_REQUIRED' && (
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
                    <AlertTriangle className="h-3.5 w-3.5" /> Officer confirmation required
                  </p>
                )}
                {candidate.extraction_method === 'OFFICER_CONFIRMED' && (
                  <p className="mt-1.5 inline-flex rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">Officer-confirmed correction</p>
                )}
              </div>
              {!isFinalized && (
                <button
                  type="button"
                  onClick={() => onCorrect(candidate, index)}
                  className="inline-flex min-h-10 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-sm hover:border-slate-400 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  <Pencil className="h-4 w-4" /> Correct
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {candidates.length > 5 && (
        <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm dark:border-slate-700 dark:bg-slate-900/20">
          <summary className="flex cursor-pointer items-center gap-1.5 font-bold text-slate-600 dark:text-slate-300">
            <ChevronDown className="h-4 w-4" /> View all detected information
          </summary>
          <div className="mt-3 space-y-3">
            {candidates.slice(5).map(({ candidate, index }) => (
              <div key={`${candidate.field}-more-${index}`} className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900/40">
                <p className="text-xs font-bold text-slate-500">{getFieldLabel(candidate)}</p>
                <p className="mt-1 text-sm leading-6 text-slate-800 dark:text-slate-200">{formatValue(candidate)}</p>
                {!isFinalized && (
                  <button
                    type="button"
                    onClick={() => onCorrect(candidate, index)}
                    className="mt-2 inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700"
                  >
                    <Pencil className="h-4 w-4" /> Correct detected value
                  </button>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      {!isFinalized && (
        <button
          type="button"
          onClick={onReviewed}
          disabled={reviewed || savingReview}
          className={`mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-extrabold transition-colors ${
            reviewed
              ? 'cursor-default border border-emerald-200 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
              : 'bg-[#102a43] text-white shadow-sm hover:bg-[#163a5f] disabled:opacity-60'
          }`}
        >
          <CheckCircle2 className="h-5 w-5" />
          {reviewed
            ? 'Package information reviewed'
            : savingReview
              ? 'Saving your confirmation…'
              : candidates.length > 0
                ? 'Confirm package information'
                : 'Continue with officer review'}
        </button>
      )}

      {reviewed && (
        <p className="mt-3 text-center text-xs leading-5 text-slate-500 dark:text-slate-400">
          Confirmed by {review.reviewed_by_username}{reviewTime ? ` on ${reviewTime}` : ''}.
          {isFinalized ? ' The finalized package record is immutable.' : ' A new photograph or correction will require review again.'}
        </p>
      )}
    </section>
  );
};

export default PackageInformationCard;
