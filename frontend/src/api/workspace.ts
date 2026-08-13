import { apiClient } from './client';
import { Company, LogEntry, Note, User, Workspace } from '../types';
import { PlanProposal, ScheduleProposal } from './chat';

export interface TodayCandidate {
  task_id: string;
  title: string;
  project_id?: string | null;
  project_name?: string | null;
  eligibility: string;
  blocked_by: Array<{ id: string; title: string }>;
  deadline?: string | null;
  priority?: string;
  estimated_effort_minutes: number;
  schedule_fit: string;
  mastery_reason?: string | null;
  plan_reason?: string | null;
  calendar_event_id?: string | null;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  session_status?: string | null;
  score: number;
  reasons: string[];
}

export interface WorkspaceHome {
  workspace: { id: string };
  today: {
    generated_at: string;
    availability: { minutes: number; source: string };
    now: TodayCandidate | null;
    next: TodayCandidate[];
    later_count: number;
    excluded_count: number;
    missed_sessions?: Array<{ id: string; task_id?: string; title: string; start?: string; end?: string }>;
    explanation: string[];
  };
  calendar: { event_count: number; busy_minutes: number; events: Array<Record<string, unknown>> };
  active_projects: Array<{ id: string; name: string; type?: string; progress?: number; task_count: number; done_count: number }>;
  pending_plan?: PlanProposal | null;
  pending_schedule?: ScheduleProposal | null;
  scheduling_metrics?: Record<string, number>;
  plan_health?: {
    status: 'HEALTHY' | 'AT_RISK' | 'REVISION_RECOMMENDED';
    reasons: string[];
    capacity?: Record<string, unknown>;
  };
  execution_signals?: Record<string, { count: number; affects: string[]; gap?: string }>;
  retrieval_benchmark?: {
    decision: string;
    results: Array<{ query: string; hit_count: number; vector_retrieval_justified: boolean | string }>;
  };
  pending_revision?: {
    id: string;
    base_plan_id: string;
    trigger: string;
    hard_constraints: Array<Record<string, unknown>>;
    operations: Array<Record<string, unknown>>;
    rationale?: string;
    status: string;
  } | null;
  alerts: Array<{ type: string; message: string }>;
}

export interface WorkspaceSearchResult {
  type: 'project' | 'task' | 'plan' | 'concept';
  id: string;
  title: string;
  subtitle?: string | null;
  scope?: Record<string, unknown>;
  conceptKey?: string;
}

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

export const fetchWorkspaceHome = async (
  workspaceId: string,
  options?: { availableMinutes?: number; exclude?: string[]; prefer?: string[] }
): Promise<WorkspaceHome> => {
  const params: Record<string, unknown> = {};
  if (options?.availableMinutes) params.availableMinutes = options.availableMinutes;
  if (options?.exclude) params.exclude = options.exclude;
  if (options?.prefer) params.prefer = options.prefer;
  const res = await apiClient.get(`/workspaces/${workspaceId}/home`, { params });
  return res.data;
};

export const createAssessmentEvidence = async (
  workspaceId: string,
  payload: {
    conceptName: string;
    domain?: string;
    evidenceType?: string;
    strength?: string;
    result: Record<string, unknown>;
  }
) => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/assessments`, payload);
  return res.data;
};

export const searchWorkspace = async (workspaceId: string, query: string): Promise<WorkspaceSearchResult[]> => {
  if (query.trim().length < 2) return [];
  const res = await apiClient.get(`/workspaces/${workspaceId}/search`, { params: { q: query } });
  return res.data.results || [];
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
