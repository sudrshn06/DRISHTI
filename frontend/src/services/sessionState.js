const SESSION_USER_KEY = 'drishti_session_user';
const WORKSPACE_KEY = 'drishti_active_workspace';
const DEFAULT_WORKSPACE = {
  activeView: 'dashboard',
  selectedInspectionId: null,
};
const RESTORABLE_VIEWS = new Set([
  'dashboard',
  'multi-view',
  'prepare-case',
  'history',
  'reports',
  'rule-library',
]);

const sessionStorageForBrowser = () => window.sessionStorage;

export const readSessionUser = (storage = sessionStorageForBrowser()) => {
  try {
    const value = storage.getItem(SESSION_USER_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
};

export const saveSessionUser = (user, storage = sessionStorageForBrowser()) => {
  try {
    storage.setItem(SESSION_USER_KEY, JSON.stringify(user));
  } catch {
    // A valid token remains authoritative when session storage is unavailable.
  }
};

export const readWorkspaceState = (storage = sessionStorageForBrowser()) => {
  try {
    const saved = JSON.parse(storage.getItem(WORKSPACE_KEY) || 'null');
    if (!saved || !RESTORABLE_VIEWS.has(saved.activeView)) return { ...DEFAULT_WORKSPACE };
    return {
      activeView: saved.activeView,
      selectedInspectionId: typeof saved.selectedInspectionId === 'string'
        ? saved.selectedInspectionId
        : null,
    };
  } catch {
    return { ...DEFAULT_WORKSPACE };
  }
};

export const saveWorkspaceState = (workspace, storage = sessionStorageForBrowser()) => {
  try {
    storage.setItem(WORKSPACE_KEY, JSON.stringify({
      activeView: RESTORABLE_VIEWS.has(workspace.activeView)
        ? workspace.activeView
        : DEFAULT_WORKSPACE.activeView,
      selectedInspectionId: typeof workspace.selectedInspectionId === 'string'
        ? workspace.selectedInspectionId
        : null,
    }));
  } catch {
    // The server inspection remains authoritative if session storage is unavailable.
  }
};

export const clearSessionState = (storage = sessionStorageForBrowser()) => {
  try {
    storage.removeItem(SESSION_USER_KEY);
    storage.removeItem(WORKSPACE_KEY);
  } catch {
    // Logout still removes the authoritative JWT even if session storage is unavailable.
  }
};

export const isExplicitAuthRejection = (error) => (
  error?.response?.status === 401 || error?.response?.status === 403
);

export const createSessionRevalidator = (loadCurrentUser, timeoutMs = 12000) => {
  let inFlight = null;

  return () => {
    if (inFlight) return inFlight;

    let timeoutId;
    const timeout = new Promise((_, reject) => {
      timeoutId = setTimeout(() => reject(new Error('Secure session check timed out')), timeoutMs);
    });

    inFlight = Promise.race([
      Promise.resolve().then(loadCurrentUser),
      timeout,
    ]).finally(() => {
      clearTimeout(timeoutId);
      inFlight = null;
    });

    return inFlight;
  };
};

