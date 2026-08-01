import React, { useState, useEffect } from 'react';
import { User, CustomRole, Project, Company } from '../types';
import { Users, Shield, Plus, MoreHorizontal, UserPlus, Trash2, X, Loader2, Mail, CheckCircle2, ChevronDown } from 'lucide-react';
import { getWorkspaceMembers, addMemberToWorkspace, getProjectMembers, assignUserToProject, removeUserFromProject, removeWorkspaceMember } from '../services/db';
import { trackEvent } from '../services/analytics';

interface TeamManagementProps {
  workspaceId: string;
  customRoles: CustomRole[];
  companies?: Company[];
}

export const TeamManagement: React.FC<TeamManagementProps> = ({ workspaceId, customRoles: initialRoles, companies = [] }) => {
  const [activeTab, setActiveTab] = useState<'members' | 'projects'>('members');
  const [members, setMembers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [projectMembers, setProjectMembers] = useState<Record<string, User[]>>({});
  const [projectLoading, setProjectLoading] = useState<Record<string, boolean>>({});
  
  // Invite State
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  
  // Project Assignment State
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedMember, setSelectedMember] = useState<User | null>(null);
  const [assignLoading, setAssignLoading] = useState(false);

  useEffect(() => {
    loadMembers();
  }, [workspaceId]);

  const loadMembers = async () => {
      setLoading(true);
      try {
        const data = await getWorkspaceMembers(workspaceId);
        setMembers(data);
      } catch (e) {
          console.error(e);
      } finally {
          setLoading(false);
      }
  };

  const loadProjectMembers = async (projectId: string) => {
    if (projectMembers[projectId]) return; // Already loaded
    
    setProjectLoading(prev => ({ ...prev, [projectId]: true }));
    try {
      const data = await getProjectMembers(projectId);
      setProjectMembers(prev => ({ ...prev, [projectId]: data }));
    } catch (e) {
      console.error(e);
    } finally {
      setProjectLoading(prev => ({ ...prev, [projectId]: false }));
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
      e.preventDefault();
      setInviteLoading(true);
      try {
          await addMemberToWorkspace(workspaceId, inviteEmail, 'contributor');
          trackEvent('TEAM_MEMBER_ADDED', { workspaceId });
          
          await loadMembers();
          setSuccessMsg(`Invitation sent to ${inviteEmail}`);
          setInviteEmail('');
          setTimeout(() => {
              setSuccessMsg('');
              setInviteModalOpen(false);
          }, 1500);
      } catch (e) {
          console.error("Invite failed", e);
      } finally {
          setInviteLoading(false);
      }
  };

  const handleAssignMember = async () => {
    if (!selectedProject || !selectedMember) return;
    
    setAssignLoading(true);
    try {
      await assignUserToProject(selectedProject.id, selectedMember.id, 'contributor');
      trackEvent('TEAM_MEMBER_ASSIGNED_TO_PROJECT', { projectId: selectedProject.id, memberId: selectedMember.id });
      
      // Reload project members
      await loadProjectMembers(selectedProject.id);
      setAssignModalOpen(false);
      setSelectedProject(null);
      setSelectedMember(null);
    } catch (e) {
      console.error("Assignment failed", e);
    } finally {
      setAssignLoading(false);
    }
  };

  const handleRemoveFromProject = async (projectId: string, memberId: string) => {
    if (!confirm('Remove this member from the project?')) return;
    
    try {
      await removeUserFromProject(projectId, memberId);
      trackEvent('TEAM_MEMBER_REMOVED_FROM_PROJECT', { projectId, memberId });
      await loadProjectMembers(projectId);
    } catch (e) {
      console.error("Removal failed", e);
    }
  };

  const handleRemoveFromWorkspace = async (memberId: string) => {
    if (!confirm('Remove this member from the workspace?')) return;
    
    try {
      await removeWorkspaceMember(workspaceId, memberId);
      trackEvent('TEAM_MEMBER_REMOVED', { workspaceId, memberId });
      await loadMembers();
    } catch (e) {
      console.error("Removal failed", e);
    }
  };

  return (
    <div className="h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-slate-50 border-b border-slate-200">
            <div>
                <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <Users className="text-indigo-600" /> Team & Permissions
                </h2>
                <p className="text-sm text-slate-500 mt-1">Manage access to this Neural Workspace.</p>
            </div>
            <button 
                onClick={() => setInviteModalOpen(true)}
                className="w-full sm:w-auto bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors flex items-center justify-center gap-2"
            >
                <UserPlus size={16} /> Invite Member
            </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab('members')}
            className={`flex-1 px-4 py-3 text-sm font-medium text-center ${activeTab === 'members' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
          >
            Workspace Members ({members.length})
          </button>
          <button
            onClick={() => setActiveTab('projects')}
            className={`flex-1 px-4 py-3 text-sm font-medium text-center ${activeTab === 'projects' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
          >
            Project Access
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
            {activeTab === 'members' ? (
              loading ? (
                <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-500" /></div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {members.map((member) => (
                        <div key={member.id} className="border border-slate-200 rounded-xl p-4 flex items-center gap-4 hover:shadow-md transition-shadow group relative bg-white">
                            <div className="w-12 h-12 rounded-full bg-slate-100 overflow-hidden border border-slate-200 flex-shrink-0">
                                <img src={member.avatar || `https://ui-avatars.com/api/?name=${member.name}`} alt={member.name} className="w-full h-full object-cover" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <h3 className="font-bold text-slate-800 truncate">{member.name}</h3>
                                <p className="text-xs text-slate-500 truncate">{member.email}</p>
                                <span className={`inline-block mt-2 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${member.role === 'owner' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>
                                    {member.role === 'owner' ? 'Owner' : 'Contributor'}
                                </span>
                            </div>
                            {member.role !== 'owner' && (
                              <button onClick={() => handleRemoveFromWorkspace(member.id)} className="absolute top-4 right-4 text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100">
                                  <Trash2 size={16} />
                              </button>
                            )}
                        </div>
                    ))}
                </div>
              )
            ) : (
              <div className="space-y-4">
                {companies.length === 0 ? (
                  <p className="text-slate-500 text-center py-8">No projects found. Create a company and projects first.</p>
                ) : (
                  companies.map(company => (
                    <div key={company.id}>
                      {company.projects && company.projects.map(project => (
                        <div key={project.id} className="border border-slate-200 rounded-lg overflow-hidden mb-3">
                          <button
                            onClick={() => {
                              setExpandedProject(expandedProject === project.id ? null : project.id);
                              if (expandedProject !== project.id) {
                                loadProjectMembers(project.id);
                              }
                            }}
                            className="w-full px-4 py-3 bg-slate-50 hover:bg-slate-100 flex items-center justify-between text-left transition-colors"
                          >
                            <div>
                              <h3 className="font-bold text-slate-800">{project.name}</h3>
                              <p className="text-xs text-slate-500">{company.name}</p>
                            </div>
                            <ChevronDown size={18} className={`text-slate-400 transition-transform ${expandedProject === project.id ? 'rotate-180' : ''}`} />
                          </button>
                          
                          {expandedProject === project.id && (
                            <div className="p-4 border-t border-slate-200 space-y-3">
                              <div className="flex justify-between items-center mb-3">
                                <p className="text-sm font-medium text-slate-700">Assigned Members:</p>
                                <button
                                  onClick={() => {
                                    setSelectedProject(project);
                                    setAssignModalOpen(true);
                                  }}
                                  className="text-xs bg-indigo-100 text-indigo-700 px-2 py-1 rounded hover:bg-indigo-200 transition-colors flex items-center gap-1"
                                >
                                  <Plus size={14} /> Assign
                                </button>
                              </div>
                              
                              {projectLoading[project.id] ? (
                                <div className="flex justify-center py-4"><Loader2 className="animate-spin w-4 h-4 text-indigo-500" /></div>
                              ) : projectMembers[project.id]?.length === 0 ? (
                                <p className="text-xs text-slate-500 italic py-2">No members assigned yet</p>
                              ) : (
                                <div className="space-y-2">
                                  {projectMembers[project.id]?.map(member => (
                                    <div key={member.id} className="flex items-center justify-between bg-white p-2 rounded border border-slate-100 group">
                                      <div className="flex items-center gap-2 flex-1 min-w-0">
                                        <img src={member.avatar || `https://ui-avatars.com/api/?name=${member.name}`} alt={member.name} className="w-8 h-8 rounded-full" />
                                        <div className="min-w-0">
                                          <p className="text-sm font-medium text-slate-800 truncate">{member.name}</p>
                                          <p className="text-xs text-slate-500 truncate">{member.email}</p>
                                        </div>
                                      </div>
                                      <button
                                        onClick={() => handleRemoveFromProject(project.id, member.id)}
                                        className="text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 ml-2"
                                      >
                                        <Trash2 size={14} />
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ))
                )}
              </div>
            )}
        </div>

        {/* Invite Modal */}
        {inviteModalOpen && (
            <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <div className="flex justify-between items-center p-4 border-b border-slate-100">
                        <h3 className="font-bold text-slate-800">Invite Team Member</h3>
                        <button onClick={() => setInviteModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
                    </div>
                    
                    {successMsg ? (
                        <div className="p-8 text-center">
                            <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-3">
                                <CheckCircle2 size={24} />
                            </div>
                            <p className="text-emerald-800 font-medium">{successMsg}</p>
                        </div>
                    ) : (
                        <form onSubmit={handleInvite} className="p-4 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                                    <input 
                                        type="email" 
                                        required 
                                        value={inviteEmail}
                                        onChange={(e) => setInviteEmail(e.target.value)}
                                        className="w-full pl-9 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none" 
                                        placeholder="colleague@company.com" 
                                    />
                                </div>
                            </div>
                            <div className="bg-blue-50 text-blue-800 text-xs p-3 rounded-lg">
                                Tip: If they don't have a Sindhai account, a profile will be created for them automatically.
                            </div>
                            <button disabled={inviteLoading} type="submit" className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2">
                                {inviteLoading && <Loader2 className="animate-spin w-4 h-4" />} Send Invitation
                            </button>
                        </form>
                    )}
                </div>
            </div>
        )}

        {/* Project Assignment Modal */}
        {assignModalOpen && selectedProject && (
            <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <div className="flex justify-between items-center p-4 border-b border-slate-100">
                        <h3 className="font-bold text-slate-800">Assign Member to Project</h3>
                        <button onClick={() => {
                          setAssignModalOpen(false);
                          setSelectedProject(null);
                          setSelectedMember(null);
                        }} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
                    </div>
                    
                    <div className="p-4 space-y-4">
                        <div>
                            <p className="text-sm font-medium text-slate-700 mb-2">Project: <span className="font-bold text-indigo-600">{selectedProject.name}</span></p>
                        </div>
                        
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Select Member</label>
                            <select
                              value={selectedMember?.id || ''}
                              onChange={(e) => {
                                const member = members.find(m => m.id === e.target.value);
                                setSelectedMember(member || null);
                              }}
                              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                            >
                              <option value="">Choose a team member...</option>
                              {members.map(m => (
                                <option key={m.id} value={m.id}>{m.name} ({m.email})</option>
                              ))}
                            </select>
                        </div>

                        <button
                          disabled={!selectedMember || assignLoading}
                          onClick={handleAssignMember}
                          className="w-full bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2"
                        >
                          {assignLoading && <Loader2 className="animate-spin w-4 h-4" />} Assign to Project
                        </button>
                    </div>
                </div>
            </div>
        )}
    </div>
  );
};