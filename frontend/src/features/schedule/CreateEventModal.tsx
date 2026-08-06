import React, { useState, useEffect } from 'react';
import { X, Loader2, Repeat } from 'lucide-react';
import { CalendarEvent } from '../../types';

interface CreateEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (event: Partial<CalendarEvent>) => Promise<void>;
  defaultStart: Date;
  defaultDurationHours?: number;
}

const RECURRENCE_PRESETS: { label: string; rule: string | null }[] = [
  { label: 'Does not repeat', rule: null },
  { label: 'Daily', rule: 'FREQ=DAILY' },
  { label: 'Weekly', rule: 'FREQ=WEEKLY' },
  { label: 'Weekdays (Mon-Fri)', rule: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR' },
  { label: 'Monthly', rule: 'FREQ=MONTHLY' },
];

export const CreateEventModal: React.FC<CreateEventModalProps> = ({
  isOpen, onClose, onSubmit, defaultStart, defaultDurationHours = 1,
}) => {
  const [title, setTitle] = useState('');
  const [scope, setScope] = useState<CalendarEvent['scope']>('personal');
  const [color, setColor] = useState('blue');
  const [recurrenceRule, setRecurrenceRule] = useState<string | null>(null);
  const [durationHours, setDurationHours] = useState(defaultDurationHours);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setScope('personal');
      setColor('blue');
      setRecurrenceRule(null);
      setDurationHours(defaultDurationHours);
    }
  }, [isOpen, defaultDurationHours]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    const start = new Date(defaultStart);
    const end = new Date(start);
    end.setMinutes(end.getMinutes() + durationHours * 60);
    try {
      await onSubmit({
        title,
        start: start.toISOString(),
        end: end.toISOString(),
        type: 'block',
        scope,
        color,
        recurrenceRule: recurrenceRule || undefined,
      });
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800">New Event</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Event Title</label>
            <input
              autoFocus required type="text" value={title} onChange={e => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              placeholder="e.g. Client sync"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Starts</label>
              <div className="px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 text-sm text-slate-600">
                {defaultStart.toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Duration (hrs)</label>
              <input
                type="number" min="0.5" step="0.5" value={durationHours}
                onChange={e => setDurationHours(parseFloat(e.target.value) || 0.5)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Visibility</label>
            <select value={scope} onChange={e => setScope(e.target.value as CalendarEvent['scope'])}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white">
              <option value="personal">Personal (only you)</option>
              <option value="workspace">Workspace (all members)</option>
              <option value="company">Company (whole organization)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center gap-1">
              <Repeat size={14} /> Repeats
            </label>
            <select
              value={recurrenceRule ?? ''}
              onChange={e => setRecurrenceRule(e.target.value || null)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
            >
              {RECURRENCE_PRESETS.map(p => (
                <option key={p.label} value={p.rule ?? ''}>{p.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Color</label>
            <div className="flex gap-2">
              {['blue', 'indigo', 'emerald', 'violet', 'orange', 'rose'].map(c => (
                <button key={c} type="button" onClick={() => setColor(c)}
                  className={`w-6 h-6 rounded-full border-2 ${color === c ? 'border-slate-800' : 'border-transparent'} bg-${c}-500`}
                />
              ))}
            </div>
          </div>

          <button disabled={loading} type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2 disabled:opacity-70">
            {loading && <Loader2 className="animate-spin w-4 h-4" />} Create Event
          </button>
        </form>
      </div>
    </div>
  );
};

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  isSeries?: boolean;
  onConfirm: (deleteSeries: boolean) => Promise<void>;
  onClose: () => void;
}

export const ConfirmDeleteModal: React.FC<ConfirmDeleteModalProps> = ({
  isOpen, title, message, isSeries, onConfirm, onClose,
}) => {
  const [deleteSeries, setDeleteSeries] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) setDeleteSeries(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await onConfirm(deleteSeries);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800">{title}</h3>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-sm text-slate-600">{message}</p>
          {isSeries && (
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={deleteSeries} onChange={e => setDeleteSeries(e.target.checked)} />
              Delete the entire recurring series
            </label>
          )}
        </div>
        <div className="p-4 pt-0 flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-lg">Cancel</button>
          <button disabled={loading} onClick={handleConfirm}
            className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-70">
            {loading && <Loader2 className="animate-spin w-4 h-4" />} Delete
          </button>
        </div>
      </div>
    </div>
  );
};
