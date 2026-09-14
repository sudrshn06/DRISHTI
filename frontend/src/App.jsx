import { useEffect, useState } from 'react';
import {
  BookOpen, ClipboardCheck, FileText, History as HistoryIcon,
  LayoutDashboard, LogOut, PackageSearch, User
} from 'lucide-react';
import drishtiHeaderLogo from './assets/branding/drishti-logo-header.png';
import drishtiIcon from './assets/branding/drishti-icon.png';
import AuthPortal from './components/auth/AuthPortal';
import Dashboard from './pages/Dashboard';
import InspectionHistory from './pages/InspectionHistory';
import MultiViewInspection from './pages/MultiViewInspection';
import PrepareCase from './pages/PrepareCase';
import RuleLibrary from './pages/RuleLibrary';
import { getCurrentUser, logoutUser } from './services/api';
import {
  clearSessionState,
  createSessionRevalidator,
  isExplicitAuthRejection,
  readSessionUser,
  readWorkspaceState,
  saveSessionUser,
  saveWorkspaceState,
} from './services/sessionState';

const EXTERNAL_PORTAL_URL = import.meta.env.VITE_EXTERNAL_COMPLAINT_PORTAL_URL || '';
const revalidateCurrentUser = createSessionRevalidator(getCurrentUser);

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', mobileLabel: 'Dashboard', icon: LayoutDashboard },
  { id: 'multi-view', label: 'Inspect Product', mobileLabel: 'Inspect', icon: PackageSearch },
  { id: 'history', label: 'Inspection History', mobileLabel: 'History', icon: HistoryIcon },
  { id: 'reports', label: 'Reports', mobileLabel: 'Reports', icon: FileText },
  { id: 'rule-library', label: 'Rule Library', mobileLabel: 'Rules', icon: BookOpen },
];

function App() {
  const [initialAuth] = useState(() => {
    const hasToken = Boolean(localStorage.getItem('drishti_token'));
    return {
      hasToken,
      cachedUser: hasToken ? readSessionUser() : null,
    };
  });
  const [initialWorkspace] = useState(() => readWorkspaceState());
  const [currentUser, setCurrentUser] = useState(initialAuth.cachedUser);
  const [authLoading, setAuthLoading] = useState(
    initialAuth.hasToken && !initialAuth.cachedUser,
  );
  const [activeView, setActiveView] = useState(initialWorkspace.activeView);
  const [selectedInspectionId, setSelectedInspectionId] = useState(
    initialWorkspace.selectedInspectionId,
  );
  const [historyFilters, setHistoryFilters] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('drishti_token');
    if (!token) {
      clearSessionState();
      return undefined;
    }

    let active = true;
    revalidateCurrentUser()
      .then((user) => {
        if (!active) return;
        saveSessionUser(user);
        setCurrentUser(user);
      })
      .catch((error) => {
        if (!active || !isExplicitAuthRejection(error)) return;
        logoutUser();
        clearSessionState();
        setCurrentUser(null);
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    saveWorkspaceState({ activeView, selectedInspectionId });
  }, [activeView, currentUser, selectedInspectionId]);

  const navigate = (view) => {
    setActiveView(view);
    if (view !== 'multi-view' && view !== 'prepare-case') setSelectedInspectionId(null);
    if (view !== 'history') setHistoryFilters(null);
  };

  const handleLogout = () => {
    logoutUser();
    clearSessionState();
    setCurrentUser(null);
    setSelectedInspectionId(null);
    setHistoryFilters(null);
    setActiveView('dashboard');
  };

  const handleOpenInspection = (inspectionId) => {
    setSelectedInspectionId(inspectionId);
    setActiveView('multi-view');
  };

  const handleStartNewInspection = () => {
    setSelectedInspectionId(null);
    setActiveView('multi-view');
  };

  const handleAuthSuccess = (user) => {
    saveSessionUser(user);
    setCurrentUser(user);
    setActiveView('dashboard');
    setSelectedInspectionId(null);
    setHistoryFilters(null);
  };

  const handleNavigateToHistory = (filters = null) => {
    setHistoryFilters(filters || null);
    setSelectedInspectionId(null);
    setActiveView('history');
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f7f8]">
        <div className="rounded-2xl border border-slate-200 bg-white px-10 py-8 text-center shadow-[0_18px_50px_rgba(16,42,67,0.10)]" role="status">
          <div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-[3px] border-slate-200 border-t-[#087f83]" />
          <p className="text-sm font-semibold text-slate-700">Checking secure session…</p>
          <p className="mt-1 text-xs text-slate-500">Preparing your DRISHTI workspace</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <div className="portal-view"><AuthPortal onAuthSuccess={handleAuthSuccess} /></div>;
  }

  return (
    <div className="min-h-screen bg-transparent text-slate-800">
      <header className="sticky top-0 z-40 border-b border-slate-200/90 bg-white/95 shadow-[0_8px_28px_rgba(16,42,67,0.06)] backdrop-blur-xl">
        <div className="bg-[#102a43] px-4 py-1.5 text-center text-[10px] font-bold tracking-[0.14em] text-white sm:text-left">
          <div className="mx-auto flex max-w-[1520px] items-center justify-between">
            <span>PACKAGED COMMODITY INSPECTION &amp; DECISION SUPPORT</span>
            <span className="hidden text-white/65 md:inline">Secure Officer Workspace</span>
          </div>
        </div>

        <div className="mx-auto flex max-w-[1520px] items-center justify-between gap-5 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => navigate('dashboard')}
            className="group flex min-w-0 items-center rounded-xl px-1.5 py-1 text-left"
            aria-label="Open inspection dashboard"
          >
            <span className="min-w-0">
              <picture>
                <source media="(max-width: 639px)" srcSet={drishtiIcon} />
                <img
                  src={drishtiHeaderLogo}
                  alt="DRISHTI"
                  className="h-11 w-auto max-w-[52px] object-contain transition-transform duration-200 group-hover:scale-[1.02] sm:h-10 sm:max-w-[205px]"
                />
              </picture>
              <span className="mt-0.5 hidden text-[10px] font-semibold tracking-wide text-slate-500 xl:block">Packaged Commodity Inspection Portal</span>
            </span>
          </button>

          <nav className="hidden items-center gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 p-1.5 lg:flex" aria-label="Primary navigation">
            {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
              const active = activeView === id || (id === 'multi-view' && activeView === 'prepare-case');
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => id === 'multi-view' ? handleStartNewInspection() : navigate(id)}
                  className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-all duration-200 ${active ? 'bg-white text-[#102a43] shadow-[0_3px_10px_rgba(16,42,67,0.10)] ring-1 ring-slate-200' : 'text-slate-600 hover:bg-white/80 hover:text-[#102a43]'}`}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon size={16} className={active ? 'text-[#087f83]' : ''} aria-hidden="true" /> {label}
                </button>
              );
            })}
            {selectedInspectionId && activeView === 'multi-view' && (
              <span className="ml-1 flex items-center gap-2 rounded-xl bg-[#e8f6f5] px-3 py-2 text-sm font-semibold text-[#087f83]">
                <ClipboardCheck size={16} aria-hidden="true" /> Inspection Record
              </span>
            )}
          </nav>

          <div className="flex shrink-0 items-center gap-2.5">
            <div className="hidden items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 md:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e8f6f5] text-[#087f83]">
                <User size={16} aria-hidden="true" />
              </div>
              <div className="leading-tight">
                <div className="max-w-[180px] truncate text-xs font-bold text-slate-800">{currentUser.full_name || currentUser.username}</div>
                <div className="mt-0.5 text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-500">{currentUser.role}</div>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50 hover:text-[#102a43]"
              aria-label="Sign out"
            >
              <LogOut size={16} aria-hidden="true" /> <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="pb-20 lg:pb-0">
        <div key={`${activeView}-${selectedInspectionId || 'register'}`} className="portal-view">
          {activeView === 'dashboard' && <Dashboard onStartNew={handleStartNewInspection} onOpenInspection={handleOpenInspection} onNavigateToHistory={handleNavigateToHistory} />}
          {activeView === 'history' && <InspectionHistory onOpenInspection={handleOpenInspection} onStartNew={handleStartNewInspection} initialFilters={historyFilters} />}
          {activeView === 'reports' && <InspectionHistory onOpenInspection={handleOpenInspection} onStartNew={handleStartNewInspection} initialFilters={{ lifecycle_status: 'FINALIZED' }} reportsOnly />}
          {activeView === 'multi-view' && (
            <MultiViewInspection
              initialInspectionId={selectedInspectionId}
              onInspectionStarted={setSelectedInspectionId}
              onBackToHistory={() => navigate('history')}
              onOpenInspection={handleOpenInspection}
              onPrepareCase={(inspectionId) => { setSelectedInspectionId(inspectionId); setActiveView('prepare-case'); }}
            />
          )}
          {activeView === 'prepare-case' && <PrepareCase inspectionId={selectedInspectionId} onBack={() => setActiveView('multi-view')} externalPortalUrl={EXTERNAL_PORTAL_URL} />}
          {activeView === 'rule-library' && <RuleLibrary />}
        </div>
      </main>

      <nav className="fixed inset-x-3 bottom-3 z-50 grid grid-cols-5 rounded-2xl border border-slate-200 bg-white/95 px-1.5 py-1.5 shadow-[0_10px_35px_rgba(16,42,67,0.16)] backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
        {NAV_ITEMS.map(({ id, mobileLabel, icon: Icon }) => {
          const active = activeView === id || (id === 'multi-view' && activeView === 'prepare-case');
          return (
            <button key={id} type="button" onClick={() => id === 'multi-view' ? handleStartNewInspection() : navigate(id)} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[11px] font-semibold ${active ? 'bg-[#e8f6f5] text-[#087f83]' : 'text-slate-500 hover:bg-slate-50 hover:text-[#102a43]'}`} aria-current={active ? 'page' : undefined}>
              <Icon size={18} aria-hidden="true" /> {mobileLabel}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

export default App;
