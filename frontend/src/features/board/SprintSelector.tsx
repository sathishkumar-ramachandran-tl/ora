import React, { useState, useEffect, useRef } from 'react';
import { Sprint, SprintStatus } from '../../types';
import { ChevronDown, Plus, Play, CheckCircle, X } from 'lucide-react';
import { listSprints, createSprint, updateSprint } from '../../api/projects';

interface SprintSelectorProps {
  projectId: string;
  activeSprintId: string | 'all';
  onChange: (sprintId: string | 'all') => void;
  refreshKey: number;
  onSprintsChanged: () => void;
}

export const SprintSelector: React.FC<SprintSelectorProps> = ({ projectId, activeSprintId, onChange, refreshKey, onSprintsChanged }) => {
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newSprintName, setNewSprintName] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listSprints(projectId).then(setSprints).catch(console.error);
  }, [projectId, refreshKey]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const activeSprint = sprints.find(s => s.id === activeSprintId);

  const submitCreate = async () => {
    if (!newSprintName.trim()) return;
    await createSprint(projectId, { name: newSprintName, status: 'planned' });
    setNewSprintName('');
    setCreating(false);
    onSprintsChanged();
  };

  const setSprintStatus = async (sprintId: string, status: SprintStatus) => {
    await updateSprint(sprintId, { status });
    onSprintsChanged();
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 whitespace-nowrap"
      >
        {activeSprint ? activeSprint.name : 'All Sprints'}
        <ChevronDown size={14} />
      </button>

      {open && (
        <div className="absolute top-full mt-2 left-0 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-30 p-2">
          <button
            onClick={() => { onChange('all'); setOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${activeSprintId === 'all' ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-slate-50 text-slate-700'}`}
          >
            All Sprints
          </button>
          <div className="max-h-64 overflow-y-auto custom-scrollbar">
            {sprints.map(s => (
              <div
                key={s.id}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm group ${activeSprintId === s.id ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-slate-50 text-slate-700'}`}
              >
                <button onClick={() => { onChange(s.id); setOpen(false); }} className="flex-1 text-left flex items-center gap-2">
                  {s.name}
                  <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                    s.status === 'active' ? 'bg-emerald-100 text-emerald-700' :
                    s.status === 'completed' ? 'bg-slate-200 text-slate-500' : 'bg-blue-100 text-blue-700'
                  }`}>{s.status}</span>
                </button>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {s.status === 'planned' && (
                    <button onClick={() => setSprintStatus(s.id, 'active')} title="Start sprint" className="p-1 text-slate-400 hover:text-emerald-600"><Play size={12} /></button>
                  )}
                  {s.status === 'active' && (
                    <button onClick={() => setSprintStatus(s.id, 'completed')} title="Complete sprint" className="p-1 text-slate-400 hover:text-indigo-600"><CheckCircle size={12} /></button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-slate-100 mt-2 pt-2">
            {creating ? (
              <div className="flex gap-1 px-1">
                <input
                  autoFocus
                  value={newSprintName}
                  onChange={e => setNewSprintName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') submitCreate(); if (e.key === 'Escape') setCreating(false); }}
                  placeholder="Sprint name"
                  className="flex-1 px-2 py-1.5 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button onClick={submitCreate} className="px-2 text-indigo-600 hover:bg-indigo-50 rounded-lg"><CheckCircle size={16} /></button>
                <button onClick={() => setCreating(false)} className="px-2 text-slate-400 hover:bg-slate-50 rounded-lg"><X size={16} /></button>
              </div>
            ) : (
              <button onClick={() => setCreating(true)} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-50">
                <Plus size={14} /> New Sprint
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
