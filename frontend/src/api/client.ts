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
    const token = localStorage.getItem('sindhai_auth_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
};

// Response Interceptor: Handle Auth Failures
const handleAuthError = (error: any) => {
    if (error.response && error.response.status === 401) {
        const url: string = error.config?.url || '';
        // Skip auto-logout for auth endpoints (OTP login flow — 401 there means wrong code, not expired session)
        const isAuthRoute = url.includes('/auth/request-otp') || url.includes('/auth/verify-otp') || url.includes('/auth/check-user');
        if (!isAuthRoute) {
            localStorage.removeItem('sindhai_auth_token');
            localStorage.removeItem('sindhai_user_id');
            window.location.href = '/';
        }
    }
    return Promise.reject(error);
};

apiClient.interceptors.request.use(attachToken);
apiClient.interceptors.response.use((r) => r, handleAuthError);

apiV2Client.interceptors.request.use(attachToken);
apiV2Client.interceptors.response.use((r) => r, handleAuthError);
