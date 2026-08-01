import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Workspace } from '../types';
import { authApi, workspaceApi } from '../api/auth';

interface AuthContextType {
    user: User | null;
    workspace: Workspace | null;
    workspaces: Workspace[];
    isLoading: boolean;
    login: (token: string, user: User) => Promise<void>;
    logout: () => void;
    setWorkspace: (ws: Workspace) => void;
    switchWorkspace: (workspaceId: string) => void;
    refreshWorkspaces: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ACTIVE_WS_KEY = 'sindhai_active_workspace';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [workspace, setWorkspaceState] = useState<Workspace | null>(null);
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const loadWorkspaces = useCallback(async (userId: string): Promise<Workspace[]> => {
        const list = await workspaceApi.getUserWorkspaces(userId);
        setWorkspaces(list);
        return list;
    }, []);

    const setWorkspace = useCallback((ws: Workspace) => {
        setWorkspaceState(ws);
        localStorage.setItem(ACTIVE_WS_KEY, ws.id);
    }, []);

    const switchWorkspace = useCallback((workspaceId: string) => {
        const target = workspaces.find(w => w.id === workspaceId);
        if (target) {
            setWorkspace(target);
            // Full reload so all data re-fetches with new workspace context
            window.location.reload();
        }
    }, [workspaces, setWorkspace]);

    const refreshWorkspaces = useCallback(async () => {
        if (!user) return;
        const list = await loadWorkspaces(user.id);
        // Keep current workspace if still valid, else switch to first
        if (workspace && !list.find(w => w.id === workspace.id)) {
            if (list.length > 0) setWorkspace(list[0]);
        }
    }, [user, workspace, loadWorkspaces, setWorkspace]);

    useEffect(() => {
        const restoreSession = async () => {
            const token = localStorage.getItem('sindhai_auth_token');
            const userId = localStorage.getItem('sindhai_user_id');
            if (!token || !userId) { setIsLoading(false); return; }

            try {
                const currentUser = await authApi.getCurrentUser();
                setUser(currentUser);

                const list = await loadWorkspaces(currentUser.id);
                if (list.length > 0) {
                    const savedId = localStorage.getItem(ACTIVE_WS_KEY);
                    const active = (savedId && list.find(w => w.id === savedId)) || list[0];
                    setWorkspaceState(active);
                }
            } catch {
                logout();
            } finally {
                setIsLoading(false);
            }
        };
        restoreSession();
    }, []);

    const login = async (token: string, user: User) => {
        localStorage.setItem('sindhai_auth_token', token);
        localStorage.setItem('sindhai_user_id', user.id);
        setUser(user);
        const list = await loadWorkspaces(user.id);
        if (list.length > 0) {
            const savedId = localStorage.getItem(ACTIVE_WS_KEY);
            const active = (savedId && list.find(w => w.id === savedId)) || list[0];
            setWorkspaceState(active);
        }
    };

    const logout = () => {
        localStorage.removeItem('sindhai_auth_token');
        localStorage.removeItem('sindhai_user_id');
        localStorage.removeItem(ACTIVE_WS_KEY);
        setUser(null);
        setWorkspaceState(null);
        setWorkspaces([]);
    };

    return (
        <AuthContext.Provider value={{
            user, workspace, workspaces, isLoading,
            login, logout, setWorkspace, switchWorkspace, refreshWorkspaces
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
