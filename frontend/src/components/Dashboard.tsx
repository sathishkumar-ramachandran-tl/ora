import React, { useEffect, useState } from 'react';
import { Company, Task } from '../types';
import { generateExecutiveSummary } from '../services/geminiService';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { AlertTriangle, CheckCircle, Brain, Briefcase, TrendingUp, Pin, Play } from 'lucide-react';
import { trackEvent } from '../services/analytics';

interface DashboardProps {
  companies: Company[];
  onStartFocus: (task: Task) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ companies, onStartFocus }) => {
  const [aiSummary, setAiSummary] = useState<{ summary: string; risks: string[] } | null>(null);

  useEffect(() => {
    // Generate AI summary on mount (simulated "Morning Brief")
    generateExecutiveSummary(companies).then(setAiSummary);
  }, [companies]);

  const handleStartTask = (task: Task) => {
      trackEvent('TASK_COMPLETED', { taskId: task.id, type: 'focus_session_start' });
      onStartFocus(task);
  };

  // Transform data for chart
  const data = companies.flatMap(c => c.projects.map(p => ({
    name: p.name,
    progress: p.progress,
    type: p.type
  })));

  const totalTasks = companies.reduce((acc, c) => acc + c.projects.reduce((pAcc, p) => pAcc + p.tasks.length, 0), 0);
  const completedTasks = companies.reduce((acc, c) => acc + c.projects.reduce((pAcc, p) => pAcc + p.tasks.filter(t => t.status === 'done').length, 0), 0);
  const completionRate = totalTasks === 0 ? 0 : Math.round((completedTasks / totalTasks) * 100);

  // Get Daily Essentials (Rule of 3)
  const pinnedTasks: { task: Task; project: string; companyColor: string }[] = [];
  companies.forEach(c => {
    c.projects.forEach(p => {
      p.tasks.filter(t => t.isDailyFocus).forEach(t => {
        pinnedTasks.push({ task: t, project: p.name, companyColor: c.color });
      });
    });
  });

  return (
    <div className="h-full overflow-y-auto pr-2 custom-scrollbar space-y-6">
      
      {/* AI Executive Summary Card */}
      {/* <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-xl p-6 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white opacity-5 rounded-full -mr-10 -mt-10 blur-3xl pointer-events-none"></div>
        <h2 className="text-lg font-bold mb-2 flex items-center gap-2">
           <Brain className="w-5 h-5 text-indigo-300" /> Neural Brief
        </h2>
        {aiSummary ? (
          <div className="space-y-4">
             <p className="text-slate-200 leading-relaxed font-light text-lg">"{aiSummary.summary}"</p>
             <div className="flex flex-wrap gap-3 mt-4">
               {aiSummary.risks.map((risk, idx) => (
                 <div key={idx} className="flex items-center gap-2 bg-red-500/20 border border-red-500/30 px-3 py-1.5 rounded-full text-xs font-medium text-red-100">
                   <AlertTriangle className="w-3 h-3" /> {risk}
                 </div>
               ))}
             </div>
          </div>
        ) : (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-slate-700 rounded w-3/4"></div>
            <div className="h-4 bg-slate-700 rounded w-1/2"></div>
          </div>
        )}
      </div> */}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content Column */}
          <div className="lg:col-span-2 space-y-6">
             {/* The Rule of 3 - Daily Essentials */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-200 bg-amber-50 flex justify-between items-center">
                    <div>
                        <h3 className="text-slate-800 font-bold flex items-center gap-2">
                            <Pin className="w-4 h-4 text-amber-600 fill-current" /> Today's Essentials
                        </h3>
                        <p className="text-slate-500 text-xs mt-0.5">The "Rule of 3" — Focus on less, but better.</p>
                    </div>
                    <span className="text-xs font-mono bg-white px-2 py-1 rounded text-slate-500 border border-slate-200">
                        {pinnedTasks.length}/3
                    </span>
                </div>
                <div className="p-2">
                    {pinnedTasks.length === 0 && (
                        <div className="text-center py-6 text-slate-400 text-sm italic">
                            No critical tasks pinned. Go to a project and pin tasks to focus your day.
                        </div>
                    )}
                    {pinnedTasks.map((item) => (
                        <div key={item.task.id} className="group flex items-center justify-between p-3 hover:bg-slate-50 rounded-lg border border-transparent hover:border-slate-100 transition-all">
                            <div className="flex items-start gap-3 overflow-hidden">
                                <div className={`w-1 h-10 rounded-full bg-${item.companyColor}-500 flex-shrink-0`}></div>
                                <div>
                                    <p className={`text-sm font-medium ${item.task.status === 'done' ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                                        {item.task.title}
                                    </p>
                                    <p className="text-xs text-slate-500">{item.project}</p>
                                </div>
                            </div>
                            <button 
                                onClick={() => handleStartTask(item.task)}
                                className="opacity-0 group-hover:opacity-100 p-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-full transition-all"
                                title="Enter Deep Work"
                            >
                                <Play className="w-4 h-4 fill-current" />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            {/* KPI Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between h-28">
                    <div className="p-2 w-fit bg-blue-50 rounded-lg"><Briefcase className="w-5 h-5 text-blue-600" /></div>
                    <div>
                        <p className="text-slate-500 text-[10px] font-medium uppercase">Initiatives</p>
                        <p className="text-xl font-bold text-slate-800">{companies.length}</p>
                    </div>
                </div>
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between h-28">
                    <div className="p-2 w-fit bg-emerald-50 rounded-lg"><CheckCircle className="w-5 h-5 text-emerald-600" /></div>
                    <div>
                        <p className="text-slate-500 text-[10px] font-medium uppercase">Completion</p>
                        <p className="text-xl font-bold text-slate-800">{completionRate}%</p>
                    </div>
                </div>
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between h-28">
                    <div className="p-2 w-fit bg-purple-50 rounded-lg"><TrendingUp className="w-5 h-5 text-purple-600" /></div>
                    <div>
                        <p className="text-slate-500 text-[10px] font-medium uppercase">Projects</p>
                        <p className="text-xl font-bold text-slate-800">{data.length}</p>
                    </div>
                </div>
            </div>
          </div>

          {/* Right Column - Charts */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm h-full flex flex-col">
            <h3 className="text-slate-800 font-bold mb-6">Progress Overview</h3>
            <div className="flex-1 min-h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} layout="vertical" margin={{ left: 0, right: 10 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" width={100} tick={{fontSize: 11}} interval={0} />
                    <Tooltip cursor={{fill: '#f1f5f9'}} />
                    <Bar dataKey="progress" fill="#475569" radius={[0, 4, 4, 0]} barSize={16}>
                    {data.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={
                        entry.type === 'learning' ? '#10b981' : 
                        entry.type === 'client' ? '#8b5cf6' : '#3b82f6'
                        } />
                    ))}
                    </Bar>
                </BarChart>
                </ResponsiveContainer>
            </div>
          </div>
      </div>
    </div>
  );
};
