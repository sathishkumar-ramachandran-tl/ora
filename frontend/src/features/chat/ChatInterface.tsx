import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare, X, Send, Plus, Trash2, ChevronDown,
  Loader2, Bot, User, Wrench, CheckCircle, AlertCircle,
  Sparkles, History, Minimize2, Maximize2, ClipboardList, Play, AlertTriangle, RotateCcw, CalendarDays
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useChat, UIMessage } from '../../hooks/useChat';
import { RichText } from '../../components/shared/RichText';
import { AgentActionEvent, applyPlanProposal, ChatScope, PlanProposal, ScheduleProposal, undoAgentAction } from '../../api/chat';
import { applyScheduleProposal } from '../../api/calendar';

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
  { label: 'Launch a product', prompt: 'Help me launch an MVP in 6 weeks' },
  { label: 'Plan my week', prompt: 'Plan my week around my current commitments' },
  { label: 'Client work', prompt: 'Help me deliver a client redesign on time' },
  { label: 'Learn something', prompt: 'Create a focused plan to become advanced in Computer Networks' },
  { label: 'Find work', prompt: 'Help me prepare for senior SWE interviews' },
  { label: 'Review risk', prompt: 'What needs attention across my workspace?' },
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

const ActionCard: React.FC<{ action: AgentActionEvent }> = ({ action }) => {
  const [undoing, setUndoing] = useState(false);
  const [undoError, setUndoError] = useState<string | null>(null);
  const [undoDone, setUndoDone] = useState(Boolean(action.undoStatus === 'SUCCEEDED'));
  const failed = action.status === 'FAILED' || action.status === 'UNKNOWN';
  const waiting = action.status === 'WAITING_FOR_CONFIRMATION';
  const succeeded = action.status === 'SUCCEEDED';
  const title = action.actionType.replace(/\./g, ' ');
  const after = action.afterState || {};
  const error = typeof after.error === 'string' ? after.error : undefined;
  const canUndo = Boolean(action.reversible && succeeded && !undoDone && action.undoStatus !== 'CONFLICT');

  const handleUndo = async () => {
    setUndoing(true);
    setUndoError(null);
    try {
      await undoAgentAction(action.id);
      setUndoDone(true);
    } catch (err: any) {
      setUndoError(err.message || 'Undo failed');
    } finally {
      setUndoing(false);
    }
  };

  return (
    <div className={`w-full rounded-lg border px-3 py-2 text-xs
      ${succeeded ? 'border-emerald-700/60 bg-emerald-950/30 text-emerald-100' :
        failed ? 'border-amber-700/60 bg-amber-950/30 text-amber-100' :
        waiting ? 'border-sky-700/60 bg-sky-950/30 text-sky-100' :
        'border-slate-700 bg-slate-800/70 text-slate-200'}`}>
      <div className="flex items-center gap-2">
        {succeeded ? <CheckCircle size={14} /> : failed ? <AlertTriangle size={14} /> : <Loader2 size={14} className={action.status === 'RUNNING' ? 'animate-spin' : ''} />}
        <span className="font-medium capitalize">{title}</span>
        <span className="ml-auto text-[10px] opacity-70">{action.status.replace(/_/g, ' ')}</span>
      </div>
      {action.resourceId && <p className="mt-1 opacity-75">Resource: {action.resourceId}</p>}
      {error && <p className="mt-1 opacity-80">{error}</p>}
      {undoError && <p className="mt-1 text-amber-200">{undoError}</p>}
      {undoDone && <p className="mt-1 text-emerald-200">Undo completed</p>}
      {canUndo && (
        <button
          onClick={handleUndo}
          disabled={undoing}
          className="mt-2 inline-flex items-center gap-1 rounded-md border border-emerald-600/60 px-2 py-1 text-[11px] hover:bg-emerald-900/30 disabled:opacity-60">
          {undoing ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
          Undo
        </button>
      )}
    </div>
  );
};

const ScheduleProposalCard: React.FC<{ schedule: ScheduleProposal; onApplied: (schedule: ScheduleProposal) => void }> = ({ schedule, onApplied }) => {
  const [current, setCurrent] = useState(schedule);
  const [expanded, setExpanded] = useState(false);
  const [applying, setApplying] = useState(false);
  const applied = current.status === 'APPLIED' || current.status === 'PARTIALLY_APPLIED';
  const infeasible = current.status === 'INFEASIBLE';

  const handleApply = async () => {
    setApplying(true);
    try {
      const updated = await applyScheduleProposal(current.id);
      setCurrent(updated);
      onApplied(updated);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="w-full overflow-hidden rounded-lg border border-cyan-700/60 bg-cyan-950/30 text-slate-100">
      <div className="border-b border-cyan-800/50 px-3 py-3">
        <div className="flex items-start gap-2">
          <CalendarDays size={16} className="mt-0.5 text-cyan-300" />
          <div className="min-w-0 flex-1">
            <h4 className="truncate text-sm font-semibold">{String(current.summary.title || 'Schedule proposal')}</h4>
            <p className="text-[11px] text-slate-400">
              {current.summary.sessionCount || current.sessions.length} sessions · {Math.round(Number(current.summary.requiredMinutes || 0) / 60 * 10) / 10}h requested
            </p>
          </div>
          <span className={`rounded-full px-2 py-0.5 text-[10px] ${infeasible ? 'bg-amber-900/70 text-amber-200' : 'bg-cyan-900/70 text-cyan-200'}`}>
            {current.status.replace(/_/g, ' ')}
          </span>
        </div>
        {infeasible && (
          <p className="mt-2 text-xs text-amber-200">
            Needs {current.summary.requiredMinutes || 0} min, but only {current.summary.availableMinutes || 0} min are free in this window.
          </p>
        )}
      </div>
      {expanded && (
        <div className="max-h-64 space-y-1 overflow-y-auto px-3 py-2">
          {current.sessions.map(session => (
            <div key={session.session_ref} className="rounded-md border border-slate-700/80 p-2 text-xs">
              <p className="font-medium">{session.title}</p>
              <p className="text-[11px] text-slate-400">
                {new Date(session.start_at).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })}
                {' - '}
                {new Date(session.end_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                {' · '}{session.duration_minutes} min
              </p>
            </div>
          ))}
        </div>
      )}
      {current.applicationResult && Object.keys(current.applicationResult).length > 0 && (
        <div className="border-t border-cyan-800/50 px-3 py-2 text-xs text-slate-300">
          {current.status === 'PARTIALLY_APPLIED' ? 'Partially applied' : 'Applied'}:
          {' '}{current.applicationResult.successes || 0} succeeded,
          {' '}{current.applicationResult.failures || 0} failed
        </div>
      )}
      <div className="flex items-center justify-between border-t border-cyan-800/50 px-3 py-2">
        <button onClick={() => setExpanded(v => !v)} className="text-xs text-cyan-200 hover:text-white">
          {expanded ? 'Hide details' : 'Review schedule'}
        </button>
        <button
          onClick={handleApply}
          disabled={applying || applied || infeasible}
          className="inline-flex items-center gap-1.5 rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-medium hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-400">
          {applying ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          {applied ? 'Applied' : 'Apply'}
        </button>
      </div>
    </div>
  );
};

const PlanCard: React.FC<{ plan: PlanProposal; onApplied: (plan: PlanProposal) => void }> = ({ plan, onApplied }) => {
  const [currentPlan, setCurrentPlan] = useState(plan);
  const [expanded, setExpanded] = useState(false);
  const [applying, setApplying] = useState(false);
  const findings = currentPlan.qualityReport?.findings || [];
  const applied = currentPlan.status === 'APPLIED' || currentPlan.status === 'PARTIALLY_APPLIED';
  const differential = currentPlan.content.differential || {};
  const researchCount = currentPlan.planningContext?.research?.evidence_count || currentPlan.planningContext?.research?.evidence?.length || 0;
  const names = (items?: Array<{ concept_name?: string; concept_key?: string }>) =>
    (items || []).slice(0, 4).map(item => item.concept_name || item.concept_key).filter(Boolean).join(', ');

  const handleApply = async () => {
    setApplying(true);
    try {
      const updated = await applyPlanProposal(plan.id);
      setCurrentPlan(updated);
      onApplied(updated);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="w-full rounded-lg border border-indigo-700/60 bg-indigo-950/30 text-slate-100 overflow-hidden">
      <div className="px-3 py-3 border-b border-indigo-800/50">
        <div className="flex items-start gap-2">
          <ClipboardList size={16} className="text-indigo-300 mt-0.5" />
          <div className="min-w-0 flex-1">
            <h4 className="text-sm font-semibold truncate">{currentPlan.title}</h4>
            <p className="text-[11px] text-slate-400">
              {currentPlan.summary.phaseCount} phases · {currentPlan.summary.taskCount} proposed tasks · v{currentPlan.version}
            </p>
          </div>
          <span className={`text-[10px] px-2 py-0.5 rounded-full
            ${currentPlan.qualityStatus === 'PASS' ? 'bg-emerald-900/70 text-emerald-200' :
              currentPlan.qualityStatus === 'WARNING' ? 'bg-amber-900/70 text-amber-200' :
              'bg-slate-800 text-slate-300'}`}>
            {currentPlan.qualityStatus}
          </span>
        </div>
        {findings.length > 0 && (
          <p className="mt-2 text-xs text-amber-200">{findings.length} quality finding{findings.length === 1 ? '' : 's'}</p>
        )}
        {researchCount > 0 && (
          <p className="mt-2 text-xs text-emerald-200">Research-backed: {researchCount} source{researchCount === 1 ? '' : 's'}</p>
        )}
        {(differential.builds_on?.length || differential.deepens?.length || differential.adds?.length || differential.reviews?.length) && (
          <div className="mt-2 grid grid-cols-1 gap-1 text-[11px] text-slate-300">
            {Boolean(differential.builds_on?.length) && <p><span className="text-slate-500">Builds on:</span> {names(differential.builds_on)}</p>}
            {Boolean(differential.deepens?.length) && <p><span className="text-slate-500">Deepens:</span> {names(differential.deepens)}</p>}
            {Boolean(differential.adds?.length) && <p><span className="text-slate-500">Adds:</span> {names(differential.adds)}</p>}
            {Boolean(differential.reviews?.length) && <p><span className="text-slate-500">Reviews:</span> {names(differential.reviews)}</p>}
          </div>
        )}
      </div>

      {expanded && (
        <div className="px-3 py-2 space-y-2 max-h-64 overflow-y-auto">
          {(currentPlan.content.phases || []).map(phase => (
            <div key={phase.id} className="border border-slate-700/80 rounded-md p-2">
              <p className="text-xs font-medium">{phase.title}</p>
              <p className="text-[11px] text-slate-400">{phase.target}</p>
              {Boolean(phase.concepts?.some(concept => concept.rationale?.length || concept.source_ids?.length)) && (
                <p className="mt-1 text-[11px] text-emerald-200">
                  Added because: {phase.concepts?.find(concept => concept.rationale?.length)?.rationale?.[0] || 'source-backed planning requirement'}
                </p>
              )}
              <ul className="mt-1 space-y-1">
                {(phase.tasks || []).slice(0, 4).map(task => (
                  <li key={task.id} className="text-[11px] text-slate-300">• {task.title}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {currentPlan.applicationResult && Object.keys(currentPlan.applicationResult).length > 0 && (
        <div className="px-3 py-2 text-xs border-t border-indigo-800/50 text-slate-300">
          {currentPlan.status === 'PARTIALLY_APPLIED' ? 'Partially applied' : 'Applied'}:
          {' '}{currentPlan.applicationResult.successes || 0} succeeded,
          {' '}{currentPlan.applicationResult.failures || 0} failed,
          {' '}{currentPlan.applicationResult.skipped || 0} skipped
        </div>
      )}

      <div className="px-3 py-2 flex items-center justify-between border-t border-indigo-800/50">
        <button onClick={() => setExpanded(v => !v)} className="text-xs text-indigo-200 hover:text-white">
          {expanded ? 'Hide details' : 'Review plan'}
        </button>
        <button
          onClick={handleApply}
          disabled={applying || applied}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-400 text-xs font-medium">
          {applying ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          {applied ? 'Applied' : 'Apply'}
        </button>
      </div>
    </div>
  );
};

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

        {msg.plans && msg.plans.length > 0 && (
          <div className="w-full space-y-2">
            {msg.plans.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onApplied={() => undefined}
              />
            ))}
          </div>
        )}

        {msg.schedules && msg.schedules.length > 0 && (
          <div className="w-full space-y-2">
            {msg.schedules.map(schedule => (
              <ScheduleProposalCard
                key={schedule.id}
                schedule={schedule}
                onApplied={() => undefined}
              />
            ))}
          </div>
        )}

        {msg.actions && msg.actions.length > 0 && (
          <div className="w-full space-y-2">
            {msg.actions.map(action => <ActionCard key={action.id} action={action} />)}
          </div>
        )}

        {/* Legacy tool call pills remain secondary compatibility UI */}
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
  scope?: ChatScope;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ workspaceId, scope }) => {
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
  } = useChat(workspaceId, scope);

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

  useEffect(() => {
    const handleCommand = async (event: Event) => {
      const detail = (event as CustomEvent<{ content?: string }>).detail;
      if (!detail?.content) return;
      setIsOpen(true);
      setInputValue(detail.content);
      if (!activeSession) {
        await startNewSession();
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    };
    window.addEventListener('ora:command', handleCommand);
    return () => window.removeEventListener('ora:command', handleCommand);
  }, [activeSession, startNewSession]);

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
        title="Open Ora">
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
              {activeSession?.title || 'Ora'}
            </p>
            <p className="text-[10px] text-emerald-400 flex items-center gap-1 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block flex-shrink-0" />
              <span className="truncate">{scope?.label ? `Context: ${scope.label}` : 'Workspace context'}</span>
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
                    <h3 className="text-white font-semibold text-lg">Ora</h3>
                    <p className="text-slate-400 text-sm max-w-xs mx-auto leading-relaxed">
                      Ask about an outcome, project, task, schedule, or piece of context. Ora keeps the scope visible.
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
              <div className="mb-2 flex items-center gap-2">
                <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] font-medium text-slate-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                  <span className="truncate">{scope?.label || 'Ora'}</span>
                </span>
              </div>
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
                Recommendations, proposals, and applied changes stay distinct.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
