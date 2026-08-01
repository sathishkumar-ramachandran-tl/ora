import axios from 'axios';
import { API_BASE_URL, getAuthHeader } from '../config';
import { Company, Project, Task, User, Workspace, Note, LogEntry, TaskResource, CanvasItem, CalendarEvent } from '../types';

// API Client Instance
const api = axios.create({
  baseURL: API_BASE_URL + '/api/v1',
});

// Interceptor to add token to every request
api.interceptors.request.use((config) => {
  const headersToAdd = getAuthHeader();
  if (headersToAdd.Authorization) {
    config.headers.set('Authorization', headersToAdd.Authorization);
  }
  return config;
});

// --- Identity & Auth ---

export const findUserByEmail = async (email: string): Promise<User | null> => {
  try {
    const res = await api.post('/auth/check-user', { email });
    return res.data.exists ? res.data.user : null;
  } catch (e) {
    return null;
  }
};

export const requestOtp = async (email: string): Promise<void> => {
  await api.post('/auth/request-otp', { email });
};

export const verifyOtp = async (email: string, code: string): Promise<{ token: string, user: User }> => {
  const res = await api.post('/auth/verify-otp', { email, code });
  return res.data;
};

export const updateProfile = async (profileData: Partial<User>): Promise<User> => {
    const res = await api.post('/auth/update-profile', profileData);
    return res.data.user;
};

export const getCurrentUser = async (): Promise<User> => {
    const res = await api.get('/auth/me');
    return res.data;
};

// --- Workspace & Data Fetching ---

export const initDB = async () => {
  // No-op for API client, but kept for compatibility with existing App.tsx calls
  console.log("Sindhai API Client Initialized");
};

export const fetchFullState = async (workspaceId: string): Promise<Company[]> => {
  try {
    const res = await api.get(`/workspaces/${workspaceId}/full-state`);
    return res.data;
  } catch (err) {
    console.error("API Fetch Error", err);
    return [];
  }
};

export const createWorkspace = async (ws: Workspace, userId: string): Promise<void> => {
  await api.post('/workspaces', { workspace: ws, userId });
};

export const createUser = async (user: User): Promise<void> => {
  await api.post('/users', user);
};

export const getUserWorkspaces = async (userId: string): Promise<Workspace[]> => {
  const res = await api.get(`/users/${userId}/workspaces`);
  return res.data;
};

export const getWorkspaceMembers = async (workspaceId: string): Promise<User[]> => {
  const res = await api.get(`/workspaces/${workspaceId}/members`);
  return res.data;
};

export const addMemberToWorkspace = async (workspaceId: string, userEmail: string, roleId: string): Promise<User | null> => {
  const res = await api.post(`/workspaces/${workspaceId}/invite`, { email: userEmail, role: roleId });
  return res.data;
};

export const removeWorkspaceMember = async (workspaceId: string, memberId: string): Promise<void> => {
  await api.delete(`/workspaces/${workspaceId}/members/${memberId}`);
};

// --- Project Member Management ---

export const getProjectMembers = async (projectId: string): Promise<User[]> => {
  const res = await api.get(`/projects/${projectId}/members`);
  return res.data;
};

export const assignUserToProject = async (projectId: string, userId: string, role: string = 'contributor'): Promise<any> => {
  const res = await api.post(`/projects/${projectId}/assign-member`, { userId, role });
  return res.data;
};

export const removeUserFromProject = async (projectId: string, memberId: string): Promise<void> => {
  await api.delete(`/projects/${projectId}/members/${memberId}`);
};

// --- Core Data Operations ---

export const createCompany = async (company: Company) => {
  await api.post(`/companies`, company);
};

export const createProject = async (project: Project, companyId: string) => {
  await api.post(`/companies/${companyId}/projects`, project);
};

export const addTasks = async (tasks: Task[], projectId: string) => {
  await api.post(`/projects/${projectId}/tasks`, { tasks });
};

export const updateTaskStatus = async (taskId: string, status: string) => {
  await api.patch(`/tasks/${taskId}`, { status });
};

export const updateTaskResources = async (taskId: string, resources: TaskResource[]) => {
  await api.patch(`/tasks/${taskId}`, { resources });
};

export const toggleTaskDailyFocus = async (taskId: string, isFocused: boolean) => {
  await api.patch(`/tasks/${taskId}`, { isDailyFocus: isFocused });
};

export const saveWhiteboard = async (contextType: 'company' | 'project', id: string, items: CanvasItem[]) => {
  const endpoint = contextType === 'company' ? 'companies' : 'projects';
  await api.patch(`/${endpoint}/${id}/whiteboard`, { items });
};

// --- Notes & Incubator ---

export const createNote = async (note: Note): Promise<void> => {
  await api.post(`/workspaces/${note.workspaceId}/notes`, note);
};

export const getNotes = async (workspaceId: string, contextId?: string): Promise<Note[]> => {
  const params: any = {};
  if (contextId) params.contextId = contextId;
  
  const res = await api.get(`/workspaces/${workspaceId}/notes`, { params });
  return res.data.map((n: any) => ({
    ...n,
    createdAt: new Date(n.createdAt)
  }));
};

export const deleteNote = async (noteId: string): Promise<void> => {
  await api.delete(`/notes/${noteId}`);
};

// --- Analytics ---

export const logEvent = async (event: LogEntry): Promise<void> => {
  // Fire and forget
  api.post('/analytics/event', event).catch(() => {});
};

// --- Calendar ---

export const getEvents = async (workspaceId: string, start?: Date, end?: Date): Promise<CalendarEvent[]> => {
  const params: any = {};
  if (start) params.start = start.toISOString();
  if (end) params.end = end.toISOString();
  const res = await api.get(`/workspaces/${workspaceId}/events`, { params });
  return res.data;
};

export const createEvent = async (workspaceId: string, event: Partial<CalendarEvent>) => {
  await api.post(`/workspaces/${workspaceId}/events`, event);
};

export const deleteEvent = async (eventId: string) => {
  await api.delete(`/events/${eventId}`);
};

export const optimizeSchedule = async (tasks: Task[], date: Date): Promise<CalendarEvent[]> => {
    // Call AI Agent
    const res = await api.post('/agents/optimize-schedule', { 
        tasks,
        date: date.toISOString().split('T')[0]
    });
    return res.data;
};
