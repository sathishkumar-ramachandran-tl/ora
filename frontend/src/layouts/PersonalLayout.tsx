import React from 'react';
import {
  LayoutDashboard, Network, Calendar, ChevronRight, Plus, PlusCircle,
  HardDrive, Users, LogOut, Languages, Lightbulb, Menu, X,
  Target, Globe, Briefcase, Bot, Home, FolderOpen, Sparkles,
  ChevronDown, Check, Building2, User
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { createWorkspace } from '../api/workspace';
import { createOrganization } from '../api/org';
import { Company, Language } from '../types';

interface PersonalLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  onTabChange: (tab: string) => void;
  companies: Company[];
  selectedCompanyId: string | null;
  selectedProjectId: string | null;
  onSelectCompany: (id: string) => void;
  onSelectProject: (pid: string, cid: string) => void;
  onAddCompany: () => void;
  onAddProject: (cid: string) => void;
  headerActions?: React.ReactNode;
}

const getLabels = (persona: string = 'general') => {
  if (persona.includes('student') || persona.includes('upsc')) {
    return { company: 'Subject / Area', project: 'Module' };
  }
  if (persona.includes('researcher')) {
    return { company: 'Research Domain', project: 'Paper / Grant' };
  }
  return { company: 'Initiative', project: 'Project' };
};

// Bottom nav items for mobile
const BOTTOM_NAV = [
  { id: 'dashboard', icon: Home, label: 'Home' },
  { id: 'schedule', icon: Calendar, label: 'Schedule' },
  { id: 'graph', icon: Network, label: 'Graph' },
  { id: 'ideas', icon: Lightbulb, label: 'Ideas' },
  { id: 'documents', icon: HardDrive, label: 'Vault' },
];

export const PersonalLayout: React.FC<PersonalLayoutProps> = ({
  children,
  activeTab,
  onTabChange,
  companies,
  selectedCompanyId,
  selectedProjectId,
  onSelectCompany,
  onSelectProject,
  onAddCompany,
  onAddProject,
  headerActions
}) => {
  const { user, workspace, workspaces, logout, switchWorkspace, refreshWorkspaces } = useAuth();
  const [language, setLanguage] = React.useState<Language>('en');
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(false);
  const [expandedCompanies, setExpandedCompanies] = React.useState<Set<string>>(new Set());
  const [wsMenuOpen, setWsMenuOpen] = React.useState(false);
  const [creatingWs, setCreatingWs] = React.useState(false);
  const [newWsName, setNewWsName] = React.useState('');
  const [newWsType, setNewWsType] = React.useState<'personal' | 'company'>('personal');

  const currentCompany = companies.find(c => c.id === selectedCompanyId);
  const currentProject = currentCompany?.projects.find(p => p.id === selectedProjectId);
  const labels = getLabels(workspace?.persona);

  const toggleCompany = (id: string) => {
    setExpandedCompanies(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSelectCompany = (id: string) => {
    onSelectCompany(id);
    setExpandedCompanies(prev => new Set([...prev, id]));
    setIsSidebarOpen(false);
  };

  const handleSelectProject = (pid: string, cid: string) => {
    onSelectProject(pid, cid);
    setIsSidebarOpen(false);
  };

  const PageTitle = () => {
    if (activeTab === 'dashboard') return <><Target className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Neural Overview</span></>;
    if (activeTab === 'documents') return <><HardDrive className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Secure Vault</span></>;
    if (activeTab === 'team') return <><Users className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Team & Roles</span></>;
    if (activeTab === 'graph') return <><Network className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Knowledge Graph</span></>;
    if (activeTab === 'schedule') return <><Calendar className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Schedule</span></>;
    if (activeTab === 'ideas') return <><Lightbulb className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Idea Incubator</span></>;
    if (activeTab === 'modules') return <><Sparkles className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">Module Marketplace</span></>;
    if (activeTab === 'company' && currentCompany) return <><Globe className="text-indigo-600 flex-shrink-0" size={18} /><span className="truncate">{currentCompany.name}</span></>;
    if (activeTab === 'project' && currentProject) return (
      <>
        <Briefcase className="text-indigo-600 flex-shrink-0" size={18} />
        <span className="text-slate-400 font-normal hidden sm:inline truncate max-w-[80px]">{currentCompany?.name} /</span>
        <span className="truncate">{currentProject.name}</span>
      </>
    );
    return <span className="truncate">Ora</span>;
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden backdrop-blur-sm"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Sidebar — fixed on desktop, slide-in drawer on mobile              */}
      {/* ------------------------------------------------------------------ */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-slate-900 text-slate-300
        flex flex-col flex-shrink-0 transition-transform duration-300 ease-in-out shadow-2xl
        md:relative md:w-64 md:translate-x-0
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Brand + Workspace Switcher */}
        <div className="px-3 pt-4 pb-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center flex-shrink-0">
                <Bot size={12} className="text-white" />
              </div>
              <span className="text-white font-bold text-sm tracking-tight">Ora</span>
            </div>
            <button onClick={() => setIsSidebarOpen(false)} className="md:hidden text-slate-400 hover:text-white p-1">
              <X size={16} />
            </button>
          </div>

          {/* Workspace Dropdown */}
          <div className="relative">
            <button
              onClick={() => setWsMenuOpen(v => !v)}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors group">
              <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0
                ${workspace?.context === 'company' ? 'bg-blue-600' : 'bg-indigo-600'}`}>
                {workspace?.context === 'company'
                  ? <Building2 size={11} className="text-white" />
                  : <User size={11} className="text-white" />}
              </div>
              <span className="flex-1 text-left text-xs font-medium text-slate-200 truncate">{workspace?.name}</span>
              <ChevronDown size={12} className={`text-slate-500 transition-transform flex-shrink-0 ${wsMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {wsMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setWsMenuOpen(false)} />
                <div className="absolute top-full left-0 right-0 mt-1 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden">
                  <div className="p-1">
                    {workspaces.map(ws => (
                      <button
                        key={ws.id}
                        onClick={() => { switchWorkspace(ws.id); setWsMenuOpen(false); }}
                        className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-slate-700 transition-colors text-left">
                        <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0
                          ${ws.context === 'company' ? 'bg-blue-600/80' : 'bg-indigo-600/80'}`}>
                          {ws.context === 'company'
                            ? <Building2 size={9} className="text-white" />
                            : <User size={9} className="text-white" />}
                        </div>
                        <span className="flex-1 text-xs text-slate-300 truncate">{ws.name}</span>
                        {ws.id === workspace?.id && <Check size={11} className="text-indigo-400 flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                  <div className="border-t border-slate-700 p-1">
                    {!creatingWs ? (
                      <button
                        onClick={() => setCreatingWs(true)}
                        className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-slate-700 transition-colors text-xs text-indigo-400">
                        <Plus size={11} /> New Workspace
                      </button>
                    ) : (
                      <div className="p-1.5 space-y-1.5">
                        <div className="flex gap-1">
                          <button
                            onClick={() => setNewWsType('personal')}
                            className={`flex-1 text-[10px] py-1 rounded-md border transition-colors
                              ${newWsType === 'personal' ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300' : 'border-slate-600 text-slate-400 hover:border-slate-500'}`}>
                            Personal
                          </button>
                          <button
                            onClick={() => setNewWsType('company')}
                            className={`flex-1 text-[10px] py-1 rounded-md border transition-colors
                              ${newWsType === 'company' ? 'border-blue-500 bg-blue-500/20 text-blue-300' : 'border-slate-600 text-slate-400 hover:border-slate-500'}`}>
                            Company
                          </button>
                        </div>
                        <input
                          autoFocus
                          value={newWsName}
                          onChange={e => setNewWsName(e.target.value)}
                          onKeyDown={async e => {
                            if (e.key === 'Enter' && newWsName.trim() && user) {
                              const organizationId = newWsType === 'company'
                                ? (await createOrganization(newWsName.trim())).id
                                : undefined;
                              await createWorkspace(user.id, newWsName.trim(), newWsType, 'general', organizationId);
                              await refreshWorkspaces();
                              setCreatingWs(false); setNewWsName(''); setWsMenuOpen(false);
                            }
                            if (e.key === 'Escape') { setCreatingWs(false); setNewWsName(''); }
                          }}
                          placeholder="Workspace name…"
                          className="w-full bg-slate-700 border border-slate-600 rounded-md px-2 py-1 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                        />
                        <p className="text-[10px] text-slate-500">Press Enter to create · Esc to cancel</p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <nav className="flex-1 px-3 pt-2 space-y-5 overflow-y-auto">
          {/* Cognitive Core */}
          <div>
            <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Cognitive Core</p>
            {[
              { id: 'dashboard', icon: LayoutDashboard, label: 'Overview' },
              { id: 'schedule', icon: Calendar, label: 'Schedule' },
            ].map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => { onTabChange(id); setIsSidebarOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                  ${activeTab === id ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/30' : 'hover:bg-slate-800/70 text-slate-400 hover:text-slate-200'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          {/* Initiatives */}
          <div>
            <div className="px-3 flex items-center justify-between mb-1.5">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{labels.company}s</p>
              <button onClick={onAddCompany} className="text-slate-500 hover:text-indigo-400 transition-colors p-0.5 rounded" title={`Add ${labels.company}`}>
                <PlusCircle size={14} />
              </button>
            </div>
            {companies.length === 0 && (
              <div className="px-3 py-2 text-xs text-slate-600 italic">No {labels.company.toLowerCase()}s yet.</div>
            )}
            <div className="space-y-0.5">
              {companies.map(company => {
                const isExpanded = expandedCompanies.has(company.id);
                const isActiveCompany = selectedCompanyId === company.id;
                return (
                  <div key={company.id}>
                    {/* Company row */}
                    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer group transition-all
                      ${isActiveCompany && activeTab === 'company' ? 'bg-slate-800 text-white' : 'hover:bg-slate-800/50 text-slate-400 hover:text-slate-200'}`}>
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 bg-${company.color || 'indigo'}-500`} />
                      <span
                        className="flex-1 text-xs font-medium truncate"
                        onClick={() => handleSelectCompany(company.id)}>
                        {company.name}
                      </span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={e => { e.stopPropagation(); onAddProject(company.id); }}
                          className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-indigo-400 transition-all p-0.5">
                          <Plus size={12} />
                        </button>
                        <button
                          onClick={() => toggleCompany(company.id)}
                          className="text-slate-600 hover:text-slate-300 transition-colors p-0.5">
                          <ChevronRight size={13} className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                        </button>
                      </div>
                    </div>
                    {/* Projects */}
                    {isExpanded && (
                      <div className="ml-4 pl-2 border-l border-slate-800 space-y-0.5 mt-0.5 mb-1">
                        {company.projects?.length === 0 && (
                          <p className="text-[11px] text-slate-600 px-2 py-1">No {labels.project.toLowerCase()}s</p>
                        )}
                        {company.projects?.map(project => (
                          <button
                            key={project.id}
                            onClick={() => handleSelectProject(project.id, company.id)}
                            className={`w-full text-left flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all
                              ${selectedProjectId === project.id
                                ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-600/25'
                                : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800/50'}`}>
                            <FolderOpen size={12} className="flex-shrink-0" />
                            <span className="truncate flex-1">{project.name}</span>
                            {selectedProjectId === project.id && <ChevronRight size={11} />}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Second Brain */}
          <div>
            <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Second Brain</p>
            {[
              { id: 'modules', icon: Sparkles, label: 'Modules' },
              { id: 'graph', icon: Network, label: 'Neural Graph' },
              { id: 'ideas', icon: Lightbulb, label: 'Incubator' },
              { id: 'documents', icon: HardDrive, label: 'Vault' },
              ...(workspace?.context === 'company' ? [{ id: 'team', icon: Users, label: 'Team' }] : []),
            ].map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => { onTabChange(id); setIsSidebarOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                  ${activeTab === id ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/30' : 'hover:bg-slate-800/70 text-slate-400 hover:text-slate-200'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3 text-sm text-slate-400 mb-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 overflow-hidden">
              {user?.avatar ? <img src={user.avatar} className="w-full h-full object-cover" alt="avatar" /> : user?.name?.charAt(0)}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-white text-sm font-medium truncate">{user?.name}</p>
              <p className="text-[10px] truncate text-indigo-400">{workspace?.persona?.replace(/_/g, ' ').toUpperCase()}</p>
            </div>
            <button onClick={logout} className="hover:text-red-400 transition-colors p-1 rounded-lg hover:bg-slate-800">
              <LogOut size={15} />
            </button>
          </div>
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-1"><Languages size={12} /> Lang</div>
            <select
              value={language}
              onChange={e => setLanguage(e.target.value as Language)}
              className="bg-slate-800 border border-slate-700 rounded-lg text-slate-300 text-xs py-1 px-2 outline-none cursor-pointer">
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="fr">Français</option>
              <option value="hi">हिंदी</option>
            </select>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* Main content area                                                  */}
      {/* ------------------------------------------------------------------ */}
      <main className="flex-1 overflow-hidden bg-white relative flex flex-col w-full min-w-0">
        {/* Top header */}
        <header className="h-14 border-b border-slate-200 flex items-center px-4 justify-between
          bg-white/80 backdrop-blur-sm flex-shrink-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="text-slate-600 hover:bg-slate-100 p-2 rounded-xl transition-colors flex-shrink-0 md:hidden">
              <Menu size={20} />
            </button>
            <h2 className="text-sm md:text-base font-semibold text-slate-800 flex items-center gap-2 truncate min-w-0">
              <PageTitle />
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {headerActions}
            <div className="hidden sm:flex flex-col items-end">
              <p className="text-xs font-bold text-slate-700 leading-none">{user?.name}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">{workspace?.type?.toUpperCase()}</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 text-xs font-bold flex-shrink-0">
              {user?.name?.charAt(0)}
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 min-h-0 overflow-hidden relative flex flex-col">
          {children}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Mobile bottom navigation                                         */}
        {/* ---------------------------------------------------------------- */}
        <nav className="md:hidden border-t border-slate-200 bg-white flex-shrink-0 safe-area-inset-bottom">
          <div className="flex items-center justify-around px-2 py-2">
            {BOTTOM_NAV.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                onClick={() => onTabChange(id)}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-0 flex-1
                  ${activeTab === id ? 'text-indigo-600' : 'text-slate-400'}`}>
                <Icon size={20} strokeWidth={activeTab === id ? 2.5 : 1.5} />
                <span className="text-[10px] font-medium leading-none">{label}</span>
              </button>
            ))}
            {/* Initiatives shortcut */}
            <button
              onClick={() => setIsSidebarOpen(true)}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-0 flex-1
                ${['company', 'project'].includes(activeTab) ? 'text-indigo-600' : 'text-slate-400'}`}>
              <FolderOpen size={20} strokeWidth={['company', 'project'].includes(activeTab) ? 2.5 : 1.5} />
              <span className="text-[10px] font-medium leading-none">Projects</span>
            </button>
          </div>
        </nav>
      </main>
    </div>
  );
};
