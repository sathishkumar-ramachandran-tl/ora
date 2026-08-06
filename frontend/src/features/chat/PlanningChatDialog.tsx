/**
 * Multi-discussion Planning Dialog
 *
 * Replaces the single-shot AI plan generation in AgileBoard.
 * Opens a focused chat conversation pre-seeded with project context.
 * The planning agent (LangGraph) guides through:
 *   gathering → drafting → refining → confirming → executing
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  X, Send, Loader2, Bot, User, Sparkles, CheckCircle,
  Wrench, RotateCcw, Lightbulb
} from 'lucide-react';
import { useChat, UIMessage } from '../../hooks/useChat';
import { RichText } from '../../components/shared/RichText';

interface PlanningChatDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectName: string;
  projectType: string;
  workspaceId: string;
  companyMission: string;
  /** Called when the agent successfully creates tasks; triggers a data reload */
  onPlanExecuted: () => void;
}

const PLANNING_STARTERS = [
  'What is the main goal or deliverable for this project?',
  'Do you have a specific timeline or deadline in mind?',
  'Are there any constraints I should know about (budget, team size, tech stack)?',
];

const ToolBadge: React.FC<{ name: string; status: string }> = ({ name, status }) => (
  <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-mono
    ${status === 'running' ? 'bg-amber-100 text-amber-700 animate-pulse' :
      'bg-emerald-100 text-emerald-700'}`}>
    <Wrench size={9} />
    {name.replace(/_/g, ' ')}
    {status === 'running' && <Loader2 size={8} className="animate-spin" />}
    {status === 'done' && <CheckCircle size={8} />}
  </span>
);

const Bubble: React.FC<{ msg: UIMessage }> = ({ msg }) => {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5
        ${isUser ? 'bg-indigo-600' : 'bg-slate-100 border border-slate-200'}`}>
        {isUser ? <User size={13} className="text-white" /> : <Bot size={13} className="text-indigo-600" />}
      </div>
      <div className={`max-w-[82%] space-y-1.5 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {msg.toolCalls.map((tc, i) => <ToolBadge key={i} name={tc.name} status={tc.status} />)}
          </div>
        )}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isUser
            ? 'bg-indigo-600 text-white rounded-tr-sm'
            : 'bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-sm'}`}>
          {msg.content
            ? <RichText content={msg.content} variant="light" />
            : msg.streaming
              ? <span className="flex items-center gap-2 text-slate-400">
                  <Loader2 size={12} className="animate-spin" /> Thinking…
                </span>
              : null
          }
        </div>
      </div>
    </div>
  );
};

export const PlanningChatDialog: React.FC<PlanningChatDialogProps> = ({
  isOpen, onClose, projectId, projectName, projectType,
  workspaceId, companyMission, onPlanExecuted
}) => {
  const [inputValue, setInputValue] = useState('');
  const [sessionStarted, setSessionStarted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    activeSession, messages, isSending,
    startNewSession, sendMessage
  } = useChat(workspaceId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-start planning when dialog opens
  useEffect(() => {
    if (!isOpen || sessionStarted) return;
    const init = async () => {
      await startNewSession();
      setSessionStarted(true);
      // Send initial context to the planning agent
      const seedMsg = [
        `I want to plan the project: "${projectName}" (type: ${projectType}).`,
        `Context: ${companyMission}`,
        `Project ID for task creation: ${projectId}`,
        `Workspace ID: ${workspaceId}`,
        `\nPlease start the planning conversation by asking me the key questions you need to build a great plan.`
      ].join('\n');
      await sendMessage(seedMsg);
    };
    init();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Reset when dialog closes
  useEffect(() => {
    if (!isOpen) setSessionStarted(false);
  }, [isOpen]);

  // Detect when agent successfully creates tasks
  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (!lastMsg || lastMsg.role !== 'assistant' || lastMsg.streaming) return;
    const toolNames = (lastMsg.toolCalls || []).map(tc => tc.name);
    if (toolNames.some(n => n.includes('create_project_plan') || n.includes('create_multiple_tasks') || n.includes('create_task'))) {
      onPlanExecuted();
    }
  }, [messages, onPlanExecuted]);

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

  const handleRestart = async () => {
    setSessionStarted(false);
    // The useEffect will reinit
  };

  if (!isOpen) return null;

  // Filter messages: hide the long seed message from UI
  const visibleMessages = messages.filter((m, i) => !(i === 0 && m.role === 'user'));

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full sm:max-w-2xl bg-white rounded-t-3xl sm:rounded-3xl
        shadow-2xl flex flex-col max-h-[90vh] sm:max-h-[85vh] overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100 flex-shrink-0 bg-gradient-to-r from-indigo-50 to-purple-50">
          <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center flex-shrink-0">
            <Sparkles size={18} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="font-bold text-slate-900 text-sm truncate">AI Planning Session</h2>
            <p className="text-xs text-slate-500 truncate">{projectName} · Multi-turn conversation</p>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleRestart}
              className="p-2 hover:bg-white/80 rounded-xl transition-colors text-slate-400 hover:text-slate-700"
              title="Restart planning">
              <RotateCcw size={15} />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/80 rounded-xl transition-colors text-slate-400 hover:text-slate-700">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* How it works hint */}
        <div className="px-5 py-3 bg-amber-50 border-b border-amber-100 flex-shrink-0">
          <div className="flex items-start gap-2">
            <Lightbulb size={14} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-[11px] text-amber-800 leading-relaxed">
              <span className="font-semibold">Multi-discussion planning:</span> The AI will ask questions,
              generate a draft plan, then refine it based on your feedback.
              Say <span className="font-semibold">"confirm"</span> when you're happy — it will create all tasks automatically.
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 bg-slate-50/50">
          {!sessionStarted && (
            <div className="flex flex-col items-center justify-center h-32 space-y-3">
              <Loader2 size={28} className="animate-spin text-indigo-500" />
              <p className="text-sm text-slate-500">Starting planning session…</p>
            </div>
          )}

          {visibleMessages.map(msg => (
            <Bubble key={msg.id} msg={msg} />
          ))}

          {/* Quick reply suggestions (shown after AI message) */}
          {messages.length > 0 && !isSending && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.streaming && (
            <div className="flex flex-wrap gap-2 mt-2">
              {['Looks good, confirm', 'Make all high priority', 'Add 2 more research tasks', 'Shorten to 4 tasks'].map(s => (
                <button
                  key={s}
                  onClick={() => { setInputValue(s); inputRef.current?.focus(); }}
                  className="text-[11px] px-3 py-1.5 bg-white border border-slate-200 rounded-full
                    hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 transition-all text-slate-600">
                  {s}
                </button>
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-200 p-4 flex-shrink-0 bg-white">
          <div className="flex items-end gap-3 bg-slate-100 rounded-2xl px-4 py-2.5
            focus-within:ring-2 focus-within:ring-indigo-200 transition-all">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Answer the AI's questions, request changes, or say 'confirm'…"
              rows={1}
              className="flex-1 bg-transparent text-sm text-slate-800 placeholder-slate-400
                resize-none outline-none max-h-28 leading-relaxed py-1"
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isSending}
              className="w-9 h-9 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-300
                rounded-xl flex items-center justify-center transition-colors flex-shrink-0">
              {isSending
                ? <Loader2 size={15} className="animate-spin text-white" />
                : <Send size={15} className="text-white" />
              }
            </button>
          </div>
          <p className="text-[10px] text-slate-400 text-center mt-2">
            ⏎ send · Shift+⏎ newline · Powered by LangGraph Planning Agent
          </p>
        </div>
      </div>
    </div>
  );
};
