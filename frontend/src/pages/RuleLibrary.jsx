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
      {/* Header */}
      <div className="portal-card mb-6 flex flex-col justify-between gap-4 border-t-4 border-t-blue-900 p-6 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2.5">
            <BookOpen className="text-indigo-600 dark:text-indigo-400" size={28} />
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Rule Library</h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">
            Browse and query authoritative Legal Metrology and FSSAI statutory regulations.
          </p>
        </div>
        <span className="border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-blue-900">Official reference</span>
      </div>

      {/* Filters & Search */}
      <div className="portal-card mb-6 flex flex-col items-center gap-4 p-5 md:flex-row">
        {/* Search */}
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
          <input
            type="text"
            placeholder="Search keywords, provisions, rules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-2.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {/* Domain */}
        <div className="relative w-full md:w-64">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer appearance-none"
          >
            <option value="">All Domains</option>
            <option value="LEGAL_METROLOGY">Legal Metrology</option>
            <option value="FOOD_LABEL_FSSAI">Food Label / FSSAI</option>
          </select>
        </div>

        {/* Reference Date */}
        <div className="relative w-full md:w-56">
          <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="date"
            value={referenceDate}
            onChange={(e) => setReferenceDate(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Main List */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin inline-block w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mb-3"></div>
          <p className="text-sm text-slate-500 dark:text-slate-400">Retrieving statutory provisions…</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-xl p-5 text-center max-w-xl mx-auto">
          <ShieldAlert className="mx-auto text-red-500 dark:text-red-400 mb-2.5" size={32} />
          <p className="text-sm font-medium text-red-800 dark:text-red-200">{error}</p>
        </div>
      ) : rules.length === 0 ? (
        <div className="text-center py-12 bg-slate-50 dark:bg-slate-900/20 border border-slate-100 dark:border-slate-800/80 rounded-2xl">
          <p className="text-slate-500 dark:text-slate-400 font-medium">No statutory rules found matching filters.</p>
        </div>
      ) : (
        <div className="portal-result-reveal grid grid-cols-1 gap-6">
          {rules.map((rule) => (
            <div
              key={rule.chunk_id}
              className="portal-card border-l-4 border-l-blue-900 p-6"
            >
              {/* Card Title & Badges */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
                <div>
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 mr-2.5">
                    {rule.provision_number}
                  </span>
                  <h3 className="text-lg font-bold text-slate-950 dark:text-white inline-block">
                    {rule.title}
                  </h3>
                </div>
                <div className="flex gap-2">
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full ${
                    rule.regulatory_domain === 'LEGAL_METROLOGY'
                      ? 'bg-blue-50 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400 border border-blue-200/50'
                      : 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 border border-emerald-200/50'
                  }`}>
                    {rule.regulatory_domain === 'LEGAL_METROLOGY' ? 'Legal Metrology' : 'Food Label / FSSAI'}
                  </span>
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full ${
                    rule.status === 'Current'
                      ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 border border-green-200/50'
                      : 'bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400 border border-amber-200/50'
                  }`}>
                    {rule.status}
                  </span>
                </div>
              </div>

              {/* Card Body */}
              <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 rounded-lg p-4 mb-4">
                <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                  {rule.content}
                </p>
              </div>

              {/* Card Footer Details */}
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800 pt-4">
                <div>
                  <span className="font-semibold text-slate-700 dark:text-slate-300 mr-1.5">Official Source:</span>
                  {rule.official_source}
                </div>
                <div>
                  <span className="font-semibold text-slate-700 dark:text-slate-300 mr-1.5">Effective From:</span>
                  {rule.effective_from}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
