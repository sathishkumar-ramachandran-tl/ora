import { API_BASE_URL } from '../config';

export interface ChatSession {
  id: string;
  title: string;
  workspaceId: string;
  scopeLevel?: ChatScopeLevel;
  scopeProjectId?: string | null;
  scopeTaskId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant';
  content: string;
  metadata: {
    agentType?: string;
    toolCalls?: ToolCallEvent[];
    artifacts?: Artifact[];
  };
  createdAt: string;
}

export interface ToolCallEvent {
  name: string;
  status: 'running' | 'done' | 'error';
  result?: unknown;
}

export type ChatScopeLevel = 'workspace' | 'project' | 'task';

export interface ChatScope {
  level: ChatScopeLevel;
  projectId?: string | null;
  taskId?: string | null;
  label?: string;
}

export interface AgentActionEvent {
  id: string;
  runId?: string;
  actionType: string;
  resourceType?: string;
  resourceId?: string;
  status: 'PROPOSED' | 'WAITING_FOR_CONFIRMATION' | 'APPROVED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'UNKNOWN' | 'SKIPPED';
  riskLevel?: 'LOW' | 'MEDIUM' | 'HIGH';
  confirmationRequired?: boolean;
  reversible?: boolean;
  undoStatus?: string | null;
  undoActionId?: string | null;
  proposedArgs?: Record<string, unknown>;
  afterState?: Record<string, unknown>;
}

export interface ScheduleProposal {
  id: string;
  runId?: string;
  workspaceId: string;
  status: string;
  version: number;
  windowStart: string;
  windowEnd: string;
  timezone: string;
  constraints: Array<Record<string, unknown>>;
  sessions: Array<{
    session_ref: string;
    task_id?: string;
    title: string;
    start_at: string;
    end_at: string;
    duration_minutes: number;
    reason?: string;
    fixed?: boolean;
    flexible?: boolean;
    event_id?: string;
  }>;
  summary: Record<string, unknown> & {
    sessionCount?: number;
    requiredMinutes?: number;
    availableMinutes?: number;
    unscheduled?: Array<Record<string, unknown>>;
    title?: string;
  };
  compiledActions?: Array<Record<string, unknown>>;
  applicationResult?: { successes?: number; failures?: number; unknown?: number; skipped?: number };
  appliedActionId?: string | null;
  supersedesId?: string | null;
  revisionReason?: string | null;
}

export interface PlanProposal {
  id: string;
  runId?: string;
  workspaceId: string;
  scope: { level: ChatScopeLevel; projectId?: string | null; taskId?: string | null };
  title: string;
  goal: string;
  status: string;
  version: number;
  qualityStatus: 'UNREVIEWED' | 'PASS' | 'WARNING' | 'FAIL';
  summary: { phaseCount: number; taskCount: number; estimatedEffortHours?: number };
  content: {
    title?: string;
    description?: string;
    metadata?: Record<string, unknown>;
    phases?: Array<{
      id: string;
      title: string;
      description?: string;
      sequence?: number;
      target?: string;
      concepts?: Array<{
        key?: string;
        name?: string;
        source_ids?: string[];
        rationale?: string[];
      }>;
      expected_outcomes?: string[];
      tasks?: Array<{
        id: string;
        title: string;
        description?: string;
        estimated_hours?: number;
        priority?: string;
      }>;
    }>;
    differential?: {
      builds_on?: Array<{ concept_name?: string; concept_key?: string }>;
      deepens?: Array<{ concept_name?: string; concept_key?: string }>;
      adds?: Array<{ concept_name?: string; concept_key?: string }>;
      reviews?: Array<{ concept_name?: string; concept_key?: string }>;
      skipped_as_duplicate?: Array<{ concept_name?: string; concept_key?: string }>;
      research_backed?: Array<{ concept_name?: string; concept_key?: string; source_ids?: string[] }>;
    };
  };
  planningContext?: Record<string, unknown> & {
    research?: {
      evidence_count?: number;
      evidence?: Array<{ id: string; title: string; source_url?: string | null }>;
    };
  };
  qualityReport?: { status: string; findings: Array<{ dimension: string; severity: string; message: string }> };
  duplicationReport?: Record<string, unknown>;
  compiledActions?: Array<Record<string, unknown>>;
  applicationResult?: { successes?: number; failures?: number; unknown?: number; skipped?: number };
  appliedActionId?: string | null;
}

export interface Artifact {
  type: 'task_list' | 'project_summary' | 'analysis' | 'plan_draft';
  data: unknown;
}

export type StreamEvent =
  | { type: 'agent_run_started'; runId: string }
  | { type: 'chunk'; content: string; node: string }
  | { type: 'action_proposed'; action: AgentActionEvent }
  | { type: 'action_started'; action: AgentActionEvent }
  | { type: 'action_completed'; action: AgentActionEvent }
  | { type: 'action_failed'; action: AgentActionEvent }
  | { type: 'confirmation_required'; action: AgentActionEvent }
  | { type: 'plan_proposed'; plan: PlanProposal }
  | { type: 'plan_updated'; plan: PlanProposal }
  | { type: 'plan_applied'; plan: PlanProposal }
  | { type: 'schedule_proposed'; schedule: ScheduleProposal }
  | { type: 'schedule_updated'; schedule: ScheduleProposal }
  | { type: 'schedule_applied'; schedule: ScheduleProposal }
  | { type: 'agent_run_completed'; runId: string; status: string }
  | { type: 'tool_call'; name: string; status: 'running' }
  | { type: 'tool_result'; name: string; result: unknown }
  | { type: 'done'; message_id: string }
  | { type: 'error'; message: string };

function getToken(): string {
  return localStorage.getItem('ora_auth_token') || '';
}

function authHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
  };
}

const BASE = `${API_BASE_URL}/api/v1/chat`;

// ---------------------------------------------------------------------------
// Session Management
// ---------------------------------------------------------------------------

export async function createChatSession(workspaceId: string, scope?: ChatScope): Promise<ChatSession> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      workspace_id: workspaceId,
      scope_level: scope?.level,
      scope_project_id: scope?.projectId,
      scope_task_id: scope?.taskId,
    }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function listChatSessions(workspaceId: string): Promise<ChatSession[]> {
  const res = await fetch(`${BASE}/sessions?workspace_id=${workspaceId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`);
  return res.json();
}

export async function getChatSession(
  sessionId: string
): Promise<ChatSession & { messages: ChatMessage[] }> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
  return res.json();
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

// ---------------------------------------------------------------------------
// Streaming Message Send
// ---------------------------------------------------------------------------

/**
 * Send a message and yield SSE events as they stream in.
 * Usage:
 *   for await (const event of streamMessage(sessionId, content, workspaceId)) { ... }
 */
export async function* streamMessage(
  sessionId: string,
  content: string,
  workspaceId: string,
  scope?: ChatScope
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      content,
      workspace_id: workspaceId,
      scope_level: scope?.level,
      scope_project_id: scope?.projectId,
      scope_task_id: scope?.taskId,
    }),
  });

  if (!res.ok) {
    yield { type: 'error', message: `HTTP ${res.status}: ${res.statusText}` };
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    yield { type: 'error', message: 'No response body' };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        const raw = trimmed.slice(6).trim();
        if (!raw || raw === '[DONE]') continue;
        try {
          yield JSON.parse(raw) as StreamEvent;
        } catch {
          // malformed line — skip
        }
      }
    }
  } finally {
    reader.cancel();
  }
}

export async function applyPlanProposal(planId: string): Promise<PlanProposal> {
  const res = await fetch(`${API_BASE_URL}/api/v1/plans/${planId}/apply`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ approved: true }),
  });
  if (!res.ok) throw new Error(`Failed to apply plan: ${res.status}`);
  return res.json();
}

export async function undoAgentAction(actionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE_URL}/api/v1/agents/actions/${actionId}/undo`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to undo action: ${res.status}`);
  return res.json();
}
