import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ScheduleView } from './ScheduleView';
import { CalendarEvent, Company } from '../../types';

const weekStart = new Date();
weekStart.setHours(0, 0, 0, 0);
weekStart.setDate(weekStart.getDate() - weekStart.getDay());

const isoAt = (dayOffset: number, hour: number, minute = 0) => {
  const d = new Date(weekStart);
  d.setDate(d.getDate() + dayOffset);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
};

const events: CalendarEvent[] = [
  {
    id: 'fixed-1',
    workspaceId: 'w1',
    title: 'Team sync',
    start: isoAt(1, 10),
    end: isoAt(1, 11),
    type: 'meeting',
    scope: 'workspace',
    color: 'neutral',
    locked: true,
  },
  {
    id: 'work-1',
    workspaceId: 'w1',
    title: 'Build checkout integration',
    start: isoAt(1, 13),
    end: isoAt(1, 14),
    type: 'task_block',
    scope: 'personal',
    color: 'accent',
    taskId: 'task-1',
    isFlexible: true,
    sessionStatus: 'SCHEDULED',
  },
  {
    id: 'missed-1',
    workspaceId: 'w1',
    title: 'CIDR Review',
    start: isoAt(2, 9),
    end: isoAt(2, 9, 30),
    type: 'task_block',
    scope: 'personal',
    color: 'accent',
    taskId: 'task-2',
    isFlexible: true,
    sessionStatus: 'MISSED',
  },
  {
    id: 'done-1',
    workspaceId: 'w1',
    title: 'Customer interview analysis',
    start: isoAt(3, 15),
    end: isoAt(3, 16),
    type: 'task_block',
    scope: 'personal',
    color: 'accent',
    taskId: 'task-3',
    isFlexible: true,
    sessionStatus: 'COMPLETED',
  },
  {
    id: 'deadline-1',
    workspaceId: 'w1',
    title: 'MVP launch',
    start: isoAt(5, 17),
    end: isoAt(5, 17, 15),
    type: 'reminder',
    scope: 'workspace',
    color: 'amber',
  },
];

vi.mock('../../api/calendar', () => ({
  getEvents: vi.fn(async () => events),
  createEvent: vi.fn(async (_workspaceId, event) => ({ id: 'new-event', ...event })),
  deleteEvent: vi.fn(async () => undefined),
  autoScheduleTasks: vi.fn(async () => ({ scheduledCount: 1, unscheduledCount: 0, scheduled: [], unscheduled: [] })),
}));

const companies: Company[] = [{
  id: 'c1',
  workspaceId: 'w1',
  name: 'Acme',
  mission: 'Launch MVP',
  color: 'blue',
  projects: [{
    id: 'p1',
    workspaceId: 'w1',
    companyId: 'c1',
    name: 'Acme MVP',
    type: 'build',
    progress: 0,
    tasks: [
      { id: 'task-1', workspaceId: 'w1', projectId: 'p1', title: 'Build checkout integration', status: 'todo', priority: 'high', estimatedHours: 1 },
      { id: 'task-2', workspaceId: 'w1', projectId: 'p1', title: 'CIDR Review', status: 'todo', priority: 'high', estimatedHours: 0.5 },
      { id: 'task-3', workspaceId: 'w1', projectId: 'p1', title: 'Customer interview analysis', status: 'done', priority: 'medium', estimatedHours: 1 },
      { id: 'task-4', workspaceId: 'w1', projectId: 'p1', title: 'Landing Page Copy', status: 'todo', priority: 'medium', estimatedHours: 50 },
    ],
  }],
}];

describe('ScheduleView', () => {
  it('defaults to week-oriented time execution with semantic events and unscheduled work', async () => {
    render(<ScheduleView companies={companies} onStartFocus={vi.fn()} />);

    expect(screen.getByText('Time execution')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Week$/i })).toHaveClass('text-ora-accent');
    await waitFor(() => expect(screen.getAllByText('Team sync').length).toBeGreaterThan(0));

    expect(screen.getAllByText('Build checkout integration').length).toBeGreaterThan(0);
    expect(screen.getAllByText('CIDR Review').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Customer interview analysis').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MVP launch').length).toBeGreaterThan(0);
    expect(screen.getByText('Unscheduled')).toBeInTheDocument();
    expect(screen.getByText('Landing Page Copy')).toBeInTheDocument();
    expect(screen.getByText(/over capacity/i)).toBeInTheDocument();
  });

  it('opens a compact inspector for a session', async () => {
    render(<ScheduleView companies={companies} onStartFocus={vi.fn()} />);

    await waitFor(() => expect(screen.getAllByText('Build checkout integration').length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByText('Build checkout integration')[0]);

    expect(screen.getByText('Ora session')).toBeInTheDocument();
    expect(screen.getByText('Acme MVP')).toBeInTheDocument();
    expect(screen.getByText('Move')).toBeInTheDocument();
  });
});
