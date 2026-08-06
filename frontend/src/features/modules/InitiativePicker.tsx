import React, { useState } from 'react';
import { X, Loader2, FolderPlus, Check, LayoutGrid } from 'lucide-react';
import { Company } from '../../types';

interface InitiativePickerProps {
  companies: Company[];
  onCreateCompany: (company: Company) => Promise<void>;
  onConfirm: (companyId: string | undefined) => void;
  onClose: () => void;
  title?: string;
}

const COLORS = ['indigo', 'blue', 'emerald', 'amber', 'rose', 'violet'];

const COLOR_DOT: Record<string, string> = {
  indigo: 'bg-brand-500', blue: 'bg-blue-500', emerald: 'bg-emerald-500',
  amber: 'bg-amber-500', rose: 'bg-rose-500', violet: 'bg-violet-500',
};

export const InitiativePicker: React.FC<InitiativePickerProps> = ({
  companies, onCreateCompany, onConfirm, onClose, title = 'Choose an Initiative',
}) => {
  const [selectedId, setSelectedId] = useState<string>('');
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);

  const handleCreateAndSelect = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    const id = crypto.randomUUID();
    try {
      await onCreateCompany({
        id, workspaceId: '', name: newName.trim(), mission: '',
        color: COLORS[Math.floor(Math.random() * COLORS.length)], projects: [],
      });
      onConfirm(id);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[90] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-[0_24px_64px_-16px_rgba(15,23,42,0.4)] border border-slate-200/60 w-full max-w-sm overflow-hidden">
        <div className="flex justify-between items-center px-5 py-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-900 text-sm">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg p-1 transition-colors"><X size={18} /></button>
        </div>

        <div className="p-4">
          {!creating ? (
            <div className="space-y-3">
              <div className="space-y-1.5 max-h-56 overflow-y-auto custom-scrollbar pr-0.5">
                <button
                  onClick={() => setSelectedId('')}
                  className={`w-full flex items-center gap-2.5 text-left px-3 py-2.5 rounded-xl border transition-colors ${
                    selectedId === '' ? 'border-brand-300 bg-brand-50/60' : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <span className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                    <LayoutGrid size={13} className="text-slate-500" />
                  </span>
                  <span className="flex-1 text-sm font-medium text-slate-700">Default (Modules)</span>
                  {selectedId === '' && <Check size={15} className="text-brand-600 flex-shrink-0" />}
                </button>
                {companies.map(c => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedId(c.id)}
                    className={`w-full flex items-center gap-2.5 text-left px-3 py-2.5 rounded-xl border transition-colors ${
                      selectedId === c.id ? 'border-brand-300 bg-brand-50/60' : 'border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${COLOR_DOT[c.color] || 'bg-slate-400'}`} />
                    <span className="flex-1 text-sm font-medium text-slate-700 truncate">{c.name}</span>
                    {selectedId === c.id && <Check size={15} className="text-brand-600 flex-shrink-0" />}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setCreating(true)}
                className="w-full flex items-center justify-center gap-1.5 text-xs text-brand-600 hover:bg-brand-50 py-2 rounded-xl border border-dashed border-brand-200 transition-colors"
              >
                <FolderPlus size={13} /> New Initiative
              </button>
            </div>
          ) : (
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1.5">New Initiative name</label>
              <input
                autoFocus
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Product Launch"
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2.5 outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-400 transition-shadow"
              />
              <button onClick={() => setCreating(false)} className="text-xs text-slate-400 hover:text-slate-600 mt-2 transition-colors">
                &larr; choose existing instead
              </button>
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 border-t border-slate-100 flex justify-end gap-2">
          <button onClick={onClose} className="text-slate-500 hover:text-slate-800 text-sm font-medium px-3 rounded-lg transition-colors">Cancel</button>
          {creating ? (
            <button
              onClick={handleCreateAndSelect}
              disabled={saving || !newName.trim()}
              className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-xl disabled:opacity-50 transition-colors"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : null} Create &amp; Use
            </button>
          ) : (
            <button
              onClick={() => onConfirm(selectedId || undefined)}
              className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
            >
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
