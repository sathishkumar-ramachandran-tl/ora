import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PersonalLayout } from './PersonalLayout';
import { Workspace } from '../types';

const switchWorkspace = vi.fn();
const refreshWorkspaces = vi.fn();

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
  name: 'Teams Lab',
  context: 'company',
  type: 'project',
  organizationId: 'org-1',
  persona: 'general',
  members: [],
  customRoles: [],
};

let activeWorkspace = company;

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', name: 'Sathish', email: 's@example.com' },
    workspace: activeWorkspace,
    workspaces: [personal, company],
    logout: vi.fn(),
    switchWorkspace,
    refreshWorkspaces,
  }),
}));

vi.mock('../api/workspace', () => ({
  createWorkspace: vi.fn(),
}));

vi.mock('../api/org', () => ({
  createOrganization: vi.fn(),
}));

const renderLayout = () => render(
  <PersonalLayout
    activeTab="dashboard"
    onTabChange={vi.fn()}
    companies={[]}
    selectedCompanyId={null}
    selectedProjectId={null}
    onSelectCompany={vi.fn()}
    onSelectProject={vi.fn()}
    onAddCompany={vi.fn()}
    onAddProject={vi.fn()}>
    <div>Workspace content</div>
  </PersonalLayout>
);

describe('PersonalLayout workspace shell', () => {
  beforeEach(() => {
    activeWorkspace = company;
    switchWorkspace.mockClear();
  });

  it('keeps the workspace switcher visible in company workspaces and can switch back to personal', () => {
    renderLayout();

    fireEvent.click(screen.getByRole('button', { name: /Teams Lab/i }));
    fireEvent.click(screen.getByRole('button', { name: /Personal/i }));

    expect(switchWorkspace).toHaveBeenCalledWith('personal-1');
  });

  it('uses the same primary navigation for company workspaces', () => {
    renderLayout();

    expect(screen.getAllByRole('button', { name: /^Home$/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /^Work$/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /^Search$/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /^Team$/i })).toBeInTheDocument();
  });
});
