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
    <section className="mt-4 rounded-2xl border border-[#bcd4d5] bg-gradient-to-b from-[#f7fbfb] to-[#eef8f7] p-4 shadow-[0_8px_22px_rgba(16,42,67,0.05)] dark:border-indigo-800/60 dark:bg-indigo-950/30 sm:p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-[#087f83] shadow-sm ring-1 ring-[#cfe2e2]">
            <CheckCircle2 size={17} />
          </div>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#087f83]">Applicability check</p>
            <h3 className="mt-1 text-sm font-extrabold text-[#102a43] dark:text-slate-100">Confirm package context</h3>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600 dark:text-slate-400">
              These details determine which statutory requirements apply. Confirm them, correct them, or choose “Not sure.”
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {suggestions.map((item) => {
          const config = FIELD_CONFIG[item.field];
          return (
            <label key={item.field} className="rounded-xl border border-[#d5e5e5] bg-white p-3 text-xs font-bold text-slate-700 shadow-sm dark:text-slate-300">
              {config.label}
              <select
                value={draft[item.field] || 'UNKNOWN'}
                disabled={disabled || saving}
                onChange={(event) => setEdits((current) => ({
                  ...current,
                  [item.field]: event.target.value,
                }))}
                className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
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
        <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span>Some package details conflicted across photographs and remain for manual officer review.</span>
        </div>
      )}

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          disabled={disabled || saving}
          onClick={() => onSave(draft)}
          className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#102a43] px-4 py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#163a5f] disabled:opacity-60"
        >
          {saving ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
          Confirm details
        </button>
        <button
          type="button"
          disabled={disabled || saving}
          onClick={() => onSave({ dismiss_question_id: 'DETECTED_PACKAGE_CONTEXT' })}
          className="min-h-12 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-bold text-slate-600 hover:border-slate-400 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          I’m not sure — ask one question at a time
        </button>
      </div>

      <details className="mt-4 border-t border-[#d5e5e5] pt-3 text-[11px] leading-5 text-slate-500 dark:border-indigo-900 dark:text-slate-400">
        <summary className="cursor-pointer font-bold text-slate-600">View detection details</summary>
        <div className="mt-2 space-y-1.5">
          {suggestions.map((item) => (
            <p key={item.field}>
              <strong>{FIELD_CONFIG[item.field].label}:</strong> {Math.round(item.confidence * 100)}% reading confidence
              {item.evidence?.[0] ? ` — ${item.evidence[0]}` : ''}
            </p>
          ))}
        </div>
      </details>
    </section>
  );
};

export default DetectedPackageContextCard;
