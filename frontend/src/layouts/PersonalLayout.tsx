import React from 'react';
import {
  Network, Calendar, ChevronRight, Plus, PlusCircle,
  HardDrive, Users, LogOut, Languages, Lightbulb, Menu, X,
  Target, Globe, Briefcase, Bot, Home, FolderOpen, Sparkles,
  ChevronDown, Check, Building2, User, Search, Library, Zap, Command
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
  onNewCommand?: (content: string) => void;
}

// Bottom nav items for mobile
const BOTTOM_NAV = [
  { id: 'dashboard', icon: Home, label: 'Home' },
  { id: 'work', icon: Target, label: 'Work' },
  { id: 'search', icon: Search, label: 'Search' },
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
  headerActions,
  onNewCommand
}) => {
  const { user, workspace, workspaces, logout, switchWorkspace, refreshWorkspaces } = useAuth();
  const [language, setLanguage] = React.useState<Language>('en');
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(false);
  const [expandedCompanies, setExpandedCompanies] = React.useState<Set<string>>(new Set());
  const [wsMenuOpen, setWsMenuOpen] = React.useState(false);
  const [creatingWs, setCreatingWs] = React.useState(false);
  const [newWsName, setNewWsName] = React.useState('');
  const [newWsType, setNewWsType] = React.useState<'personal' | 'company'>('personal');
  const [isNewOpen, setIsNewOpen] = React.useState(false);
  const [newIntent, setNewIntent] = React.useState('');

  const currentCompany = selectedCompanyId
    ? companies.find(c => c.id === selectedCompanyId)
    : companies.find(c => (c.projects || []).some(p => p.id === selectedProjectId));
  const currentProject = selectedProjectId
    ? companies.flatMap(c => c.projects || []).find(p => p.id === selectedProjectId)
    : null;

  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        onTabChange('search');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onTabChange]);

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
    if (activeTab === 'dashboard') return <><Home className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Home</span></>;
    if (activeTab === 'work') return <><Target className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Work</span></>;
    if (activeTab === 'search') return <><Search className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Search</span></>;
    if (activeTab === 'documents') return <><Library className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Library</span></>;
    if (activeTab === 'team') return <><Users className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Team</span></>;
    if (activeTab === 'graph') return <><Network className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Explore connections</span></>;
    if (activeTab === 'schedule') return <><Calendar className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Calendar detail</span></>;
    if (activeTab === 'ideas') return <><Lightbulb className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Ideas</span></>;
    if (activeTab === 'modules') return <><Sparkles className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Capabilities</span></>;
    if (activeTab === 'automations') return <><Zap className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">Automations</span></>;
    if (activeTab === 'company' && currentCompany) return <><Globe className="text-ora-accent flex-shrink-0" size={18} /><span className="truncate">{currentCompany.name}</span></>;
    if (activeTab === 'project' && currentProject) return (
      <>
        <Briefcase className="text-ora-accent flex-shrink-0" size={18} />
        <span className="text-ora-tertiary font-normal hidden sm:inline truncate max-w-[80px]">{currentCompany?.name} /</span>
        <span className="truncate">{currentProject.name}</span>
      </>
    );
    return <span className="truncate">Ora</span>;
  };

  const submitIntent = (content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    onNewCommand?.(trimmed);
    setNewIntent('');
    setIsNewOpen(false);
  };

  return (
    <div className="flex h-screen bg-ora-canvas overflow-hidden">
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
        ora-app-sidebar fixed inset-y-0 left-0 z-50 w-72 bg-ora-nav text-white/70
        flex flex-col flex-shrink-0 transition-transform duration-300 ease-in-out shadow-2xl
        md:relative md:w-64 md:translate-x-0
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Brand + Workspace Switcher */}
        <div className="px-3 pt-4 pb-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-ora-accent flex items-center justify-center flex-shrink-0 shadow-sm shadow-ora-accent/25">
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
              className="ora-nav-surface w-full flex items-center gap-2 px-2.5 py-2 rounded-lg bg-ora-nav-surface border border-white/10 hover:border-white/20 transition-colors group">
              <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0
                ${workspace?.context === 'company' ? 'bg-ora-info' : 'bg-ora-accent'}`}>
                {workspace?.context === 'company'
                  ? <Building2 size={11} className="text-white" />
                  : <User size={11} className="text-white" />}
              </div>
              <span className="flex-1 text-left text-xs font-medium text-white truncate">{workspace?.name}</span>
              <ChevronDown size={12} className={`text-white/45 transition-transform flex-shrink-0 ${wsMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {wsMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setWsMenuOpen(false)} />
                <div className="absolute top-full left-0 right-0 mt-1 bg-ora-nav border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
                  <div className="p-1">
                    {workspaces.map(ws => (
                      <button
                        key={ws.id}
                        onClick={() => { switchWorkspace(ws.id); setWsMenuOpen(false); }}
                        className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-white/10 transition-colors text-left">
                        <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0
                          ${ws.context === 'company' ? 'bg-ora-info' : 'bg-ora-accent'}`}>
                          {ws.context === 'company'
                            ? <Building2 size={9} className="text-white" />
                            : <User size={9} className="text-white" />}
                        </div>
                        <span className="flex-1 text-xs text-white/75 truncate">{ws.name}</span>
                        {ws.id === workspace?.id && <Check size={11} className="text-ora-accent flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                    <div className="border-t border-white/10 p-1">
                    {!creatingWs ? (
                      <button
                        onClick={() => setCreatingWs(true)}
                        className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-white/10 transition-colors text-xs text-ora-accent">
                        <Plus size={11} /> New Workspace
                      </button>
                    ) : (
                      <div className="p-1.5 space-y-1.5">
                        <div className="flex gap-1">
                          <button
                            onClick={() => setNewWsType('personal')}
                            className={`flex-1 text-[10px] py-1 rounded-md border transition-colors
                              ${newWsType === 'personal' ? 'border-ora-accent bg-ora-accent/20 text-white' : 'border-white/15 text-ora-nav-muted hover:border-white/25'}`}>
                            Personal
                          </button>
                          <button
                            onClick={() => setNewWsType('company')}
                            className={`flex-1 text-[10px] py-1 rounded-md border transition-colors
                              ${newWsType === 'company' ? 'border-ora-info bg-ora-info/20 text-white' : 'border-white/15 text-ora-nav-muted hover:border-white/25'}`}>
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
                        className="ora-nav-surface w-full bg-ora-nav-surface border border-white/15 rounded-md px-2 py-1 text-xs text-white placeholder:text-ora-nav-muted/60 outline-none focus:border-ora-accent"
                        />
                        <p className="text-[10px] text-ora-nav-muted/60">Press Enter to create · Esc to cancel</p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="px-3 pt-2">
          <button
            onClick={() => setIsNewOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg bg-ora-accent px-3 py-2 text-sm font-semibold text-white shadow-sm shadow-black/20 hover:bg-ora-accent-hover">
            <Plus size={15} /> New
          </button>
        </div>

        <nav className="flex-1 px-3 pt-4 space-y-5 overflow-y-auto">
          {/* Primary */}
          <div>
            <p className="px-3 text-[10px] font-bold text-white/35 uppercase tracking-widest mb-1.5">Primary</p>
            {[
              { id: 'dashboard', icon: Home, label: 'Home' },
              { id: 'work', icon: Target, label: 'Work' },
              { id: 'search', icon: Search, label: 'Search' },
            ].map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => {
                onTabChange(id); setIsSidebarOpen(false);
              }}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                  ${activeTab === id ? 'bg-ora-accent/15 text-white border border-ora-accent/35 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]' : 'hover:bg-white/10 text-ora-nav-muted hover:text-white/85'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          {/* Projects */}
          <div>
            <div className="px-3 flex items-center justify-between mb-1.5">
              <p className="text-[10px] font-bold text-white/35 uppercase tracking-widest">Projects</p>
              <button onClick={onAddCompany} className="text-white/35 hover:text-ora-accent transition-colors p-0.5 rounded" title="Add project group">
                <PlusCircle size={14} />
              </button>
            </div>
            {companies.length === 0 && (
              <div className="px-3 py-2 text-xs text-white/30 italic">No projects yet.</div>
            )}
            <div className="space-y-0.5">
              {companies.map(company => {
                const isExpanded = expandedCompanies.has(company.id);
                const isActiveCompany = selectedCompanyId === company.id;
                return (
                  <div key={company.id}>
                    {/* Company row */}
                    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer group transition-all
                      ${isActiveCompany && activeTab === 'company' ? 'bg-ora-accent/15 text-white shadow-[inset_3px_0_0_rgb(var(--ora-accent))]' : 'hover:bg-white/10 text-ora-nav-muted hover:text-white/85'}`}>
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0 bg-ora-accent"
                        style={company.color ? { backgroundColor: company.color } : undefined}
                      />
                      <span
                        className="flex-1 text-xs font-medium truncate"
                        onClick={() => handleSelectCompany(company.id)}>
                        {company.name}
                      </span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={e => { e.stopPropagation(); onAddProject(company.id); }}
                          className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-ora-accent transition-all p-0.5">
                          <Plus size={12} />
                        </button>
                        <button
                          onClick={() => toggleCompany(company.id)}
                          className="text-white/30 hover:text-white/75 transition-colors p-0.5">
                          <ChevronRight size={13} className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                        </button>
                      </div>
                    </div>
                    {/* Projects */}
                    {isExpanded && (
                      <div className="ml-4 pl-2 border-l border-white/10 space-y-0.5 mt-0.5 mb-1">
                        {company.projects?.length === 0 && (
                          <p className="text-[11px] text-white/30 px-2 py-1">No outcomes</p>
                        )}
                        {company.projects?.map(project => (
                          <button
                            key={project.id}
                            onClick={() => handleSelectProject(project.id, company.id)}
                            className={`w-full text-left flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all
                              ${selectedProjectId === project.id
                                ? 'bg-ora-accent/15 text-white border border-ora-accent/30 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]'
                                : 'text-ora-nav-muted/75 hover:text-white/85 hover:bg-white/10'}`}>
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

          {/* Secondary */}
          <div>
            <p className="px-3 text-[10px] font-bold text-white/35 uppercase tracking-widest mb-1.5">Secondary</p>
            {[
              { id: 'documents', icon: Library, label: 'Library' },
              { id: 'automations', icon: Zap, label: 'Automations' },
              { id: 'modules', icon: Sparkles, label: 'Capabilities' },
              ...(workspace?.context === 'company' ? [{ id: 'team', icon: Users, label: 'Team' }] : []),
            ].map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => { onTabChange(id); setIsSidebarOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                  ${activeTab === id ? 'bg-ora-accent/15 text-white border border-ora-accent/35 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]' : 'hover:bg-white/10 text-ora-nav-muted hover:text-white/85'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          <div>
            <p className="px-3 text-[10px] font-bold text-white/35 uppercase tracking-widest mb-1.5">Advanced</p>
            {[
              { id: 'schedule', icon: Calendar, label: 'Calendar detail' },
              { id: 'graph', icon: Network, label: 'Explore connections' },
              { id: 'ideas', icon: Lightbulb, label: 'Ideas' },
            ].map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => { onTabChange(id); setIsSidebarOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                  ${activeTab === id ? 'bg-ora-accent/15 text-white border border-ora-accent/35 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]' : 'hover:bg-white/10 text-ora-nav-muted hover:text-white/85'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-3 text-sm text-ora-nav-muted mb-3">
            <div className="ora-nav-surface w-9 h-9 rounded-full bg-ora-nav-surface border border-white/10 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 overflow-hidden">
              {user?.avatar ? <img src={user.avatar} className="w-full h-full object-cover" alt="avatar" /> : user?.name?.charAt(0)}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-white text-sm font-medium truncate">{user?.name}</p>
              <p className="text-[10px] truncate text-ora-accent">{workspace?.context === 'company' ? 'TEAM WORKSPACE' : 'PERSONAL WORKSPACE'}</p>
            </div>
            <button onClick={logout} className="hover:text-ora-danger transition-colors p-1 rounded-lg hover:bg-white/10">
              <LogOut size={15} />
            </button>
          </div>
          <div className="flex items-center justify-between text-xs text-ora-nav-muted/70">
            <div className="flex items-center gap-1"><Languages size={12} /> Lang</div>
            <select
              value={language}
              onChange={e => setLanguage(e.target.value as Language)}
              className="ora-nav-surface bg-ora-nav-surface border border-white/10 rounded-lg text-ora-nav-muted text-xs py-1 px-2 outline-none cursor-pointer">
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
      <main className="ora-app-main flex-1 overflow-hidden bg-ora-canvas relative flex flex-col w-full min-w-0">
        {/* Top header */}
        <header className="h-14 border-b border-ora-border flex items-center px-4 justify-between
          bg-ora-canvas/92 backdrop-blur-sm flex-shrink-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="text-ora-secondary hover:bg-ora-subtle p-2 rounded-xl transition-colors flex-shrink-0 md:hidden">
              <Menu size={20} />
            </button>
            <h2 className="text-sm md:text-base font-semibold text-ora-primary flex items-center gap-2 truncate min-w-0">
              <PageTitle />
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {headerActions}
            <div className="hidden sm:flex flex-col items-end">
              <p className="text-xs font-bold text-ora-primary leading-none">{user?.name}</p>
            <p className="text-[10px] text-ora-tertiary mt-0.5">{workspace?.context === 'company' ? 'TEAM' : 'PERSONAL'}</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-ora-accent-soft border border-ora-border flex items-center justify-center text-ora-accent text-xs font-bold flex-shrink-0">
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
        <nav className="md:hidden border-t border-ora-border bg-ora-surface flex-shrink-0 safe-area-inset-bottom">
          <div className="flex items-center justify-around px-2 py-2">
            {BOTTOM_NAV.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                onClick={() => {
                  onTabChange(id);
                }}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-0 flex-1
                  ${activeTab === id ? 'text-ora-accent' : 'text-ora-tertiary'}`}>
                <Icon size={20} strokeWidth={activeTab === id ? 2.5 : 1.5} />
                <span className="text-[10px] font-medium leading-none">{label}</span>
              </button>
            ))}
            <button
              onClick={() => setIsSidebarOpen(true)}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-0 flex-1
                ${['company', 'project'].includes(activeTab) ? 'text-ora-accent' : 'text-ora-tertiary'}`}>
              <FolderOpen size={20} strokeWidth={['company', 'project'].includes(activeTab) ? 2.5 : 1.5} />
              <span className="text-[10px] font-medium leading-none">Projects</span>
            </button>
          </div>
        </nav>
      </main>
      {isNewOpen && (
        <div className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-950/40 px-4 pt-20 backdrop-blur-sm" onClick={() => setIsNewOpen(false)}>
          <div className="w-full max-w-xl rounded-2xl bg-ora-surface p-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2">
              <Command size={18} className="text-ora-accent" />
              <h2 className="text-sm font-semibold text-ora-primary">What do you want to create or accomplish?</h2>
            </div>
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 focus-within:border-indigo-400">
              <input
                autoFocus
                value={newIntent}
                onChange={e => setNewIntent(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') submitIntent(newIntent);
                  if (e.key === 'Escape') setIsNewOpen(false);
                }}
                placeholder="Launch my MVP, plan my week, deliver a client redesign..."
                className="min-w-0 flex-1 border-0 py-2 text-sm outline-none"
              />
              <button
                onClick={() => submitIntent(newIntent)}
                className="rounded-md bg-ora-accent px-3 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover">
                Ask Ora
              </button>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {[
                'Launch a product',
                'Plan my week',
                'Deliver a client project',
                'Build a portfolio',
                'Prepare for an exam',
                'Find a job',
              ].map(prompt => (
                <button
                  key={prompt}
                  onClick={() => submitIntent(prompt)}
                  className="rounded-lg border border-ora-border px-3 py-2 text-left text-sm text-ora-secondary hover:border-ora-accent/30 hover:bg-ora-accent-soft">
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
