import React, { useState } from 'react';
import {
  Building2, LayoutDashboard, FolderKanban,
  Users, ShieldCheck, Menu, X, ChevronDown
} from 'lucide-react';
import { Organization } from '../types';

interface CompanyLayoutProps {
  children: React.ReactNode;
  organization: Organization;
  activeTab: string;
  onTabChange: (tab: string) => void;
  headerActions?: React.ReactNode;
  userInitials?: string;
}

const TABS = [
  { id: 'overview', icon: LayoutDashboard, label: 'Overview', short: 'Home' },
  { id: 'projects', icon: FolderKanban, label: 'Projects', short: 'Projects' },
  { id: 'team', icon: Users, label: 'Team', short: 'Team' },
  { id: 'admin', icon: ShieldCheck, label: 'Settings', short: 'Settings' },
];

export const CompanyLayout: React.FC<CompanyLayoutProps> = ({
  children, organization, activeTab, onTabChange, headerActions, userInitials = 'A'
}) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const activeTabInfo = TABS.find(t => t.id === activeTab);

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-white flex flex-col
        shadow-2xl border-r border-slate-800 transition-transform duration-300 ease-in-out
        md:relative md:translate-x-0
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Brand */}
        <div className="px-4 pt-5 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <Building2 size={16} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-bold text-white text-sm truncate leading-tight">{organization.name}</p>
              <p className="text-[10px] text-blue-400 font-medium">Company Workspace</p>
            </div>
            <button onClick={() => setIsSidebarOpen(false)} className="md:hidden text-slate-400 hover:text-white p-1">
              <X size={16} />
            </button>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-0.5">
          {TABS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => { onTabChange(id); setIsSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
                ${activeTab === id
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}>
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        {/* User badge */}
        <div className="p-3 border-t border-slate-800">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-slate-800/60">
            <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {userInitials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold text-slate-300 truncate">Admin</p>
              <p className="text-[10px] text-slate-500">{organization.name}</p>
            </div>
            <ShieldCheck size={12} className="text-amber-400 flex-shrink-0" />
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col w-full min-w-0">
        {/* Header */}
        <header className="h-13 bg-white border-b border-slate-200 flex items-center px-4 justify-between flex-shrink-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="text-slate-600 hover:bg-slate-100 p-2 rounded-lg transition-colors flex-shrink-0 md:hidden">
              <Menu size={18} />
            </button>
            <div className="min-w-0">
              <h1 className="font-bold text-slate-800 text-sm md:text-base truncate leading-tight">
                {activeTabInfo?.label ?? 'Company'}
              </h1>
              <span className="text-[10px] text-slate-400 hidden sm:block">{organization.name}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {headerActions}
            <span className="px-2 py-0.5 bg-blue-50 border border-blue-200 rounded text-[10px] font-bold text-blue-600 uppercase tracking-wide hidden sm:block">
              Company
            </span>
          </div>
        </header>

        {/* Page content — flex column so children can use flex-1 */}
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          {children}
        </div>

        {/* Mobile bottom nav */}
        <nav className="md:hidden border-t border-slate-200 bg-white flex-shrink-0">
          <div className="flex items-center justify-around px-2 py-1.5">
            {TABS.map(({ id, icon: Icon, short }) => (
              <button
                key={id}
                onClick={() => onTabChange(id)}
                className={`flex flex-col items-center gap-0.5 flex-1 py-1.5 rounded-lg transition-all
                  ${activeTab === id ? 'text-blue-600' : 'text-slate-400'}`}>
                <Icon size={18} strokeWidth={activeTab === id ? 2.5 : 1.5} />
                <span className="text-[9px] font-medium">{short}</span>
              </button>
            ))}
          </div>
        </nav>
      </main>
    </div>
  );
};
