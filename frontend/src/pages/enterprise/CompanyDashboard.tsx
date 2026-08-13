import React, { useEffect, useState } from 'react';
import {
  Users, FolderKanban, CheckSquare, TrendingUp,
  Clock, AlertCircle, ChevronRight, UserPlus, Plus,
  Activity, Zap, Target, ArrowUpRight
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { Company } from '../../types';

interface CompanyDashboardProps {
  workspaceId: string;
  companies: Company[];
  onNavigateProjects: () => void;
  onNavigateTeam: () => void;
  onCreateProject: () => void;
}

interface Member {
  id: string;
  userId: string;
  name: string;
  email: string;
  role: string;
  joinedAt: string;
}

const ROLE_COLORS: Record<string, string> = {
  owner: 'bg-ora-warning-soft text-ora-warning border-ora-warning/25',
  admin: 'bg-ora-accent-soft text-ora-accent border-ora-accent/20',
  contributor: 'bg-ora-subtle text-ora-secondary border-ora-border',
  viewer: 'bg-ora-subtle text-ora-secondary border-ora-border',
};

const TYPE_COLORS: Record<string, string> = {
  build: 'bg-ora-accent',
  learning: 'bg-ora-info',
  client: 'bg-ora-accent',
  research: 'bg-ora-warning',
  campaign: 'bg-ora-danger',
};

export const CompanyDashboard: React.FC<CompanyDashboardProps> = ({
  workspaceId, companies, onNavigateProjects, onNavigateTeam, onCreateProject
}) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(true);

  useEffect(() => {
    if (!workspaceId) return;
    apiClient.get(`/workspaces/${workspaceId}/members`)
      .then(r => setMembers(r.data))
      .catch(console.error)
      .finally(() => setLoadingMembers(false));
  }, [workspaceId]);

  // Derived stats
  const allProjects = companies.flatMap(c => c.projects || []);
  const allTasks = allProjects.flatMap(p => p.tasks || []);
  const doneTasks = allTasks.filter(t => t.status === 'done');
  const overdueTasks = allTasks.filter(t => {
    if (!t.dueDate || t.status === 'done') return false;
    return new Date(t.dueDate) < new Date();
  });
  const avgProgress = allProjects.length
    ? Math.round(allProjects.reduce((a, p) => a + p.progress, 0) / allProjects.length)
    : 0;

  const statCards = [
    {
      label: 'Team Members',
      value: loadingMembers ? '…' : members.length,
      icon: Users,
      onClick: onNavigateTeam,
    },
    {
      label: 'Active Projects',
      value: allProjects.length,
      icon: FolderKanban,
      onClick: onNavigateProjects,
    },
    {
      label: 'Tasks Completed',
      value: doneTasks.length,
      icon: CheckSquare,
      onClick: onNavigateProjects,
    },
    {
      label: 'Avg. Progress',
      value: `${avgProgress}%`,
      icon: TrendingUp,
      onClick: onNavigateProjects,
    },
  ];

  return (
    <div className="flex-1 overflow-auto p-5 space-y-6 bg-ora-canvas">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, onClick }) => (
          <button
            key={label}
            onClick={onClick}
            className="bg-ora-surface border border-ora-border rounded-lg p-4 flex items-center gap-3 hover:border-ora-border-strong transition-all text-left group"
          >
            <div className="bg-ora-accent-soft p-2.5 rounded-lg flex-shrink-0">
              <Icon size={18} className="text-ora-accent" />
            </div>
            <div className="min-w-0">
              <p className="text-xl font-bold text-ora-primary leading-none">{value}</p>
              <p className="text-xs text-ora-secondary mt-1">{label}</p>
            </div>
            <ArrowUpRight size={14} className="ml-auto text-ora-tertiary group-hover:text-ora-accent transition-colors flex-shrink-0" />
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Project Health */}
        <div className="lg:col-span-2 bg-ora-surface/75 border border-ora-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-ora-primary text-sm flex items-center gap-2">
              <Target size={14} className="text-ora-accent" />
              Project Health
            </h2>
            <button
              onClick={onCreateProject}
              className="flex items-center gap-1.5 text-xs text-ora-accent hover:text-ora-accent-hover font-medium border border-ora-accent/20 hover:border-ora-accent/35 rounded-lg px-2.5 py-1 transition-colors"
            >
              <Plus size={12} /> New Project
            </button>
          </div>
          {allProjects.length === 0 ? (
            <div className="text-center py-10">
              <FolderKanban size={32} className="mx-auto text-ora-tertiary mb-3" />
              <p className="text-sm text-ora-secondary">No projects yet.</p>
              <button
                onClick={onCreateProject}
                className="mt-3 text-xs text-ora-accent hover:underline font-medium"
              >
                Create your first project
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {allProjects.map(proj => {
                const company = companies.find(c => (c.projects || []).some(p => p.id === proj.id));
                const openTasks = (proj.tasks || []).filter(t => t.status !== 'done').length;
                return (
                  <div key={proj.id} className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_COLORS[proj.type] ?? 'bg-slate-400'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-baseline mb-1">
                        <span className="text-xs font-semibold text-ora-primary truncate">{proj.name}</span>
                        <span className="text-xs font-mono text-ora-secondary ml-2 flex-shrink-0">{proj.progress}%</span>
                      </div>
                      <div className="h-1.5 bg-ora-subtle rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${proj.progress === 100 ? 'bg-ora-success' : proj.progress >= 60 ? 'bg-ora-accent' : proj.progress >= 30 ? 'bg-ora-warning' : 'bg-ora-danger'}`}
                          style={{ width: `${proj.progress}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2 text-[10px] text-ora-tertiary">
                      {openTasks > 0 && (
                        <span className="flex items-center gap-1">
                          <Clock size={10} />{openTasks} open
                        </span>
                      )}
                      {company && (
                        <span className="px-1.5 py-0.5 bg-ora-subtle rounded text-ora-secondary">{company.name}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-5">
          {/* Overdue tasks alert */}
          {overdueTasks.length > 0 && (
            <div className="bg-ora-danger-soft border border-ora-danger/25 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle size={14} className="text-ora-danger" />
                <h3 className="text-xs font-bold text-ora-danger">Overdue Tasks</h3>
                <span className="ml-auto text-xs font-mono font-bold text-ora-danger">{overdueTasks.length}</span>
              </div>
              <div className="space-y-1.5 max-h-32 overflow-auto">
                {overdueTasks.slice(0, 5).map(t => (
                  <div key={t.id} className="text-xs text-ora-danger truncate bg-ora-surface/70 rounded px-2 py-1">
                    {t.title}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Team members */}
          <div className="bg-ora-surface border border-ora-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-ora-primary text-sm flex items-center gap-2">
                <Users size={14} className="text-ora-accent" />
                Team
              </h2>
              <button
                onClick={onNavigateTeam}
                className="text-[11px] text-ora-accent hover:text-ora-accent-hover font-medium flex items-center gap-1"
              >
                Manage <ChevronRight size={11} />
              </button>
            </div>
            {loadingMembers ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-8 bg-ora-subtle rounded-lg animate-pulse" />
                ))}
              </div>
            ) : members.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-xs text-ora-secondary mb-2">No team members yet.</p>
                <button
                  onClick={onNavigateTeam}
                  className="text-xs text-ora-accent hover:underline font-medium flex items-center gap-1 mx-auto"
                >
                  <UserPlus size={12} /> Invite someone
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {members.slice(0, 5).map(m => (
                  <div key={m.userId} className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-ora-accent flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                      {(m.name || m.email)[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-ora-primary truncate">{m.name || m.email}</p>
                      <p className="text-[10px] text-ora-tertiary truncate">{m.email}</p>
                    </div>
                    <span className={`text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border ${ROLE_COLORS[m.role] ?? ROLE_COLORS.viewer}`}>
                      {m.role}
                    </span>
                  </div>
                ))}
                {members.length > 5 && (
                  <button onClick={onNavigateTeam} className="text-xs text-ora-tertiary hover:text-ora-secondary pt-1">
                    +{members.length - 5} more…
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="bg-ora-nav rounded-lg p-4 text-white">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={14} />
              <span className="text-xs font-bold">Quick Actions</span>
            </div>
            <div className="space-y-2">
              <button
                onClick={onCreateProject}
                className="w-full flex items-center gap-2 text-xs font-medium bg-white/15 hover:bg-white/25 rounded-lg px-3 py-2 transition-colors text-left"
              >
                <Plus size={12} /> New Project
              </button>
              <button
                onClick={onNavigateTeam}
                className="w-full flex items-center gap-2 text-xs font-medium bg-white/15 hover:bg-white/25 rounded-lg px-3 py-2 transition-colors text-left"
              >
                <UserPlus size={12} /> Invite Member
              </button>
              <button
                onClick={onNavigateProjects}
                className="w-full flex items-center gap-2 text-xs font-medium bg-white/15 hover:bg-white/25 rounded-lg px-3 py-2 transition-colors text-left"
              >
                <Activity size={12} /> View All Projects
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
