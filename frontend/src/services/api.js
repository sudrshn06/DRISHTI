import axios from 'axios';

const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000/api`;

const api = axios.create({
  baseURL,
});

// Attach Authorization header automatically if JWT token is stored in localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('drishti_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const analyzeImage = async (file) => {
  const formData = new FormData();
  formData.append('image', file);
  
  const response = await api.post('/ocr/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const startInspection = async (data) => {
  const formData = new URLSearchParams();
  formData.append('reference_date', data.reference_date);
  formData.append('product_category', data.product_category);
  formData.append('capture_plan_id', data.capture_plan_id);

  const response = await api.post('/inspections', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const getInspection = async (inspectionId) => {
  const response = await api.get(`/inspections/${inspectionId}`);
  return response.data;
};

export const getWorkflowSummary = async (inspectionId) => {
  const response = await api.get(`/inspections/${inspectionId}/workflow`);
  return response.data;
};

export const finalizeInspection = async (inspectionId) => {
  const response = await api.post(`/inspections/${inspectionId}/finalize`);
  return response.data;
};

export const uploadCapture = async (inspectionId, viewId, file) => {
  const formData = new FormData();
  formData.append('view_id', viewId);
  formData.append('image', file);
  
  const response = await api.post(`/inspections/${inspectionId}/captures`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getCaptureImage = async (inspectionId, captureId) => {
  const response = await api.get(
    `/inspections/${inspectionId}/captures/${captureId}/image`,
    { responseType: 'blob' },
  );
  return response.data instanceof Blob
    ? response.data
    : new Blob([response.data], { type: response.headers['content-type'] || 'image/jpeg' });
};

export const confirmPackageInformation = async (inspectionId) => {
  const response = await api.post(`/inspections/${inspectionId}/package-information/review`);
  return response.data;
};

export const correctDeclaration = async (inspectionId, correction) => {
  const response = await api.post(`/inspections/${inspectionId}/declaration-corrections`, correction);
  return response.data;
};

export const updateInspectionContext = async (inspectionId, contextData) => {
  const response = await api.put(`/inspections/${inspectionId}/context`, contextData);
  return response.data;
};

export const getActivePlan = async () => {
  const response = await api.get('/inspections/plans/active');
  return response.data;
};

export const getReport = async (inspectionId) => {
  const response = await api.get(`/inspections/${inspectionId}/report`);
  return response.data;
};

export const downloadReportPdf = async (inspectionId, filename = null) => {
  const response = await api.get(`/inspections/${inspectionId}/report.pdf`, {
    responseType: 'blob',
  });
  const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'application/pdf' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename || 'DRISHTI_Inspection_Report.pdf');
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    try {
      if (document.body.contains(link)) {
        document.body.removeChild(link);
      }
      window.URL.revokeObjectURL(url);
    } catch {}
  }, 1000);
};

export const downloadReportDocx = async (inspectionId, filename = null) => {
  const response = await api.get(`/inspections/${inspectionId}/report.docx`, {
    responseType: 'blob',
  });
  const blob = response.data instanceof Blob ? response.data : new Blob([response.data], {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename || 'DRISHTI_Inspection_Report.docx');
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    try {
      if (document.body.contains(link)) {
        document.body.removeChild(link);
      }
      window.URL.revokeObjectURL(url);
    } catch {}
  }, 1000);
};

export const getInspectionHistory = async (params = {}) => {
  const cleanParams = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value;
    }
  }
  const response = await api.get('/inspections', { params: cleanParams });
  return response.data;
};

export const getDashboardSummary = async () => {
  const response = await api.get('/dashboard');
  return response.data;
};

export const registerUser = async ({ username, email, full_name, password }) => {
  const response = await api.post('/auth/register', {
    username,
    email,
    full_name,
    password,
  });
  return response.data;
};

export const loginUser = async ({ username, password }) => {
  const response = await api.post('/auth/login', { username, password });
  if (response.data?.access_token) {
    localStorage.setItem('drishti_token', response.data.access_token);
  }
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const logoutUser = () => {
  localStorage.removeItem('drishti_token');
};

export const downloadEvidencePackage = async (inspectionId, payload, filename = null) => {
  const response = await api.post(`/inspections/${inspectionId}/evidence_package`, payload, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data], { type: 'application/zip' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename || 'DRISHTI_Evidence_Package.zip');
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    try {
      if (document.body.contains(link)) {
        document.body.removeChild(link);
      }
      window.URL.revokeObjectURL(url);
    } catch {}
  }, 1000);
};

export const getGroundedExplanation = async (query, domain, referenceDate) => {
  const response = await api.post('/rag/explain', {
    query,
    domain,
    reference_date: referenceDate
  });
  return response.data;
};

export const getRuleLibrary = async (params = {}) => {
  const cleanParams = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value;
    }
  }
  const response = await api.get('/rag/rules', { params: cleanParams });
  return response.data;
};

export const reindexCorpus = async () => {
  const response = await api.post('/rag/reindex');
  return response.data;
};

export default api;
