const DATABASE_NAME = 'drishti-field-work';
const DATABASE_VERSION = 1;
const STORE_NAME = 'pending-captures';

const openDatabase = () => new Promise((resolve, reject) => {
  if (!('indexedDB' in window)) {
    reject(new Error('Durable device storage is unavailable'));
    return;
  }
  const request = window.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
  request.onupgradeneeded = () => {
    const db = request.result;
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' });
      store.createIndex('inspectionId', 'inspectionId', { unique: false });
    }
  };
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error || new Error('Device storage could not be opened'));
});

const runTransaction = async (mode, operation) => {
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, mode);
      const store = transaction.objectStore(STORE_NAME);
      let requestResult;
      let requestError;
      let request;
      try {
        request = operation(store);
      } catch (error) {
        transaction.abort();
        reject(error);
        return;
      }
      request.onsuccess = () => {
        requestResult = request.result;
      };
      request.onerror = () => {
        requestError = request.error || new Error('Device storage operation failed');
      };
      transaction.oncomplete = () => resolve(requestResult);
      transaction.onerror = () => reject(
        transaction.error || requestError || new Error('Device storage transaction failed'),
      );
      transaction.onabort = () => reject(transaction.error || new Error('Device storage operation was cancelled'));
    });
  } finally {
    db.close();
  }
};

const pendingKey = (inspectionId, viewId) => `${inspectionId}:${viewId}`;

export const savePendingCapture = async (inspectionId, viewId, file) => {
  const record = {
    key: pendingKey(inspectionId, viewId),
    inspectionId,
    viewId,
    blob: file,
    name: file.name || `${viewId.toLowerCase()}-package-photo`,
    type: file.type || 'image/jpeg',
    lastModified: file.lastModified || Date.now(),
    queuedAt: new Date().toISOString(),
  };
  await runTransaction('readwrite', (store) => store.put(record));
  return record;
};

export const listPendingCaptures = async (inspectionId) => {
  const records = await runTransaction('readonly', (store) => (
    store.index('inspectionId').getAll(inspectionId)
  ));
  return (records || []).map((record) => ({
    ...record,
    file: new File([record.blob], record.name, {
      type: record.type,
      lastModified: record.lastModified,
    }),
  }));
};

export const removePendingCapture = async (inspectionId, viewId) => {
  await runTransaction('readwrite', (store) => store.delete(pendingKey(inspectionId, viewId)));
};
