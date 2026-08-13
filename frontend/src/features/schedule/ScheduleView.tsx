import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  LayoutGrid,
  List,
  Lock,
  MinusCircle,
  MoveRight,
  PlusCircle,
  Target,
  X,
  Zap,
} from 'lucide-react';
import { CalendarEvent, Company, Project, Task } from '../../types';
import { autoScheduleTasks, createEvent, deleteEvent, getEvents } from '../../api/calendar';
import { ConfirmDeleteModal, CreateEventModal } from './CreateEventModal';

interface ScheduleViewProps {
  companies: Company[];
  onStartFocus: (task: Task) => void;
}

type ViewMode = 'day' | 'week' | 'month';
type EventKind = 'fixed' | 'work' | 'deadline';

const VIEW_OPTIONS: Array<{ id: ViewMode; icon: React.ElementType; label: string }> = [
  { id: 'day', icon: List, label: 'Day' },
  { id: 'week', icon: Calendar, label: 'Week' },
  { id: 'month', icon: LayoutGrid, label: 'Month' },
];

const HOURS = Array.from({ length: 13 }, (_, i) => i + 8);
const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const startOfDay = (date: Date) => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
};

const endOfDay = (date: Date) => {
  const d = new Date(date);
  d.setHours(23, 59, 59, 999);
  return d;
};

const startOfWeek = (date: Date) => {
  const d = startOfDay(date);
  d.setDate(d.getDate() - d.getDay());
  return d;
};

const addDays = (date: Date, days: number) => {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
};

const minutesBetween = (start: Date, end: Date) => Math.max(0, Math.round((end.getTime() - start.getTime()) / 60000));

const formatTime = (value: string | Date) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const formatDuration = (minutes: number) => minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`;

const allProjectTasks = (companies: Company[]): Array<{ task: Task; project: Project; company: Company }> => (
  companies.flatMap(company => (company.projects || []).flatMap(project => (project.tasks || []).map(task => ({ task, project, company }))))
);

const eventKind = (event: CalendarEvent): EventKind => {
  if (event.type === 'reminder') return 'deadline';
  if (event.type === 'task_block' || event.taskId || event.isFlexible) return 'work';
  return 'fixed';
};

const projectForEvent = (event: CalendarEvent, items: Array<{ task: Task; project: Project; company: Company }>) => (
  event.taskId ? items.find(item => item.task.id === event.taskId)?.project : null
);

const eventTitle = (event: CalendarEvent) => event.title.replace(/^Focus:\s*/i, '');

const styleForEvent = (event: CalendarEvent) => {
  const kind = eventKind(event);
  const missed = event.sessionStatus === 'MISSED';
  const completed = event.sessionStatus === 'COMPLETED';
  if (kind === 'deadline') return 'border-l-ora-warning bg-ora-warning-soft text-ora-ink';
  if (missed) return 'border-l-ora-warning bg-ora-warning-soft text-ora-ink';
  if (completed) return 'border-l-ora-success bg-ora-success-soft text-ora-secondary opacity-80';
  if (kind === 'work') return 'border-l-ora-accent bg-ora-accent-soft text-ora-ink';
  return 'border-l-ora-border-strong bg-ora-surface-subtle text-ora-ink';
};

const weekRangeLabel = (date: Date) => {
  const start = startOfWeek(date);
  const end = addDays(start, 6);
  return `${start.toLocaleDateString([], { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
};

const monthDays = (date: Date) => {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const last = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  const days: Array<Date | null> = [];
  for (let i = 0; i < first.getDay(); i += 1) days.push(null);
  for (let day = 1; day <= last.getDate(); day += 1) days.push(new Date(date.getFullYear(), date.getMonth(), day));
  return days;
};

const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

const EventBlock: React.FC<{
  event: CalendarEvent;
  projectName?: string;
  compact?: boolean;
  onInspect: (event: CalendarEvent) => void;
}> = ({ event, projectName, compact = false, onInspect }) => {
  const kind = eventKind(event);
  const start = new Date(event.start);
  const end = new Date(event.end);
  const duration = minutesBetween(start, end);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onInspect(event);
      }}
      className={`w-full rounded-lg border-l-4 px-3 py-2 text-left text-xs shadow-sm transition-colors hover:brightness-[0.98] ${styleForEvent(event)}`}>
      <div className="flex items-start gap-2">
        {kind === 'fixed' && <Lock size={12} className="mt-0.5 text-ora-tertiary" />}
        {kind === 'deadline' && <Flag size={12} className="mt-0.5 text-ora-warning" />}
        {event.sessionStatus === 'COMPLETED' && <CheckCircle2 size={12} className="mt-0.5 text-ora-success" />}
        {event.sessionStatus === 'MISSED' && <AlertTriangle size={12} className="mt-0.5 text-ora-warning" />}
        <span className="min-w-0 flex-1">
          <span className={`block truncate font-semibold ${compact ? 'text-[11px]' : 'text-sm'}`}>{eventTitle(event)}</span>
          {!compact && (
            <span className="mt-1 block truncate text-[11px] opacity-75">
              {projectName || (kind === 'fixed' ? 'Fixed commitment' : 'Ora session')} · {formatTime(start)}-{formatTime(end)} · {formatDuration(duration)}
            </span>
          )}
        </span>
      </div>
    </button>
  );
};

export const ScheduleView: React.FC<ScheduleViewProps> = ({ companies, onStartFocus }) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>('week');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);

  const [constraintsModalOpen, setConstraintsModalOpen] = useState(false);
  const [instruction, setInstruction] = useState('');
  const [dayStartHour, setDayStartHour] = useState(9);
  const [dayEndHour, setDayEndHour] = useState(18);
  const [weekdaysOnly, setWeekdaysOnly] = useState(true);
  const [targetEndDate, setTargetEndDate] = useState('');

  const [createModalStart, setCreateModalStart] = useState<Date | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CalendarEvent | null>(null);

  const items = useMemo(() => allProjectTasks(companies), [companies]);
  const workspaceId = companies[0]?.workspaceId;
  const unfinished = items.filter(item => item.task.status !== 'done');
  const unscheduledTasks = unfinished.filter(item => !events.some(event => event.taskId === item.task.id));

  const visibleRange = useMemo(() => {
    if (viewMode === 'day') return { start: startOfDay(currentDate), end: endOfDay(currentDate) };
    if (viewMode === 'week') {
      const start = startOfWeek(currentDate);
      return { start, end: endOfDay(addDays(start, 6)) };
    }
    return {
      start: new Date(currentDate.getFullYear(), currentDate.getMonth(), 1),
      end: new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0, 23, 59, 59),
    };
  }, [currentDate, viewMode]);

  const loadEvents = async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      setEvents(await getEvents(workspaceId, visibleRange.start, visibleRange.end));
    } catch (e) {
      console.error('Failed to load events', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [workspaceId, visibleRange.start.getTime(), visibleRange.end.getTime()]);

  useEffect(() => {
    if (!banner) return;
    const timer = setTimeout(() => setBanner(null), 4200);
    return () => clearTimeout(timer);
  }, [banner]);

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(currentDate), i));
  const workMinutes = events
    .filter(event => eventKind(event) === 'work')
    .reduce((sum, event) => sum + minutesBetween(new Date(event.start), new Date(event.end)), 0);
  const fixedMinutes = events
    .filter(event => eventKind(event) === 'fixed')
    .reduce((sum, event) => sum + minutesBetween(new Date(event.start), new Date(event.end)), 0);
  const unscheduledMinutes = unscheduledTasks.reduce((sum, item) => sum + Math.round((item.task.estimatedHours || 1) * 60), 0);
  const availableEstimate = Math.max(0, (dayEndHour - dayStartHour) * 60 * (weekdaysOnly ? 5 : 7) - workMinutes - fixedMinutes);
  const overCapacity = unscheduledMinutes > availableEstimate;

  const handleNavigate = (direction: -1 | 1) => {
    const next = new Date(currentDate);
    if (viewMode === 'day') next.setDate(next.getDate() + direction);
    if (viewMode === 'week') next.setDate(next.getDate() + direction * 7);
    if (viewMode === 'month') next.setMonth(next.getMonth() + direction);
    setCurrentDate(next);
  };

  const handleOpenCreateEvent = (date: Date, hour = dayStartHour) => {
    const start = new Date(date);
    start.setHours(hour, 0, 0, 0);
    setCreateModalStart(start);
  };

  const handleSubmitCreateEvent = async (event: Partial<CalendarEvent>) => {
    if (!workspaceId) return;
    await createEvent(workspaceId, event);
    loadEvents();
  };

  const handleAssignTaskToSlot = async (task: Task, date = currentDate, hour = dayStartHour) => {
    const start = new Date(date);
    start.setHours(hour, 0, 0, 0);
    const duration = task.estimatedHours || 1;
    const end = new Date(start.getTime() + duration * 60 * 60 * 1000);
    await createEvent(task.workspaceId, {
      title: task.title,
      start: start.toISOString(),
      end: end.toISOString(),
      type: 'task_block',
      taskId: task.id,
      color: 'accent',
      scope: 'personal',
      isFlexible: true,
      sessionStatus: 'SCHEDULED',
    });
    loadEvents();
  };

  const handleConfirmDeleteEvent = async (deleteSeries: boolean) => {
    if (!pendingDelete) return;
    await deleteEvent(pendingDelete.id, deleteSeries);
    setPendingDelete(null);
    setSelectedEvent(null);
    loadEvents();
  };

  const handleAutoSchedule = async () => {
    if (!workspaceId) return;
    setIsOptimizing(true);
    try {
      const trimmedInstruction = instruction.trim();
      const result = await autoScheduleTasks(workspaceId, trimmedInstruction
        ? { instruction: trimmedInstruction }
        : {
          dayStartHour,
          dayEndHour,
          weekdaysOnly,
          targetEndDate: targetEndDate ? new Date(targetEndDate).toISOString() : undefined,
        });
      setConstraintsModalOpen(false);
      setInstruction('');
      if (result.scheduledCount > 0) {
        const skipped = result.unscheduledCount > 0 ? ` ${result.unscheduledCount} still needs time.` : '';
        setBanner(`Scheduled ${result.scheduledCount} session${result.scheduledCount === 1 ? '' : 's'}.${skipped}`);
        loadEvents();
      } else if (result.unscheduledCount > 0) {
        setBanner('There is not enough available time for the remaining work.');
      } else {
        setBanner('No open work needs scheduling.');
      }
    } catch (e) {
      console.error('Auto-schedule failed', e);
      setBanner('Scheduling failed. Please try again.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const headerLabel = viewMode === 'month'
    ? currentDate.toLocaleDateString([], { month: 'long', year: 'numeric' })
    : viewMode === 'week'
      ? weekRangeLabel(currentDate)
      : currentDate.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });

  return (
    <div className="flex h-full flex-col gap-6 text-ora-ink">
      <header className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-ora-secondary">Calendar</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Time execution</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ora-secondary">Fixed commitments, flexible Ora sessions, deadlines, and unscheduled work in one view.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => setCurrentDate(new Date())} className="rounded-lg px-3 py-2 text-sm font-medium text-ora-secondary hover:bg-ora-surface">Today</button>
            <div className="flex items-center rounded-lg border border-ora-border bg-ora-surface p-1 shadow-sm">
              <button onClick={() => handleNavigate(-1)} className="rounded-md p-2 hover:bg-ora-subtle" aria-label="Previous"><ChevronLeft size={16} /></button>
              <span className="min-w-36 px-2 text-center text-sm font-semibold">{headerLabel}</span>
              <button onClick={() => handleNavigate(1)} className="rounded-md p-2 hover:bg-ora-subtle" aria-label="Next"><ChevronRight size={16} /></button>
            </div>
            <div className="flex rounded-lg border border-ora-border bg-ora-surface p-1 shadow-sm">
              {VIEW_OPTIONS.map(({ id, icon: ViewIcon, label }) => {
                return (
                  <button
                    key={id}
                    onClick={() => setViewMode(id)}
                    className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium ${viewMode === id ? 'bg-ora-accent-soft text-ora-accent' : 'text-ora-secondary hover:bg-ora-subtle'}`}>
                    <ViewIcon size={14} /> {label}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setConstraintsModalOpen(true)}
              disabled={isOptimizing}
              className="inline-flex items-center gap-2 rounded-lg bg-ora-accent px-4 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover disabled:opacity-70">
              <Zap size={15} /> {isOptimizing ? 'Scheduling...' : 'Plan my week'}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-sm text-ora-secondary">
          <span><strong className="text-ora-ink">{formatDuration(workMinutes)}</strong> scheduled work</span>
          <span><strong className="text-ora-ink">{formatDuration(Math.max(0, availableEstimate))}</strong> estimated free focus</span>
          <span><strong className={overCapacity ? 'text-ora-warning' : 'text-ora-success'}>{overCapacity ? formatDuration(unscheduledMinutes - availableEstimate) : 'Clear'}</strong> capacity risk</span>
          {loading && <span>Loading...</span>}
        </div>
        {banner && <div className="rounded-xl bg-ora-ink px-4 py-3 text-center text-sm text-white">{banner}</div>}
        {overCapacity && (
          <div className="flex items-start gap-3 rounded-lg border border-ora-warning/25 bg-ora-warning-soft px-4 py-3 text-sm text-ora-secondary">
            <AlertTriangle size={17} className="mt-0.5 text-ora-warning" />
            <p>This week is over capacity by about {formatDuration(unscheduledMinutes - availableEstimate)}. Ora can rebalance without moving fixed commitments.</p>
          </div>
        )}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <main className="min-h-0 overflow-hidden rounded-lg border border-ora-border bg-ora-surface shadow-sm">
          {viewMode === 'month' ? (
            <MonthView
              currentDate={currentDate}
              events={events}
              items={items}
              onInspect={setSelectedEvent}
            />
          ) : (
            <>
              <WeekGrid
                days={viewMode === 'day' ? [currentDate] : weekDays}
                events={events}
                items={items}
                onInspect={setSelectedEvent}
                onCreate={handleOpenCreateEvent}
              />
              <AgendaView
                days={viewMode === 'day' ? [currentDate] : weekDays}
                events={events}
                items={items}
                onInspect={setSelectedEvent}
              />
            </>
          )}
        </main>

        <aside className={`${railOpen ? 'block' : 'hidden lg:block'} min-h-0 rounded-lg border border-ora-border bg-ora-surface-subtle`}>
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold">Unscheduled</h2>
              <p className="text-xs text-ora-secondary">{formatDuration(unscheduledMinutes)} still needs time</p>
            </div>
            <button onClick={() => setRailOpen(value => !value)} className="rounded-lg p-2 text-ora-secondary hover:bg-ora-subtle lg:hidden">
              <X size={16} />
            </button>
          </div>
          <div className="max-h-[calc(100vh-260px)] space-y-2 overflow-y-auto px-3 pb-4">
            {unscheduledTasks.slice(0, 8).map(({ task, project }) => (
              <div key={task.id} className="rounded-xl px-3 py-3 hover:bg-ora-subtle">
                <p className="text-sm font-semibold">{task.title}</p>
                <p className="mt-1 text-xs text-ora-secondary">{project.name} · {formatDuration(Math.round((task.estimatedHours || 1) * 60))}</p>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => onStartFocus(task)} className="rounded-md px-2 py-1 text-xs font-medium text-ora-secondary hover:bg-ora-surface">Start</button>
                  <button onClick={() => handleAssignTaskToSlot(task, currentDate, dayStartHour)} className="rounded-md bg-ora-accent-soft px-2 py-1 text-xs font-medium text-ora-accent">Schedule</button>
                </div>
              </div>
            ))}
            {unscheduledTasks.length === 0 && <p className="px-3 py-8 text-center text-sm text-ora-secondary">Everything currently actionable has time.</p>}
          </div>
          {unscheduledTasks.length > 0 && (
            <div className="border-t border-ora-border px-5 py-4">
              <button onClick={() => setConstraintsModalOpen(true)} className="flex w-full items-center justify-center gap-2 rounded-lg bg-ora-accent px-3 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover">
                Ask Ora to schedule <ArrowRight size={15} />
              </button>
            </div>
          )}
        </aside>
      </div>

      <CreateEventModal
        isOpen={createModalStart !== null}
        onClose={() => setCreateModalStart(null)}
        onSubmit={handleSubmitCreateEvent}
        defaultStart={createModalStart || new Date()}
      />

      <ConfirmDeleteModal
        isOpen={pendingDelete !== null}
        title="Delete event"
        message={`Delete "${pendingDelete?.title}"?`}
        isSeries={!!pendingDelete?.recurrenceRule || pendingDelete?.isRecurringOccurrence}
        onConfirm={handleConfirmDeleteEvent}
        onClose={() => setPendingDelete(null)}
      />

      {selectedEvent && (
        <SessionInspector
          event={selectedEvent}
          project={projectForEvent(selectedEvent, items)}
          task={selectedEvent.taskId ? items.find(item => item.task.id === selectedEvent.taskId)?.task : undefined}
          onClose={() => setSelectedEvent(null)}
          onDelete={() => setPendingDelete(selectedEvent)}
          onStartFocus={onStartFocus}
        />
      )}

      {constraintsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ora-ink/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-ora-ink">Plan time with Ora</h3>
              <button onClick={() => setConstraintsModalOpen(false)} className="rounded-lg p-2 text-ora-secondary hover:bg-ora-subtle"><X size={20} /></button>
            </div>
            <p className="mt-2 text-sm leading-6 text-ora-secondary">Place {unscheduledTasks.length} open item{unscheduledTasks.length === 1 ? '' : 's'} into real free slots while respecting fixed commitments.</p>
            <label className="mt-5 block text-sm font-medium text-ora-ink">Constraints</label>
            <textarea
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              placeholder="e.g. no mornings, keep Friday exam fixed, finish by Sunday"
              className="mt-2 w-full resize-none rounded-xl border border-ora-border px-3 py-3 text-sm outline-none focus:border-ora-accent"
              rows={3}
            />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="text-sm text-ora-secondary">
                Start hour
                <input type="number" min={0} max={23} value={dayStartHour} onChange={e => setDayStartHour(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-ora-border px-3 py-2 text-sm outline-none focus:border-ora-accent" />
              </label>
              <label className="text-sm text-ora-secondary">
                End hour
                <input type="number" min={0} max={23} value={dayEndHour} onChange={e => setDayEndHour(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-ora-border px-3 py-2 text-sm outline-none focus:border-ora-accent" />
              </label>
              <label className="text-sm text-ora-secondary">
                Target end
                <input type="date" value={targetEndDate} onChange={e => setTargetEndDate(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-ora-border px-3 py-2 text-sm outline-none focus:border-ora-accent" />
              </label>
              <label className="flex items-end gap-2 pb-2 text-sm text-ora-secondary">
                <input type="checkbox" checked={weekdaysOnly} onChange={e => setWeekdaysOnly(e.target.checked)} className="rounded border-ora-border" />
                Weekdays only
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setConstraintsModalOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-ora-secondary hover:bg-ora-subtle">Cancel</button>
              <button onClick={handleAutoSchedule} disabled={isOptimizing} className="rounded-lg bg-ora-accent px-4 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover disabled:opacity-60">
                {isOptimizing ? 'Scheduling...' : 'Schedule'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const WeekGrid: React.FC<{
  days: Date[];
  events: CalendarEvent[];
  items: Array<{ task: Task; project: Project; company: Company }>;
  onInspect: (event: CalendarEvent) => void;
  onCreate: (date: Date, hour?: number) => void;
}> = ({ days, events, items, onInspect, onCreate }) => {
  const today = new Date();
  const currentHour = today.getHours() + today.getMinutes() / 60;
  return (
    <div className="hidden h-full min-h-[560px] overflow-auto lg:block">
      <div className="grid min-w-[760px]" style={{ gridTemplateColumns: `72px repeat(${days.length}, minmax(140px, 1fr))` }}>
        <div className="sticky top-0 z-20 bg-ora-surface" />
        {days.map(day => (
          <div key={day.toISOString()} className={`sticky top-0 z-20 border-b border-l border-ora-border px-3 py-3 ${sameDay(day, today) ? 'bg-ora-accent-soft text-ora-accent' : 'bg-ora-surface text-ora-secondary'}`}>
            <p className="text-xs">{DAY_LABELS[day.getDay()]}</p>
            <p className="text-lg font-semibold">{day.getDate()}</p>
          </div>
        ))}
        {HOURS.map(hour => (
          <React.Fragment key={hour}>
            <div className="border-t border-ora-border px-2 py-2 text-right text-xs text-ora-tertiary">
              {hour > 12 ? `${hour - 12} PM` : hour === 12 ? '12 PM' : `${hour} AM`}
            </div>
            {days.map(day => {
              const slotEvents = events.filter(event => sameDay(new Date(event.start), day) && new Date(event.start).getHours() === hour);
              const isToday = sameDay(day, today);
              const showNow = isToday && currentHour >= hour && currentHour < hour + 1;
              return (
                <div key={`${day.toISOString()}-${hour}`} onClick={() => onCreate(day, hour)} className={`relative min-h-[92px] cursor-pointer border-l border-t border-ora-border px-2 py-2 text-left hover:bg-ora-subtle/70 ${isToday ? 'bg-ora-accent-soft/35' : 'bg-ora-surface/55'}`}>
                  {showNow && <span className="absolute left-0 right-0 top-1/2 h-px bg-ora-danger" />}
                  <div className="space-y-1">
                    {slotEvents.map(event => (
                      <EventBlock
                        key={event.id}
                        event={event}
                        projectName={projectForEvent(event, items)?.name}
                        onInspect={onInspect}
                      />
                    ))}
                  </div>
                  {slotEvents.length === 0 && <span className="opacity-0 transition-opacity hover:opacity-100 text-xs text-ora-tertiary"><PlusCircle size={13} className="inline" /> Add</span>}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

const AgendaView: React.FC<{
  days: Date[];
  events: CalendarEvent[];
  items: Array<{ task: Task; project: Project; company: Company }>;
  onInspect: (event: CalendarEvent) => void;
}> = ({ days, events, items, onInspect }) => (
  <div className="space-y-4 p-4 lg:hidden">
    {days.map(day => {
      const dayEvents = events
        .filter(event => sameDay(new Date(event.start), day))
        .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
      return (
        <section key={day.toISOString()} className="space-y-2">
          <h2 className="text-sm font-semibold text-ora-ink">{sameDay(day, new Date()) ? 'Today' : day.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}</h2>
          {dayEvents.map(event => (
            <EventBlock key={event.id} event={event} projectName={projectForEvent(event, items)?.name} onInspect={onInspect} />
          ))}
          {dayEvents.length === 0 && <p className="rounded-lg bg-ora-subtle px-3 py-3 text-sm text-ora-secondary">No committed time.</p>}
        </section>
      );
    })}
  </div>
);

const MonthView: React.FC<{
  currentDate: Date;
  events: CalendarEvent[];
  items: Array<{ task: Task; project: Project; company: Company }>;
  onInspect: (event: CalendarEvent) => void;
}> = ({ currentDate, events, items, onInspect }) => (
  <div className="flex h-full min-h-[560px] flex-col">
    <div className="grid grid-cols-7 border-b border-ora-border bg-ora-surface">
      {DAY_LABELS.map(day => <div key={day} className="px-3 py-3 text-center text-xs font-medium text-ora-secondary">{day}</div>)}
    </div>
    <div className="grid flex-1 grid-cols-7 auto-rows-fr">
      {monthDays(currentDate).map((day, index) => {
        if (!day) return <div key={index} className="bg-ora-subtle/70" />;
        const dayEvents = events.filter(event => sameDay(new Date(event.start), day));
        return (
          <div key={day.toISOString()} className={`min-h-[104px] border-b border-r border-ora-border p-2 ${sameDay(day, new Date()) ? 'bg-ora-accent-soft/70' : 'bg-ora-surface/60'}`}>
            <p className={`mb-2 text-sm font-semibold ${sameDay(day, new Date()) ? 'text-ora-accent' : 'text-ora-secondary'}`}>{day.getDate()}</p>
            <div className="space-y-1">
              {dayEvents.slice(0, 3).map(event => (
                <EventBlock key={event.id} event={event} projectName={projectForEvent(event, items)?.name} compact onInspect={onInspect} />
              ))}
              {dayEvents.length > 3 && <p className="pl-1 text-xs text-ora-tertiary">+ {dayEvents.length - 3} more</p>}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

const SessionInspector: React.FC<{
  event: CalendarEvent;
  project?: Project | null;
  task?: Task;
  onClose: () => void;
  onDelete: () => void;
  onStartFocus: (task: Task) => void;
}> = ({ event, project, task, onClose, onDelete, onStartFocus }) => {
  const start = new Date(event.start);
  const end = new Date(event.end);
  const kind = eventKind(event);
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ora-ink/30" onClick={onClose}>
      <aside className="h-full w-full max-w-sm bg-white p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm text-ora-secondary">{kind === 'work' ? 'Ora session' : kind === 'deadline' ? 'Deadline' : 'Fixed commitment'}</p>
          <button onClick={onClose} className="rounded-lg p-2 text-ora-secondary hover:bg-ora-subtle"><X size={18} /></button>
        </div>
        <h2 className="mt-4 text-2xl font-semibold tracking-tight text-ora-ink">{eventTitle(event)}</h2>
        <p className="mt-2 text-sm text-ora-secondary">{project?.name || (kind === 'fixed' ? 'Fixed time' : 'Calendar')}</p>
        <div className="mt-6 space-y-3 text-sm text-ora-secondary">
          <p className="flex items-center gap-2"><Clock size={15} /> {start.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })} · {formatTime(start)}-{formatTime(end)}</p>
          {event.locked && <p className="flex items-center gap-2"><Lock size={15} /> Locked. Ora should not move this automatically.</p>}
          {event.sessionStatus && <p className="flex items-center gap-2"><Target size={15} /> {event.sessionStatus.replace(/_/g, ' ').toLowerCase()}</p>}
          {event.sessionStatus === 'MISSED' && <p className="rounded-xl bg-ora-warning-soft px-3 py-3 text-ora-secondary">This session was missed. The task itself remains truthful until completed elsewhere.</p>}
          {event.sessionStatus === 'COMPLETED' && <p className="rounded-xl bg-ora-success-soft px-3 py-3 text-ora-secondary">This session is complete. Multi-session tasks may still need more work.</p>}
        </div>
        <div className="mt-8 space-y-2">
          {task && <button onClick={() => onStartFocus(task)} className="flex w-full items-center justify-center gap-2 rounded-lg bg-ora-accent px-4 py-2 text-sm font-medium text-white hover:bg-ora-accent-hover">Start <ArrowRight size={15} /></button>}
          <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-ora-subtle px-4 py-2 text-sm font-medium text-ora-ink"><MoveRight size={15} /> Move</button>
          <button onClick={onDelete} className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-ora-danger hover:bg-red-50"><MinusCircle size={15} /> Remove</button>
        </div>
      </aside>
    </div>
  );
};
