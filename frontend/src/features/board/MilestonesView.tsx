import React, { useState, useEffect } from 'react';
import { Project, Milestone, MilestoneStatus } from '../../types';
import { Plus, Loader2, Trash2, Pencil, X, Check, Flag } from 'lucide-react';
import { listMilestones, createMilestone, updateMilestone, deleteMilestone } from '../../api/projects';

interface MilestonesViewProps {
  project: Project;
}

const STATUS_CONFIG: Record<MilestoneStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'bg-slate-100 text-slate-600 border-slate-200' },
  in_progress: { label: 'In Progress', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  done: { label: 'Done', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

export const MilestonesView: React.FC<MilestonesViewProps> = ({ project }) => {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');

  useEffect(() => {
    load();
  }, [project.id]);

  const load = async () => {
    setLoading(true);
    try {
      const data = await listMilestones(project.id);
      setMilestones(data.sort((a, b) => a.order - b.order));
    } catch (e) {
      console.error('Failed to load milestones', e);
    } finally {
      setLoading(false);
    }
  };

  const progressFor = (milestoneId: string) => {
    const linked = project.tasks.filter(t => t.milestoneId === milestoneId);
    if (linked.length === 0) return null;
    const done = linked.filter(t => t.status === 'done').length;
    return { done, total: linked.length, pct: Math.round((done / linked.length) * 100) };
  };

  const resetForm = () => {
    setFormOpen(false);
    setEditingId(null);
    setTitle('');
    setDescription('');
    setDueDate('');
  };

  const startEdit = (m: Milestone) => {
    setEditingId(m.id);
    setTitle(m.title);
    setDescription(m.description || '');
    setDueDate(m.dueDate ? m.dueDate.slice(0, 10) : '');
    setFormOpen(true);
  };

  const submitForm = async () => {
    if (!title.trim()) return;
    try {
      if (editingId) {
        await updateMilestone(editingId, {
          title, description, dueDate: dueDate ? new Date(dueDate).toISOString() : undefined,
        });
      } else {
        await createMilestone(project.id, {
          title, description, dueDate: dueDate ? new Date(dueDate).toISOString() : undefined,
          order: milestones.length,
        });
      }
      resetForm();
      await load();
    } catch (e) {
      console.error('Failed to save milestone', e);
    }
  };

  const cycleStatus = async (m: Milestone) => {
    const next: Record<MilestoneStatus, MilestoneStatus> = {
      pending: 'in_progress', in_progress: 'done', done: 'pending',
    };
    await updateMilestone(m.id, { status: next[m.status] });
    await load();
  };

  const removeMilestone = async (id: string) => {
    if (!confirm('Delete this milestone? Linked tasks will be unlinked, not deleted.')) return;
    await deleteMilestone(id);
    await load();
  };

  if (loading) {
    return <div className="flex-1 flex items-center justify-center"><Loader2 className="animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-1">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wider">Milestones</h2>
        <button
          onClick={() => { resetForm(); setFormOpen(true); }}
          className="flex items-center gap-2 bg-slate-900 text-white hover:bg-slate-800 px-3 py-1.5 rounded-lg text-sm font-medium"
        >
          <Plus size={14} /> Milestone
        </button>
      </div>

      {milestones.length === 0 && !formOpen ? (
        <div className="text-center text-slate-400 text-sm py-16 border border-dashed border-slate-200 rounded-xl">
          No milestones yet. Group tasks into phases to track project progress.
        </div>
      ) : (
        <div className="space-y-3 max-w-3xl">
          {milestones.map(m => {
            const progress = progressFor(m.id);
            const cfg = STATUS_CONFIG[m.status];
            return (
              <div key={m.id} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <button onClick={() => cycleStatus(m)} className={`mt-0.5 p-1.5 rounded-lg border ${cfg.color}`} title="Click to cycle status">
                      <Flag size={14} />
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-slate-800">{m.title}</h3>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${cfg.color}`}>{cfg.label}</span>
                      </div>
                      {m.description && <p className="text-sm text-slate-500 mt-1">{m.description}</p>}
                      {m.dueDate && (
                        <p className="text-xs text-slate-400 mt-1">Due {new Date(m.dueDate).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
                    <button onClick={() => startEdit(m)} className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded"><Pencil size={14} /></button>
                    <button onClick={() => removeMilestone(m.id)} className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"><Trash2 size={14} /></button>
                  </div>
                </div>
                {progress && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>{progress.done}/{progress.total} tasks</span>
                      <span>{progress.pct}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${progress.pct}%` }} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {formOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-slate-800">{editingId ? 'Edit Milestone' : 'New Milestone'}</h3>
              <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="space-y-3">
              <input
                type="text" placeholder="Title" value={title} onChange={e => setTitle(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                autoFocus
              />
              <textarea
                placeholder="Description (optional)" value={description} onChange={e => setDescription(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                rows={3}
              />
              <input
                type="date" value={dueDate} onChange={e => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={resetForm} className="text-slate-500 hover:text-slate-800 font-medium text-sm">Cancel</button>
              <button onClick={submitForm} disabled={!title.trim()} className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2">
                <Check size={16} /> Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
