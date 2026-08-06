import { apiClient } from './client';
import { Company, LogEntry, Note, User, Workspace } from '../types';

export const getUserWorkspaces = async (userId: string): Promise<Workspace[]> => {
  const res = await apiClient.get<Workspace[]>(`/users/${userId}/workspaces`);
  return res.data;
};

export const createWorkspace = async (
  userId: string,
  name: string,
  context: 'personal' | 'company',
  persona = 'general',
  organizationId?: string
): Promise<Workspace> => {
  const res = await apiClient.post('/workspaces', {
    workspace: {
      id: crypto.randomUUID(),
      name,
      context,
      type: context === 'personal' ? 'study' : 'project',
      persona,
      organizationId,
    },
    userId
  });
  return res.data;
};

export const fetchFullState = async (workspaceId: string): Promise<Company[]> => {
  try {
    const res = await apiClient.get(`/workspaces/${workspaceId}/full-state`);
    return res.data;
  } catch (err) {
    console.error('API Fetch Error', err);
    return [];
  }
};

export const getWorkspaceMembers = async (workspaceId: string): Promise<User[]> => {
  const res = await apiClient.get(`/workspaces/${workspaceId}/members`);
  return res.data;
};

export const addMemberToWorkspace = async (workspaceId: string, userEmail: string, roleId: string): Promise<User | null> => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/invite`, { email: userEmail, role: roleId });
  return res.data;
};

export const removeWorkspaceMember = async (workspaceId: string, memberId: string): Promise<void> => {
  await apiClient.delete(`/workspaces/${workspaceId}/members/${memberId}`);
};

// --- Notes & Incubator ---

export const createNote = async (note: Note): Promise<void> => {
  await apiClient.post(`/workspaces/${note.workspaceId}/notes`, note);
};

export const getNotes = async (workspaceId: string, contextId?: string): Promise<Note[]> => {
  const params: any = {};
  if (contextId) params.contextId = contextId;

  const res = await apiClient.get(`/workspaces/${workspaceId}/notes`, { params });
  return res.data.map((n: any) => ({
    ...n,
    createdAt: new Date(n.createdAt)
  }));
};

export const deleteNote = async (noteId: string): Promise<void> => {
  await apiClient.delete(`/notes/${noteId}`);
};

// --- Analytics ---

export const logEvent = async (event: LogEntry): Promise<void> => {
  // Fire and forget
  apiClient.post('/analytics/event', event).catch(() => {});
};
