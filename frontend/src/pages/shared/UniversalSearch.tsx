import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, CalendarDays, FileText, FolderOpen, Search, Sparkles, Target } from 'lucide-react';
import { searchWorkspace, WorkspaceSearchResult } from '../../api/workspace';
import { trackEvent } from '../../services/analytics';

interface UniversalSearchProps {
  workspaceId: string;
  companies: Array<{ id: string; name: string; projects?: Array<{ id: string; name: string; tasks?: Array<{ id: string; title: string; dueDate?: string }> }> }>;
  onOpenProject: (projectId: string) => void;
  onAskOra: (content: string) => void;
}

const iconFor = (type: WorkspaceSearchResult['type']) => {
  if (type === 'project') return FolderOpen;
  if (type === 'task') return Target;
  if (type === 'plan') return Sparkles;
  return FileText;
};

const typeLabel = (type: WorkspaceSearchResult['type']) => {
  if (type === 'concept') return 'Context';
  return type;
};

export const UniversalSearch: React.FC<UniversalSearchProps> = ({ workspaceId, companies, onOpenProject, onAskOra }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<WorkspaceSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const quickResults = useMemo<WorkspaceSearchResult[]>(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const projects = companies.flatMap(company => (company.projects || []).map(project => ({
      type: 'project' as const,
      id: project.id,
      title: project.name,
      subtitle: company.name,
    })));
    const calendarHints = companies.flatMap(company => (company.projects || []).flatMap(project =>
      (project.tasks || [])
        .filter(task => task.dueDate)
        .map(task => ({
          type: 'task' as const,
          id: task.id,
          title: task.title,
          subtitle: `${project.name} · due ${new Date(task.dueDate || '').toLocaleDateString([], { month: 'short', day: 'numeric' })}`,
        }))
    ));
    return [...projects, ...calendarHints].filter(item =>
      `${item.title} ${item.subtitle || ''}`.toLowerCase().includes(q)
    ).slice(0, 8);
  }, [companies, query]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timer = window.setTimeout(() => {
      searchWorkspace(workspaceId, q)
        .then(items => {
          setResults(items);
          trackEvent('UNIVERSAL_SEARCH_USED', { queryLength: q.length, results: items.length });
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query, workspaceId]);

  const merged = useMemo(() => {
    const seen = new Set<string>();
    return [...results, ...quickResults].filter(item => {
      const key = `${item.type}:${item.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [quickResults, results]);

  const openResult = (result: WorkspaceSearchResult) => {
    if (result.type === 'project') {
      onOpenProject(result.id);
      trackEvent('SEARCH_RESULT_OPENED', { type: result.type });
    } else {
      onAskOra(`Open or explain ${result.title}`);
      trackEvent('SEARCH_RESULT_OPENED', { type: result.type, delegatedToOra: true });
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-7">
      <header className="pt-2">
        <p className="text-sm font-medium text-slate-500">Search</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Find anything by outcome, work, time, or context.</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Search stays structured first. Ora can open projects directly, and can interpret task, plan, deadline, and context references when needed.
        </p>
      </header>

      <section className="rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center gap-3">
          <Search size={19} className="ml-1 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && query.trim()) onAskOra(query.trim());
            }}
            placeholder="Search projects, work, plans, deadlines, evidence..."
            className="min-w-0 flex-1 border-0 px-1 py-3 text-base outline-none"
          />
          <button
            onClick={() => query.trim() && onAskOra(query.trim())}
            className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800">
            Ask Ora
          </button>
        </div>
      </section>

      {query.trim().length < 2 ? (
        <section className="grid gap-3 sm:grid-cols-2">
          {[
            { icon: FolderOpen, title: 'Projects', body: 'Open persistent outcomes like Acme MVP, UPSC 2027, or Computer Networks.' },
            { icon: Target, title: 'Work', body: 'Find actionable items, waiting items, deadlines, and blocked work.' },
            { icon: CalendarDays, title: 'Time', body: 'Look for schedule commitments and upcoming deadlines.' },
            { icon: FileText, title: 'Context', body: 'Surface notes, research, evidence, decisions, and generated outputs.' },
          ].map(item => (
            <div key={item.title} className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
              <item.icon size={18} className="text-indigo-600" />
              <h2 className="mt-3 text-sm font-semibold text-slate-950">{item.title}</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">{item.body}</p>
            </div>
          ))}
        </section>
      ) : (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-950">Results</h2>
            <span className="text-xs text-slate-400">{loading ? 'Searching...' : `${merged.length} found`}</span>
          </div>
          {merged.map(result => {
            const Icon = iconFor(result.type);
            return (
              <button
                key={`${result.type}-${result.id}`}
                onClick={() => openResult(result)}
                className="flex w-full items-center gap-3 rounded-lg bg-white px-4 py-3 text-left ring-1 ring-slate-200 hover:ring-slate-300">
                <Icon size={17} className="text-indigo-600" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-slate-900">{result.title}</span>
                  <span className="block truncate text-xs capitalize text-slate-500">{typeLabel(result.type)}{result.subtitle ? ` · ${result.subtitle}` : ''}</span>
                </span>
                <ArrowRight size={15} className="text-slate-300" />
              </button>
            );
          })}
          {!loading && merged.length === 0 && (
            <div className="rounded-lg bg-white p-8 text-center ring-1 ring-slate-200">
              <p className="text-sm font-semibold text-slate-950">No structured match yet.</p>
              <p className="mt-1 text-sm text-slate-500">Ask Ora to interpret the request or create the missing context.</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
};
