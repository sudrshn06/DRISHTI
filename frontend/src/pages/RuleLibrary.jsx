import { useState, useEffect, useCallback } from 'react';
import { BookOpen, Search, Filter, Calendar, ShieldAlert } from 'lucide-react';
import { getRuleLibrary } from '../services/api';

export default function RuleLibrary() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [referenceDate, setReferenceDate] = useState(() => new Date().toISOString().slice(0, 10));

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getRuleLibrary({
        domain: domainFilter,
        search: searchQuery,
        reference_date: referenceDate,
      });
      setRules(data);
    } catch {
      setError(err.response?.data?.detail || err.message || 'Failed to retrieve rule library.');
    } finally {
      setLoading(false);
    }
  }, [domainFilter, searchQuery, referenceDate]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  return (
    <main className="portal-page py-6 sm:py-8">
      <div className="portal-card mb-6 flex flex-col justify-between gap-5 border-t-4 border-t-[#087f83] p-6 md:flex-row md:items-center sm:p-7">
        <div className="flex items-start gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#e8f6f5] text-[#087f83]">
            <BookOpen size={22} />
          </div>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-[#087f83]">Authoritative reference</p>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-[#102a43] dark:text-white">Rule Library</h1>
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-400">Browse Legal Metrology and FSSAI provisions used as statutory reference within the inspection workflow.</p>
          </div>
        </div>
        <span className="inline-flex w-fit rounded-full border border-[#bfd3e2] bg-[#eef6f8] px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#102a43]">Official reference</span>
      </div>

      <div className="portal-card mb-6 p-5 sm:p-6">
        <div className="mb-4">
          <h2 className="text-sm font-extrabold text-[#102a43]">Find a statutory provision</h2>
          <p className="mt-1 text-xs text-slate-500">Search by wording, provision, regulatory domain, or the date relevant to the inspection.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_250px_220px]">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              placeholder="Search keywords, provisions, rules…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-11 pr-4 text-sm text-slate-800 focus:outline-none dark:bg-slate-900/60 dark:text-slate-200"
            />
          </div>

          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <select
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              className="w-full cursor-pointer appearance-none rounded-xl border border-slate-300 bg-white py-2.5 pl-9 pr-4 text-sm text-slate-800 focus:outline-none dark:bg-slate-900/60 dark:text-slate-200"
            >
              <option value="">All Domains</option>
              <option value="LEGAL_METROLOGY">Legal Metrology</option>
              <option value="FOOD_LABEL_FSSAI">Food Label / FSSAI</option>
            </select>
          </div>

          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="date"
              value={referenceDate}
              onChange={(e) => setReferenceDate(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-9 pr-4 text-sm text-slate-800 focus:outline-none dark:bg-slate-900/60 dark:text-slate-200"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="portal-card py-14 text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-[3px] border-slate-200 border-t-[#087f83]"></div>
          <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">Retrieving statutory provisions…</p>
        </div>
      ) : error ? (
        <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-center shadow-sm dark:border-red-900 dark:bg-red-950/20">
          <ShieldAlert className="mx-auto mb-2.5 text-red-500 dark:text-red-400" size={32} />
          <p className="text-sm font-semibold text-red-800 dark:text-red-200">{error}</p>
        </div>
      ) : rules.length === 0 ? (
        <div className="portal-card py-14 text-center">
          <BookOpen className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-3 font-semibold text-slate-600 dark:text-slate-400">No statutory rules found matching the current filters.</p>
        </div>
      ) : (
        <div className="portal-result-reveal grid grid-cols-1 gap-4">
          {rules.map((rule) => (
            <article key={rule.chunk_id} className="portal-card border-l-4 border-l-[#087f83] p-5 sm:p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-extrabold text-slate-700 dark:bg-slate-700 dark:text-slate-300">{rule.provision_number}</span>
                    <h3 className="text-lg font-extrabold leading-6 text-[#102a43] dark:text-white">{rule.title}</h3>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.08em] ${
                    rule.regulatory_domain === 'LEGAL_METROLOGY'
                      ? 'border-[#bfd3e2] bg-[#eef6f8] text-[#163a5f]'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  }`}>
                    {rule.regulatory_domain === 'LEGAL_METROLOGY' ? 'Legal Metrology' : 'Food Label / FSSAI'}
                  </span>
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.08em] ${
                    rule.status === 'Current'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-amber-200 bg-amber-50 text-amber-700'
                  }`}>
                    {rule.status}
                  </span>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/75 p-4">
                <p className="text-sm leading-7 text-slate-800 dark:text-slate-200">{rule.content}</p>
              </div>

              <div className="mt-4 grid gap-2 border-t border-slate-200 pt-4 text-xs text-slate-500 sm:grid-cols-2 dark:text-slate-400">
                <div><span className="font-bold text-slate-700 dark:text-slate-300">Official source:</span> {rule.official_source}</div>
                <div><span className="font-bold text-slate-700 dark:text-slate-300">Effective from:</span> {rule.effective_from}</div>
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
