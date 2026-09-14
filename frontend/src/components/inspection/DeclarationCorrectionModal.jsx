import { AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { useState } from 'react';

const ROLE_OPTIONS = [
  ['MANUFACTURER', 'Manufacturer'],
  ['PACKER', 'Packer'],
  ['IMPORTER', 'Importer'],
  ['MARKETER', 'Marketer'],
];

const DATE_OPTIONS = [
  ['MANUFACTURED', 'Manufacture date'],
  ['PACKED', 'Packing date'],
  ['IMPORTED', 'Import date'],
  ['USE_BY', 'Use-by date'],
  ['EXPIRY', 'Expiry date'],
  ['BEST_BEFORE', 'Best-before information'],
  ['UNKNOWN', 'Other date information'],
];

const normalizedMember = (candidate, key) => candidate?.normalized_value?.[key] || '';

const DeclarationCorrectionModal = ({ item, captures, saving, error, onClose, onSubmit }) => {
  const [confirmedValue, setConfirmedValue] = useState(item.candidate.raw_value || '');
  const [reason, setReason] = useState('Package text was read incorrectly');
  const [supportingCaptureId, setSupportingCaptureId] = useState(
    item.candidate.capture_ids?.[0] || captures[0]?.capture_id || '',
  );
  const [declarationRole, setDeclarationRole] = useState(
    normalizedMember(item.candidate, 'role') || 'MANUFACTURER',
  );
  const [dateType, setDateType] = useState(
    normalizedMember(item.candidate, 'type') || 'UNKNOWN',
  );

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      candidate_index: item.index,
      field: item.candidate.field,
      confirmed_value: confirmedValue,
      reason,
      supporting_capture_id: supportingCaptureId,
      declaration_role: item.candidate.field === 'MANUFACTURER_PACKER_IMPORTER'
        ? declarationRole
        : null,
      date_type: item.candidate.field === 'MONTH_YEAR' ? dateType : null,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-slate-900/60 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4" role="presentation">
      <form
        onSubmit={submit}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl border border-slate-200 bg-white p-5 shadow-[0_30px_90px_rgba(6,18,30,0.30)] dark:border-slate-700 dark:bg-slate-800 sm:max-w-xl sm:rounded-3xl sm:p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="correct-declaration-title"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#087f83]">Officer correction</p>
            <h2 id="correct-declaration-title" className="mt-1 text-xl font-extrabold tracking-tight text-[#102a43] dark:text-slate-100">Correct detected information</h2>
            <p className="mt-1 max-w-lg text-sm leading-6 text-slate-600 dark:text-slate-400">
              Enter exactly what is visibly printed. The original machine observation remains preserved in the inspection record.
            </p>
          </div>
          <button type="button" onClick={onClose} className="flex min-h-10 min-w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 hover:bg-slate-50" aria-label="Close correction">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.10em] text-slate-500">Original machine observation</p>
          <p className="mt-2 break-words text-sm font-semibold leading-6 text-slate-800 dark:text-slate-200">
            {item.originalCandidate?.raw_value || item.candidate.raw_value || 'Could not read this declaration clearly'}
          </p>
        </div>

        <div className="mt-5 space-y-4">
          <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
            Correct printed value
            <textarea
              value={confirmedValue}
              onChange={(event) => setConfirmedValue(event.target.value)}
              rows={3}
              required
              className="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm leading-6 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>

          {item.candidate.field === 'MANUFACTURER_PACKER_IMPORTER' && (
            <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
              Detail shown on the package
              <select value={declarationRole} onChange={(event) => setDeclarationRole(event.target.value)} className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 dark:border-slate-600 dark:bg-slate-900">
                {ROLE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          )}

          {item.candidate.field === 'MONTH_YEAR' && (
            <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
              Date information shown
              <select value={dateType} onChange={(event) => setDateType(event.target.value)} className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 dark:border-slate-600 dark:bg-slate-900">
                {DATE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          )}

          <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
            Supporting photograph
            <select value={supportingCaptureId} onChange={(event) => setSupportingCaptureId(event.target.value)} required className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 dark:border-slate-600 dark:bg-slate-900">
              {captures.map((capture) => (
                <option key={capture.capture_id} value={capture.capture_id}>
                  {capture.view_id.replace(/_/g, ' ').toLowerCase()} photograph
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
            Reason for correction
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={2} required className="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm leading-6 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100" />
          </label>
        </div>

        <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs leading-5 text-amber-800 dark:border-amber-800 dark:bg-amber-950/25 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>An unclear value cannot be marked as legally absent here. Confirm only text you can verify on the selected photograph.</p>
        </div>

        {error && <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/30 dark:text-rose-300">{error}</p>}

        <div className="mt-6 flex flex-col-reverse gap-2 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={saving} className="min-h-12 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200">Cancel</button>
          <button type="submit" disabled={saving || !confirmedValue.trim() || !reason.trim() || !supportingCaptureId} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#102a43] px-5 py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#163a5f] disabled:opacity-50">
            <CheckCircle2 className="h-5 w-5" /> {saving ? 'Saving correction…' : 'Confirm correction'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default DeclarationCorrectionModal;
