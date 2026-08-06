import { apiV2Client } from './client';

export interface Organization {
    id: string;
    name: string;
    domain?: string;
    role: 'owner' | 'admin' | 'member';
}

export interface OrgMember {
    id: string; // User ID
    name: string;
    email: string;
    role: 'owner' | 'admin' | 'member';
    customRoleId?: string | null;
    status: 'active' | 'invited' | 'suspended';
    joinedAt: string;
    permissions: string[];
}

export interface OrgDashboardStats {
    totalMembers: number;
    totalWorkspaces: number;
    activeProjects: number;
}

export interface CustomRole {
    id: string;
    name: string;
    color: string;
    permissions: string[];
    isSystem: boolean;
}

export interface PermissionCatalogEntry {
    key: string;
    description: string;
}

// --- Organizations ---

export const createOrganization = async (name: string, domain?: string): Promise<{ id: string; name: string; role: string }> => {
    const res = await apiV2Client.post('orgs/', { name, domain });
    return res.data.organization;
};

export const getMyOrganizations = async (): Promise<Organization[]> => {
    const res = await apiV2Client.get<Organization[]>('orgs/');
    return res.data;
};

export const updateOrganization = async (orgId: string, data: { name?: string; domain?: string }) => {
    await apiV2Client.patch(`orgs/${orgId}`, data);
};

// --- Dashboard & Members ---

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

export const updateMemberRole = async (orgId: string, userId: string, data: { role?: string; customRoleId?: string | null }) => {
    await apiV2Client.put(`orgs/${orgId}/members/${userId}`, data);
};

export const removeMember = async (orgId: string, userId: string) => {
    await apiV2Client.delete(`orgs/${orgId}/members/${userId}`);
};

// --- Granular RBAC ---

export const getPermissionCatalog = async (orgId: string): Promise<PermissionCatalogEntry[]> => {
    const res = await apiV2Client.get(`orgs/${orgId}/permissions`);
    return res.data;
};

export const getRoles = async (orgId: string): Promise<CustomRole[]> => {
    const res = await apiV2Client.get(`orgs/${orgId}/roles`);
    return res.data;
};

export const createRole = async (orgId: string, name: string, permissions: string[], color = 'indigo'): Promise<CustomRole> => {
    const res = await apiV2Client.post(`orgs/${orgId}/roles`, { name, permissions, color });
    return res.data;
};

export const updateRole = async (orgId: string, roleId: string, data: { name?: string; permissions?: string[]; color?: string }): Promise<CustomRole> => {
    const res = await apiV2Client.patch(`orgs/${orgId}/roles/${roleId}`, data);
    return res.data;
};

export const deleteRole = async (orgId: string, roleId: string) => {
    await apiV2Client.delete(`orgs/${orgId}/roles/${roleId}`);
};
