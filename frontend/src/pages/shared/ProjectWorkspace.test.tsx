import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ProjectWorkspace } from './ProjectWorkspace';
import { Company, Project } from '../../types';

vi.mock('../../features/board/AgileBoard', () => ({
  AgileBoard: () => <div>Legacy board surface</div>,
}));

const company: Company = {
  id: 'c1',
  workspaceId: 'w1',
  name: 'Acme',
  mission: 'Launch a product',
  color: 'indigo',
  projects: [],
};

const baseProject: Project = {
  id: 'p1',
  workspaceId: 'w1',
  companyId: 'c1',
  name: 'Computer Networks',
  type: 'learning',
  mission: 'Reach advanced networking proficiency.',
  progress: 0,
  tasks: [
    { id: 't1', workspaceId: 'w1', projectId: 'p1', title: 'CIDR Review', status: 'review', priority: 'high', estimatedHours: 0.5 },
    { id: 't2', workspaceId: 'w1', projectId: 'p1', title: 'BGP Lab', status: 'todo', priority: 'high', estimatedHours: 1.5 },
  ],
};

describe('ProjectWorkspace', () => {
  it('uses contextual learning language only inside a learning project', () => {
    render(<ProjectWorkspace project={baseProject} company={company} onUpdateProject={vi.fn()} onStartFocus={vi.fn()} onRequestRefresh={vi.fn()} />);

    expect(screen.getByText('Acme · Learning')).toBeInTheDocument();
    expect(screen.getByText('Current topic')).toBeInTheDocument();
    expect(screen.getByText('Needs review')).toBeInTheDocument();
  });

  it('shows universal Context modules and keeps the board demoted', () => {
    render(<ProjectWorkspace project={baseProject} company={company} onUpdateProject={vi.fn()} onStartFocus={vi.fn()} onRequestRefresh={vi.fn()} />);

    fireEvent.click(screen.getByText('Context'));
    expect(screen.getByText('Concepts')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
    expect(screen.queryByText('Legacy board surface')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Work'));
    fireEvent.click(screen.getByText('Advanced: view as board'));
    expect(screen.getByText('Legacy board surface')).toBeInTheDocument();
  });

  it('uses product mode language for startup/product projects without changing routes', () => {
    const productProject: Project = {
      ...baseProject,
      name: 'AI Expense MVP',
      type: 'build',
      mission: 'Launch MVP in six weeks and validate pricing.',
    };
    render(<ProjectWorkspace project={productProject} company={company} onUpdateProject={vi.fn()} onStartFocus={vi.fn()} onRequestRefresh={vi.fn()} />);

    expect(screen.getByText('Acme · Product / startup')).toBeInTheDocument();
    expect(screen.getByText('Current bet')).toBeInTheDocument();
    expect(screen.getByText('Risk')).toBeInTheDocument();
  });

  it('keeps secondary metadata inside the project info drawer', () => {
    render(<ProjectWorkspace project={baseProject} company={company} onUpdateProject={vi.fn()} onStartFocus={vi.fn()} onRequestRefresh={vi.fn()} />);

    expect(screen.queryByText('Project info')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Project info'));
    expect(screen.getByText('Project info')).toBeInTheDocument();
    expect(screen.getByText('Secondary controls')).toBeInTheDocument();
  });
});
