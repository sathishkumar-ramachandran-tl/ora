import React, { useMemo } from 'react';
import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock, Hourglass, PauseCircle } from 'lucide-react';
import { Company, Priority, Task } from '../../types';
import { trackEvent } from '../../services/analytics';

interface UniversalWorkProps {
  companies: Company[];
  onStartFocus: (task: Task) => void;
  onOpenProject: (projectId: string) => void;
  onOpenSchedule?: () => void;
}

interface WorkItem {
  task: Task;
  projectName: string;
  projectId: string;
  companyName: string;
}

const priorityScore: Record<Priority, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

const formatEffort = (hours?: number) => {
  if (!hours) return 'Flexible';
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${hours}h`;
};

const dueLabel = (dueDate?: string) => {
  if (!dueDate) return null;
  const due = new Date(dueDate);
  if (Number.isNaN(due.getTime())) return null;
  return due.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

const flattenWork = (companies: Company[]): WorkItem[] => companies.flatMap(company =>
  (company.projects || []).flatMap(project =>
    (project.tasks || []).map(task => ({
      task,
      projectName: project.name,
      projectId: project.id,
      companyName: company.name,
    }))
  )
);

const sortWork = (a: WorkItem, b: WorkItem) => {
  const ad = a.task.dueDate ? new Date(a.task.dueDate).getTime() : Number.MAX_SAFE_INTEGER;
  const bd = b.task.dueDate ? new Date(b.task.dueDate).getTime() : Number.MAX_SAFE_INTEGER;
  if (ad !== bd) return ad - bd;
  return (priorityScore[b.task.priority] || 0) - (priorityScore[a.task.priority] || 0);
};

const WorkRow: React.FC<{
  item: WorkItem;
  onStartFocus: (task: Task) => void;
  onOpenProject: (projectId: string) => void;
  variant?: 'primary' | 'quiet';
}> = ({ item, onStartFocus, onOpenProject, variant = 'quiet' }) => {
  const due = dueLabel(item.task.dueDate);
  return (
    <div className={`group rounded-lg px-4 py-3 transition-colors ${variant === 'primary' ? 'bg-ora-surface shadow-sm ring-1 ring-ora-border' : 'hover:bg-ora-surface/70'}`}>
      <div className="flex items-start justify-between gap-3">
        <button
          onClick={() => onStartFocus(item.task)}
          className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-semibold text-ora-primary">{item.task.title}</p>
          <p className="mt-1 truncate text-xs text-ora-secondary">
            {item.projectName} · {formatEffort(item.task.estimatedHours)}
            {due ? ` · due ${due}` : ''}
          </p>
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onOpenProject(item.projectId)}
            className="hidden rounded-md px-2 py-1 text-xs font-medium text-ora-secondary hover:bg-ora-subtle hover:text-ora-primary sm:inline-flex">
            Project
          </button>
          <button
            onClick={() => {
              trackEvent('TASK_FOCUS_STARTED', { taskId: item.task.id, projectId: item.projectId });
              onStartFocus(item.task);
            }}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-ora-accent text-white opacity-100 transition-opacity hover:bg-ora-accent-hover sm:opacity-0 sm:group-hover:opacity-100"
            title="Continue">
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

const Section: React.FC<{
  title: string;
  description?: string;
  icon: React.ElementType;
  items: WorkItem[];
  empty: string;
  onStartFocus: (task: Task) => void;
  onOpenProject: (projectId: string) => void;
}> = ({ title, description, icon: Icon, items, empty, onStartFocus, onOpenProject }) => (
  <section className="space-y-3">
    <div className="flex items-center gap-2">
      <Icon size={16} className="text-ora-accent" />
      <div>
        <h2 className="text-sm font-semibold text-ora-primary">{title}</h2>
        {description && <p className="text-xs text-ora-secondary">{description}</p>}
      </div>
    </div>
    <div className="space-y-2">
      {items.map(item => (
        <WorkRow
          key={item.task.id}
          item={item}
          onStartFocus={onStartFocus}
          onOpenProject={onOpenProject}
        />
      ))}
      {items.length === 0 && (
        <p className="rounded-lg bg-ora-surface/70 px-4 py-5 text-sm text-ora-secondary ring-1 ring-ora-border">{empty}</p>
      )}
    </div>
  </section>
);

export const UniversalWork: React.FC<UniversalWorkProps> = ({ companies, onStartFocus, onOpenProject, onOpenSchedule }) => {
  const { now, next, waiting, later, completedToday } = useMemo(() => {
    const items = flattenWork(companies);
    const unfinished = items.filter(item => item.task.status !== 'done');
    const active = unfinished.filter(item => item.task.status === 'in-progress').sort(sortWork);
    const review = unfinished.filter(item => item.task.status === 'review').sort(sortWork);
    const actionable = unfinished
      .filter(item => item.task.status === 'todo' || item.task.status === 'backlog')
      .sort(sortWork);
    return {
      now: active.slice(0, 2),
      next: actionable.slice(0, 6),
      waiting: review.slice(0, 6),
      later: actionable.slice(6),
      completedToday: items.filter(item => item.task.status === 'done').length,
    };
  }, [companies]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
      <header className="flex flex-col gap-4 pt-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-ora-accent">Work</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ora-primary">Everything actionable, in priority order.</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ora-secondary">
            Work is not a board. It is what needs movement now, what is waiting, and what can safely sit later.
          </p>
        </div>
        {onOpenSchedule && (
          <button
            onClick={onOpenSchedule}
            className="inline-flex items-center gap-2 rounded-md border border-ora-border bg-ora-surface px-3 py-2 text-sm font-medium text-ora-secondary shadow-sm hover:border-ora-border-strong">
            <CalendarDays size={15} /> Calendar detail
          </button>
        )}
      </header>

      {now.length > 0 ? (
        <section className="rounded-lg bg-ora-accent-soft p-5 ring-1 ring-ora-accent/15">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-ora-accent" />
            <h2 className="text-sm font-semibold text-ora-primary">Now</h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {now.map(item => (
              <WorkRow
                key={item.task.id}
                item={item}
                variant="primary"
                onStartFocus={onStartFocus}
                onOpenProject={onOpenProject}
              />
            ))}
          </div>
        </section>
      ) : (
        <section className="rounded-lg bg-ora-surface p-5 ring-1 ring-ora-border">
          <div className="flex items-start gap-3">
            <CheckCircle2 size={18} className="mt-0.5 text-ora-success" />
            <div>
              <h2 className="text-sm font-semibold text-ora-primary">No active work is already in motion.</h2>
              <p className="mt-1 text-sm text-ora-secondary">Choose from Next, or ask Ora to decide what matters most.</p>
            </div>
          </div>
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <div className="space-y-8">
          <Section
            title="Next"
            description="Eligible work that can move outcomes forward."
            icon={ArrowRight}
            items={next}
            empty="Nothing queued. Ask Ora to break an outcome into work, or add one item manually."
            onStartFocus={onStartFocus}
            onOpenProject={onOpenProject}
          />
          <Section
            title="Waiting"
            description="Items needing review, approval, input, or unblock."
            icon={PauseCircle}
            items={waiting}
            empty="No waiting items detected."
            onStartFocus={onStartFocus}
            onOpenProject={onOpenProject}
          />
        </div>
        <aside className="space-y-5">
          <section className="rounded-lg bg-ora-warning-soft p-5 ring-1 ring-ora-warning/20">
            <h2 className="text-sm font-semibold text-ora-primary">Attention</h2>
            <div className="mt-3 space-y-2 text-sm text-ora-secondary">
              {waiting.length > 0 && (
                <p className="flex items-start gap-2">
                  <AlertTriangle size={15} className="mt-0.5 text-ora-warning" />
                  {waiting.length} item{waiting.length === 1 ? '' : 's'} waiting for review or unblock.
                </p>
              )}
              {later.length > 0 && (
                <p className="flex items-start gap-2">
                  <Hourglass size={15} className="mt-0.5 text-ora-tertiary" />
                  {later.length} lower-priority item{later.length === 1 ? '' : 's'} kept out of the main flow.
                </p>
              )}
              {!waiting.length && !later.length && <p>No urgent attention signals found.</p>}
            </div>
          </section>
          <section className="rounded-lg bg-ora-surface/70 p-5 ring-1 ring-ora-border">
            <h2 className="text-sm font-semibold text-ora-primary">Progress</h2>
            <p className="mt-3 text-sm text-ora-secondary">
              {completedToday} completed item{completedToday === 1 ? '' : 's'} in this workspace.
            </p>
            <p className="mt-2 text-xs text-ora-tertiary">Ora uses execution evidence, schedule state, and deadlines before recommending changes.</p>
          </section>
        </aside>
      </div>
    </div>
  );
};
