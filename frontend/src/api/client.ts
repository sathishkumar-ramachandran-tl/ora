import axios from 'axios';
import { API_BASE_URL } from '../config';

// Primary API Client for Backend Communication
export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`, 
});

// V2 Client for Enterprise/Org specific routes
export const apiV2Client = axios.create({
    baseURL: `${API_BASE_URL}/api/v2`, 
});

// Request Interceptor: Attach Token
const attachToken = (config: any) => {
    const token = localStorage.getItem('ora_auth_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
};

// Response Interceptor: Handle Auth Failures
const handleAuthError = (error: any) => {
    if (error.response && error.response.status === 401) {
        // Only treat this as an expired/invalid session if the request actually carried
        // a bearer token — a 401 from an unauthenticated call (e.g. wrong-password login)
        // means "rejected", not "session expired", and shouldn't force-navigate the page.
        const hadToken = !!error.config?.headers?.Authorization;
        if (hadToken) {
            localStorage.removeItem('ora_auth_token');
            localStorage.removeItem('ora_user_id');
            window.location.href = '/';
        }
    }
    return Promise.reject(error);
};

apiClient.interceptors.request.use(attachToken);
apiClient.interceptors.response.use((r) => r, handleAuthError);

apiV2Client.interceptors.request.use(attachToken);
apiV2Client.interceptors.response.use((r) => r, handleAuthError);
