import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Workspace } from '../types';
import { getCurrentUser } from '../api/auth';
import { getUserWorkspaces } from '../api/workspace';

interface AuthContextType {
    user: User | null;
    workspace: Workspace | null;
    workspaces: Workspace[];
    isLoading: boolean;
    bootstrapStatus: 'checking_session' | 'loading_profile' | 'loading_workspaces' | 'ready' | 'signed_out';
    login: (token: string, user: User) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
    setWorkspace: (ws: Workspace) => void;
    switchWorkspace: (workspaceId: string) => void;
    refreshWorkspaces: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ACTIVE_WS_KEY = 'ora_active_workspace';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [workspace, setWorkspaceState] = useState<Workspace | null>(null);
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [bootstrapStatus, setBootstrapStatus] = useState<AuthContextType['bootstrapStatus']>('checking_session');

    const loadWorkspaces = useCallback(async (userId: string): Promise<Workspace[]> => {
        const list = await getUserWorkspaces(userId);
        setWorkspaces(list);
        return list;
    }, []);

    const setWorkspace = useCallback((ws: Workspace) => {
        setWorkspaceState(ws);
        localStorage.setItem(ACTIVE_WS_KEY, ws.id);
    }, []);

    const chooseWorkspace = useCallback((list: Workspace[]) => {
        if (list.length === 0) return null;
        const savedId = localStorage.getItem(ACTIVE_WS_KEY);
        const saved = savedId ? list.find(w => w.id === savedId) : null;
        return saved || list.find(w => w.context === 'personal') || list[0];
    }, []);

    const switchWorkspace = useCallback((workspaceId: string) => {
        const target = workspaces.find(w => w.id === workspaceId);
        if (target) {
            setWorkspace(target);
            window.dispatchEvent(new CustomEvent('ora:workspace-switched', {
                detail: { workspaceId: target.id, context: target.context }
            }));
        }
    }, [workspaces, setWorkspace]);

    const refreshWorkspaces = useCallback(async () => {
        if (!user) return;
        const list = await loadWorkspaces(user.id);
        // Keep current workspace if still valid, else fall back deterministically.
        if (workspace && !list.find(w => w.id === workspace.id)) {
            const fallback = chooseWorkspace(list);
            if (fallback) setWorkspace(fallback);
            else setWorkspaceState(null);
        }
    }, [user, workspace, loadWorkspaces, setWorkspace, chooseWorkspace]);

    useEffect(() => {
        const restoreSession = async () => {
            const token = localStorage.getItem('ora_auth_token');
            const userId = localStorage.getItem('ora_user_id');
            if (!token || !userId) {
                setBootstrapStatus('signed_out');
                setIsLoading(false);
                return;
            }

            try {
                setBootstrapStatus('loading_profile');
                const currentUser = await getCurrentUser();
                setBootstrapStatus('loading_workspaces');
                const list = await loadWorkspaces(currentUser.id);
                const active = chooseWorkspace(list);
                setUser(currentUser);
                setWorkspaceState(active);
                if (active) localStorage.setItem(ACTIVE_WS_KEY, active.id);
                setBootstrapStatus('ready');
            } catch {
                logout();
            } finally {
                setIsLoading(false);
            }
        };
        restoreSession();
    }, []);

    const login = async (token: string, user: User) => {
        setIsLoading(true);
        setBootstrapStatus('loading_profile');
        localStorage.setItem('ora_auth_token', token);
        localStorage.setItem('ora_user_id', user.id);
        try {
            const currentUser = await getCurrentUser();
            setBootstrapStatus('loading_workspaces');
            const list = await loadWorkspaces(currentUser.id);
            const active = chooseWorkspace(list);
            setUser(currentUser);
            setWorkspaceState(active);
            if (active) localStorage.setItem(ACTIVE_WS_KEY, active.id);
            setBootstrapStatus('ready');
        } finally {
            setIsLoading(false);
        }
    };

    const refreshUser = async () => {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
    };

    const logout = () => {
        localStorage.removeItem('ora_auth_token');
        localStorage.removeItem('ora_user_id');
        localStorage.removeItem(ACTIVE_WS_KEY);
        setUser(null);
        setWorkspaceState(null);
        setWorkspaces([]);
        setBootstrapStatus('signed_out');
        setIsLoading(false);
    };

    return (
        <AuthContext.Provider value={{
            user, workspace, workspaces, isLoading, bootstrapStatus,
            login, logout, refreshUser, setWorkspace, switchWorkspace, refreshWorkspaces
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within AuthProvider");
    return context;
};
