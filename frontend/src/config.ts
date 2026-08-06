// Centralized Configuration
const isDev = import.meta.env.DEV;

// FORCE empty string for dev to use proxy, unless explicitly overridden
export const API_BASE_URL = isDev
  ? ''  
  : (import.meta.env.VITE_API_BASE_URL || ''); 

export const getAuthHeader = () => {
  const token = localStorage.getItem('ora_auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

