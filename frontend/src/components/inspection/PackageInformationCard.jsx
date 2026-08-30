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
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-300">
          <CheckCircle2 className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
            {isFinalized ? 'Package information confirmed' : 'Package information detected'}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {isFinalized
              ? 'Package information confirmed. The finalized record is locked.'
              : 'Please confirm these details. You can correct a reading while the original remains preserved.'}
          </p>
        </div>
      </div>

      {candidates.length === 0 ? (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-300">
          <p className="font-bold">Could not read the package declarations clearly.</p>
          <p className="mt-1">Take another photograph where possible. No unreadable declaration has been treated as legally absent.</p>
        </div>
      ) : (
      <div className="mt-4 overflow-hidden border border-slate-200">
        <div className="hidden grid-cols-[minmax(170px,0.8fr)_minmax(0,1.6fr)_auto] gap-4 bg-slate-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wide text-slate-500 sm:grid">
          <span>Declaration</span><span>Recorded value</span><span>Officer action</span>
        </div>
        {candidates.slice(0, 5).map(({ candidate, index }) => (
          <div
            key={`${candidate.field}-${index}`}
            className={`grid gap-3 border-t border-slate-200 p-4 first:border-t-0 sm:grid-cols-[minmax(170px,0.8fr)_minmax(0,1.6fr)_auto] sm:items-start ${
              candidate.status === 'REVIEW_REQUIRED'
                ? 'bg-amber-50/60 dark:bg-amber-950/20'
                : 'bg-white dark:bg-slate-900/30'
            }`}
          >
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  {getFieldLabel(candidate)}
                </p>
              </div>
              <div className="min-w-0">
                <p className="mt-1 break-words text-sm font-medium text-slate-900 dark:text-slate-100">
                  {formatValue(candidate)}
                </p>
                {candidate.status === 'REVIEW_REQUIRED' && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300">
                    <AlertTriangle className="h-3.5 w-3.5" /> Officer confirmation required
                  </p>
                )}
                {candidate.extraction_method === 'OFFICER_CONFIRMED' && (
                  <p className="mt-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">Officer-confirmed correction</p>
                )}
              </div>
              {!isFinalized && (
                <button
                  type="button"
                  onClick={() => onCorrect(candidate, index)}
                  className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  <Pencil className="h-4 w-4" /> Correct
                </button>
              )}
          </div>
        ))}
      </div>
      )}

      {candidates.length > 5 && (
        <details className="mt-3 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
          <summary className="flex cursor-pointer items-center gap-1.5 font-semibold text-slate-600 dark:text-slate-300">
            <ChevronDown className="h-4 w-4" /> View all detected information
          </summary>
          <div className="mt-3 space-y-3">
            {candidates.slice(5).map(({ candidate, index }) => (
              <div key={`${candidate.field}-more-${index}`} className="border-t border-slate-100 pt-3 dark:border-slate-700">
                <p className="text-xs font-semibold text-slate-500">{getFieldLabel(candidate)}</p>
                <p className="mt-1 text-sm text-slate-800 dark:text-slate-200">{formatValue(candidate)}</p>
                {!isFinalized && (
                  <button
                    type="button"
                    onClick={() => onCorrect(candidate, index)}
                    className="mt-2 inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold"
                  >
                    <Pencil className="h-4 w-4" /> Correct detected value
                  </button>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      {!isFinalized && <button
        type="button"
        onClick={onReviewed}
        disabled={reviewed || savingReview}
        className={`mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold transition-colors ${
          reviewed
            ? 'cursor-default bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
            : 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60'
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
      </button>}
      {reviewed && (
        <p className="mt-2 text-center text-xs text-slate-500 dark:text-slate-400">
          Confirmed by {review.reviewed_by_username}{reviewTime ? ` on ${reviewTime}` : ''}.
          {isFinalized ? ' The finalized package record is immutable.' : ' A new photograph or correction will require review again.'}
        </p>
      )}
    </section>
  );
};

export default PackageInformationCard;
