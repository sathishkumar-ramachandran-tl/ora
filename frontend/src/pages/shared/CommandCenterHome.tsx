import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Clock, Loader2, MessageCircle, RefreshCw, Sparkles } from 'lucide-react';
import { Task } from '../../types';
import { fetchWorkspaceHome, searchWorkspace, TodayCandidate, WorkspaceHome, WorkspaceSearchResult } from '../../api/workspace';
import { PlanProposal } from '../../api/chat';

interface CommandCenterHomeProps {
  workspaceId: string;
  onStartFocus: (task: Task) => void;
  onOpenProject: (projectId: string) => void;
}

const candidateToTask = (candidate: TodayCandidate): Task => ({
  id: candidate.task_id,
  workspaceId: '',
  projectId: candidate.project_id || undefined,
  title: candidate.title,
  status: 'todo',
  priority: (candidate.priority as Task['priority']) || 'medium',
  estimatedHours: candidate.estimated_effort_minutes / 60,
});

const formatMinutes = (minutes: number) => {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
};

const formatTimeRange = (start?: string | null, end?: string | null) => {
  if (!start || !end) return null;
  return `${new Date(start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${new Date(end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};

const NowCard: React.FC<{ candidate: TodayCandidate | null; onStart: (candidate: TodayCandidate) => void }> = ({ candidate, onStart }) => {
  if (!candidate) {
    return (
      <section className="rounded-lg border border-ora-border bg-ora-surface p-5">
        <p className="text-xs font-semibold uppercase text-ora-tertiary">Now</p>
        <h2 className="mt-3 text-xl font-semibold text-ora-primary">What do you want to accomplish?</h2>
        <p className="mt-2 text-sm text-ora-secondary">Start with an outcome. Ora can turn it into a plan, work, time, and next action.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-ora-border bg-ora-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-ora-tertiary">Now</p>
          <h2 className="mt-2 text-2xl font-semibold text-ora-primary">{candidate.title}</h2>
          <p className="mt-1 text-sm text-ora-secondary">
            {formatMinutes(candidate.estimated_effort_minutes)}
            {candidate.project_name ? ` · ${candidate.project_name}` : ''}
          </p>
          {candidate.scheduled_start && (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-ora-info-soft px-2 py-1 text-xs font-medium text-ora-info">
              <Clock size={13} /> {formatTimeRange(candidate.scheduled_start, candidate.scheduled_end)}
            </p>
          )}
        </div>
        <button
          onClick={() => onStart(candidate)}
          className="inline-flex items-center gap-2 rounded-md bg-ora-accent px-4 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover">
          Start <ArrowRight size={15} />
        </button>
      </div>
      <div className="mt-4 grid gap-2">
        {candidate.reasons.slice(0, 4).map(reason => (
          <div key={reason} className="flex items-start gap-2 text-sm text-ora-secondary">
            <CheckCircle2 size={15} className="mt-0.5 text-ora-success" />
            <span>{reason}</span>
          </div>
        ))}
      </div>
    </section>
  );
};

const NextList: React.FC<{ items: TodayCandidate[]; laterCount: number; onStart: (candidate: TodayCandidate) => void }> = ({ items, laterCount, onStart }) => (
  <section className="rounded-lg border border-ora-border bg-ora-surface/55 p-4">
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-semibold text-ora-primary">Next</h3>
      {laterCount > 0 && <span className="text-xs text-ora-tertiary">{laterCount} later</span>}
    </div>
    <div className="mt-3 space-y-2">
      {items.map(item => (
        <button
          key={item.task_id}
          onClick={() => onStart(item)}
          className="w-full rounded-md border border-transparent px-3 py-2 text-left hover:border-ora-border hover:bg-ora-surface">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-ora-primary">{item.title}</p>
            <span className="text-xs text-ora-tertiary">{formatMinutes(item.estimated_effort_minutes)}</span>
          </div>
          <p className="mt-1 text-xs text-ora-secondary line-clamp-1">{item.reasons[0]}</p>
          {item.scheduled_start && (
            <p className="mt-1 text-xs text-ora-info">{formatTimeRange(item.scheduled_start, item.scheduled_end)}</p>
          )}
        </button>
      ))}
      {items.length === 0 && <p className="py-4 text-sm text-ora-secondary">Ora will suggest follow-ups after you create or apply a plan.</p>}
    </div>
  </section>
);

const PlanStrip: React.FC<{ plan?: PlanProposal | null }> = ({ plan }) => {
  if (!plan) return null;
  return (
    <section className="rounded-lg border border-ora-accent/20 bg-ora-accent-soft p-4 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]">
      <p className="text-xs font-semibold uppercase text-ora-accent">Plan waiting</p>
      <h3 className="mt-1 text-sm font-semibold text-ora-primary">{plan.title}</h3>
      <p className="mt-1 text-xs text-ora-secondary">
        {plan.summary.phaseCount} phases · {plan.summary.taskCount} proposed tasks · {plan.qualityStatus}
      </p>
    </section>
  );
};

const RevisionStrip: React.FC<{ revision: WorkspaceHome['pending_revision'] }> = ({ revision }) => {
  if (!revision) return null;
  const ops = revision.operations || [];
  return (
    <section className="rounded-lg border border-ora-warning/25 bg-ora-warning-soft p-4">
      <p className="text-xs font-semibold uppercase text-ora-warning">Plan update proposed</p>
      <h3 className="mt-1 text-sm font-semibold text-ora-primary">{revision.trigger}</h3>
      <div className="mt-2 space-y-1 text-xs text-ora-secondary">
        {ops.slice(0, 3).map((op, idx) => (
          <p key={idx}>{String(op.op || '=')} {String(op.target || op.target_concept_key || 'plan item')}</p>
        ))}
      </div>
    </section>
  );
};

const ScheduleStrip: React.FC<{ schedule?: WorkspaceHome['pending_schedule'] | null }> = ({ schedule }) => {
  if (!schedule) return null;
  return (
    <section className="rounded-lg border border-ora-info/25 bg-ora-info-soft p-4">
      <p className="text-xs font-semibold uppercase text-ora-info">Schedule waiting</p>
      <h3 className="mt-1 text-sm font-semibold text-ora-primary">{String(schedule.summary.title || 'This schedule')}</h3>
      <p className="mt-1 text-xs text-ora-secondary">
        {schedule.summary.sessionCount || schedule.sessions.length} sessions · {schedule.status.replace(/_/g, ' ')}
      </p>
    </section>
  );
};

const HealthStrip: React.FC<{ health?: WorkspaceHome['plan_health'] }> = ({ health }) => {
  if (!health || health.status === 'HEALTHY') return null;
  const tone = health.status === 'REVISION_RECOMMENDED'
    ? 'border-ora-danger/25 bg-ora-danger-soft text-ora-primary'
    : 'border-ora-warning/25 bg-ora-warning-soft text-ora-primary';
  return (
    <section className={`rounded-lg border p-4 ${tone}`}>
      <p className="text-xs font-semibold uppercase opacity-70">{health.status.replace(/_/g, ' ')}</p>
      <div className="mt-2 space-y-1">
        {health.reasons.slice(0, 3).map(reason => (
          <p key={reason} className="text-sm">{reason}</p>
        ))}
      </div>
    </section>
  );
};

export const CommandCenterHome: React.FC<CommandCenterHomeProps> = ({ workspaceId, onStartFocus, onOpenProject }) => {
  const [home, setHome] = useState<WorkspaceHome | null>(null);
  const [loading, setLoading] = useState(true);
  const [command, setCommand] = useState('');
  const [searchResults, setSearchResults] = useState<WorkspaceSearchResult[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      setHome(await fetchWorkspaceHome(workspaceId));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [workspaceId]);

  const examples = useMemo(() => [
    'Launch a product in 6 weeks.',
    'Plan my week.',
    'Deliver a client redesign.',
    'Build my portfolio this month.',
    'Prepare for an exam.',
    'Get ready for senior SWE interviews.',
  ], []);

  useEffect(() => {
    const q = command.trim().replace(/^>/, '').trim();
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      searchWorkspace(workspaceId, q).then(setSearchResults).catch(() => setSearchResults([]));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [command, workspaceId]);

  const askOra = () => {
    const content = command.trim();
    if (!content) return;
    window.dispatchEvent(new CustomEvent('ora:command', { detail: { content } }));
  };

  const hasActiveState = Boolean(
    home?.today.now ||
    home?.today.next?.length ||
    home?.pending_plan ||
    home?.pending_schedule ||
    home?.pending_revision ||
    (home?.plan_health ? home.plan_health.status !== 'HEALTHY' : false)
  );

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-ora-secondary">
        <Loader2 className="mr-2 animate-spin" size={18} /> Loading Ora…
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <section className="pt-2">
        <p className="text-sm font-medium text-ora-accent">Ora</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ora-primary">
          {hasActiveState ? 'What matters now?' : 'What do you want to accomplish?'}
        </h1>
        <div className="mt-5 rounded-lg border border-ora-border bg-ora-surface p-2 shadow-sm focus-within:border-ora-accent focus-within:ring-2 focus-within:ring-ora-accent/15">
          <div className="flex items-center gap-2">
            <MessageCircle size={18} className="ml-2 text-ora-accent" />
            <input
              value={command}
              onChange={e => setCommand(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') askOra();
              }}
              placeholder="Ask Ora anything..."
              className="min-w-0 flex-1 border-0 bg-transparent px-2 py-3 text-sm outline-none placeholder:text-ora-tertiary"
            />
            <button
              onClick={askOra}
              className="rounded-md bg-ora-accent px-4 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover">
              Ask
            </button>
          </div>
        </div>
        {searchResults.length > 0 && (
          <div className="mt-2 rounded-lg border border-ora-border bg-ora-surface p-2 shadow-sm">
            {searchResults.slice(0, 5).map(result => (
              <button
                key={`${result.type}-${result.id}`}
                onClick={() => {
                  if (result.type === 'project') onOpenProject(result.id);
                  else setCommand(result.title);
                }}
                className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left hover:bg-ora-subtle">
                <span>
                  <span className="block text-sm font-medium text-ora-primary">{result.title}</span>
                  <span className="text-xs capitalize text-ora-tertiary">{result.type}{result.subtitle ? ` · ${result.subtitle}` : ''}</span>
                </span>
                <ArrowRight size={14} className="text-ora-tertiary" />
              </button>
            ))}
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {examples.map(example => (
            <button
              key={example}
              onClick={() => setCommand(example)}
              className="rounded-full border border-ora-border px-3 py-1 text-xs text-ora-secondary hover:border-ora-accent/35 hover:bg-ora-surface">
              {example}
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <div className="space-y-5">
          <NowCard candidate={home?.today.now || null} onStart={candidate => onStartFocus(candidateToTask(candidate))} />
          {hasActiveState && (
            <NextList items={home?.today.next || []} laterCount={home?.today.later_count || 0} onStart={candidate => onStartFocus(candidateToTask(candidate))} />
          )}
        </div>

        <aside className="space-y-4">
          {hasActiveState && <section className="rounded-lg border border-ora-border bg-ora-surface/70 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ora-primary">Active</h3>
              <button onClick={load} className="text-ora-tertiary hover:text-ora-primary" title="Refresh">
                <RefreshCw size={14} />
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {(home?.active_projects || []).slice(0, 4).map(project => (
                <button
                  key={project.id}
                  onClick={() => onOpenProject(project.id)}
                  className="w-full rounded-md px-2 py-2 text-left hover:bg-ora-surface">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-ora-primary">{project.name}</span>
                    <span className="text-xs text-ora-tertiary">{project.done_count}/{project.task_count}</span>
                  </div>
                </button>
              ))}
              {(!home?.active_projects || home.active_projects.length === 0) && (
                <p className="py-3 text-sm text-ora-secondary">No active structure yet. Start with a goal.</p>
              )}
            </div>
          </section>}

          <PlanStrip plan={home?.pending_plan} />
          <HealthStrip health={home?.plan_health} />
          <ScheduleStrip schedule={home?.pending_schedule || null} />
          <RevisionStrip revision={home?.pending_revision || null} />

          {Boolean(home?.today.missed_sessions?.length) && (
            <section className="rounded-lg border border-ora-warning/25 bg-ora-warning-soft p-4">
              <p className="text-xs font-semibold uppercase text-ora-warning">Missed sessions</p>
              <div className="mt-2 space-y-1">
                {(home?.today.missed_sessions || []).slice(0, 3).map(session => (
                  <p key={session.id} className="text-sm text-ora-primary">{session.title}</p>
                ))}
              </div>
            </section>
          )}

          {hasActiveState && <section className="rounded-lg border border-ora-border bg-ora-surface/70 p-4">
            <h3 className="text-sm font-semibold text-ora-primary">Progress signals</h3>
            <div className="mt-3 space-y-2 text-sm text-ora-secondary">
              <p className="flex items-center gap-2"><Clock size={14} /> {home?.calendar.event_count || 0} calendar items today</p>
              <p className="flex items-center gap-2"><Sparkles size={14} /> {home?.alerts.length || 0} attention signal{home?.alerts.length === 1 ? '' : 's'}</p>
              <p className="flex items-center gap-2"><CheckCircle2 size={14} /> Recommendations use evidence and schedule reality when available</p>
            </div>
          </section>}
        </aside>
      </div>
    </div>
  );
};
