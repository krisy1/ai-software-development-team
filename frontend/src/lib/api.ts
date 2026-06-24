import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const detail = error.response.data?.detail;
      const status = error.response.status;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.message || `Request failed with status ${status}`;
      return Promise.reject(new Error(msg));
    }
    if (error.request) {
      return Promise.reject(
        new Error('No response from server. Is the backend running?')
      );
    }
    return Promise.reject(error);
  }
);

export default api;
