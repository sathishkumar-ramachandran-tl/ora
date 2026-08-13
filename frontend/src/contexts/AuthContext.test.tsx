import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { Workspace } from '../types';
import { getCurrentUser } from '../api/auth';
import { getUserWorkspaces } from '../api/workspace';

vi.mock('../api/auth', () => ({
  getCurrentUser: vi.fn(),
}));

vi.mock('../api/workspace', () => ({
  getUserWorkspaces: vi.fn(),
}));

const personal: Workspace = {
  id: 'personal-1',
  name: 'Personal',
  context: 'personal',
  type: 'study',
  persona: 'general',
  members: [],
  customRoles: [],
};

const company: Workspace = {
  id: 'company-1',
  name: 'Company',
  context: 'company',
  type: 'project',
  persona: 'general',
  members: [],
  customRoles: [],
};

const Probe = () => {
  const { user, workspace, isLoading, bootstrapStatus } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="status">{bootstrapStatus}</span>
      <span data-testid="user">{user?.email || 'none'}</span>
      <span data-testid="workspace">{workspace?.id || 'none'}</span>
    </div>
  );
};

describe('AuthProvider bootstrap', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(getCurrentUser).mockReset();
    vi.mocked(getUserWorkspaces).mockReset();
  });

  it('does not expose an existing user until profile and workspace bootstrap complete', async () => {
    localStorage.setItem('ora_auth_token', 'token');
    localStorage.setItem('ora_user_id', 'u1');
    localStorage.setItem('ora_active_workspace', 'company-1');
    vi.mocked(getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'existing@example.com',
      name: 'Existing',
      is_onboarded: true,
      email_verified: true,
    });
    vi.mocked(getUserWorkspaces).mockResolvedValue([personal, company]);

    render(<AuthProvider><Probe /></AuthProvider>);

    expect(screen.getByTestId('loading')).toHaveTextContent('true');
    expect(screen.getByTestId('user')).toHaveTextContent('none');

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(screen.getByTestId('user')).toHaveTextContent('existing@example.com');
    expect(screen.getByTestId('workspace')).toHaveTextContent('company-1');
  });

  it('falls back to personal workspace when the persisted workspace is invalid', async () => {
    localStorage.setItem('ora_auth_token', 'token');
    localStorage.setItem('ora_user_id', 'u1');
    localStorage.setItem('ora_active_workspace', 'deleted-workspace');
    vi.mocked(getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'existing@example.com',
      name: 'Existing',
      is_onboarded: true,
      email_verified: true,
    });
    vi.mocked(getUserWorkspaces).mockResolvedValue([company, personal]);

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(screen.getByTestId('workspace')).toHaveTextContent('personal-1');
  });
});
