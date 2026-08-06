import React, { useState, useEffect } from 'react';
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
import { CompanyLayout } from './layouts/CompanyLayout';

import { Dashboard } from './pages/shared/Dashboard';
import { AgileBoard } from './features/board/AgileBoard';
import { InitiativeBoard } from './features/ideas/InitiativeBoard';
import { KnowledgeGraph } from './features/canvas/KnowledgeGraph';
import { IdeaBoard } from './features/ideas/IdeaBoard';
import { CreateCompanyModal, CreateProjectModal } from './components/shared/CreationModals';
import { FocusTimer } from './features/schedule/FocusTimer';
import { DocumentVault } from './features/documents/DocumentVault';
import { LiveVoiceAssistant } from './features/chat/LiveVoiceAssistant';
import { TeamManagement } from './features/team/TeamManagement';
import { AdminConsole } from './pages/enterprise/AdminConsole';
import { CompanyDashboard } from './pages/enterprise/CompanyDashboard';
import { CompanyProjects } from './pages/enterprise/CompanyProjects';
import { ScheduleView } from './features/schedule/ScheduleView';
import { ChatInterface } from './features/chat/ChatInterface';
import { ModuleMarketplace } from './features/modules/ModuleMarketplace';

import { generateWeeklyScheduleAdvice } from './services/geminiService';
import { fetchFullState } from './api/workspace';
import { createCompany, createProject } from './api/projects';
import { addTasks } from './api/tasks';
import { trackEvent } from './services/analytics';
import { getMyOrganizations, Organization } from './api/org';

const AppRoutes: React.FC = () => {
    const { user, workspace, isLoading } = useAuth();

    // UI State
    const [activeTab, setActiveTab] = useState('dashboard');
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
    const [companies, setCompanies] = useState<Company[]>([]);
    const [organization, setOrganization] = useState<Organization | null>(null);
    const [focusedTask, setFocusedTask] = useState<Task | null>(null);
    const [isVoiceActive, setIsVoiceActive] = useState(false);

    // Modals
    const [isCompanyModalOpen, setCompanyModalOpen] = useState(false);
    const [projectModalTarget, setProjectModalTarget] = useState<string | null>(null);

    // Schedule
    const [scheduleAdvice, setScheduleAdvice] = useState<string>('');

    // Data Loading
    useEffect(() => {
        if (workspace) loadData(workspace.id);
    }, [workspace]);

    useEffect(() => {
        if (workspace?.context === 'company' && workspace.organizationId) {
            getMyOrganizations()
                .then(orgs => setOrganization(orgs.find(o => o.id === workspace.organizationId) || null))
                .catch(() => setOrganization(null));
        } else {
            setOrganization(null);
        }
    }, [workspace?.organizationId]);

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

    const handleOptimizeSchedule = async () => {
        trackEvent('AI_AGENT_START', { agent: 'Scheduler' });
        setScheduleAdvice('Ora is analyzing your velocity and constraints…');
        const advice = await generateWeeklyScheduleAdvice(companies, workspace?.persona);
        setScheduleAdvice(advice);
        trackEvent('AI_AGENT_COMPLETE', { agent: 'Scheduler' });
    };

    // Derived
    const currentProject = selectedProjectId
        ? companies.flatMap(c => c.projects || []).find(p => p.id === selectedProjectId)
        : null;
    const currentCompany = selectedCompanyId
        ? companies.find(c => c.id === selectedCompanyId)
        : (currentProject ? companies.find(c => (c.projects || []).some(p => p.id === currentProject.id)) : null);

    // Loading / Auth gates
    if (isLoading) {
        return (
            <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">
                <Loader2 className="w-8 h-8 text-indigo-500 animate-spin mr-3" />
                <span className="text-lg">Loading Cortex…</span>
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
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 text-white rounded-full shadow-lg
              hover:bg-slate-800 transition-all font-medium text-xs border border-slate-700 whitespace-nowrap">
            <Mic size={14} />
            <span className="hidden sm:inline">Voice</span>
        </button>
    );

    const MainContent = () => (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative">
            {/* Graph tab: full-bleed, no scroll, no padding wrapper */}
            {activeTab === 'graph' ? (
                <div className="flex-1 min-h-0 p-4 md:p-6 flex flex-col">
                    <KnowledgeGraph companies={companies} onNavigate={(type, id) => {
                        if (type === 'project') { setSelectedProjectId(id); setActiveTab('project'); }
                        else { setSelectedCompanyId(id); setActiveTab('company'); }
                    }} />
                </div>
            ) : (
                <div className="flex-1 overflow-auto p-4 md:p-6">
                    {activeTab === 'dashboard' && (
                        <Dashboard companies={companies} onStartFocus={setFocusedTask} />
                    )}
                    {activeTab === 'documents' && (
                        <DocumentVault workspaceId={workspace.id} />
                    )}
                    {activeTab === 'team' && (
                        <TeamManagement
                            workspaceId={workspace.id}
                            customRoles={workspace.customRoles || []}
                            companies={companies}
                        />
                    )}
                    {activeTab === 'ideas' && (
                        <IdeaBoard workspaceId={workspace.id} onCreateCompany={handleCreateCompany} />
                    )}
                    {activeTab === 'modules' && (
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
                    )}
                    {activeTab === 'company' && currentCompany && (
                        <InitiativeBoard
                            company={currentCompany}
                            onNavigateProject={pid => { setSelectedProjectId(pid); setActiveTab('project'); setSelectedCompanyId(null); }}
                            onUpdateCompany={handleUpdateCompany}
                            onCreateProject={handleCreateProject}
                        />
                    )}
                    {activeTab === 'project' && currentProject && currentCompany && (
                        <AgileBoard
                            project={currentProject}
                            companyMission={currentCompany.mission}
                            onUpdateProject={handleUpdateProject}
                            onStartFocus={setFocusedTask}
                            onRequestRefresh={() => loadData(workspace.id)}
                        />
                    )}
                    {activeTab === 'schedule' && (
                        <ScheduleView companies={companies} onStartFocus={setFocusedTask} />
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

    // Route by workspace context
    if (workspace.context === 'company') {
        if (!organization) {
            return (
                <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">
                    <Loader2 className="w-8 h-8 text-indigo-500 animate-spin mr-3" />
                    <span className="text-lg">Loading organization…</span>
                </div>
            );
        }
        const userInitials = (user.name || user.email || 'A')[0].toUpperCase();

        const CompanyContent = () => {
            if (activeTab === 'overview') {
                return (
                    <CompanyDashboard
                        workspaceId={workspace.id}
                        companies={companies}
                        onNavigateProjects={() => setActiveTab('projects')}
                        onNavigateTeam={() => setActiveTab('team')}
                        onCreateProject={() => {
                            const firstCompany = companies[0];
                            if (firstCompany) setProjectModalTarget(firstCompany.id);
                        }}
                    />
                );
            }
            if (activeTab === 'projects') {
                return (
                    <CompanyProjects
                        companies={companies}
                        onNavigateProject={(pid, cid) => {
                            setSelectedProjectId(pid);
                            setSelectedCompanyId(cid);
                            setActiveTab('project');
                        }}
                        onCreateProject={cid => setProjectModalTarget(cid)}
                    />
                );
            }
            if (activeTab === 'team') {
                return (
                    <div className="flex-1 overflow-auto p-5">
                        <TeamManagement
                            workspaceId={workspace.id}
                            customRoles={workspace.customRoles || []}
                            companies={companies}
                        />
                    </div>
                );
            }
            if (activeTab === 'admin') {
                return <AdminConsole organizationId={organization.id} />;
            }
            // project drill-in reuses MainContent
            return (
                <div className="flex-1 overflow-auto p-4 md:p-6">
                    {activeTab === 'project' && currentProject && currentCompany && (
                        <AgileBoard
                            project={currentProject}
                            companyMission={currentCompany.mission}
                            onUpdateProject={handleUpdateProject}
                            onStartFocus={setFocusedTask}
                            onRequestRefresh={() => loadData(workspace.id)}
                        />
                    )}
                </div>
            );
        };

        return (
            <>
                <CompanyLayout
                    organization={organization}
                    activeTab={activeTab}
                    onTabChange={t => setActiveTab(t)}
                    headerActions={voiceButton}
                    userInitials={userInitials}>
                    <CompanyContent />
                    <FocusTimer activeTask={focusedTask} onClearTask={() => setFocusedTask(null)} />
                    <LiveVoiceAssistant isOpen={isVoiceActive} onClose={() => setIsVoiceActive(false)} persona={workspace.persona} />
                    {projectModalTarget && (
                        <CreateProjectModal
                            isOpen={!!projectModalTarget}
                            companyId={projectModalTarget}
                            onClose={() => setProjectModalTarget(null)}
                            onSubmit={handleCreateProject}
                        />
                    )}
                </CompanyLayout>
                {/* Agentic Chat — available in all contexts */}
                <ChatInterface workspaceId={workspace.id} />
            </>
        );
    }

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
                onAddProject={cid => setProjectModalTarget(cid)}>
                <MainContent />
            </PersonalLayout>
            {/* Agentic Chat — floating widget, always accessible */}
            <ChatInterface workspaceId={workspace.id} />
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
