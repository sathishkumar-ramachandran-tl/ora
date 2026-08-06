import React, { useState, useEffect } from 'react';
import { X, Loader2, Trash2, Plus, Save, Download, CheckCircle2, GripVertical, Clock, ListChecks, Flag } from 'lucide-react';
import { getModule, updateModuleStructure, installModule, publishModule } from '../../api/modules';
import { ModuleMilestoneSpec, ModuleTaskSpec, Priority, Company } from '../../types';
import { InitiativePicker } from './InitiativePicker';
import { PRIORITY_VISUALS } from './moduleVisuals';

interface ModuleReviewScreenProps {
  moduleTemplateId: string;
  workspaceId?: string;
  companies?: Company[];
  onCreateCompany?: (company: Company) => Promise<void>;
  onClose: () => void;
  onInstalled?: (projectId: string) => void;
  onPublished?: () => void;
}

const PRIORITIES: Priority[] = ['low', 'medium', 'high', 'critical'];

const emptyTask = (): ModuleTaskSpec => ({ title: '', description: '', priority: 'medium', estimated_hours: 2 });
const emptyMilestone = (order: number): ModuleMilestoneSpec => ({ title: '', description: '', order, tasks: [] });

export const ModuleReviewScreen: React.FC<ModuleReviewScreenProps> = ({
  moduleTemplateId, workspaceId, companies, onCreateCompany, onClose, onInstalled, onPublished,
}) => {
  const [title, setTitle] = useState('');
  const [milestones, setMilestones] = useState<ModuleMilestoneSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pickingInitiative, setPickingInitiative] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const detail = await getModule(moduleTemplateId);
        setTitle(detail.title);
        setMilestones(detail.structure?.milestones || []);
      } catch (e) {
        setError('Failed to load module draft.');
      } finally {
        setLoading(false);
      }
    })();
  }, [moduleTemplateId]);

  const mutate = (fn: (prev: ModuleMilestoneSpec[]) => ModuleMilestoneSpec[]) => {
    setMilestones(fn);
    setDirty(true);
  };

  const updateMilestoneField = (idx: number, field: 'title' | 'description', value: string) => {
    mutate(prev => prev.map((m, i) => i === idx ? { ...m, [field]: value } : m));
  };

  const addMilestone = () => {
    mutate(prev => [...prev, emptyMilestone(prev.length)]);
  };

  const removeMilestone = (idx: number) => {
    mutate(prev => prev.filter((_, i) => i !== idx).map((m, i) => ({ ...m, order: i })));
  };

  const addTask = (milestoneIdx: number) => {
    mutate(prev => prev.map((m, i) => i === milestoneIdx ? { ...m, tasks: [...m.tasks, emptyTask()] } : m));
  };

  const removeTask = (milestoneIdx: number, taskIdx: number) => {
    mutate(prev => prev.map((m, i) => i === milestoneIdx ? { ...m, tasks: m.tasks.filter((_, ti) => ti !== taskIdx) } : m));
  };

  const updateTaskField = (milestoneIdx: number, taskIdx: number, field: keyof ModuleTaskSpec, value: any) => {
    mutate(prev => prev.map((m, i) => i === milestoneIdx ? {
      ...m,
      tasks: m.tasks.map((t, ti) => ti === taskIdx ? { ...t, [field]: value } : t),
    } : m));
  };

  const validate = (): string | null => {
    if (milestones.length === 0) return 'Add at least one milestone.';
    for (const m of milestones) {
      if (!m.title.trim()) return 'Every milestone needs a title.';
      for (const t of m.tasks) {
        if (!t.title.trim()) return 'Every task needs a title.';
      }
    }
    return null;
  };

  const persist = async (): Promise<boolean> => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return false;
    }
    setError(null);
    setSaving(true);
    try {
      await updateModuleStructure(moduleTemplateId, milestones);
      setDirty(false);
      return true;
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to save changes.');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => { persist(); };

  const handleInstall = async (companyId?: string) => {
    if (!workspaceId) return;
    if (dirty && !(await persist())) return;
    setInstalling(true);
    try {
      const result = await installModule(moduleTemplateId, workspaceId, companyId);
      onInstalled?.(result.projectId);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to install module.');
    } finally {
      setInstalling(false);
    }
  };

  const startInstall = async () => {
    if (onCreateCompany && companies) {
      setPickingInitiative(true);
      return;
    }
    await handleInstall();
  };

  const handlePublish = async () => {
    if (dirty && !(await persist())) return;
    setPublishing(true);
    try {
      await publishModule(moduleTemplateId);
      onPublished?.();
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to publish module.');
    } finally {
      setPublishing(false);
    }
  };

  const totalTasks = milestones.reduce((sum, m) => sum + m.tasks.length, 0);
  const totalHours = milestones.reduce((sum, m) => sum + m.tasks.reduce((s, t) => s + (t.estimated_hours || 0), 0), 0);
  const milestoneHours = (m: ModuleMilestoneSpec) => m.tasks.reduce((s, t) => s + (t.estimated_hours || 0), 0);

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[80] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-[0_24px_64px_-16px_rgba(15,23,42,0.4)] border border-slate-200/60 w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="relative flex-shrink-0">
          <div className="h-1 bg-gradient-to-r from-brand-500 via-violet-500 to-brand-500" />
          <div className="px-6 py-4 flex justify-between items-start bg-white border-b border-slate-100">
            <div>
              <h3 className="text-[17px] font-semibold text-slate-900 tracking-tight">{title || 'Review Module'}</h3>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <Flag size={12} className="text-slate-400" /> {milestones.length} milestones
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <ListChecks size={12} className="text-slate-400" /> {totalTasks} tasks
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock size={12} className="text-slate-400" /> {totalHours}h estimated
                </span>
                {dirty && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Unsaved changes
                  </span>
                )}
              </div>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg p-1.5 transition-colors"><X size={20} /></button>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center py-16"><Loader2 className="animate-spin text-slate-400" size={28} /></div>
        ) : (
          <div className="flex-1 overflow-y-auto custom-scrollbar bg-slate-50/40">
            <table className="w-full border-collapse text-sm table-fixed">
              <colgroup>
                <col className="w-[38%]" />
                <col className="w-[34%]" />
                <col className="w-[120px]" />
                <col className="w-[90px]" />
                <col className="w-[40px]" />
              </colgroup>
              <thead className="sticky top-0 z-10">
                <tr className="bg-slate-100/95 backdrop-blur text-[11px] font-semibold uppercase tracking-wide text-slate-500 border-b border-slate-200">
                  <th className="text-left px-4 py-2 font-semibold">Task</th>
                  <th className="text-left px-3 py-2 font-semibold">Description</th>
                  <th className="text-left px-3 py-2 font-semibold">Priority</th>
                  <th className="text-left px-3 py-2 font-semibold">Hours</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {milestones.map((milestone, mIdx) => (
                  <React.Fragment key={mIdx}>
                    <tr className="bg-white">
                      <td colSpan={5} className="px-0 pt-4 pb-1.5">
                        <div className="flex items-center gap-2 px-4">
                          <GripVertical size={14} className="text-slate-300 flex-shrink-0" />
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-50 border border-brand-200 text-brand-700 flex items-center justify-center text-[11px] font-semibold">
                            {mIdx + 1}
                          </span>
                          <input
                            value={milestone.title}
                            onChange={e => updateMilestoneField(mIdx, 'title', e.target.value)}
                            placeholder="Milestone title"
                            className="flex-1 font-semibold text-[13px] text-slate-800 bg-transparent outline-none border-b border-transparent focus:border-brand-400 px-1 py-0.5 min-w-0"
                          />
                          <input
                            value={milestone.description}
                            onChange={e => updateMilestoneField(mIdx, 'description', e.target.value)}
                            placeholder="Description (optional)"
                            className="flex-1 text-xs text-slate-400 bg-transparent outline-none border-b border-transparent focus:border-brand-400 focus:text-slate-600 px-1 py-0.5 min-w-0"
                          />
                          <span className="flex-shrink-0 text-[11px] text-slate-400 whitespace-nowrap">
                            {milestone.tasks.length} task{milestone.tasks.length === 1 ? '' : 's'} · {milestoneHours(milestone)}h
                          </span>
                          <button onClick={() => removeMilestone(mIdx)} className="flex-shrink-0 p-1 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>

                    {milestone.tasks.map((task, tIdx) => {
                      const pv = PRIORITY_VISUALS[task.priority];
                      return (
                        <tr key={tIdx} className="bg-white hover:bg-slate-50/70 border-t border-slate-100 group align-top">
                          <td className="px-4 py-1.5">
                            <input
                              value={task.title}
                              onChange={e => updateTaskField(mIdx, tIdx, 'title', e.target.value)}
                              placeholder="Task title"
                              className="w-full text-sm font-medium text-slate-800 bg-transparent outline-none rounded-lg px-2 py-1.5 focus:bg-white focus:ring-2 focus:ring-brand-500/20 transition-shadow"
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <input
                              value={task.description}
                              onChange={e => updateTaskField(mIdx, tIdx, 'description', e.target.value)}
                              placeholder="Description"
                              className="w-full text-xs text-slate-500 bg-transparent outline-none rounded-lg px-2 py-1.5 focus:bg-white focus:text-slate-700 focus:ring-2 focus:ring-brand-500/20 transition-shadow"
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <select
                              value={task.priority}
                              onChange={e => updateTaskField(mIdx, tIdx, 'priority', e.target.value as Priority)}
                              className={`w-full text-[11px] font-medium border rounded-lg pl-2 pr-1 py-1.5 outline-none appearance-none cursor-pointer ${pv.chip}`}
                            >
                              {PRIORITIES.map(p => <option key={p} value={p}>{PRIORITY_VISUALS[p].label}</option>)}
                            </select>
                          </td>
                          <td className="px-3 py-1.5">
                            <input
                              type="number" min={0.5} step={0.5}
                              value={task.estimated_hours}
                              onChange={e => updateTaskField(mIdx, tIdx, 'estimated_hours', parseFloat(e.target.value) || 0)}
                              className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white outline-none focus:ring-2 focus:ring-brand-500/20"
                            />
                          </td>
                          <td className="px-2 py-1.5">
                            <button
                              onClick={() => removeTask(mIdx, tIdx)}
                              className="p-1 text-slate-300 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}

                    <tr className="bg-white">
                      <td colSpan={5} className="px-4 pt-1 pb-3">
                        <button
                          onClick={() => addTask(mIdx)}
                          className="flex items-center gap-1.5 text-xs text-brand-600 hover:bg-brand-50 px-2.5 py-1.5 rounded-lg transition-colors"
                        >
                          <Plus size={12} /> Add Task
                        </button>
                      </td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>

            <div className="p-4">
              <button
                onClick={addMilestone}
                className="w-full flex items-center justify-center gap-2 text-sm text-slate-600 hover:bg-white hover:text-slate-800 py-3 rounded-xl border border-dashed border-slate-300 transition-colors"
              >
                <Plus size={16} /> Add Milestone
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="px-6 py-2.5 bg-rose-50 border-t border-rose-100 text-rose-600 text-xs flex-shrink-0">{error}</div>
        )}

        <div className="px-6 py-3.5 border-t border-slate-200 bg-white flex justify-end gap-2.5 flex-shrink-0">
          <button onClick={onClose} className="text-slate-500 hover:text-slate-800 font-medium text-sm px-3 rounded-lg transition-colors">Close</button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save Changes
          </button>
          {workspaceId && (
            <button
              onClick={startInstall}
              disabled={installing || loading}
              className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 shadow-[0_1px_2px_rgba(79,70,229,0.3),0_6px_16px_-6px_rgba(79,70,229,0.5)] transition-colors"
            >
              {installing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} Install
            </button>
          )}
          <button
            onClick={handlePublish}
            disabled={publishing || loading}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 shadow-[0_1px_2px_rgba(16,185,129,0.3),0_6px_16px_-6px_rgba(16,185,129,0.5)] transition-colors"
          >
            {publishing ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} Publish
          </button>
        </div>
      </div>

      {pickingInitiative && onCreateCompany && companies && (
        <InitiativePicker
          companies={companies}
          onCreateCompany={onCreateCompany}
          onClose={() => setPickingInitiative(false)}
          onConfirm={(companyId) => {
            setPickingInitiative(false);
            handleInstall(companyId);
          }}
        />
      )}
    </div>
  );
};
