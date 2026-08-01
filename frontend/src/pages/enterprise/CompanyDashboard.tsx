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
  owner: 'bg-amber-100 text-amber-700 border-amber-200',
  admin: 'bg-blue-100 text-blue-700 border-blue-200',
  contributor: 'bg-slate-100 text-slate-600 border-slate-200',
  viewer: 'bg-slate-100 text-slate-500 border-slate-200',
};

const TYPE_COLORS: Record<string, string> = {
  build: 'bg-blue-500',
  learning: 'bg-emerald-500',
  client: 'bg-violet-500',
  research: 'bg-amber-500',
  campaign: 'bg-rose-500',
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
      color: 'text-blue-600',
      bg: 'bg-blue-50',
      onClick: onNavigateTeam,
    },
    {
      label: 'Active Projects',
      value: allProjects.length,
      icon: FolderKanban,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
      onClick: onNavigateProjects,
    },
    {
      label: 'Tasks Completed',
      value: doneTasks.length,
      icon: CheckSquare,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      onClick: onNavigateProjects,
    },
    {
      label: 'Avg. Progress',
      value: `${avgProgress}%`,
      icon: TrendingUp,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      onClick: onNavigateProjects,
    },
  ];

  return (
    <div className="flex-1 overflow-auto p-5 space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color, bg, onClick }) => (
          <button
            key={label}
            onClick={onClick}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-3 hover:shadow-md hover:border-slate-300 transition-all text-left group"
          >
            <div className={`${bg} p-2.5 rounded-lg flex-shrink-0`}>
              <Icon size={18} className={color} />
            </div>
            <div className="min-w-0">
              <p className="text-xl font-bold text-slate-800 leading-none">{value}</p>
              <p className="text-xs text-slate-500 mt-1">{label}</p>
            </div>
            <ArrowUpRight size={14} className="ml-auto text-slate-300 group-hover:text-slate-500 transition-colors flex-shrink-0" />
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Project Health */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-slate-800 text-sm flex items-center gap-2">
              <Target size={14} className="text-indigo-500" />
              Project Health
            </h2>
            <button
              onClick={onCreateProject}
              className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-700 font-medium border border-indigo-200 hover:border-indigo-300 rounded-lg px-2.5 py-1 transition-colors"
            >
              <Plus size={12} /> New Project
            </button>
          </div>
          {allProjects.length === 0 ? (
            <div className="text-center py-10">
              <FolderKanban size={32} className="mx-auto text-slate-200 mb-3" />
              <p className="text-sm text-slate-400">No projects yet.</p>
              <button
                onClick={onCreateProject}
                className="mt-3 text-xs text-indigo-600 hover:underline font-medium"
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
                        <span className="text-xs font-semibold text-slate-700 truncate">{proj.name}</span>
                        <span className="text-xs font-mono text-slate-500 ml-2 flex-shrink-0">{proj.progress}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${proj.progress === 100 ? 'bg-emerald-500' : proj.progress >= 60 ? 'bg-blue-500' : proj.progress >= 30 ? 'bg-amber-500' : 'bg-rose-400'}`}
                          style={{ width: `${proj.progress}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2 text-[10px] text-slate-400">
                      {openTasks > 0 && (
                        <span className="flex items-center gap-1">
                          <Clock size={10} />{openTasks} open
                        </span>
                      )}
                      {company && (
                        <span className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500">{company.name}</span>
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
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle size={14} className="text-rose-500" />
                <h3 className="text-xs font-bold text-rose-700">Overdue Tasks</h3>
                <span className="ml-auto text-xs font-mono font-bold text-rose-600">{overdueTasks.length}</span>
              </div>
              <div className="space-y-1.5 max-h-32 overflow-auto">
                {overdueTasks.slice(0, 5).map(t => (
                  <div key={t.id} className="text-xs text-rose-600 truncate bg-white/70 rounded px-2 py-1">
                    {t.title}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Team members */}
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                <Users size={14} className="text-blue-500" />
                Team
              </h2>
              <button
                onClick={onNavigateTeam}
                className="text-[11px] text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
              >
                Manage <ChevronRight size={11} />
              </button>
            </div>
            {loadingMembers ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-8 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : members.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-xs text-slate-400 mb-2">No team members yet.</p>
                <button
                  onClick={onNavigateTeam}
                  className="text-xs text-indigo-600 hover:underline font-medium flex items-center gap-1 mx-auto"
                >
                  <UserPlus size={12} /> Invite someone
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {members.slice(0, 5).map(m => (
                  <div key={m.userId} className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                      {(m.name || m.email)[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-700 truncate">{m.name || m.email}</p>
                      <p className="text-[10px] text-slate-400 truncate">{m.email}</p>
                    </div>
                    <span className={`text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border ${ROLE_COLORS[m.role] ?? ROLE_COLORS.viewer}`}>
                      {m.role}
                    </span>
                  </div>
                ))}
                {members.length > 5 && (
                  <button onClick={onNavigateTeam} className="text-xs text-slate-400 hover:text-slate-600 pt-1">
                    +{members.length - 5} more…
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="bg-gradient-to-br from-indigo-600 to-blue-600 rounded-xl p-4 text-white">
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
