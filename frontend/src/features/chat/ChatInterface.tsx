import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare, X, Send, Plus, Trash2, ChevronDown,
  Loader2, Bot, User, Wrench, CheckCircle, AlertCircle,
  Sparkles, MoreVertical, History, Minimize2, Maximize2
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useChat, UIMessage } from '../../hooks/useChat';
import { RichText } from '../../components/shared/RichText';

// ---------------------------------------------------------------------------
// Agent node → display label mapping
// ---------------------------------------------------------------------------
const NODE_LABELS: Record<string, { label: string; color: string }> = {
  query_agent: { label: 'Reading data…', color: 'text-blue-400' },
  crud_agent: { label: 'Executing…', color: 'text-emerald-400' },
  analysis_agent: { label: 'Analyzing…', color: 'text-purple-400' },
  planning_agent: { label: 'Planning…', color: 'text-amber-400' },
  router: { label: 'Routing…', color: 'text-slate-400' },
};

// ---------------------------------------------------------------------------
// Suggested prompts for empty state
// ---------------------------------------------------------------------------
const SUGGESTIONS = [
  { label: 'List pending tasks', prompt: 'Show me all my pending and in-progress tasks' },
  { label: 'Analyze workspace', prompt: 'Analyze my workspace and tell me what I should focus on this week' },
  { label: 'Create a task', prompt: 'Create a high priority task "Review design specs" in my first project' },
  { label: 'Plan a project', prompt: 'Help me plan a new mobile app project' },
  { label: 'Progress report', prompt: 'Give me a progress report on all my projects' },
  { label: 'Prioritize backlog', prompt: 'Order my backlog tasks by urgency and suggest which to tackle first' },
];

// ---------------------------------------------------------------------------
// Tool call pill component
// ---------------------------------------------------------------------------
const ToolPill: React.FC<{ name: string; status: 'running' | 'done' | 'error' | string }> = ({ name, status }) => (
  <div className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-mono transition-all
    ${status === 'running' ? 'bg-amber-900/40 text-amber-300 animate-pulse' :
      status === 'done' ? 'bg-emerald-900/40 text-emerald-300' :
      'bg-red-900/40 text-red-300'}`}>
    <Wrench size={10} />
    {name.replace(/_/g, ' ')}
    {status === 'running' && <Loader2 size={9} className="animate-spin" />}
    {status === 'done' && <CheckCircle size={9} />}
  </div>
);

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------
const MessageBubble: React.FC<{ msg: UIMessage }> = ({ msg }) => {
  const isUser = msg.role === 'user';
  const nodeInfo = msg.node ? NODE_LABELS[msg.node] : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} group`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5
        ${isUser ? 'bg-indigo-600' : 'bg-slate-700 border border-slate-600'}`}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-indigo-400" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] space-y-1.5 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        {/* Agent node label (only while streaming) */}
        {nodeInfo && msg.streaming && (
          <span className={`text-[10px] ${nodeInfo.color} font-medium`}>{nodeInfo.label}</span>
        )}

        {/* Tool call pills */}
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {msg.toolCalls.map((tc, i) => (
              <ToolPill key={i} name={tc.name} status={tc.status} />
            ))}
          </div>
        )}

        {/* Content bubble */}
        <div className={`rounded-2xl px-4 py-3 text-slate-100
          ${isUser
            ? 'bg-indigo-600 rounded-tr-sm'
            : 'bg-slate-800 border border-slate-700 rounded-tl-sm'}`}>
          {msg.content
            ? <RichText content={msg.content} />
            : msg.streaming
              ? <span className="flex items-center gap-2 text-slate-400 text-sm">
                  <Loader2 size={12} className="animate-spin" /> Thinking…
                </span>
              : <span className="text-slate-500 text-sm italic">Empty response</span>
          }
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity px-1">
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Session item in sidebar
// ---------------------------------------------------------------------------
const SessionItem: React.FC<{
  session: { id: string; title: string };
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}> = ({ session, active, onSelect, onDelete }) => (
  <div
    onClick={onSelect}
    className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer group transition-colors text-sm
      ${active ? 'bg-slate-700 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}>
    <MessageSquare size={14} className="flex-shrink-0" />
    <span className="truncate flex-1 text-xs">{session.title}</span>
    <button
      onClick={e => { e.stopPropagation(); onDelete(); }}
      className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all flex-shrink-0">
      <Trash2 size={12} />
    </button>
  </div>
);

// ---------------------------------------------------------------------------
// Main ChatInterface component
// ---------------------------------------------------------------------------
interface ChatInterfaceProps {
  workspaceId: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ workspaceId }) => {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    sessions, activeSession, messages, isLoading, isSending,
    loadSessions, startNewSession, loadSession, removeSession, sendMessage
  } = useChat(workspaceId);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load sessions when opening
  useEffect(() => {
    if (isOpen && workspaceId) {
      loadSessions();
    }
  }, [isOpen, workspaceId, loadSessions]);

  const handleOpen = useCallback(async () => {
    setIsOpen(true);
    if (!activeSession) {
      await startNewSession();
    }
  }, [activeSession, startNewSession]);

  const handleSend = useCallback(async () => {
    const content = inputValue.trim();
    if (!content || isSending) return;
    setInputValue('');
    await sendMessage(content);
  }, [inputValue, isSending, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestion = (prompt: string) => {
    setInputValue(prompt);
    inputRef.current?.focus();
  };

  const panelWidth = isExpanded ? 'w-full md:w-[700px]' : 'w-full md:w-[420px]';
  const panelHeight = isExpanded ? 'h-[90vh]' : 'h-[75vh] md:h-[520px]';

  if (!isOpen) {
    return (
      <button
        onClick={handleOpen}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-indigo-600 hover:bg-indigo-500
          rounded-full shadow-2xl shadow-indigo-900/50 flex items-center justify-center
          transition-all duration-200 hover:scale-110 group"
        title="Open Ora AI Assistant">
        <Bot size={24} className="text-white" />
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full
          border-2 border-slate-900 animate-pulse" />
      </button>
    );
  }

  return (
    <>
      {/* Backdrop (mobile) */}
      <div
        className="fixed inset-0 bg-black/60 z-40 md:hidden"
        onClick={() => setIsOpen(false)}
      />

      {/* Panel */}
      <div className={`fixed bottom-0 right-0 md:bottom-6 md:right-6 z-50
        ${panelWidth} ${panelHeight} max-h-[calc(100vh-1.5rem)]
        bg-slate-900 border border-slate-700 rounded-t-2xl md:rounded-2xl
        shadow-2xl shadow-slate-900/80 flex flex-col overflow-hidden
        transition-all duration-300`}>

        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700 flex-shrink-0 bg-slate-900/95 backdrop-blur-sm">
          <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate">
              {activeSession?.title || 'Ora AI'}
            </p>
            <p className="text-[10px] text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              Multi-Agent Active
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowHistory(v => !v)}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white"
              title="Chat history">
              <History size={16} />
            </button>
            <button
              onClick={() => setIsExpanded(v => !v)}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white hidden md:block"
              title={isExpanded ? 'Minimize' : 'Expand'}>
              {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
            <button
              onClick={() => startNewSession()}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white"
              title="New chat">
              <Plus size={16} />
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* History sidebar */}
          {showHistory && (
            <div className="w-48 border-r border-slate-800 flex flex-col bg-slate-900/95 flex-shrink-0">
              <div className="p-3 border-b border-slate-800">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Recent</p>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {isLoading && <Loader2 size={16} className="animate-spin text-slate-500 mx-auto mt-4" />}
                {sessions.length === 0 && !isLoading && (
                  <p className="text-xs text-slate-600 px-2 pt-3">No sessions yet</p>
                )}
                {sessions.map(sess => (
                  <SessionItem
                    key={sess.id}
                    session={sess}
                    active={sess.id === activeSession?.id}
                    onSelect={() => { loadSession(sess.id); setShowHistory(false); }}
                    onDelete={() => removeSession(sess.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Main chat area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 scroll-smooth">
              {messages.length === 0 && (
                <div className="space-y-6 pt-4">
                  {/* Welcome state */}
                  <div className="text-center space-y-2">
                    <div className="w-16 h-16 bg-indigo-600/20 rounded-2xl mx-auto flex items-center justify-center border border-indigo-500/30">
                      <Sparkles size={28} className="text-indigo-400" />
                    </div>
                    <h3 className="text-white font-semibold text-lg">Ora AI</h3>
                    <p className="text-slate-400 text-sm max-w-xs mx-auto leading-relaxed">
                      Your AI Chief of Staff. Ask anything about your workspace — I can create, update, analyze, and plan.
                    </p>
                  </div>

                  {/* Suggestions grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {SUGGESTIONS.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => handleSuggestion(s.prompt)}
                        className="text-left px-3 py-2.5 rounded-xl border border-slate-700 hover:border-indigo-500/50
                          hover:bg-indigo-600/10 transition-all text-xs text-slate-300 hover:text-white group">
                        <span className="font-medium text-slate-200 block mb-0.5">{s.label}</span>
                        <span className="text-slate-500 text-[11px] line-clamp-2 group-hover:text-slate-400">
                          {s.prompt}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map(msg => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-slate-800 p-3 flex-shrink-0 bg-slate-900/95 backdrop-blur-sm">
              <div className="flex items-end gap-2 bg-slate-800 rounded-2xl border border-slate-700
                focus-within:border-indigo-500/50 transition-colors px-3 py-2">
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything… (⏎ to send, Shift+⏎ for newline)"
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500
                    resize-none outline-none max-h-32 py-1 leading-relaxed"
                  style={{ minHeight: '24px' }}
                />
                <button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isSending}
                  className="w-8 h-8 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700
                    disabled:cursor-not-allowed rounded-xl flex items-center justify-center
                    transition-colors flex-shrink-0">
                  {isSending
                    ? <Loader2 size={14} className="animate-spin text-white" />
                    : <Send size={14} className="text-white" />
                  }
                </button>
              </div>
              <p className="text-[10px] text-slate-600 mt-1.5 text-center">
                Multi-agent AI · LangGraph orchestrated · Actions are real
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
