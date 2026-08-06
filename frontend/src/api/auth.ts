import { apiClient } from './client';
import { API_BASE_URL } from '../config';
import { User } from '../types';

export const register = async (email: string, password: string, name?: string): Promise<{ token: string; user: User }> => {
  const res = await apiClient.post<{ token: string; user: User }>('/auth/register', { email, password, name });
  return res.data;
};

export const login = async (email: string, password: string): Promise<{ token: string; user: User }> => {
  const res = await apiClient.post<{ token: string; user: User }>('/auth/login', { email, password });
  return res.data;
};

export const verifyEmailCode = async (code: string): Promise<User> => {
  const res = await apiClient.post<{ user: User }>('/auth/verify-email', { code });
  return res.data.user;
};

export const resendVerification = async (): Promise<void> => {
  await apiClient.post('/auth/resend-verification');
};

export const forgotPassword = async (email: string): Promise<void> => {
  await apiClient.post('/auth/forgot-password', { email });
};

export const resetPassword = async (token: string, password: string): Promise<void> => {
  await apiClient.post('/auth/reset-password', { token, password });
};

export const oauthLoginUrl = (provider: 'google' | 'microsoft'): string =>
  `${API_BASE_URL}/api/v1/auth/oauth/${provider}/login`;

export const updateProfile = async (data: Partial<User>): Promise<User> => {
  const res = await apiClient.post('/auth/update-profile', data);
  return res.data.user;
};

export const getCurrentUser = async (): Promise<User> => {
  const res = await apiClient.get<User>('/auth/me');
  return res.data;
};
