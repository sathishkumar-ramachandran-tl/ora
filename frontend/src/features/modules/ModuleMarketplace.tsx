import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Sparkles, Download, CheckCircle2, Loader2, Pencil, Search, LayoutGrid, PackageOpen, Zap } from 'lucide-react';
import { browseModules, getMyModules, publishModule, installModule } from '../../api/modules';
import { ModuleSummary, ModuleCategory, Company } from '../../types';
import { ModuleGenerationDialog } from './ModuleGenerationDialog';
import { ModuleReviewScreen } from './ModuleReviewScreen';
import { InitiativePicker } from './InitiativePicker';
import { CATEGORY_VISUALS, DIFFICULTY_LABEL, DIFFICULTY_DOT } from './moduleVisuals';
import { AgentEconomyDashboard } from '../payments/AgentEconomyDashboard';

interface ModuleMarketplaceProps {
  workspaceId: string;
  companies: Company[];
  onCreateCompany: (company: Company) => Promise<void>;
  onModuleInstalled: (projectId: string) => void;
}

const FILTERS: { value: ModuleCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'exam_prep', label: 'Exam Prep' },
  { value: 'course', label: 'Course' },
  { value: 'project', label: 'Project' },
  { value: 'habit', label: 'Habit' },
  { value: 'general', label: 'General' },
];

const ModuleCardSkeleton: React.FC = () => (
  <div className="rounded-2xl border border-slate-200/70 bg-white p-4 animate-pulse">
    <div className="w-10 h-10 rounded-xl bg-slate-100 mb-3" />
    <div className="h-3.5 w-3/4 rounded bg-slate-100 mb-2" />
    <div className="h-3 w-full rounded bg-slate-100 mb-1.5" />
    <div className="h-3 w-2/3 rounded bg-slate-100 mb-4" />
    <div className="h-7 w-full rounded-lg bg-slate-100" />
  </div>
);

export const ModuleMarketplace: React.FC<ModuleMarketplaceProps> = ({ workspaceId, companies, onCreateCompany, onModuleInstalled }) => {
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [myModules, setMyModules] = useState<ModuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [isGenerateOpen, setGenerateOpen] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [reviewingModuleId, setReviewingModuleId] = useState<string | null>(null);
  const [pickingInitiativeFor, setPickingInitiativeFor] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<ModuleCategory | 'all'>('all');
  const [section, setSection] = useState<'marketplace' | 'economy'>('marketplace');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [published, mine] = await Promise.all([browseModules(), getMyModules()]);
      setModules(published);
      setMyModules(mine);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleInstall = async (moduleTemplateId: string, companyId?: string) => {
    setInstallingId(moduleTemplateId);
    try {
      const result = await installModule(moduleTemplateId, workspaceId, companyId);
      onModuleInstalled(result.projectId);
    } finally {
      setInstallingId(null);
    }
  };

  const handlePublish = async (moduleTemplateId: string) => {
    setPublishingId(moduleTemplateId);
    try {
      await publishModule(moduleTemplateId);
      await load();
    } finally {
      setPublishingId(null);
    }
  };

  const unpublishedDrafts = myModules.filter(m => !m.isPublished);

  const filteredModules = useMemo(() => {
    const q = query.trim().toLowerCase();
    return modules.filter(m => {
      const matchesFilter = activeFilter === 'all' || m.category === activeFilter;
      const matchesQuery = !q || m.title.toLowerCase().includes(q) || m.description.toLowerCase().includes(q);
      return matchesFilter && matchesQuery;
    });
  }, [modules, activeFilter, query]);

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      {/* Section switch */}
      <div className="flex items-center gap-1 bg-slate-100/80 rounded-xl p-1 w-fit">
        <button
          onClick={() => setSection('marketplace')}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            section === 'marketplace' ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <LayoutGrid size={13} /> Marketplace
        </button>
        <button
          onClick={() => setSection('economy')}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            section === 'economy' ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Zap size={13} /> Agent Economy
        </button>
      </div>

      {section === 'economy' && <AgentEconomyDashboard workspaceId={workspaceId} />}

      {section === 'marketplace' && (
      <>
      {/* Command surface */}
      <div className="rounded-2xl border border-slate-200/70 bg-gradient-to-br from-white to-slate-50 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_12px_32px_-16px_rgba(15,23,42,0.12)] p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-brand-600 mb-1.5">
              <LayoutGrid size={13} /> Module Marketplace
            </div>
            <h2 className="text-[26px] font-semibold text-slate-900 tracking-tight leading-tight">
              Plan any goal, phase by phase
            </h2>
            <p className="text-sm text-slate-500 mt-1 max-w-xl">
              Generate a structured milestone plan for any goal and install it as a project in one click.
            </p>
          </div>
          <button
            onClick={() => setGenerateOpen(true)}
            className="group inline-flex items-center gap-2 self-start lg:self-center bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white font-medium px-4 py-2.5 rounded-xl text-sm shadow-[0_1px_2px_rgba(79,70,229,0.3),0_8px_20px_-8px_rgba(79,70,229,0.5)] transition-all hover:shadow-[0_1px_2px_rgba(79,70,229,0.35),0_10px_24px_-6px_rgba(79,70,229,0.55)]"
          >
            <Sparkles size={16} className="transition-transform group-hover:rotate-12" /> Generate Module
          </button>
        </div>

        {/* Search + filters */}
        <div className="flex flex-col sm:flex-row gap-3 mt-5 pt-5 border-t border-slate-200/70">
          <div className="relative flex-1 max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search modules…"
              className="w-full text-sm bg-white border border-slate-200 rounded-xl pl-9 pr-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-400 transition-shadow"
            />
          </div>
          <div className="flex items-center gap-1 bg-slate-100/80 rounded-xl p-1 overflow-x-auto">
            {FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setActiveFilter(f.value)}
                className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeFilter === f.value
                    ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Drafts */}
      {unpublishedDrafts.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight">Your Drafts</h3>
            <span className="text-[11px] text-slate-400">{unpublishedDrafts.length} in progress</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
            {unpublishedDrafts.map(m => (
              <div
                key={m.id}
                className="flex-shrink-0 w-64 rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 p-4 hover:bg-slate-50 hover:border-brand-300 transition-colors"
              >
                <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-600 mb-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Draft
                </div>
                <p className="font-medium text-slate-800 text-sm truncate">{m.title}</p>
                <p className="text-xs text-slate-400 mt-0.5 line-clamp-2 min-h-[2rem]">{m.description || 'No description yet'}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setReviewingModuleId(m.id)}
                    className="flex items-center justify-center gap-1.5 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium py-1.5 rounded-lg transition-colors"
                  >
                    <Pencil size={12} /> Edit
                  </button>
                  <button
                    onClick={() => handlePublish(m.id)}
                    disabled={publishingId === m.id}
                    className="flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                  >
                    {publishingId === m.id ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                    Publish
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Published */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight">Published Modules</h3>
          {!loading && <span className="text-[11px] text-slate-400">{filteredModules.length} of {modules.length}</span>}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <ModuleCardSkeleton key={i} />)}
          </div>
        ) : filteredModules.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-16 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
            <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center mb-3 shadow-sm">
              <PackageOpen size={20} className="text-slate-400" />
            </div>
            <p className="text-sm font-medium text-slate-600">
              {modules.length === 0 ? 'No published modules yet' : 'No modules match your search'}
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-xs">
              {modules.length === 0 ? 'Generate one to get started.' : 'Try a different filter or search term.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredModules.map(m => {
              const visual = CATEGORY_VISUALS[m.category];
              const Icon = visual.icon;
              return (
                <div
                  key={m.id}
                  className={`group relative rounded-2xl border border-slate-200/80 bg-white p-4 transition-all duration-150 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_1px_2px_rgba(15,23,42,0.04),0_16px_32px_-16px_rgba(15,23,42,0.16)] ring-1 ring-transparent ${visual.ring}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl ${visual.iconWrap} flex items-center justify-center flex-shrink-0`}>
                      <Icon size={17} className={visual.iconColor} />
                    </div>
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-500 bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${DIFFICULTY_DOT[m.difficulty]}`} />
                      {DIFFICULTY_LABEL[m.difficulty]}
                    </span>
                  </div>
                  <p className="font-semibold text-slate-800 text-[15px] leading-snug">{m.title}</p>
                  <p className="text-[13px] text-slate-500 mt-1 leading-relaxed line-clamp-2 min-h-[2.25rem]">{m.description}</p>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100">
                    <span className="text-[11px] text-slate-400">{m.installCount} install{m.installCount === 1 ? '' : 's'}</span>
                    <button
                      onClick={() => setPickingInitiativeFor(m.id)}
                      disabled={installingId === m.id}
                      className="flex items-center gap-1.5 bg-brand-50 hover:bg-brand-600 text-brand-700 hover:text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {installingId === m.id ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                      Install
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <ModuleGenerationDialog
        isOpen={isGenerateOpen}
        onClose={() => setGenerateOpen(false)}
        onGenerated={async (moduleTemplateId) => {
          setGenerateOpen(false);
          await load();
          setReviewingModuleId(moduleTemplateId);
        }}
      />

      {reviewingModuleId && (
        <ModuleReviewScreen
          moduleTemplateId={reviewingModuleId}
          workspaceId={workspaceId}
          companies={companies}
          onCreateCompany={onCreateCompany}
          onClose={() => setReviewingModuleId(null)}
          onInstalled={(projectId) => {
            setReviewingModuleId(null);
            onModuleInstalled(projectId);
          }}
          onPublished={async () => {
            setReviewingModuleId(null);
            await load();
          }}
        />
      )}

      {pickingInitiativeFor && (
        <InitiativePicker
          companies={companies}
          onCreateCompany={onCreateCompany}
          onClose={() => setPickingInitiativeFor(null)}
          onConfirm={(companyId) => {
            const moduleTemplateId = pickingInitiativeFor;
            setPickingInitiativeFor(null);
            handleInstall(moduleTemplateId, companyId);
          }}
        />
      )}
      </>
      )}
    </div>
  );
};
