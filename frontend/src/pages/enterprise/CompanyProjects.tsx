import React, { useState } from 'react';
import {
  FolderKanban, Plus, Search, Filter, CheckSquare,
  Clock, AlertTriangle, ChevronRight, Users, Tag,
  Bug, Star, BookOpen, Check as CheckIcon, Circle
} from 'lucide-react';
import { Company, Project } from '../../types';

interface CompanyProjectsProps {
  companies: Company[];
  onNavigateProject: (projectId: string, companyId: string) => void;
  onCreateProject: (companyId: string) => void;
}

type FilterType = 'all' | 'build' | 'learning' | 'client' | 'research' | 'campaign';

const TYPE_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  build:    { color: 'text-blue-600',   bg: 'bg-blue-50 border-blue-200',    label: 'Build' },
  learning: { color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', label: 'Learning' },
  client:   { color: 'text-violet-600',  bg: 'bg-violet-50 border-violet-200',  label: 'Client' },
  research: { color: 'text-amber-600',   bg: 'bg-amber-50 border-amber-200',    label: 'Research' },
  campaign: { color: 'text-rose-600',    bg: 'bg-rose-50 border-rose-200',      label: 'Campaign' },
};

const ISSUE_ICON: Record<string, React.ElementType> = {
  task:    CheckIcon,
  bug:     Bug,
  feature: Star,
  story:   BookOpen,
};

function progressRingStyle(progress: number): React.CSSProperties {
  const r = 18;
  const c = 2 * Math.PI * r;
  return {
    strokeDasharray: `${c}`,
    strokeDashoffset: `${c - (progress / 100) * c}`,
  };
}

const ProgressRing: React.FC<{ progress: number }> = ({ progress }) => (
  <svg width="44" height="44" viewBox="0 0 44 44" className="flex-shrink-0 -rotate-90">
    <circle cx="22" cy="22" r="18" fill="none" stroke="#e2e8f0" strokeWidth="4" />
    <circle
      cx="22" cy="22" r="18" fill="none"
      stroke={progress === 100 ? '#10b981' : progress >= 60 ? '#3b82f6' : progress >= 30 ? '#f59e0b' : '#f87171'}
      strokeWidth="4"
      strokeLinecap="round"
      style={progressRingStyle(progress)}
      className="transition-all duration-700"
    />
    <text
      x="22" y="22"
      textAnchor="middle" dominantBaseline="central"
      fontSize="9" fontWeight="700"
      fill="#475569"
      className="rotate-90"
      transform="rotate(90, 22, 22)"
    >
      {progress}%
    </text>
  </svg>
);

const ProjectCard: React.FC<{
  project: Project;
  company: Company;
  onOpen: () => void;
}> = ({ project, company, onOpen }) => {
  const cfg = TYPE_CONFIG[project.type] ?? { color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200', label: project.type };
  const tasks = project.tasks || [];
  const open = tasks.filter(t => t.status !== 'done');
  const done = tasks.filter(t => t.status === 'done');
  const overdue = tasks.filter(t => {
    if (!t.dueDate || t.status === 'done') return false;
    return new Date(t.dueDate) < new Date();
  });

  return (
    <div
      className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group"
      onClick={onOpen}
    >
      <div className="flex items-start gap-3">
        <ProgressRing progress={project.progress} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-bold text-slate-800 text-sm leading-tight truncate">{project.name}</h3>
            <ChevronRight size={14} className="text-slate-300 group-hover:text-slate-500 transition-colors flex-shrink-0 mt-0.5" />
          </div>

          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className={`text-[10px] font-bold uppercase tracking-wide border px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
              {cfg.label}
            </span>
            <span className="text-[10px] text-slate-400 truncate">{company.name}</span>
          </div>

          {project.mission && (
            <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed line-clamp-2">{project.mission}</p>
          )}

          <div className="flex items-center gap-3 mt-2.5 flex-wrap">
            {tasks.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-slate-500">
                <CheckSquare size={10} /> {done.length}/{tasks.length} tasks
              </span>
            )}
            {open.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-slate-500">
                <Clock size={10} /> {open.length} open
              </span>
            )}
            {overdue.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-rose-500 font-medium">
                <AlertTriangle size={10} /> {overdue.length} overdue
              </span>
            )}
          </div>

          {/* Labels */}
          {tasks.some(t => (t.labels || []).length > 0) && (
            <div className="flex items-center gap-1 mt-2 flex-wrap">
              {[...new Set(tasks.flatMap(t => t.labels || []))].slice(0, 4).map(label => (
                <span key={label} className="text-[9px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded-full border border-indigo-100">
                  {label}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const CompanyProjects: React.FC<CompanyProjectsProps> = ({
  companies, onNavigateProject, onCreateProject
}) => {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set(companies.map(c => c.id)));

  const allProjects = companies.flatMap(c => (c.projects || []).map(p => ({ ...p, _company: c })));
  const filtered = allProjects.filter(p => {
    const matchType = filter === 'all' || p.type === filter;
    const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
      p._company.name.toLowerCase().includes(search.toLowerCase());
    return matchType && matchSearch;
  });

  const toggleCompany = (id: string) => {
    setExpandedCompanies(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const FILTER_TABS: { id: FilterType; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'build', label: 'Build' },
    { id: 'learning', label: 'Learning' },
    { id: 'client', label: 'Client' },
    { id: 'research', label: 'Research' },
    { id: 'campaign', label: 'Campaign' },
  ];

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search projects…"
            className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 bg-white"
          />
        </div>

        <div className="flex gap-1 bg-white border border-slate-200 rounded-lg p-1 overflow-x-auto">
          {FILTER_TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={`px-2.5 py-1 rounded text-xs font-medium whitespace-nowrap transition-colors
                ${filter === id ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total', value: allProjects.length, color: 'text-slate-700' },
          { label: 'Showing', value: filtered.length, color: 'text-indigo-600' },
          { label: 'Complete', value: allProjects.filter(p => p.progress === 100).length, color: 'text-emerald-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-slate-200 rounded-lg p-3 text-center">
            <p className={`text-lg font-bold ${color}`}>{value}</p>
            <p className="text-[10px] text-slate-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Projects grouped by company */}
      {companies.length === 0 ? (
        <div className="text-center py-16">
          <FolderKanban size={40} className="mx-auto text-slate-200 mb-3" />
          <p className="text-sm text-slate-400 mb-2">No initiatives yet.</p>
          <p className="text-xs text-slate-400">Create an initiative to start organizing projects.</p>
        </div>
      ) : (
        companies.map(company => {
          const companyProjects = (company.projects || []).filter(p => {
            const matchType = filter === 'all' || p.type === filter;
            const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
              company.name.toLowerCase().includes(search.toLowerCase());
            return matchType && matchSearch;
          });

          if (companyProjects.length === 0 && (filter !== 'all' || search)) return null;

          const isExpanded = expandedCompanies.has(company.id);

          return (
            <div key={company.id}>
              {/* Company header */}
              <div
                className="flex items-center gap-3 mb-3 cursor-pointer group"
                onClick={() => toggleCompany(company.id)}
              >
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: `var(--color-${company.color}-500, #6366f1)` }}
                />
                <h2 className="font-bold text-slate-700 text-sm">{company.name}</h2>
                <span className="text-xs text-slate-400">({companyProjects.length})</span>
                <button
                  onClick={(e) => { e.stopPropagation(); onCreateProject(company.id); }}
                  className="ml-auto flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-700 font-medium opacity-0 group-hover:opacity-100 transition-opacity border border-indigo-200 hover:border-indigo-300 rounded px-2 py-0.5"
                >
                  <Plus size={10} /> Project
                </button>
                <ChevronRight
                  size={14}
                  className={`text-slate-400 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                />
              </div>

              {isExpanded && (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mb-5 ml-6">
                  {companyProjects.map(proj => (
                    <ProjectCard
                      key={proj.id}
                      project={proj}
                      company={company}
                      onOpen={() => onNavigateProject(proj.id, company.id)}
                    />
                  ))}
                  {companyProjects.length === 0 && (
                    <div className="col-span-full py-6 text-center text-slate-400 text-xs">
                      No projects in this initiative.
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
};
