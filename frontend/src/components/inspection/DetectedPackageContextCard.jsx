import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';

const FIELD_CONFIG = {
  regulatory_product_class: {
    label: 'Product type',
    options: [
      ['FOOD', 'Food'],
      ['NON_FOOD', 'Non-food'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  product_origin: {
    label: 'Origin',
    options: [
      ['DOMESTIC', 'Domestic'],
      ['IMPORTED', 'Imported'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  package_structure: {
    label: 'Package structure',
    options: [
      ['SINGLE', 'Single package'],
      ['COMBINATION', 'Combination package'],
      ['GROUP', 'Group package'],
      ['MULTI_PIECE', 'Multi-piece package'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  alcohol_context: {
    label: 'Alcohol status',
    options: [
      ['ALCOHOLIC', 'Alcoholic'],
      ['NON_ALCOHOLIC', 'Non-alcoholic'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  is_electronic: {
    label: 'Electronic status',
    options: [
      ['ELECTRONIC', 'Electronic'],
      ['NON_ELECTRONIC', 'Non-electronic'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  date_regulatory_regime: {
    label: 'Date-label category',
    options: [
      ['GENERAL', 'General'],
      ['FOOD', 'Food'],
      ['CERTIFIED_SEED', 'Certified seed'],
      ['COSMETIC', 'Cosmetic'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
  date_package_exemption: {
    label: 'Date exemption',
    options: [
      ['NONE', 'No exemption detected'],
      ['BIDI_OR_INCENSE', 'Bidi or incense'],
      ['PSU_DOMESTIC_LPG_14_2_OR_5KG', 'PSU domestic LPG'],
      ['UNKNOWN', 'Not sure'],
    ],
  },
};

const buildDraft = (session, suggestions) => Object.fromEntries(
  suggestions.map((item) => [
    item.field,
    session[item.field] && session[item.field] !== 'UNKNOWN'
      ? session[item.field]
      : item.suggested_value,
  ]),
);

const DetectedPackageContextCard = ({ session, disabled, saving, onSave }) => {
  const detected = session.detected_package_context;
  const suggestions = useMemo(
    () => (detected?.suggestions || []).filter((item) => FIELD_CONFIG[item.field]),
    [detected],
  );
  const [edits, setEdits] = useState({});
  const draft = { ...buildDraft(session, suggestions), ...edits };

  if (!detected?.ready_for_confirmation || suggestions.length === 0) return null;

  return (
    <section className="mt-3 rounded-xl border border-indigo-200 bg-indigo-50/60 p-4 dark:border-indigo-800/60 dark:bg-indigo-950/30">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 rounded-lg bg-indigo-100 p-1.5 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300">
          <CheckCircle2 size={16} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Please confirm these package details
          </h3>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">
            These details affect which legal requirements apply. Confirm them, correct them, or choose “Not sure.”
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {suggestions.map((item) => {
          const config = FIELD_CONFIG[item.field];
          return (
            <label key={item.field} className="text-xs font-medium text-slate-700 dark:text-slate-300">
              {config.label}
              <select
                value={draft[item.field] || 'UNKNOWN'}
                disabled={disabled || saving}
                onChange={(event) => setEdits((current) => ({
                  ...current,
                  [item.field]: event.target.value,
                }))}
                className="mt-1 w-full rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs text-slate-800 dark:border-indigo-800 dark:bg-slate-900 dark:text-slate-200"
              >
                {config.options.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          );
        })}
      </div>

      {detected.contradiction_fields?.length > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Some package details conflicted across images and were left for manual review.</span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={disabled || saving}
          onClick={() => onSave(draft)}
          className="inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {saving ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
          Confirm details
        </button>
        <button
          type="button"
          disabled={disabled || saving}
          onClick={() => onSave({ dismiss_question_id: 'DETECTED_PACKAGE_CONTEXT' })}
          className="min-h-12 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          I’m not sure — ask one question at a time
        </button>
      </div>

      <details className="mt-3 border-t border-indigo-200 pt-2 text-[11px] text-slate-500 dark:border-indigo-900 dark:text-slate-400">
        <summary className="cursor-pointer font-medium">View details</summary>
        <div className="mt-2 space-y-1.5">
          {suggestions.map((item) => (
            <p key={item.field}>
              {FIELD_CONFIG[item.field].label}: {Math.round(item.confidence * 100)}% reading confidence
              {item.evidence?.[0] ? ` — ${item.evidence[0]}` : ''}
            </p>
          ))}
        </div>
      </details>
    </section>
  );
};

export default DetectedPackageContextCard;
