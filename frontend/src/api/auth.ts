import { apiClient } from './client';
import { User, Workspace } from '../types';

export const authApi = {
    requestOtp: async (email: string) => {
        return apiClient.post('/auth/request-otp', { email });
    },

    verifyOtp: async (email: string, code: string) => {
        const res = await apiClient.post<{ token: string, user: User }>('/auth/verify-otp', { email, code });
        return res.data;
    },

    checkUser: async (email: string) => {
        const res = await apiClient.post('/auth/check-user', { email });
        return res.data; // { exists: boolean, user?: partialUser }
    },

    updateProfile: async (data: Partial<User>) => {
        const res = await apiClient.post('/auth/update-profile', data);
        return res.data;
    },

    getCurrentUser: async () => {
        const res = await apiClient.get<User>('/auth/me');
        return res.data;
    }
};

export const workspaceApi = {
    getUserWorkspaces: async (userId: string) => {
        const res = await apiClient.get<Workspace[]>(`/users/${userId}/workspaces`);
        return res.data;
    },

    createWorkspace: async (userId: string, name: string, context: 'personal' | 'company', persona = 'general') => {
        const res = await apiClient.post('/workspaces', {
            workspace: {
                id: crypto.randomUUID(),
                name,
                context,
                type: context === 'personal' ? 'study' : 'project',
                persona,
            },
            userId
        });
        return res.data;
    },

    getWorkspaceState: async (workspaceId: string) => {
        const res = await apiClient.get(`/workspaces/${workspaceId}/full-state`);
        return res.data;
    }
};
