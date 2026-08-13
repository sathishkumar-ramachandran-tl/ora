import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileText,
  Info,
  MessageCircle,
  MoreHorizontal,
  PauseCircle,
  Target,
  X,
} from 'lucide-react';
import { Company, Project, Task } from '../../types';
import { AgileBoard } from '../../features/board/AgileBoard';

interface ProjectWorkspaceProps {
  project: Project;
  company: Company;
  onUpdateProject: (project: Project) => void;
  onStartFocus: (task: Task) => void;
  onRequestRefresh: () => void;
}

type ProjectMode = 'GENERAL' | 'LEARNING' | 'PRODUCT' | 'CLIENT' | 'RESEARCH' | 'TEAM';
type ProjectTab = 'overview' | 'plan' | 'work' | 'context';

const MODE_CONFIG: Record<ProjectMode, {
  label: string;
  currentLabel: string;
  nextLabel: string;
  attentionLabel: string;
  emptyAttention: string;
  contextSections: string[];
  progressLanguage: string[];
}> = {
  GENERAL: {
    label: 'General project',
    currentLabel: 'Current',
    nextLabel: 'Next',
    attentionLabel: 'Attention',
    emptyAttention: 'No important risk or waiting state detected.',
    contextSections: ['Notes', 'Decisions', 'Files', 'Links'],
    progressLanguage: ['Plan', 'Work', 'Schedule'],
  },
  LEARNING: {
    label: 'Learning',
    currentLabel: 'Current topic',
    nextLabel: 'Next topic',
    attentionLabel: 'Needs review',
    emptyAttention: 'No weak concept is blocking the next step.',
    contextSections: ['Concepts', 'Research', 'Notes', 'Resources', 'Evidence'],
    progressLanguage: ['Plan', 'What you have covered', 'Needs review'],
  },
  PRODUCT: {
    label: 'Product / startup',
    currentLabel: 'Current bet',
    nextLabel: 'Next validation',
    attentionLabel: 'Risk',
    emptyAttention: 'No launch risk is currently prominent.',
    contextSections: ['Customer research', 'Decisions', 'Requirements', 'Metrics', 'Feedback'],
    progressLanguage: ['Scope', 'Validation', 'Launch readiness'],
  },
  CLIENT: {
    label: 'Client work',
    currentLabel: 'Current deliverable',
    nextLabel: 'Next delivery step',
    attentionLabel: 'Waiting / approval',
    emptyAttention: 'No client approval or waiting state detected.',
    contextSections: ['Client brief', 'Feedback', 'Assets', 'Decisions', 'Deliverables', 'Approvals'],
    progressLanguage: ['Deliverables', 'Approvals', 'Deadline'],
  },
  RESEARCH: {
    label: 'Research',
    currentLabel: 'Current question',
    nextLabel: 'Next investigation',
    attentionLabel: 'Open uncertainty',
    emptyAttention: 'No unresolved research gap is currently prominent.',
    contextSections: ['Sources', 'Notes', 'Claims', 'Gaps', 'Artifacts'],
    progressLanguage: ['Investigation', 'Evidence', 'Outputs'],
  },
  TEAM: {
    label: 'Team outcome',
    currentLabel: 'Collective focus',
    nextLabel: 'Next owner action',
    attentionLabel: 'Blockers',
    emptyAttention: 'No team blocker is currently prominent.',
    contextSections: ['Decisions', 'Requirements', 'Files', 'Metrics', 'People'],
    progressLanguage: ['Focus', 'Owners', 'Risk'],
  },
};

const inferMode = (project: Project, company: Company): ProjectMode => {
  if (project.type === 'learning') return 'LEARNING';
  if (project.type === 'client') return 'CLIENT';
  if (project.type === 'research') return 'RESEARCH';
  const text = `${project.name} ${project.mission || ''} ${company.name} ${company.mission || ''}`.toLowerCase();
  if (/(mvp|startup|launch|saas|pricing|customer|product|validation)/.test(text)) return 'PRODUCT';
  if (/(client|redesign|deliverable|approval|invoice|assets)/.test(text)) return 'CLIENT';
  if (/(team|owner|blocker|approval|member)/.test(text)) return 'TEAM';
  if (/(learn|study|exam|course|curriculum|network|upsc|interview prep)/.test(text)) return 'LEARNING';
  return 'GENERAL';
};

const taskEffort = (task?: Task | null) => {
  if (!task?.estimatedHours) return 'Flexible';
  return task.estimatedHours < 1 ? `${Math.round(task.estimatedHours * 60)} min` : `${task.estimatedHours}h`;
};

const dueCopy = (task?: Task | null) => {
  if (!task?.dueDate) return null;
  const due = new Date(task.dueDate);
  if (Number.isNaN(due.getTime())) return null;
  return `Due ${due.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
};

const sortByMeaning = (a: Task, b: Task) => {
  const priority = { critical: 4, high: 3, medium: 2, low: 1 };
  const ad = a.dueDate ? new Date(a.dueDate).getTime() : Number.MAX_SAFE_INTEGER;
  const bd = b.dueDate ? new Date(b.dueDate).getTime() : Number.MAX_SAFE_INTEGER;
  if (ad !== bd) return ad - bd;
  return (priority[b.priority] || 0) - (priority[a.priority] || 0);
};

const PrimaryWorkItem: React.FC<{
  label: string;
  task?: Task | null;
  fallback: string;
  onStartFocus: (task: Task) => void;
  tone?: 'default' | 'attention';
}> = ({ label, task, fallback, onStartFocus, tone = 'default' }) => (
  <section className="space-y-3">
    <p className="text-sm font-semibold text-ora-secondary">{label}</p>
    {task ? (
      <button
        onClick={() => onStartFocus(task)}
      className={`group w-full rounded-lg border px-5 py-5 text-left transition-colors ${
          tone === 'attention'
            ? 'border-ora-warning/25 bg-ora-warning-soft text-ora-ink'
            : 'border-ora-border bg-ora-surface text-ora-ink shadow-sm'
        }`}>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-xl font-semibold tracking-tight">{task.title}</h3>
            <p className="mt-2 text-sm text-ora-secondary">
              {[taskEffort(task), dueCopy(task), task.priority ? `${task.priority} priority` : null].filter(Boolean).join(' · ')}
            </p>
          </div>
          <ArrowRight size={18} className="mt-1 text-ora-tertiary transition-transform group-hover:translate-x-1 group-hover:text-ora-accent" />
        </div>
      </button>
    ) : (
      <div className="rounded-lg border border-ora-border bg-ora-surface/60 px-5 py-5 text-sm text-ora-secondary">{fallback}</div>
    )}
  </section>
);

const AttentionLine: React.FC<{ children: React.ReactNode; tone?: 'warning' | 'success' | 'neutral' }> = ({ children, tone = 'warning' }) => {
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'neutral' ? Info : AlertTriangle;
  const color = tone === 'success' ? 'text-ora-success' : tone === 'neutral' ? 'text-ora-info' : 'text-ora-warning';
  const surface = tone === 'success'
    ? 'border-ora-success/25 bg-ora-success-soft'
    : tone === 'neutral'
      ? 'border-ora-info/25 bg-ora-info-soft'
      : 'border-ora-warning/25 bg-ora-warning-soft';
  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${surface}`}>
      <Icon size={17} className={`mt-0.5 ${color}`} />
      <p className="text-sm leading-6 text-ora-secondary">{children}</p>
    </div>
  );
};

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({
  project,
  company,
  onUpdateProject,
  onStartFocus,
  onRequestRefresh,
}) => {
  const [tab, setTab] = useState<ProjectTab>('overview');
  const [showBoard, setShowBoard] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const tasks = project.tasks || [];
  const mode = useMemo(() => inferMode(project, company), [company, project]);
  const config = MODE_CONFIG[mode];

  const done = tasks.filter(task => task.status === 'done').length;
  const completion = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
  const unfinished = tasks.filter(task => task.status !== 'done').sort(sortByMeaning);
  const current = unfinished.find(task => task.status === 'in-progress') || unfinished[0] || null;
  const next = unfinished.find(task => task.id !== current?.id && task.status !== 'review') || null;
  const attention = unfinished.find(task => task.status === 'review' || task.priority === 'critical') || null;
  const later = unfinished.filter(task => task.id !== current?.id && task.id !== next?.id && task.id !== attention?.id).slice(0, 6);

  return (
    <div className="mx-auto max-w-6xl space-y-10 text-ora-ink">
      <header className="space-y-6 pt-2">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ora-tertiary">{company.name} · {config.label}</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-ora-ink">{project.name}</h1>
          </div>
          <button
            onClick={() => setShowInfo(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-ora-secondary hover:bg-ora-subtle hover:text-ora-ink"
            title="Project info">
            <MoreHorizontal size={19} />
          </button>
        </div>
        <p className="max-w-3xl border-l-2 border-ora-accent pl-4 text-2xl leading-9 text-ora-ink">
          {project.mission || 'Define the outcome with Ora, then let the system keep work and time aligned.'}
        </p>
        <div className="flex flex-wrap items-center gap-3 text-sm text-ora-secondary">
          <span className="rounded-full bg-ora-surface px-3 py-1 ring-1 ring-ora-border">{config.progressLanguage[0]} {completion}%</span>
          <span className="rounded-full bg-ora-surface-subtle px-3 py-1">{done}/{tasks.length} done</span>
          <span>{config.progressLanguage.slice(1).join(' · ')}</span>
        </div>
        <nav className="flex gap-6 overflow-x-auto border-b border-ora-border">
          {[
            ['overview', 'Overview'],
            ['plan', 'Plan'],
            ['work', 'Work'],
            ['context', 'Context'],
          ].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id as ProjectTab)}
              className={`whitespace-nowrap py-3 text-sm font-medium transition-colors ${
                tab === id ? 'border-b-2 border-ora-accent text-ora-ink' : 'text-ora-secondary hover:text-ora-ink'
              }`}>
              {label}
            </button>
          ))}
        </nav>
      </header>

      {tab === 'overview' && (
        <main className="grid gap-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <div className="space-y-8">
            <PrimaryWorkItem
              label={config.currentLabel}
              task={current}
              fallback="No current work is active. Ask Ora to choose the next move."
              onStartFocus={onStartFocus}
            />
            <PrimaryWorkItem
              label={config.nextLabel}
              task={next}
              fallback="No clear next item yet."
              onStartFocus={onStartFocus}
            />
          </div>
          <aside className="space-y-6">
            <section className="space-y-3">
              <p className="text-sm font-semibold text-ora-secondary">{config.attentionLabel}</p>
              {attention ? (
                <AttentionLine>{attention.title} needs attention before the project can move cleanly.</AttentionLine>
              ) : (
                <AttentionLine tone="success">{config.emptyAttention}</AttentionLine>
              )}
            </section>
            <section className="rounded-lg border border-ora-accent/20 bg-ora-accent-soft px-5 py-5 shadow-[inset_3px_0_0_rgb(var(--ora-accent))]">
              <div className="flex items-center gap-2 text-ora-ink">
                <MessageCircle size={17} className="text-ora-accent" />
                <h2 className="text-sm font-semibold">Ask Ora about {project.name}</h2>
              </div>
              <button
                onClick={() => window.dispatchEvent(new CustomEvent('ora:command', { detail: { content: `What should we focus on next for ${project.name}?` } }))}
                className="mt-4 w-full rounded-lg bg-ora-surface px-4 py-3 text-left text-sm text-ora-secondary shadow-sm hover:text-ora-ink">
                <span className="inline-flex rounded-full bg-ora-subtle px-2 py-1 text-xs text-ora-secondary">{project.name} ×</span>
                <span className="mt-3 block">What should we focus on next?</span>
              </button>
            </section>
          </aside>
        </main>
      )}

      {tab === 'plan' && (
        <main className="space-y-6">
          <section className="max-w-3xl space-y-3">
            <p className="text-sm font-semibold text-ora-secondary">Plan</p>
            <h2 className="text-2xl font-semibold tracking-tight">Strategy before task detail.</h2>
            <p className="text-sm leading-6 text-ora-secondary">
              Ora plan proposals, revisions, dependencies, and major objectives belong here as a vertical progression. Manual task detail remains available as advanced detail.
            </p>
          </section>
          <div className="space-y-3">
            {unfinished.slice(0, 5).map((task, idx) => (
              <div key={task.id} className="flex gap-4">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-ora-subtle text-sm font-semibold text-ora-secondary">{idx + 1}</div>
                <button onClick={() => onStartFocus(task)} className="min-w-0 flex-1 pb-5 text-left">
                  <p className="text-base font-semibold text-ora-ink">{task.title}</p>
                  <p className="mt-1 text-sm text-ora-secondary">{task.status.replace(/-/g, ' ')} · {taskEffort(task)}</p>
                </button>
              </div>
            ))}
          </div>
        </main>
      )}

      {tab === 'work' && (
        <main className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="space-y-6">
            <PrimaryWorkItem label="Now" task={current} fallback="No active work." onStartFocus={onStartFocus} />
            <PrimaryWorkItem label="Next" task={next} fallback="No next work." onStartFocus={onStartFocus} />
            {later.length > 0 && (
              <section className="space-y-3">
                <p className="text-sm font-semibold text-ora-secondary">Later</p>
                <div className="space-y-2">
                  {later.map(task => (
                    <button key={task.id} onClick={() => onStartFocus(task)} className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left hover:bg-white">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-ora-ink">{task.title}</span>
                        <span className="text-xs text-ora-secondary">{taskEffort(task)}</span>
                      </span>
                      <ArrowRight size={15} className="text-ora-tertiary" />
                    </button>
                  ))}
                </div>
              </section>
            )}
          </section>
          <aside className="space-y-4">
            <AttentionLine tone={attention ? 'warning' : 'neutral'}>{attention ? `${attention.title} is waiting or high risk.` : 'No waiting work detected.'}</AttentionLine>
            <section className="rounded-lg border border-ora-border bg-ora-surface/70">
              <button
                onClick={() => setShowBoard(value => !value)}
                className="flex w-full items-center justify-between px-5 py-4 text-left">
                <span className="text-sm font-semibold text-ora-ink">Advanced: view as board</span>
                <ChevronDown size={16} className={`text-ora-tertiary transition-transform ${showBoard ? 'rotate-180' : ''}`} />
              </button>
            </section>
          </aside>
        </main>
      )}

      {tab === 'context' && (
        <main className="space-y-6">
          <section className="max-w-3xl">
            <p className="text-sm font-semibold text-ora-secondary">Context</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">What Ora should know about this outcome.</h2>
          </section>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {config.contextSections.map(section => (
              <div key={section} className="rounded-lg border border-ora-border bg-ora-surface/75 px-5 py-5">
                <FileText size={17} className="text-ora-tertiary" />
                <h3 className="mt-4 text-base font-semibold text-ora-ink">{section}</h3>
                <p className="mt-2 text-sm leading-6 text-ora-secondary">Add or retrieve relevant evidence without changing the page structure.</p>
              </div>
            ))}
          </div>
        </main>
      )}

      {showBoard && (
        <section className="rounded-lg border border-ora-border bg-ora-surface shadow-sm">
          <AgileBoard
            project={project}
            companyMission={company.mission}
            onUpdateProject={onUpdateProject}
            onStartFocus={onStartFocus}
            onRequestRefresh={onRequestRefresh}
          />
        </section>
      )}

      {showInfo && (
        <div className="fixed inset-0 z-50 flex justify-end bg-ora-ink/30" onClick={() => setShowInfo(false)}>
          <aside className="h-full w-full max-w-md bg-white p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-ora-ink">Project info</h2>
              <button onClick={() => setShowInfo(false)} className="rounded-lg p-2 text-ora-secondary hover:bg-ora-subtle"><X size={18} /></button>
            </div>
            <div className="mt-8 space-y-5 text-sm">
              <div>
                <p className="text-ora-secondary">Mode</p>
                <p className="mt-1 font-medium text-ora-ink">{config.label}</p>
              </div>
              <div>
                <p className="text-ora-secondary">Project group</p>
                <p className="mt-1 font-medium text-ora-ink">{company.name}</p>
              </div>
              <div>
                <p className="text-ora-secondary">Progress</p>
                <p className="mt-1 font-medium text-ora-ink">{completion}% · {done}/{tasks.length} complete</p>
              </div>
              <div className="rounded-xl bg-ora-subtle p-4">
                <p className="flex items-center gap-2 font-medium text-ora-ink"><Clock size={16} /> Secondary controls</p>
                <p className="mt-2 leading-6 text-ora-secondary">Deadline, owners, project mode overrides, archive, and schedule settings belong here rather than in the main header.</p>
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
};
