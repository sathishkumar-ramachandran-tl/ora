import React, { useState, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';
import { Company, Project, Task, Priority, Status } from '../types';

interface CreateCompanyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (company: Company) => Promise<void>;
  initialName?: string;
  initialMission?: string;
}

export const CreateCompanyModal: React.FC<CreateCompanyModalProps> = ({ isOpen, onClose, onSubmit, initialName, initialMission }) => {
  const [name, setName] = useState('');
  const [mission, setMission] = useState('');
  const [color, setColor] = useState('blue');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
        setName(initialName || '');
        setMission(initialMission || '');
    }
  }, [isOpen, initialName, initialMission]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const newCompany: Company = {
      id: crypto.randomUUID(),
      workspaceId: '', // Populated by parent
      name,
      mission,
      color,
      projects: []
    };
    await onSubmit(newCompany);
    setLoading(false);
    onClose();
    setName('');
    setMission('');
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800">New Initiative (Company)</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Initiative Name</label>
            <input required type="text" value={name} onChange={e => setName(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="e.g. Real Estate Ventures" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Mission / Goal</label>
            <textarea required value={mission} onChange={e => setMission(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="What is the high-level objective?" rows={3} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Color Theme</label>
            <div className="flex gap-2">
              {['blue', 'emerald', 'violet', 'orange', 'rose', 'slate'].map(c => (
                <button key={c} type="button" onClick={() => setColor(c)}
                  className={`w-6 h-6 rounded-full border-2 ${color === c ? 'border-slate-800' : 'border-transparent'}`}
                  style={{ backgroundColor: `var(--color-${c}-500)` }}
                >
                 <div className={`w-full h-full rounded-full bg-${c}-500`}></div>
                </button>
              ))}
            </div>
          </div>
          <button disabled={loading} type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2">
            {loading && <Loader2 className="animate-spin w-4 h-4" />} Create Initiative
          </button>
        </form>
      </div>
    </div>
  );
};

interface CreateProjectModalProps {
  isOpen: boolean;
  companyId: string;
  onClose: () => void;
  onSubmit: (project: Project, companyId: string) => Promise<void>;
}

export const CreateProjectModal: React.FC<CreateProjectModalProps> = ({ isOpen, companyId, onClose, onSubmit }) => {
  const [name, setName] = useState('');
  const [mission, setMission] = useState('');
  const [type, setType] = useState<Project['type']>('build');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const newProject: Project = {
      id: crypto.randomUUID(),
      workspaceId: '', // Populated by parent
      name,
      mission,
      type,
      progress: 0,
      tasks: [],
      companyId
    };
    await onSubmit(newProject, companyId);
    setLoading(false);
    onClose();
    setName('');
    setMission('');
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800">New Project</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Project Name</label>
            <input required type="text" value={name} onChange={e => setName(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" placeholder="e.g. Mobile App MVP" />
          </div>
          <div>
             <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
             <select value={type} onChange={e => setType(e.target.value as any)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white">
                <option value="build">Build (Product/Eng)</option>
                <option value="learning">Learning Track</option>
                <option value="client">Client Work</option>
             </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Goal / Outcome</label>
            <textarea required value={mission} onChange={e => setMission(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" placeholder="What defines success?" rows={3} />
          </div>
          <button disabled={loading} type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2">
             {loading && <Loader2 className="animate-spin w-4 h-4" />} Create Project
          </button>
        </form>
      </div>
    </div>
  );
};

interface CreateTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (task: Task) => Promise<void>;
}

export const CreateTaskModal: React.FC<CreateTaskModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<Priority>('medium');
  const [hours, setHours] = useState(1);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const newTask: Task = {
      id: crypto.randomUUID(),
      workspaceId: '', // Populated by parent
      title,
      description,
      priority,
      status: 'todo',
      estimatedHours: hours,
      assignee: 'Me'
    };
    await onSubmit(newTask);
    setLoading(false);
    onClose();
    setTitle('');
    setDescription('');
    setPriority('medium');
    setHours(1);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800">New Task</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Task Title</label>
            <input required value={title} onChange={e => setTitle(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" placeholder="What needs to be done?" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} 
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" rows={3} placeholder="Additional details..." />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Priority</label>
              <select value={priority} onChange={e => setPriority(e.target.value as Priority)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Est. Hours</label>
              <input type="number" min="0.5" step="0.5" value={hours} onChange={e => setHours(parseFloat(e.target.value))}
                 className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" />
            </div>
          </div>
          <button disabled={loading} type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2">
             {loading && <Loader2 className="animate-spin w-4 h-4" />} Add Task
          </button>
        </form>
      </div>
    </div>
  );
};