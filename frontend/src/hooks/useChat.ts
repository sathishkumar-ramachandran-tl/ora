import { useState, useCallback, useRef } from 'react';
import {
  ChatSession, ChatMessage, StreamEvent,
  createChatSession, listChatSessions, getChatSession,
  deleteChatSession, streamMessage
} from '../api/chat';

export interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
  toolCalls?: Array<{ name: string; status: 'running' | 'done' | 'error'; result?: unknown }>;
  node?: string;
  timestamp: Date;
}

interface UseChatState {
  sessions: ChatSession[];
  activeSession: ChatSession | null;
  messages: UIMessage[];
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
}

export function useChat(workspaceId: string) {
  const [state, setState] = useState<UseChatState>({
    sessions: [],
    activeSession: null,
    messages: [],
    isLoading: false,
    isSending: false,
    error: null,
  });

  const abortRef = useRef<(() => void) | null>(null);

  // -------------------------------------------------------------------------
  // Load sessions list
  // -------------------------------------------------------------------------
  const loadSessions = useCallback(async () => {
    if (!workspaceId) return;
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const sessions = await listChatSessions(workspaceId);
      setState(s => ({ ...s, sessions, isLoading: false }));
    } catch (e: any) {
      setState(s => ({ ...s, isLoading: false, error: e.message }));
    }
  }, [workspaceId]);

  // -------------------------------------------------------------------------
  // Start a new chat session
  // -------------------------------------------------------------------------
  const startNewSession = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const session = await createChatSession(workspaceId);
      setState(s => ({
        ...s,
        sessions: [session, ...s.sessions],
        activeSession: session,
        messages: [],
        isLoading: false
      }));
      return session;
    } catch (e: any) {
      setState(s => ({ ...s, isLoading: false, error: e.message }));
      return null;
    }
  }, [workspaceId]);

  // -------------------------------------------------------------------------
  // Load an existing session (restore history)
  // -------------------------------------------------------------------------
  const loadSession = useCallback(async (sessionId: string) => {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const data = await getChatSession(sessionId);
      const uiMessages: UIMessage[] = (data.messages || []).map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: new Date(m.createdAt),
        toolCalls: (m.metadata?.toolCalls || []).map(tc => ({
          name: tc.name,
          status: tc.status as 'running' | 'done' | 'error',
          result: tc.result
        }))
      }));
      setState(s => ({
        ...s,
        activeSession: { id: data.id, title: data.title, workspaceId: data.workspaceId, createdAt: data.createdAt, updatedAt: data.updatedAt },
        messages: uiMessages,
        isLoading: false
      }));
    } catch (e: any) {
      setState(s => ({ ...s, isLoading: false, error: e.message }));
    }
  }, []);

  // -------------------------------------------------------------------------
  // Delete session
  // -------------------------------------------------------------------------
  const removeSession = useCallback(async (sessionId: string) => {
    await deleteChatSession(sessionId);
    setState(s => ({
      ...s,
      sessions: s.sessions.filter(sess => sess.id !== sessionId),
      activeSession: s.activeSession?.id === sessionId ? null : s.activeSession,
      messages: s.activeSession?.id === sessionId ? [] : s.messages
    }));
  }, []);

  // -------------------------------------------------------------------------
  // Send message with SSE streaming
  // -------------------------------------------------------------------------
  const sendMessage = useCallback(async (content: string) => {
    if (state.isSending || !content.trim()) return;

    let session = state.activeSession;
    if (!session) {
      session = await startNewSession();
      if (!session) return;
    }

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    // Add user message immediately
    setState(s => ({
      ...s,
      isSending: true,
      error: null,
      messages: [
        ...s.messages,
        {
          id: userMsgId,
          role: 'user',
          content,
          timestamp: new Date()
        },
        {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          streaming: true,
          toolCalls: [],
          timestamp: new Date()
        }
      ]
    }));

    let cancelled = false;
    abortRef.current = () => { cancelled = true; };

    try {
      for await (const event of streamMessage(session.id, content, workspaceId)) {
        if (cancelled) break;

        setState(s => {
          const msgs = [...s.messages];
          const idx = msgs.findIndex(m => m.id === assistantMsgId);
          if (idx === -1) return s;

          const msg = { ...msgs[idx] };

          if (event.type === 'chunk') {
            msg.content += event.content;
            msg.node = event.node;
          } else if (event.type === 'tool_call') {
            msg.toolCalls = [
              ...(msg.toolCalls || []),
              { name: event.name, status: 'running' }
            ];
          } else if (event.type === 'tool_result') {
            msg.toolCalls = (msg.toolCalls || []).map(tc =>
              tc.name === event.name ? { ...tc, status: 'done', result: event.result } : tc
            );
          } else if (event.type === 'done') {
            msg.streaming = false;
          } else if (event.type === 'error') {
            msg.content = `Error: ${event.message}`;
            msg.streaming = false;
          }

          msgs[idx] = msg;
          return { ...s, messages: msgs };
        });
      }
    } catch (e: any) {
      setState(s => {
        const msgs = [...s.messages];
        const idx = msgs.findIndex(m => m.id === assistantMsgId);
        if (idx !== -1) {
          msgs[idx] = { ...msgs[idx], content: `Error: ${e.message}`, streaming: false };
        }
        return { ...s, messages: msgs, error: e.message };
      });
    } finally {
      setState(s => ({ ...s, isSending: false }));
      abortRef.current = null;
    }
  }, [state.isSending, state.activeSession, startNewSession, workspaceId]);

  const cancelStream = useCallback(() => {
    abortRef.current?.();
  }, []);

  return {
    ...state,
    loadSessions,
    startNewSession,
    loadSession,
    removeSession,
    sendMessage,
    cancelStream,
  };
}
