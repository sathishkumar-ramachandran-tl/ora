import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UniversalSearch } from './UniversalSearch';

vi.mock('../../api/workspace', async () => {
  const actual = await vi.importActual<typeof import('../../api/workspace')>('../../api/workspace');
  return {
    ...actual,
    searchWorkspace: vi.fn(async () => []),
  };
});

vi.mock('../../services/analytics', () => ({
  trackEvent: vi.fn(),
}));

const companies = [{
  id: 'c1',
  name: 'Acme',
  projects: [{
    id: 'p1',
    name: 'Acme MVP',
    tasks: [{ id: 't1', title: 'Friday exam', dueDate: '2026-08-14T10:00:00.000Z' }],
  }],
}];

describe('UniversalSearch', () => {
  it('shows structured project and deadline hints without vector search', async () => {
    render(<UniversalSearch workspaceId="w1" companies={companies} onOpenProject={vi.fn()} onAskOra={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText('Search projects, work, plans, deadlines, evidence...'), { target: { value: 'Acme' } });

    await waitFor(() => expect(screen.getByText('Acme MVP')).toBeInTheDocument());
    expect(screen.getByText('project · Acme')).toBeInTheDocument();
  });

  it('delegates non-project results to Ora when opened', async () => {
    const onAskOra = vi.fn();
    render(<UniversalSearch workspaceId="w1" companies={companies} onOpenProject={vi.fn()} onAskOra={onAskOra} />);

    fireEvent.change(screen.getByPlaceholderText('Search projects, work, plans, deadlines, evidence...'), { target: { value: 'Friday' } });

    await waitFor(() => expect(screen.getByText('Friday exam')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Friday exam'));
    expect(onAskOra).toHaveBeenCalledWith('Open or explain Friday exam');
  });
});
