import { API_BASE_URL } from '../config';

export interface ChatSession {
  id: string;
  title: string;
  workspaceId: string;
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

export interface Artifact {
  type: 'task_list' | 'project_summary' | 'analysis' | 'plan_draft';
  data: unknown;
}

export type StreamEvent =
  | { type: 'chunk'; content: string; node: string }
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

export async function createChatSession(workspaceId: string): Promise<ChatSession> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ workspace_id: workspaceId }),
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
  workspaceId: string
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content, workspace_id: workspaceId }),
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
