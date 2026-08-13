import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { UniversalWork } from './UniversalWork';
import { Company } from '../../types';

const companies: Company[] = [{
  id: 'c1',
  workspaceId: 'w1',
  name: 'Acme',
  mission: 'Launch MVP',
  color: 'indigo',
  projects: [{
    id: 'p1',
    workspaceId: 'w1',
    companyId: 'c1',
    name: 'AI Expense MVP',
    type: 'build',
    progress: 0,
    tasks: [
      { id: 't1', workspaceId: 'w1', projectId: 'p1', title: 'Validate onboarding problem', status: 'in-progress', priority: 'critical', estimatedHours: 0.75 },
      { id: 't2', workspaceId: 'w1', projectId: 'p1', title: 'Prepare pricing test', status: 'todo', priority: 'high', estimatedHours: 1 },
      { id: 't3', workspaceId: 'w1', projectId: 'p1', title: 'Client feedback review', status: 'review', priority: 'medium', estimatedHours: 0.5 },
    ],
  }],
}];

describe('UniversalWork', () => {
  it('renders actionable work as Now, Next, and Waiting rather than a board', () => {
    render(<UniversalWork companies={companies} onStartFocus={vi.fn()} onOpenProject={vi.fn()} />);

    expect(screen.getByText('Now')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('Validate onboarding problem')).toBeInTheDocument();
    expect(screen.getByText('Prepare pricing test')).toBeInTheDocument();
    expect(screen.getByText('Client feedback review')).toBeInTheDocument();
    expect(screen.queryByText('Todo')).not.toBeInTheDocument();
    expect(screen.queryByText('Done')).not.toBeInTheDocument();
  });

  it('starts focus from a primary work item', () => {
    const onStartFocus = vi.fn();
    render(<UniversalWork companies={companies} onStartFocus={onStartFocus} onOpenProject={vi.fn()} />);

    fireEvent.click(screen.getAllByTitle('Continue')[0]);
    expect(onStartFocus).toHaveBeenCalledWith(expect.objectContaining({ id: 't1' }));
  });
});
