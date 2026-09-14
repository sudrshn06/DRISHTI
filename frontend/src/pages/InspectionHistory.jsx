import { useState, useEffect, useCallback } from 'react';
import {
  Search, Calendar, ChevronLeft, ChevronRight, FileText, Download, Plus,
  RotateCcw, Lock, CheckCircle2, AlertTriangle, AlertCircle, Eye, Shield
} from 'lucide-react';
import { getInspectionHistory, downloadReportPdf, downloadReportDocx } from '../services/api';

const LIFECYCLE_CONFIG = {
  DRAFT: {
    label: 'Draft Case',
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-300 dark:border-slate-700'
  },
  IN_PROGRESS: {
    label: 'In Progress',
    bg: 'bg-indigo-50 dark:bg-indigo-950/40',
    text: 'text-indigo-700 dark:text-indigo-300',
    border: 'border-indigo-200 dark:border-indigo-800'
  },
  READY_FOR_REVIEW: {
    label: 'Awaiting Review',
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800'
  },
  FINALIZED: {
    label: 'Finalized',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-800'
  }
};

const DISPOSITION_CONFIG = {
  VIOLATIONS_FOUND: {
    label: 'Possible Violations Found',
    bg: 'bg-rose-50 dark:bg-rose-950/40',
    text: 'text-rose-700 dark:text-rose-300',
    border: 'border-rose-200 dark:border-rose-800',
    icon: AlertCircle
  },
  REVIEW_REQUIRED: {
    label: 'Needs Review',
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
    icon: AlertTriangle
  },
  NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE: {
    label: 'No Violations Detected',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-800',
    icon: CheckCircle2
  },
  INCOMPLETE_INSPECTION: {
    label: 'More Package Evidence Needed',
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-200 dark:border-slate-700',
    icon: Shield
  }
};

const getPresentedDisposition = (item) => {
  if (item.lifecycle_status === 'FINALIZED' && item.overall_disposition === 'INCOMPLETE_INSPECTION') {
    return {
      ...DISPOSITION_CONFIG.REVIEW_REQUIRED,
      label: 'Documented Review Items'
    };
  }
  return item.overall_disposition ? DISPOSITION_CONFIG[item.overall_disposition] : null;
};

const translateEnum = (val) => {
  if (!val) return '—';
  const mapping = {
    GENERIC_RETAIL_PACKAGE: 'Generic Retail Package',
    FOOD: 'Food Product',
    COSMETIC: 'Cosmetic Product',
    DRUG: 'Drug / Medical Product',
    DRAFT: 'Draft Case',
    IN_PROGRESS: 'In Progress',
    READY_FOR_REVIEW: 'Awaiting Review',
    FINALIZED: 'Finalized',
    VIOLATIONS_FOUND: 'Possible Violations Found',
    REVIEW_REQUIRED: 'Needs Review',
    NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE: 'No Violations Detected',
    INCOMPLETE_INSPECTION: 'More Package Evidence Needed',
    plan_software_1: 'Default Software Package Plan',
    DOMESTIC: 'Domestic',
    IMPORTED: 'Imported',
  };
  return mapping[val] || val.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

const InspectionHistory = ({ onOpenInspection, onStartNew, initialFilters = null, reportsOnly = false }) => {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Filters state
  const [search, setSearch] = useState(initialFilters?.search || '');
  const [lifecycleStatus, setLifecycleStatus] = useState(reportsOnly ? 'FINALIZED' : (initialFilters?.lifecycle_status || ''));
  const [disposition, setDisposition] = useState(initialFilters?.disposition || '');
  const [dateFrom, setDateFrom] = useState(initialFilters?.date_from || '');
  const [dateTo, setDateTo] = useState(initialFilters?.date_to || '');
  const [sort, setSort] = useState(initialFilters?.sort || 'newest');

  useEffect(() => {
    if (initialFilters) {
      if (initialFilters.lifecycle_status !== undefined) setLifecycleStatus(initialFilters.lifecycle_status);
      if (initialFilters.disposition !== undefined) setDisposition(initialFilters.disposition);
      if (initialFilters.search !== undefined) setSearch(initialFilters.search);
      setPage(1);
    }
  }, [initialFilters]);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getInspectionHistory({
        page,
        page_size: pageSize,
        search,
        lifecycle_status: lifecycleStatus || undefined,
        disposition: disposition || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        sort
      });
      setItems(data.items || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 0);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load inspection history.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, lifecycleStatus, disposition, dateFrom, dateTo, sort]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleResetFilters = () => {
    setSearch('');
    setLifecycleStatus(reportsOnly ? 'FINALIZED' : '');
    setDisposition('');
    setDateFrom('');
    setDateTo('');
    setSort('newest');
    setPage(1);
  };

  const hasActiveFilters = Boolean(
    search || lifecycleStatus || disposition || dateFrom || dateTo || sort !== 'newest'
  );

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  };

  return (
    <main className="portal-page space-y-6 py-6 sm:py-8">
      {/* Header */}
      <div className="portal-card flex flex-col justify-between gap-4 border-t-4 border-t-blue-900 p-6 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-slate-50 tracking-tight flex items-center gap-2">
            <FileText className="text-indigo-600 dark:text-indigo-400" size={24} />
            {reportsOnly ? 'Reports' : 'Inspection History'}
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
            {reportsOnly ? 'Access officer-approved, finalized inspection reports.' : 'Search, filter, resume, or view packaged commodity inspections.'}
          </p>
        </div>
        <button
          onClick={onStartNew}
          className="inline-flex items-center justify-center gap-1.5 px-4.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg transition-all shadow-sm hover:shadow-md cursor-pointer border border-indigo-700"
        >
          <Plus size={16} />
          Inspect Product
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white dark:bg-slate-800 p-5 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
        <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${reportsOnly ? 'lg:grid-cols-3' : 'lg:grid-cols-4'}`}>
          {/* Search Box */}
          <div className="relative">
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Search</label>
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Product, brand, business, barcode, reference or status…"
                className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100"
              />
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            </div>
          </div>

          {/* Lifecycle Filter */}
          {!reportsOnly && <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Lifecycle State</label>
            <select
              value={lifecycleStatus}
              onChange={(e) => { setLifecycleStatus(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100"
            >
              <option value="">All Lifecycles</option>
              <option value="DRAFT">New inspection (Draft)</option>
              <option value="IN_PROGRESS">Inspection in progress</option>
              <option value="READY_FOR_REVIEW">Ready for review</option>
              <option value="FINALIZED">Inspection finalized</option>
            </select>
          </div>}

          {/* Disposition Filter */}
          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Report Disposition</label>
            <select
              value={disposition}
              onChange={(e) => { setDisposition(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100"
            >
              <option value="">All Dispositions</option>
              <option value="VIOLATIONS_FOUND">Violations Detected</option>
              <option value="REVIEW_REQUIRED">Review Required</option>
              <option value="NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE">No Violations Detected</option>
              <option value="INCOMPLETE_INSPECTION">Incomplete Inspection</option>
            </select>
          </div>

          {/* Sort Control */}
          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Sort By</label>
            <select
              value={sort}
              onChange={(e) => { setSort(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100"
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="recently_updated">Recently Updated</option>
            </select>
          </div>
        </div>

        {/* Date Filters Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-slate-100 dark:border-slate-700/60">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
              <Calendar size={14} />
              <span>Created:</span>
            </div>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              className="px-2.5 py-1 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-md text-xs focus:ring-2 focus:ring-indigo-500 dark:text-slate-200"
              placeholder="From"
            />
            <span className="text-slate-400 text-xs">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              className="px-2.5 py-1 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-md text-xs focus:ring-2 focus:ring-indigo-500 dark:text-slate-200"
              placeholder="To"
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-slate-700/50 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-md transition-colors"
            >
              <RotateCcw size={13} />
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-rose-50 dark:bg-rose-900/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 rounded-xl flex items-start gap-3 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* Inspections List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent mb-3"></div>
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Loading inspection history...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <FileText className="w-12 h-12 text-slate-400 mx-auto mb-3 opacity-60" />
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-1">
              {hasActiveFilters ? 'No matching inspections found' : 'No inspections found'}
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm mx-auto mb-5">
              {hasActiveFilters
                ? 'Try adjusting or resetting your search term or filter criteria.'
                : 'Start your first Legal Metrology package inspection to generate compliance findings and reports.'}
            </p>
            {hasActiveFilters ? (
              <button
                onClick={handleResetFilters}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg text-sm font-medium transition-colors"
              >
                Reset Filters
              </button>
            ) : (
              <button
                onClick={onStartNew}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-2"
              >
                <Plus size={16} />
                Start New Inspection
              </button>
            )}
          </div>
        ) : (
          items.map((item) => {
            const lcConfig = LIFECYCLE_CONFIG[item.lifecycle_status] || LIFECYCLE_CONFIG.DRAFT;
            const dispConfig = getPresentedDisposition(item);
            const isFinalized = item.lifecycle_status === 'FINALIZED';

            return (
              <div
                key={item.inspection_id}
                onClick={() => onOpenInspection(item.inspection_id)}
                className="bg-white dark:bg-slate-800 hover:bg-slate-50/80 dark:hover:bg-slate-750/70 border border-slate-200 dark:border-slate-700 rounded-xl p-4 sm:p-5 transition-all shadow-sm cursor-pointer flex flex-col lg:flex-row lg:items-center justify-between gap-4"
              >
                {/* Left details */}
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      {translateEnum(item.product_category)} inspection
                    </span>

                    {/* Lifecycle Badge */}
                    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${lcConfig.bg} ${lcConfig.text} ${lcConfig.border}`}>
                      {isFinalized && <Lock size={11} className="shrink-0" />}
                      {lcConfig.label}
                    </span>

                    {/* Disposition Badge if available */}
                    {dispConfig ? (
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${dispConfig.bg} ${dispConfig.text} ${dispConfig.border}`}>
                        <dispConfig.icon size={12} className="shrink-0" />
                        {dispConfig.label}
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800/80 text-slate-500 border border-slate-200 dark:border-slate-700">
                        Not evaluated
                      </span>
                    )}

                    {/* Capture count */}
                    <span className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900 px-2 py-0.5 rounded border border-slate-200/60 dark:border-slate-800">
                      {item.capture_count} {item.capture_count === 1 ? 'capture' : 'captures'}
                    </span>
                  </div>

                  {/* Metadata subtitle */}
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                    <div>
                      <span className="text-slate-400">Created:</span> {formatDate(item.created_at)}
                    </div>
                    <div>
                      <span className="text-slate-400">Category:</span> {translateEnum(item.product_category)}
                    </div>
                    {item.created_by_username && (
                      <div>
                        <span className="text-slate-400">Inspector:</span> {item.created_by_username}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right actions */}
                <div className="flex flex-wrap items-center gap-2 shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100 dark:border-slate-700/60" onClick={(e) => e.stopPropagation()}>
                  {/* Download Reports buttons if report is available */}
                  {item.has_report && (
                    <div className="flex items-center gap-1.5 mr-2">
                      <button
                        onClick={async () => {
                          try {
                            await downloadReportPdf(item.inspection_id);
                          } catch (err) {
                            console.error('Failed to download PDF report', err);
                          }
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 dark:hover:bg-rose-900/60 border border-rose-200 dark:border-rose-800 rounded-lg transition-colors cursor-pointer"
                        title="Download PDF Inspection Report"
                      >
                        <FileText size={13} />
                        PDF
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await downloadReportDocx(item.inspection_id);
                          } catch (err) {
                            console.error('Failed to download DOCX report', err);
                          }
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 hover:bg-blue-100 dark:hover:bg-blue-900/60 border border-blue-200 dark:border-blue-800 rounded-lg transition-colors cursor-pointer"
                        title="Download Editable DOCX Report"
                      >
                        <Download size={13} />
                        DOCX
                      </button>
                    </div>
                  )}

                  {/* Primary Open Action */}
                  <button
                    onClick={() => onOpenInspection(item.inspection_id)}
                    className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors shadow-sm ${
                      isFinalized
                        ? 'bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-200'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                    }`}
                  >
                    {isFinalized ? (
                      <>
                        <Eye size={13} />
                        View Finalized
                      </>
                    ) : item.lifecycle_status === 'READY_FOR_REVIEW' ? (
                      <>
                        <CheckCircle2 size={13} />
                        Review Findings
                      </>
                    ) : (
                      <>
                        <ChevronRight size={13} />
                        Continue Inspection
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white dark:bg-slate-800 p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm text-sm">
          <div className="text-xs text-slate-500 dark:text-slate-400">
            Showing <span className="font-semibold text-slate-700 dark:text-slate-300">{(page - 1) * pageSize + 1}</span> to{' '}
            <span className="font-semibold text-slate-700 dark:text-slate-300">{Math.min(page * pageSize, total)}</span> of{' '}
            <span className="font-semibold text-slate-700 dark:text-slate-300">{total}</span> inspections
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Previous Page"
            >
              <ChevronLeft size={16} />
            </button>

            <span className="text-xs font-medium text-slate-600 dark:text-slate-300 px-2">
              Page {page} of {totalPages}
            </span>

            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Next Page"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </main>
  );
};

export default InspectionHistory;
