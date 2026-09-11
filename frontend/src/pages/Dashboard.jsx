import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, AlertTriangle, ArrowRight, ClipboardList, Download, FileCheck2, FileText, Plus, ShieldCheck, Users } from 'lucide-react';
import { downloadReportDocx, downloadReportPdf, getDashboardSummary } from '../services/api';

const lifecycleLabels = { DRAFT: 'Draft', IN_PROGRESS: 'In progress', READY_FOR_REVIEW: 'Awaiting review', FINALIZED: 'Finalized' };
const categoryLabel = (value) => ({ GENERIC_RETAIL_PACKAGE: 'Retail package', FOOD: 'Food product', COSMETIC: 'Cosmetic product', DRUG: 'Drug / medical product', NON_FOOD: 'Non-food product', UNKNOWN: 'Not specified' }[value] || value?.replaceAll('_', ' ').toLowerCase() || 'Not specified');
const formatDate = (value) => value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Not recorded';
const disposition = (item) => {
  if (item.lifecycle_status === 'FINALIZED' && item.overall_disposition === 'INCOMPLETE_INSPECTION') return { label: 'Documented Review Items', className: 'bg-amber-50 text-amber-800 border-amber-200' };
  return ({
    VIOLATIONS_FOUND: { label: 'Possible violations found', className: 'bg-red-50 text-red-800 border-red-200' },
    REVIEW_REQUIRED: { label: 'Officer review required', className: 'bg-amber-50 text-amber-800 border-amber-200' },
    NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE: { label: 'No violations detected', className: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
    INCOMPLETE_INSPECTION: { label: 'Further evidence required', className: 'bg-slate-50 text-slate-700 border-slate-200' },
  })[item.overall_disposition];
};

function MetricCard({ label, value, note, icon: Icon, onClick, tone = 'navy' }) {
  const toneClass = {
    navy: 'border-[#c8d9e3] bg-gradient-to-br from-white to-[#eef6f8] text-[#102a43]',
    red: 'border-red-200 bg-gradient-to-br from-white to-red-50 text-red-900',
    amber: 'border-amber-200 bg-gradient-to-br from-white to-amber-50 text-amber-900',
    green: 'border-emerald-200 bg-gradient-to-br from-white to-emerald-50 text-emerald-900',
  }[tone];
  const iconClass = {
    navy: 'bg-[#e8f6f5] text-[#087f83]',
    red: 'bg-red-100 text-red-700',
    amber: 'bg-amber-100 text-amber-700',
    green: 'bg-emerald-100 text-emerald-700',
  }[tone];

  return (
    <button type="button" onClick={onClick} className={`portal-interactive min-h-40 border p-5 text-left shadow-[0_8px_24px_rgba(16,42,67,0.05)] ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-extrabold uppercase tracking-[0.10em] text-slate-600">{label}</span>
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconClass}`}><Icon size={19} /></span>
      </div>
      <div className="mt-4 text-4xl font-extrabold tabular-nums tracking-tight">{value ?? 0}</div>
      <p className="mt-2 text-xs leading-5 text-slate-600">{note}</p>
    </button>
  );
}

export default function Dashboard({ onStartNew, onOpenInspection, onNavigateToHistory }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => { setLoading(true); setError(''); try { setData(await getDashboardSummary()); } catch (err) { setError(err.response?.data?.detail || err.message || 'The dashboard could not be loaded.'); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="portal-page py-16">
      <div className="portal-card mx-auto max-w-md p-8 text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-[3px] border-slate-200 border-t-[#087f83]" />
        <p className="text-sm font-semibold text-slate-700">Loading inspection register…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="portal-page py-8">
      <div className="portal-card flex items-center justify-between gap-4 border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <span className="flex items-center gap-2"><AlertCircle size={18} />{error}</span>
        <button type="button" onClick={load} className="border border-red-300 bg-white px-4 py-2 font-bold hover:bg-red-50">Retry</button>
      </div>
    </div>
  );

  const { workflow_counts: workflow = {}, attention_counts: attention = {}, report_counts: reports = {}, recent_inspections: recent = [], user_role: role, user_display_name: name, admin_metrics: admin } = data || {};
  const total = workflow.total || 0;
  const attentionTotal = attention.total_needing_attention ?? ((attention.violations_found || 0) + (attention.review_required || 0) + (attention.incomplete_inspection || 0));

  return <main className="portal-page space-y-7 py-6 sm:py-8">
    <section className="portal-card relative overflow-hidden border-0 bg-gradient-to-br from-[#102a43] via-[#163a5f] to-[#087f83] p-6 text-white shadow-[0_18px_50px_rgba(16,42,67,0.20)] sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full border border-white/10 bg-white/5" />
      <div className="pointer-events-none absolute -bottom-24 right-32 h-56 w-56 rounded-full bg-[#278342]/10 blur-2xl" />
      <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-teal-100">{role === 'ADMIN' ? 'Administrative oversight' : 'Officer workspace'}</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">Inspection Dashboard</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-100/85">Overview of packaged commodity inspections, evidence status, compliance outcomes and pending officer actions.</p>
          {name && <p className="mt-3 text-sm text-white/80">Signed in as <strong className="text-white">{name}</strong></p>}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button type="button" onClick={() => onNavigateToHistory?.({})} className="min-h-11 border border-white/30 bg-white/10 px-4 py-2 text-sm font-bold text-white backdrop-blur hover:bg-white/15">Open inspection register</button>
          <button type="button" onClick={onStartNew} className="inline-flex min-h-11 items-center justify-center gap-2 bg-white px-5 py-2 text-sm font-extrabold text-[#102a43] shadow-lg hover:bg-[#f6f4ef]"><Plus size={17} />Inspect product</button>
        </div>
      </div>
    </section>

    {role === 'ADMIN' && admin && (
      <section className="portal-card p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="portal-section-title"><Users size={18} />Organisation overview</h2>
          <span className="rounded-full bg-[#e8f6f5] px-3 py-1 text-xs font-bold text-[#087f83]">Admin view</span>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {[
            ['Registered inspectors', admin.total_inspectors],
            ['Active inspectors', admin.total_active_inspectors],
            ['System inspections', admin.total_system_inspections],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-xs font-semibold text-slate-500">{label}</p>
              <p className="mt-2 text-3xl font-extrabold tabular-nums tracking-tight text-[#102a43]">{value ?? 0}</p>
            </div>
          ))}
        </div>
      </section>
    )}

    <section aria-labelledby="overview-title">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 id="overview-title" className="text-xl font-extrabold tracking-tight text-[#102a43]">Inspection overview</h2>
          <p className="mt-1 text-sm text-slate-600">Authoritative counts from the inspection register.</p>
        </div>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 shadow-sm">{total} total records</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total inspections" value={total} note="All recorded inspections" icon={ClipboardList} onClick={() => onNavigateToHistory?.({})} />
        <MetricCard label="Possible violations" value={attention.violations_found} note="Confirmed non-compliance findings" icon={AlertCircle} tone="red" onClick={() => onNavigateToHistory?.({ disposition: 'VIOLATIONS_FOUND' })} />
        <MetricCard label="Needs officer review" value={attention.review_required} note="Unresolved officer-review records" icon={AlertTriangle} tone="amber" onClick={() => onNavigateToHistory?.({ disposition: 'REVIEW_REQUIRED' })} />
        <MetricCard label="Finalized inspections" value={workflow.finalized} note="Approved and immutable reports" icon={FileCheck2} tone="green" onClick={() => onNavigateToHistory?.({ lifecycle_status: 'FINALIZED' })} />
      </div>
    </section>

    <section className="portal-card p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 pb-5">
        <div>
          <h2 className="text-xl font-extrabold tracking-tight text-[#102a43]">Attention required</h2>
          <p className="mt-1 text-sm text-slate-600">Open the relevant register view to continue the officer workflow.</p>
        </div>
        <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm font-extrabold tabular-nums text-amber-800">{attentionTotal} records require attention</span>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        {[
          ['Confirmed non-compliance', attention.violations_found, 'VIOLATIONS_FOUND', AlertCircle, 'text-red-800', 'bg-red-50 border-red-100'],
          ['Officer review required', attention.review_required, 'REVIEW_REQUIRED', AlertTriangle, 'text-amber-800', 'bg-amber-50 border-amber-100'],
          ['Additional package evidence required', attention.incomplete_inspection, 'INCOMPLETE_INSPECTION', ShieldCheck, 'text-slate-800', 'bg-slate-50 border-slate-200'],
        ].map(([label, value, filter, Icon, tone, surface]) => (
          <button key={label} type="button" onClick={() => onNavigateToHistory?.({ disposition: filter })} className={`portal-interactive flex min-h-28 items-center justify-between border p-4 text-left ${surface}`}>
            <span className={`flex items-center gap-3 text-sm font-extrabold ${tone}`}><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm"><Icon size={20} /></span>{label}</span>
            <span className="text-3xl font-extrabold tabular-nums text-slate-950">{value ?? 0}</span>
          </button>
        ))}
      </div>
    </section>

    <section className="portal-card overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-gradient-to-r from-white to-slate-50/70 px-5 py-5 sm:px-6">
        <div>
          <h2 className="text-xl font-extrabold tracking-tight text-[#102a43]">Recent inspections</h2>
          <p className="mt-1 text-sm text-slate-600">Most recently updated records.</p>
        </div>
        <button type="button" onClick={() => onNavigateToHistory?.({})} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-extrabold text-[#087f83] hover:bg-[#e8f6f5]">View all <ArrowRight size={15} /></button>
      </div>

      {recent.length === 0 ? (
        <div className="p-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400"><FileText /></div>
          <p className="mt-4 text-sm text-slate-600">No inspections have been recorded.</p>
          <button type="button" onClick={onStartNew} className="mt-4 bg-[#102a43] px-4 py-2 text-sm font-bold text-white hover:bg-[#163a5f]">Start inspection</button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead className="bg-slate-50/90 text-xs uppercase tracking-[0.08em] text-slate-600">
              <tr>
                <th className="px-5 py-3.5">Product category</th>
                <th className="px-4 py-3.5">Last updated</th>
                <th className="px-4 py-3.5">Captures</th>
                <th className="px-4 py-3.5">Workflow</th>
                <th className="px-4 py-3.5">Finding</th>
                <th className="px-5 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {recent.map((item) => {
                const finding = disposition(item);
                const finalized = item.lifecycle_status === 'FINALIZED';
                return (
                  <tr key={item.inspection_id}>
                    <td className="px-5 py-4 font-bold text-slate-900">
                      {categoryLabel(item.product_category)}
                      {item.created_by_username && <span className="mt-1 block text-xs font-normal text-slate-500">Inspector: {item.created_by_username}</span>}
                    </td>
                    <td className="px-4 py-4 text-slate-600">{formatDate(item.updated_at)}</td>
                    <td className="px-4 py-4 font-semibold tabular-nums text-slate-700">{item.capture_count ?? 0}</td>
                    <td className="px-4 py-4"><span className="rounded-full border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700">{lifecycleLabels[item.lifecycle_status] || 'Draft'}</span></td>
                    <td className="px-4 py-4">{finding ? <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${finding.className}`}>{finding.label}</span> : <span className="text-xs text-slate-500">Not evaluated</span>}</td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        {item.has_report && <>
                          <button type="button" onClick={() => downloadReportPdf(item.inspection_id)} className="border border-slate-300 bg-white px-3 py-2 text-xs font-bold hover:bg-slate-50">PDF</button>
                          <button type="button" onClick={() => downloadReportDocx(item.inspection_id)} className="border border-slate-300 bg-white px-3 py-2 text-xs font-bold hover:bg-slate-50"><Download size={13} className="inline" /> Word</button>
                        </>}
                        <button type="button" onClick={() => onOpenInspection(item.inspection_id)} className="bg-[#102a43] px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-[#163a5f]">{finalized ? 'View record' : 'Continue'}</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(reports.generated || reports.available) != null && (
        <div className="border-t border-slate-200 bg-slate-50/80 px-5 py-3 text-xs text-slate-600">Finalized report register: <strong className="text-[#102a43]">{reports.generated ?? reports.available ?? 0}</strong></div>
      )}
    </section>
  </main>;
}
