import React, { useState, useEffect, useRef } from 'react';
import { X, Loader2, Sparkles, CheckCircle2, XCircle, BookOpen, Rocket, Target, Repeat, Layers } from 'lucide-react';
import { generateModule, getGenerationProgress } from '../../api/modules';
import { ModuleCategory, ModuleDifficulty, ModuleGenerationStatus } from '../../types';

interface ModuleGenerationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerated: (moduleTemplateId: string) => void;
}

const CATEGORIES: { value: ModuleCategory; label: string; icon: React.ElementType }[] = [
  { value: 'exam_prep', label: 'Exam Prep', icon: Target },
  { value: 'course', label: 'Course', icon: BookOpen },
  { value: 'project', label: 'Project', icon: Rocket },
  { value: 'habit', label: 'Habit', icon: Repeat },
  { value: 'general', label: 'General', icon: Layers },
];

const DIFFICULTIES: { value: ModuleDifficulty; label: string }[] = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
];

const STAGES = ['Connecting', 'Outlining', 'Expanding', 'Self-reviewing'];

const POLL_INTERVAL_MS = 2000;

export const ModuleGenerationDialog: React.FC<ModuleGenerationDialogProps> = ({ isOpen, onClose, onGenerated }) => {
  const [goal, setGoal] = useState('');
  const [category, setCategory] = useState<ModuleCategory>('general');
  const [difficulty, setDifficulty] = useState<ModuleDifficulty>('intermediate');
  const [status, setStatus] = useState<ModuleGenerationStatus | 'idle'>('idle');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [milestoneCount, setMilestoneCount] = useState(0);
  const [taskCount, setTaskCount] = useState(0);
  const moduleIdRef = useRef<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setGoal(''); setCategory('general'); setDifficulty('intermediate');
      setStatus('idle'); setStatusText(''); setError(null);
      setMilestoneCount(0); setTaskCount(0);
      moduleIdRef.current = null;
      if (pollRef.current) window.clearInterval(pollRef.current);
    }
  }, [isOpen]);

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  if (!isOpen) return null;

  const startPolling = (moduleTemplateId: string) => {
    pollRef.current = window.setInterval(async () => {
      try {
        const progress = await getGenerationProgress(moduleTemplateId);
        setMilestoneCount(progress.milestoneCount);
        setTaskCount(progress.taskCount);
        setStatus(progress.status);
        if (progress.status === 'ready') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setStatusText('Module ready.');
        } else if (progress.status === 'failed') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setError(progress.error || 'Generation failed');
        } else {
          setStatusText(`Designing… ${progress.milestoneCount} milestones, ${progress.taskCount} tasks so far`);
        }
      } catch (e) {
        // transient network hiccup — keep polling
      }
    }, POLL_INTERVAL_MS);
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus('generating');
    setStatusText('Connecting to Ora Cortex…');
    try {
      const draft = await generateModule(goal.trim(), undefined, category, difficulty);
      moduleIdRef.current = draft.moduleTemplateId;
      startPolling(draft.moduleTemplateId);
    } catch (e: any) {
      setStatus('failed');
      setError(e?.response?.data?.error || 'Failed to start generation');
    }
  };

  const isGenerating = status === 'generating' || status === 'pending';
  const isReady = status === 'ready';
  const isFailed = status === 'failed';

  // Rough stage inference from live counts — purely a perceived-progress cue, not exact backend state.
  const stageIdx = !isGenerating ? 0 : taskCount > 0 ? 3 : milestoneCount > 0 ? 2 : 1;

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-[0_24px_64px_-16px_rgba(15,23,42,0.35)] w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200 border border-slate-200/60">
        <div className="relative h-1 bg-gradient-to-r from-brand-500 via-violet-500 to-brand-500" />
        <div className="flex justify-between items-center px-5 py-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2 text-[15px]">
            <span className="w-7 h-7 rounded-lg bg-brand-50 flex items-center justify-center">
              <Sparkles size={14} className="text-brand-600" />
            </span>
            Generate a Module
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg p-1 transition-colors"><X size={18} /></button>
        </div>

        {status === 'idle' ? (
          <form onSubmit={handleGenerate} className="p-5 space-y-5">
            <div>
              <label className="block text-[13px] font-medium text-slate-700 mb-1.5">What do you want to accomplish?</label>
              <textarea
                required autoFocus value={goal} onChange={e => setGoal(e.target.value)}
                className="w-full px-3.5 py-2.5 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500/30 focus:border-brand-400 outline-none transition-shadow resize-none"
                rows={3} placeholder="e.g. UPSC Civil Services Prelims prep in 6 months" />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-slate-700 mb-1.5">Category</label>
              <div className="grid grid-cols-5 gap-1.5">
                {CATEGORIES.map(c => {
                  const Icon = c.icon;
                  const active = category === c.value;
                  return (
                    <button
                      type="button"
                      key={c.value}
                      onClick={() => setCategory(c.value)}
                      className={`flex flex-col items-center gap-1 py-2.5 rounded-xl border text-[11px] font-medium transition-all ${
                        active
                          ? 'bg-brand-50 border-brand-300 text-brand-700 shadow-[0_0_0_1px_rgba(79,70,229,0.15)]'
                          : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <Icon size={15} />
                      {c.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-[13px] font-medium text-slate-700 mb-1.5">Difficulty</label>
              <div className="flex bg-slate-100/80 rounded-xl p-1 gap-1">
                {DIFFICULTIES.map(d => (
                  <button
                    type="button"
                    key={d.value}
                    onClick={() => setDifficulty(d.value)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      difficulty === d.value ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            <button type="submit" className="w-full bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white font-medium py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 shadow-[0_1px_2px_rgba(79,70,229,0.3),0_8px_20px_-8px_rgba(79,70,229,0.5)] transition-colors">
              <Sparkles size={16} /> Generate
            </button>
          </form>
        ) : (
          <div className="p-6 space-y-5">
            {isGenerating && (
              <div className="flex flex-col items-center gap-4 py-4 text-center">
                <div className="relative w-14 h-14 flex items-center justify-center">
                  <Loader2 className="w-14 h-14 text-brand-100 animate-spin absolute" style={{ animationDuration: '2.4s' }} />
                  <Loader2 className="w-9 h-9 text-brand-600 animate-spin" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">{statusText || 'Designing your module…'}</p>
                  <p className="text-xs text-slate-400 mt-1 max-w-xs">Ora is outlining, expanding, and self-reviewing the plan — this can take a minute.</p>
                </div>
                <div className="w-full flex items-center justify-between px-2 pt-1">
                  {STAGES.map((s, i) => (
                    <React.Fragment key={s}>
                      <div className="flex flex-col items-center gap-1.5 flex-1">
                        <span className={`w-2 h-2 rounded-full transition-colors ${i <= stageIdx ? 'bg-brand-600' : 'bg-slate-200'}`} />
                        <span className={`text-[10px] font-medium ${i <= stageIdx ? 'text-slate-600' : 'text-slate-300'}`}>{s}</span>
                      </div>
                      {i < STAGES.length - 1 && <div className={`h-px flex-1 -mt-4 ${i < stageIdx ? 'bg-brand-300' : 'bg-slate-200'}`} />}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}
            {isReady && (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                </div>
                <p className="text-sm font-medium text-slate-700">Module ready — {milestoneCount} milestones, {taskCount} tasks.</p>
                <button
                  onClick={() => moduleIdRef.current && onGenerated(moduleIdRef.current)}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-xl text-sm transition-colors">
                  Review &amp; Publish
                </button>
              </div>
            )}
            {isFailed && (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <div className="w-14 h-14 rounded-2xl bg-rose-50 flex items-center justify-center">
                  <XCircle className="w-8 h-8 text-rose-500" />
                </div>
                <p className="text-sm font-medium text-slate-700">Generation failed</p>
                {error && <p className="text-xs text-rose-500">{error}</p>}
                <button onClick={() => setStatus('idle')} className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-2.5 rounded-xl text-sm transition-colors">
                  Try Again
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
