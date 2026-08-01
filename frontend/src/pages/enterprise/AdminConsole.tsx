import React, { useState, useEffect } from 'react';
import {
  Users, UserPlus, Mail, Trash2, Shield, ShieldCheck,
  Eye, Building2, Globe, MapPin, Layers, Save,
  CheckCircle, AlertCircle, Loader2, X
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { apiClient } from '../../api/client';

interface Member {
  id: string;
  userId: string;
  name: string;
  email: string;
  role: string;
  joinedAt: string;
}

const ROLE_OPTIONS = [
  { value: 'owner', label: 'Owner', icon: ShieldCheck, color: 'text-amber-600' },
  { value: 'admin', label: 'Admin', icon: Shield, color: 'text-blue-600' },
  { value: 'contributor', label: 'Contributor', icon: Users, color: 'text-slate-600' },
  { value: 'viewer', label: 'Viewer', icon: Eye, color: 'text-slate-400' },
];

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-amber-50 text-amber-700 border-amber-200',
  admin: 'bg-blue-50 text-blue-700 border-blue-200',
  contributor: 'bg-slate-100 text-slate-600 border-slate-200',
  viewer: 'bg-slate-50 text-slate-500 border-slate-200',
};

const Toast: React.FC<{ msg: string; type: 'success' | 'error'; onClose: () => void }> = ({ msg, type, onClose }) => (
  <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium
    ${type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-700'}`}>
    {type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
    {msg}
    <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
  </div>
);

export const AdminConsole: React.FC = () => {
  const { workspace } = useAuth();
  const [view, setView] = useState<'members' | 'settings'>('members');

  if (!workspace) return null;

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto p-5 space-y-5">
        {/* Tab bar */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
          {[
            { id: 'members' as const, label: 'Members & Access', icon: Users },
            { id: 'settings' as const, label: 'Workspace Settings', icon: Building2 },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${view === id ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {view === 'members' && <MemberManagement workspaceId={workspace.id} />}
        {view === 'settings' && <WorkspaceSettings workspace={workspace} />}
      </div>
    </div>
  );
};

// ----- Member Management -----

const MemberManagement: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('contributor');
  const [inviting, setInviting] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const loadMembers = async () => {
    try {
      const res = await apiClient.get(`/workspaces/${workspaceId}/members`);
      setMembers(res.data);
    } catch {
      showToast('Failed to load members', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadMembers(); }, [workspaceId]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await apiClient.post(`/workspaces/${workspaceId}/invite`, { email: inviteEmail.trim(), role: inviteRole });
      showToast(`Invited ${inviteEmail}`, 'success');
      setInviteEmail('');
      setShowInvite(false);
      await loadMembers();
    } catch (err: any) {
      showToast(err?.response?.data?.error || 'Failed to invite', 'error');
    } finally {
      setInviting(false);
    }
  };

  const handleRemove = async (memberId: string, name: string) => {
    if (!confirm(`Remove ${name} from this workspace?`)) return;
    try {
      await apiClient.delete(`/workspaces/${workspaceId}/members/${memberId}`);
      showToast(`Removed ${name}`, 'success');
      await loadMembers();
    } catch {
      showToast('Failed to remove member', 'error');
    }
  };

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-slate-800 text-base">Team Members</h2>
          <p className="text-xs text-slate-400 mt-0.5">{members.length} member{members.length !== 1 ? 's' : ''} in this workspace</p>
        </div>
        <button
          onClick={() => setShowInvite(v => !v)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors shadow-sm shadow-indigo-200"
        >
          <UserPlus size={13} /> Invite Member
        </button>
      </div>

      {/* Invite form */}
      {showInvite && (
        <form
          onSubmit={handleInvite}
          className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row gap-3 items-end"
        >
          <div className="flex-1">
            <label className="text-xs font-semibold text-indigo-700 mb-1 block">Email address</label>
            <input
              type="email"
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              required
              className="w-full border border-indigo-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-indigo-700 mb-1 block">Role</label>
            <select
              value={inviteRole}
              onChange={e => setInviteRole(e.target.value)}
              className="border border-indigo-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            >
              {ROLE_OPTIONS.filter(r => r.value !== 'owner').map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={inviting}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors h-[38px]"
          >
            {inviting ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />}
            {inviting ? 'Sending…' : 'Send Invite'}
          </button>
          <button
            type="button"
            onClick={() => setShowInvite(false)}
            className="text-slate-500 hover:text-slate-700 text-xs py-2 px-2"
          >
            Cancel
          </button>
        </form>
      )}

      {/* Member list */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <Loader2 size={20} className="animate-spin text-slate-400 mx-auto" />
          </div>
        ) : members.length === 0 ? (
          <div className="p-10 text-center">
            <Users size={32} className="mx-auto text-slate-200 mb-3" />
            <p className="text-sm text-slate-400">No members yet. Invite your team!</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider px-4 py-2.5">Member</th>
                <th className="text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider px-4 py-2.5 hidden sm:table-cell">Role</th>
                <th className="text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider px-4 py-2.5 hidden md:table-cell">Joined</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {members.map(m => (
                <tr key={m.userId} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-blue-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                        {(m.name || m.email)[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-800 truncate text-sm">{m.name || '—'}</p>
                        <p className="text-[11px] text-slate-400 truncate">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className={`text-[10px] font-bold uppercase tracking-wide border px-2 py-0.5 rounded-full ${ROLE_BADGE[m.role] ?? ROLE_BADGE.viewer}`}>
                      {m.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[11px] text-slate-400 hidden md:table-cell">
                    {m.joinedAt ? new Date(m.joinedAt).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {m.role !== 'owner' && (
                      <button
                        onClick={() => handleRemove(m.id, m.name || m.email)}
                        className="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                        title="Remove member"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

// ----- Workspace Settings -----

const WorkspaceSettings: React.FC<{ workspace: any }> = ({ workspace }) => {
  const [name, setName] = useState(workspace.name || '');
  const [website, setWebsite] = useState(workspace.companyWebsite || '');
  const [location, setLocation] = useState(workspace.location || '');
  const [employeeCount, setEmployeeCount] = useState(workspace.employeeCount || '');
  const [aiContext, setAiContext] = useState(workspace.aiContextDescription || '');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await apiClient.patch(`/workspaces/${workspace.id}`, {
        name, companyWebsite: website, location, employeeCount, aiContextDescription: aiContext
      });
      showToast('Settings saved', 'success');
    } catch {
      showToast('Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const EMPLOYEE_OPTIONS = ['1–5', '6–15', '16–50', '51–200', '201–500', '500+'];

  return (
    <form onSubmit={handleSave} className="space-y-5">
      <div>
        <h2 className="font-bold text-slate-800 text-base mb-4">Workspace Settings</h2>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold text-slate-700 text-sm flex items-center gap-2">
          <Building2 size={14} className="text-indigo-500" /> Organization Info
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">Workspace Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200"
              required
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1 flex items-center gap-1">
              <Globe size={11} /> Website
            </label>
            <input
              value={website}
              onChange={e => setWebsite(e.target.value)}
              placeholder="https://yourcompany.com"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1 flex items-center gap-1">
              <MapPin size={11} /> Location
            </label>
            <input
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="City, Country"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1 flex items-center gap-1">
              <Layers size={11} /> Team Size
            </label>
            <select
              value={employeeCount}
              onChange={e => setEmployeeCount(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 bg-white"
            >
              <option value="">Select…</option>
              {EMPLOYEE_OPTIONS.map(o => <option key={o} value={o}>{o} people</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
        <h3 className="font-semibold text-slate-700 text-sm flex items-center gap-2">
          <Shield size={14} className="text-indigo-500" /> AI Context
        </h3>
        <p className="text-xs text-slate-400">
          Describe your organization for the AI Chief of Staff. The more context you give, the smarter the recommendations.
        </p>
        <textarea
          value={aiContext}
          onChange={e => setAiContext(e.target.value)}
          rows={4}
          placeholder="e.g. We are a B2B SaaS startup building analytics tools for SMBs. Our team of 8 is focused on product-market fit…"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
        />
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors shadow-sm shadow-indigo-200"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </form>
  );
};
