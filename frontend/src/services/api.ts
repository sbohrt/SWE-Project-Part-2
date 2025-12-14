import axios from 'axios';

// Get the API base URL from environment or default to localhost
// REACT_APP_API_URL should be the root API Gateway URL (e.g., https://xxx.execute-api.region.amazonaws.com/Prod)
const envUrl = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// Derive root and /api/v1 base URLs
// If the URL ends with /Prod or /Prod/, use that as root and append /api/v1
// Otherwise use it as-is for /api/v1 and strip /api/v1 for root
let ROOT_URL = envUrl.replace(/\/+$/, ''); // Remove trailing slashes
let API_BASE_URL = ROOT_URL;

if (ROOT_URL.endsWith('/api/v1')) {
  // URL already has /api/v1, use it as-is
  API_BASE_URL = ROOT_URL;
  ROOT_URL = ROOT_URL.replace(/\/api\/v1$/, '');
} else {
  // URL is root (e.g., .../Prod), append /api/v1 for API calls
  API_BASE_URL = ROOT_URL + '/api/v1';
}

// Main API client for /api/v1 endpoints
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Root API client for endpoints at root level (e.g., /artifact/model/{id}/lineage)
export const rootApi = axios.create({
  baseURL: ROOT_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for auth if needed later
api.interceptors.request.use((config) => {
  // Future: Add auth token here
  return config;
});

rootApi.interceptors.request.use((config) => {
  return config;
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

rootApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('Root API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);