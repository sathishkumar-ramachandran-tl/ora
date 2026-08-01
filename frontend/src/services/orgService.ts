import { apiV2Client } from '../api/client';
import { User, Organization } from '../types';

export interface OrgMember {
    id: string; // User ID
    name: string;
    email: string;
    role: 'owner' | 'admin' | 'member';
    status: 'active' | 'invited' | 'suspended';
    joinedAt: string;
}

export interface OrgDashboardStats {
    totalMembers: number;
    totalWorkspaces: number;
    activeProjects: number;
}

export const getOrgDashboard = async (orgId: string): Promise<{ stats: OrgDashboardStats; recentMembers: OrgMember[] }> => {
    const res = await apiV2Client.get(`orgs/${orgId}/dashboard`);
    return res.data;
};

export const getOrgMembers = async (orgId: string): Promise<OrgMember[]> => {
    const res = await apiV2Client.get(`orgs/${orgId}/members`);
    return res.data;
};

export const inviteMember = async (orgId: string, email: string, role: string) => {
    const res = await apiV2Client.post(`orgs/${orgId}/members`, { email, role });
    return res.data;
};

export const updateMemberRole = async (orgId: string, userId: string, role: string) => {
    const res = await apiV2Client.put(`orgs/${orgId}/members/${userId}`, { role });
    return res.data;
};
