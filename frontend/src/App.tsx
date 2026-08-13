import React, { Suspense, lazy, useState, useEffect } from 'react';
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { Loader2, Mic } from 'lucide-react';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Company, Project, Task } from './types';
import { LoginScreen } from './pages/auth/LoginScreen';
import { Onboarding } from './pages/auth/Onboarding';
import { VerifyEmailScreen } from './pages/auth/VerifyEmailScreen';
import { OAuthCallback } from './pages/auth/OAuthCallback';
import { ResetPassword } from './pages/auth/ResetPassword';
import { PersonalLayout } from './layouts/PersonalLayout';

import { CommandCenterHome } from './pages/shared/CommandCenterHome';
import { ProjectWorkspace } from './pages/shared/ProjectWorkspace';
import { UniversalSearch } from './pages/shared/UniversalSearch';
import { UniversalWork } from './pages/shared/UniversalWork';
import { CreateCompanyModal, CreateProjectModal } from './components/shared/CreationModals';
import { FocusTimer } from './features/schedule/FocusTimer';
import { LiveVoiceAssistant } from './features/chat/LiveVoiceAssistant';
import { ChatInterface } from './features/chat/ChatInterface';

import { fetchFullState } from './api/workspace';
import { createCompany, createProject } from './api/projects';
import { trackEvent } from './services/analytics';

const InitiativeBoard = lazy(() => import('./features/ideas/InitiativeBoard').then(m => ({ default: m.InitiativeBoard })));
const KnowledgeGraph = lazy(() => import('./features/canvas/KnowledgeGraph').then(m => ({ default: m.KnowledgeGraph })));
const IdeaBoard = lazy(() => import('./features/ideas/IdeaBoard').then(m => ({ default: m.IdeaBoard })));
const DocumentVault = lazy(() => import('./features/documents/DocumentVault').then(m => ({ default: m.DocumentVault })));
const TeamManagement = lazy(() => import('./features/team/TeamManagement').then(m => ({ default: m.TeamManagement })));
const ScheduleView = lazy(() => import('./features/schedule/ScheduleView').then(m => ({ default: m.ScheduleView })));
const ModuleMarketplace = lazy(() => import('./features/modules/ModuleMarketplace').then(m => ({ default: m.ModuleMarketplace })));

const SurfaceLoader = () => (
    <div className="flex min-h-[40vh] items-center justify-center text-ora-secondary">
        <Loader2 className="mr-2 animate-spin" size={18} /> Loading surface…
    </div>
);

const AppRoutes: React.FC = () => {
    const { user, workspace, isLoading } = useAuth();

    // UI State
    const [activeTab, setActiveTab] = useState('dashboard');
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
    const [companies, setCompanies] = useState<Company[]>([]);
    const [focusedTask, setFocusedTask] = useState<Task | null>(null);
    const [isVoiceActive, setIsVoiceActive] = useState(false);

    // Modals
    const [isCompanyModalOpen, setCompanyModalOpen] = useState(false);
    const [projectModalTarget, setProjectModalTarget] = useState<string | null>(null);

    // Data Loading
    useEffect(() => {
        if (workspace) loadData(workspace.id);
    }, [workspace]);

    useEffect(() => {
        setSelectedProjectId(null);
        setSelectedCompanyId(null);
        setFocusedTask(null);
        setActiveTab('dashboard');
        setCompanies([]);
    }, [workspace?.id]);

    const loadData = async (workspaceId: string) => {
        try {
            const data = await fetchFullState(workspaceId);
            setCompanies(data);
        } catch (e) {
            console.error('Failed to load data', e);
        }
    };

    // Actions
    const handleCreateCompany = async (newCompany: Company) => {
        if (!workspace) return;
        await createCompany({ ...newCompany, workspaceId: workspace.id });
        trackEvent('PROJECT_CREATED', { type: 'company', name: newCompany.name });
        await loadData(workspace.id);
    };

    const handleCreateProject = async (newProject: Project, companyId: string) => {
        if (!workspace) return;
        await createProject({ ...newProject, workspaceId: workspace.id }, companyId);
        trackEvent('PROJECT_CREATED', { type: newProject.type, name: newProject.name });
        await loadData(workspace.id);
    };

    const handleUpdateCompany = (updatedCompany: Company) => {
        setCompanies(prev => prev.map(c => c.id === updatedCompany.id ? updatedCompany : c));
    };

    const handleUpdateProject = (updatedProject: Project) => {
        setCompanies(prev => prev.map(c => ({
            ...c,
            projects: (c.projects || []).map(p => p.id === updatedProject.id ? updatedProject : p)
        })));
    };

    // Derived
    const currentProject = selectedProjectId
        ? companies.flatMap(c => c.projects || []).find(p => p.id === selectedProjectId)
        : null;
    const currentCompany = selectedCompanyId
        ? companies.find(c => c.id === selectedCompanyId)
        : (currentProject ? companies.find(c => (c.projects || []).some(p => p.id === currentProject.id)) : null);
    const chatScope = focusedTask
        ? { level: 'task' as const, taskId: focusedTask.id, projectId: focusedTask.projectId || currentProject?.id || null, label: focusedTask.title }
        : currentProject
            ? { level: 'project' as const, projectId: currentProject.id, label: currentProject.name }
            : { level: 'workspace' as const, label: workspace?.name };

    // Loading / Auth gates
    if (isLoading) {
        return (
            <div className="min-h-screen bg-ora-canvas flex items-center justify-center text-ora-primary">
                <div className="flex items-center gap-3 rounded-2xl border border-ora-border bg-ora-surface px-5 py-4 shadow-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-ora-accent" />
                    <div>
                        <p className="text-sm font-semibold">Opening Ora</p>
                        <p className="text-xs text-ora-secondary">Restoring your workspace safely…</p>
                    </div>
                </div>
            </div>
        );
    }
    if (!user) return <LoginScreen />;
    if (!user.email_verified) return <VerifyEmailScreen />;
    if (!user.is_onboarded || !workspace) return <Onboarding />;

    // Voice button (shared between layouts)
    const voiceButton = (
        <button
            onClick={() => setIsVoiceActive(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-ora-nav text-white rounded-full shadow-lg
              hover:bg-ora-accent transition-all font-medium text-xs border border-white/10 whitespace-nowrap">
            <Mic size={14} />
            <span className="hidden sm:inline">Voice</span>
        </button>
    );

    const MainContent = () => (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative">
            {/* Graph tab: full-bleed, no scroll, no padding wrapper */}
            {activeTab === 'graph' ? (
                <div className="flex-1 min-h-0 p-4 md:p-6 flex flex-col">
                    <Suspense fallback={<SurfaceLoader />}>
                        <KnowledgeGraph companies={companies} onNavigate={(type, id) => {
                            if (type === 'project') { setSelectedProjectId(id); setActiveTab('project'); }
                            else { setSelectedCompanyId(id); setActiveTab('company'); }
                        }} />
                    </Suspense>
                </div>
            ) : (
                <div className="flex-1 overflow-auto p-4 md:p-6">
                    {activeTab === 'dashboard' && (
                        <CommandCenterHome
                            workspaceId={workspace.id}
                            onStartFocus={setFocusedTask}
                            onOpenProject={(projectId) => {
                                const company = companies.find(c => (c.projects || []).some(p => p.id === projectId));
                                if (company) {
                                    setSelectedCompanyId(company.id);
                                    setSelectedProjectId(projectId);
                                    setActiveTab('project');
                                }
                            }}
                        />
                    )}
                    {activeTab === 'work' && (
                        <UniversalWork
                            companies={companies}
                            onStartFocus={setFocusedTask}
                            onOpenProject={(projectId) => {
                                const company = companies.find(c => (c.projects || []).some(p => p.id === projectId));
                                if (company) {
                                    setSelectedCompanyId(company.id);
                                    setSelectedProjectId(projectId);
                                    setActiveTab('project');
                                }
                            }}
                            onOpenSchedule={() => setActiveTab('schedule')}
                        />
                    )}
                    {activeTab === 'search' && (
                        <UniversalSearch
                            workspaceId={workspace.id}
                            companies={companies}
                            onOpenProject={(projectId) => {
                                const company = companies.find(c => (c.projects || []).some(p => p.id === projectId));
                                if (company) {
                                    setSelectedCompanyId(company.id);
                                    setSelectedProjectId(projectId);
                                    setActiveTab('project');
                                }
                            }}
                            onAskOra={(content) => {
                                trackEvent('ORA_COMMAND_SENT', { source: 'search' });
                                window.dispatchEvent(new CustomEvent('ora:command', { detail: { content } }));
                            }}
                        />
                    )}
                    {activeTab === 'documents' && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <DocumentVault workspaceId={workspace.id} />
                        </Suspense>
                    )}
                    {activeTab === 'automations' && (
                        <div className="mx-auto max-w-4xl space-y-4">
                            <p className="text-sm font-medium text-ora-accent">Automations</p>
                            <h1 className="text-3xl font-semibold tracking-tight text-ora-primary">Recurring checks and reminders will live here.</h1>
                            <p className="max-w-2xl text-sm leading-6 text-ora-secondary">
                                Ora can already react through Today, schedule proposals, and plan health. This surface is reserved for explicit recurring reviews and conditional monitors.
                            </p>
                        </div>
                    )}
                    {activeTab === 'team' && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <TeamManagement
                                workspaceId={workspace.id}
                                customRoles={workspace.customRoles || []}
                                companies={companies}
                            />
                        </Suspense>
                    )}
                    {activeTab === 'ideas' && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <IdeaBoard workspaceId={workspace.id} onCreateCompany={handleCreateCompany} />
                        </Suspense>
                    )}
                    {activeTab === 'modules' && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <ModuleMarketplace
                                workspaceId={workspace.id}
                                companies={companies}
                                onCreateCompany={handleCreateCompany}
                                onModuleInstalled={async (projectId) => {
                                    await loadData(workspace.id);
                                    setSelectedProjectId(projectId);
                                    setActiveTab('project');
                                }}
                            />
                        </Suspense>
                    )}
                    {activeTab === 'company' && currentCompany && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <InitiativeBoard
                                company={currentCompany}
                                onNavigateProject={pid => { setSelectedProjectId(pid); setActiveTab('project'); setSelectedCompanyId(null); }}
                                onUpdateCompany={handleUpdateCompany}
                                onCreateProject={handleCreateProject}
                            />
                        </Suspense>
                    )}
                    {activeTab === 'project' && currentProject && currentCompany && (
                        <ProjectWorkspace
                            project={currentProject}
                            company={currentCompany}
                            onUpdateProject={handleUpdateProject}
                            onStartFocus={setFocusedTask}
                            onRequestRefresh={() => loadData(workspace.id)}
                        />
                    )}
                    {activeTab === 'schedule' && (
                        <Suspense fallback={<SurfaceLoader />}>
                            <ScheduleView companies={companies} onStartFocus={setFocusedTask} />
                        </Suspense>
                    )}
                </div>
            )}

            {/* Overlays */}
            <FocusTimer activeTask={focusedTask} onClearTask={() => setFocusedTask(null)} />
            <LiveVoiceAssistant isOpen={isVoiceActive} onClose={() => setIsVoiceActive(false)} persona={workspace.persona} />
            <CreateCompanyModal isOpen={isCompanyModalOpen} onClose={() => setCompanyModalOpen(false)} onSubmit={handleCreateCompany} />
            {projectModalTarget && (
                <CreateProjectModal
                    isOpen={!!projectModalTarget}
                    companyId={projectModalTarget}
                    onClose={() => setProjectModalTarget(null)}
                    onSubmit={handleCreateProject}
                />
            )}
        </div>
    );

    return (
        <>
            <PersonalLayout
                activeTab={activeTab}
                onTabChange={setActiveTab}
                headerActions={voiceButton}
                companies={companies}
                selectedCompanyId={selectedCompanyId}
                selectedProjectId={selectedProjectId}
                onSelectCompany={id => { setSelectedCompanyId(id); setActiveTab('company'); setSelectedProjectId(null); }}
                onSelectProject={(pid, cid) => { setSelectedProjectId(pid); setSelectedCompanyId(cid); setActiveTab('project'); }}
                onAddCompany={() => setCompanyModalOpen(true)}
                onAddProject={cid => setProjectModalTarget(cid)}
                onNewCommand={(content) => {
                    trackEvent('ORA_COMMAND_SENT', { source: 'new_button' });
                    window.dispatchEvent(new CustomEvent('ora:command', { detail: { content } }));
                }}>
                <MainContent />
            </PersonalLayout>
            {/* Agentic Chat — floating widget, always accessible */}
            <ChatInterface workspaceId={workspace.id} scope={chatScope} />
        </>
    );
};

const App: React.FC = () => (
    <BrowserRouter>
        <AuthProvider>
            <Routes>
                {/* Public callback routes — handle their own redirect logic regardless of auth state */}
                <Route path="/oauth/callback" element={<OAuthCallback />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                {/* Everything else is the tab-state-driven app, gated by auth internally */}
                <Route path="*" element={<AppRoutes />} />
            </Routes>
        </AuthProvider>
    </BrowserRouter>
);

export default App;
