import React, { useState, useEffect } from 'react';
import {
  Users, UserPlus, Mail, Trash2, Shield, ShieldCheck,
  Eye, Building2, Globe, MapPin, Layers, Save,
  CheckCircle, AlertCircle, Loader2, X, Plus, KeyRound, Pencil
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { apiClient } from '../../api/client';
import {
  OrgMember, CustomRole, PermissionCatalogEntry,
  getOrgMembers, inviteMember, updateMemberRole, removeMember,
  getRoles, createRole, updateRole, deleteRole, getPermissionCatalog,
} from '../../api/org';

const ROLE_OPTIONS = [
  { value: 'owner', label: 'Owner', icon: ShieldCheck, color: 'text-amber-600' },
  { value: 'admin', label: 'Admin', icon: Shield, color: 'text-blue-600' },
  { value: 'member', label: 'Member', icon: Users, color: 'text-slate-600' },
];

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-amber-50 text-amber-700 border-amber-200',
  admin: 'bg-blue-50 text-blue-700 border-blue-200',
  member: 'bg-slate-100 text-slate-600 border-slate-200',
};

const Toast: React.FC<{ msg: string; type: 'success' | 'error'; onClose: () => void }> = ({ msg, type, onClose }) => (
  <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium
    ${type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-700'}`}>
    {type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
    {msg}
    <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
  </div>
);

function useToast() {
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const show = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };
  return { toast, show, clear: () => setToast(null) };
}

export const AdminConsole: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const { workspace } = useAuth();
  const [view, setView] = useState<'members' | 'roles' | 'settings'>('members');

  if (!workspace) return null;

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto p-5 space-y-5">
        {/* Tab bar */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
          {[
            { id: 'members' as const, label: 'Members & Access', icon: Users },
            { id: 'roles' as const, label: 'Roles & Permissions', icon: KeyRound },
            { id: 'settings' as const, label: 'Settings', icon: Building2 },
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

        {view === 'members' && <MemberManagement organizationId={organizationId} />}
        {view === 'roles' && <RoleManagement organizationId={organizationId} />}
        {view === 'settings' && <WorkspaceSettings workspace={workspace} />}
      </div>
    </div>
  );
};

// ----- Member Management (Organization-scoped, real RBAC) -----

const MemberManagement: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [roles, setRoles] = useState<CustomRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviting, setInviting] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const { toast, show, clear } = useToast();

  const loadAll = async () => {
    try {
      const [m, r] = await Promise.all([getOrgMembers(organizationId), getRoles(organizationId)]);
      setMembers(m);
      setRoles(r);
    } catch {
      show('Failed to load members', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, [organizationId]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await inviteMember(organizationId, inviteEmail.trim(), inviteRole);
      show(`Invited ${inviteEmail}`, 'success');
      setInviteEmail('');
      setShowInvite(false);
      await loadAll();
    } catch (err: any) {
      show(err?.response?.data?.error || 'Failed to invite', 'error');
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await updateMemberRole(organizationId, userId, { role });
      show('Role updated', 'success');
      await loadAll();
    } catch (err: any) {
      show(err?.response?.data?.error || 'Failed to update role', 'error');
    }
  };

  const handleCustomRoleChange = async (userId: string, customRoleId: string) => {
    try {
      await updateMemberRole(organizationId, userId, { customRoleId: customRoleId || null });
      show('Permissions updated', 'success');
      await loadAll();
    } catch (err: any) {
      show(err?.response?.data?.error || 'Failed to update permissions', 'error');
    }
  };

  const handleRemove = async (userId: string, name: string) => {
    if (!confirm(`Remove ${name} from this organization?`)) return;
    try {
      await removeMember(organizationId, userId);
      show(`Removed ${name}`, 'success');
      await loadAll();
    } catch (err: any) {
      show(err?.response?.data?.error || 'Failed to remove member', 'error');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-slate-800 text-base">Organization Members</h2>
          <p className="text-xs text-slate-400 mt-0.5">{members.length} member{members.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowInvite(v => !v)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors shadow-sm shadow-indigo-200"
        >
          <UserPlus size={13} /> Invite Member
        </button>
      </div>

      {showInvite && (
        <form onSubmit={handleInvite} className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs font-semibold text-indigo-700 mb-1 block">Email address</label>
            <input
              type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com" required
              className="w-full border border-indigo-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-indigo-700 mb-1 block">Role</label>
            <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
              className="border border-indigo-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white">
              {ROLE_OPTIONS.filter(r => r.value !== 'owner').map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={inviting}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors h-[38px]">
            {inviting ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />}
            {inviting ? 'Sending…' : 'Send Invite'}
          </button>
          <button type="button" onClick={() => setShowInvite(false)} className="text-slate-500 hover:text-slate-700 text-xs py-2 px-2">Cancel</button>
        </form>
      )}

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
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
                <th className="text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider px-4 py-2.5">Role</th>
                <th className="text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider px-4 py-2.5 hidden md:table-cell">Custom Permissions</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {members.map(m => (
                <tr key={m.id} className="hover:bg-slate-50/50 transition-colors">
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
                  <td className="px-4 py-3">
                    {m.role === 'owner' ? (
                      <span className={`text-[10px] font-bold uppercase tracking-wide border px-2 py-0.5 rounded-full ${ROLE_BADGE.owner}`}>Owner</span>
                    ) : (
                      <select
                        value={m.role}
                        onChange={e => handleRoleChange(m.id, e.target.value)}
                        className={`text-[10px] font-bold uppercase tracking-wide border px-2 py-0.5 rounded-full bg-white ${ROLE_BADGE[m.role] ?? ROLE_BADGE.member}`}
                      >
                        {ROLE_OPTIONS.filter(r => r.value !== 'owner').map(r => (
                          <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    {m.role === 'owner' ? (
                      <span className="text-[11px] text-slate-400">All permissions</span>
                    ) : (
                      <select
                        value={m.customRoleId || ''}
                        onChange={e => handleCustomRoleChange(m.id, e.target.value)}
                        className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white"
                      >
                        <option value="">Default ({m.role})</option>
                        {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {m.role !== 'owner' && (
                      <button onClick={() => handleRemove(m.id, m.name || m.email)}
                        className="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors" title="Remove member">
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

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={clear} />}
    </div>
  );
};

// ----- Roles & Permissions -----

const RoleManagement: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const [roles, setRoles] = useState<CustomRole[]>([]);
  const [catalog, setCatalog] = useState<PermissionCatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingRole, setEditingRole] = useState<CustomRole | 'new' | null>(null);
  const { toast, show, clear } = useToast();

  const loadAll = async () => {
    try {
      const [r, c] = await Promise.all([getRoles(organizationId), getPermissionCatalog(organizationId)]);
      setRoles(r);
      setCatalog(c);
    } catch {
      show('Failed to load roles', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, [organizationId]);

  const handleDelete = async (role: CustomRole) => {
    if (!confirm(`Delete role "${role.name}"? Members using it will fall back to their default permissions.`)) return;
    try {
      await deleteRole(organizationId, role.id);
      show('Role deleted', 'success');
      await loadAll();
    } catch (err: any) {
      show(err?.response?.data?.error || 'Failed to delete role', 'error');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-slate-800 text-base">Roles & Permissions</h2>
          <p className="text-xs text-slate-400 mt-0.5">Granular access control — assign to members from the Members tab</p>
        </div>
        <button
          onClick={() => setEditingRole('new')}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors shadow-sm shadow-indigo-200"
        >
          <Plus size={13} /> New Role
        </button>
      </div>

      {loading ? (
        <div className="p-8 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {roles.map(role => (
            <div key={role.id} className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-slate-800 text-sm">{role.name}</h3>
                  {role.isSystem && <span className="text-[10px] text-slate-400">System default</span>}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => setEditingRole(role)} className="p-1.5 text-slate-300 hover:text-indigo-500 hover:bg-indigo-50 rounded-lg">
                    <Pencil size={13} />
                  </button>
                  {!role.isSystem && (
                    <button onClick={() => handleDelete(role)} className="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg">
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {(role.permissions || []).slice(0, 6).map(p => (
                  <span key={p} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">{p}</span>
                ))}
                {role.permissions?.length > 6 && (
                  <span className="text-[10px] text-slate-400">+{role.permissions.length - 6} more</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {editingRole && (
        <RoleEditorModal
          organizationId={organizationId}
          role={editingRole === 'new' ? null : editingRole}
          catalog={catalog}
          onClose={() => setEditingRole(null)}
          onSaved={() => { setEditingRole(null); loadAll(); }}
        />
      )}
      {toast && <Toast msg={toast.msg} type={toast.type} onClose={clear} />}
    </div>
  );
};

const RoleEditorModal: React.FC<{
  organizationId: string;
  role: CustomRole | null;
  catalog: PermissionCatalogEntry[];
  onClose: () => void;
  onSaved: () => void;
}> = ({ organizationId, role, catalog, onClose, onSaved }) => {
  const [name, setName] = useState(role?.name || '');
  const [selected, setSelected] = useState<Set<string>>(new Set(role?.permissions || []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const toggle = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleSave = async () => {
    if (!name.trim()) { setError('Role name is required'); return; }
    setSaving(true);
    setError('');
    try {
      const permissions = Array.from(selected);
      if (role) {
        await updateRole(organizationId, role.id, { name: name.trim(), permissions });
      } else {
        await createRole(organizationId, name.trim(), permissions);
      }
      onSaved();
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Failed to save role');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-auto p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-slate-800">{role ? 'Edit Role' : 'New Role'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X size={18} /></button>
        </div>

        <label className="text-xs font-semibold text-slate-600 block mb-1">Role name</label>
        <input
          value={name} onChange={e => setName(e.target.value)}
          disabled={role?.isSystem}
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:bg-slate-50"
          placeholder="e.g. Finance Reviewer"
        />

        <label className="text-xs font-semibold text-slate-600 block mb-2">Permissions</label>
        <div className="space-y-1.5 max-h-64 overflow-auto border border-slate-100 rounded-lg p-2">
          {catalog.map(({ key, description }) => (
            <label key={key} className="flex items-start gap-2.5 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer">
              <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} className="mt-0.5" />
              <div>
                <p className="text-xs font-mono font-semibold text-slate-700">{key}</p>
                <p className="text-[11px] text-slate-400">{description}</p>
              </div>
            </label>
          ))}
        </div>

        {error && <p className="text-xs text-red-500 mt-3">{error}</p>}

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="text-xs font-semibold text-slate-500 hover:text-slate-700 px-3 py-2">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold px-4 py-2 rounded-lg">
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            Save Role
          </button>
        </div>
      </div>
    </div>
  );
};

// ----- Workspace Settings (unchanged — workspace-level display fields) -----

const WorkspaceSettings: React.FC<{ workspace: any }> = ({ workspace }) => {
  const [name, setName] = useState(workspace.name || '');
  const [website, setWebsite] = useState(workspace.companyWebsite || '');
  const [location, setLocation] = useState(workspace.location || '');
  const [employeeCount, setEmployeeCount] = useState(workspace.employeeCount || '');
  const [aiContext, setAiContext] = useState(workspace.aiContextDescription || '');
  const [saving, setSaving] = useState(false);
  const { toast, show, clear } = useToast();

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await apiClient.patch(`/workspaces/${workspace.id}`, {
        name, companyWebsite: website, location, employeeCount, aiContextDescription: aiContext
      });
      show('Settings saved', 'success');
    } catch {
      show('Failed to save settings', 'error');
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

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={clear} />}
    </form>
  );
};
