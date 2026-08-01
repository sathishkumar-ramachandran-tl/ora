import React, { useState, useEffect } from 'react';
import { Company, Project, Task, CalendarEvent } from '../types';
import { Calendar, CheckCircle, Clock, MinusCircle, ChevronLeft, ChevronRight, Zap, PlusCircle, LayoutGrid, List } from 'lucide-react';
import { createEvent, getEvents, deleteEvent, optimizeSchedule } from '../services/db';

interface ScheduleViewProps {
  companies: Company[];
  onStartFocus: (task: Task) => void;
}

const HOURS = Array.from({ length: 13 }, (_, i) => i + 8); // 8 AM to 8 PM
const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const ScheduleView: React.FC<ScheduleViewProps> = ({ companies, onStartFocus }) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<'day' | 'month'>('day');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);

  // Filter state
  const [selectedScope, setSelectedScope] = useState<'all' | 'personal' | 'workspace'>('all');

  // Derive consolidated task list
  const allTasks: { task: Task; project: Project; company: Company }[] = [];
  companies.forEach(c => {
    c.projects.forEach(p => {
      p.tasks?.forEach(t => {
        allTasks.push({ task: t, project: p, company: c });
      });
    });
  });

  const unscheduledTasks = allTasks.filter(t => !events.some(e => e.taskId === t.task.id));

  const filteredEvents = selectedScope === 'all'
    ? events
    : events.filter(e => e.scope === selectedScope);

  const loadEvents = async () => {
    const wsId = companies[0]?.workspaceId;
    if (!wsId) return;
    setLoading(true);

    try {
        let start = new Date(currentDate);
        let end = new Date(currentDate);

        if (viewMode === 'day') {
            start.setHours(0,0,0,0);
            end.setHours(23,59,59,999);
        } else {
            // Month View: Get first day of month to last day of month
            start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
            end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0, 23, 59, 59);
        }

        const data = await getEvents(wsId, start, end);
        setEvents(data);
    } catch (e) {
        console.error("Failed to load events", e);
    } finally {
        setLoading(false);
    }
  };

  const handleCreateEvent = async (hour: number) => {
      const wsId = companies[0]?.workspaceId;
      if (!wsId) return;

      const title = prompt("Event Title:");
      if (!title) return;

      const start = new Date(currentDate);
      start.setHours(hour, 0, 0, 0);
      const end = new Date(start);
      end.setHours(hour + 1);

      await createEvent(wsId, {
          title,
          start: start.toISOString(),
          end: end.toISOString(),
          type: 'block',
          scope: 'personal' // Default to personal
      });
      loadEvents();
  };
  
  const handleAssignTaskToSlot = async (task: Task, hour: number) => {
      const wsId = task.workspaceId;
      const start = new Date(currentDate);
      start.setHours(hour, 0, 0, 0);
      const duration = task.estimatedHours || 1;
      const end = new Date(start);
      end.setHours(hour + Math.floor(duration), (duration % 1) * 60);

      await createEvent(wsId, {
          title: `Focus: ${task.title}`,
          start: start.toISOString(),
          end: end.toISOString(),
          type: 'task_block',
          taskId: task.id,
          color: 'indigo',
          scope: 'personal'
      });
      loadEvents();
  };

  const handleDeleteEvent = async (id: string) => {
      if(!confirm("Delete this event?")) return;
      await deleteEvent(id);
      loadEvents();
  };

  const handleOptimize = async () => {
      const wsId = companies[0]?.workspaceId;
      if (!wsId) return;
      
      setIsOptimizing(true);
      try {
          // Send unscheduled tasks to AI
          const tasksToSchedule = unscheduledTasks.map(t => t.task);
          const suggestedEvents = await optimizeSchedule(tasksToSchedule, currentDate);
          
          // In a real app, we'd show a preview modal. Here we just confirm and save.
          if (suggestedEvents.length > 0) {
              const confirmMsg = `AI suggests ${suggestedEvents.length} blocks. Apply them?`;
              if (window.confirm(confirmMsg)) {
                  // Save all (parallel)
                  await Promise.all(suggestedEvents.map(e => createEvent(wsId, e)));
                  loadEvents();
              }
          } else {
              alert("AI could not find suitable slots or no tasks to schedule.");
          }
      } catch (e) {
          console.error("Optimization failed", e);
          alert("AI Optimization failed.");
      } finally {
          setIsOptimizing(false);
      }
  };

  const nextDay = () => {
      const d = new Date(currentDate);
      if (viewMode === 'day') d.setDate(d.getDate() + 1);
      else d.setMonth(d.getMonth() + 1);
      setCurrentDate(d);
  };

  const prevDay = () => {
      const d = new Date(currentDate);
      if (viewMode === 'day') d.setDate(d.getDate() - 1);
      else d.setMonth(d.getMonth() - 1);
      setCurrentDate(d);
  };

  // Month View Helpers
  const getDaysInMonth = () => {
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const days = [];
      
      // Padding for start of week
      for (let i = 0; i < firstDay.getDay(); i++) {
          days.push(null);
      }
      
      for (let i = 1; i <= lastDay.getDate(); i++) {
          days.push(new Date(year, month, i));
      }
      return days;
  };

  useEffect(() => {
    loadEvents();
  }, [currentDate, viewMode]);

  return (
    <div className="h-full flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <Calendar className="text-indigo-600" /> Resource Allocation
          </h2>
          <p className="text-slate-500 text-sm mt-1">Design your day. Block time for what matters.</p>
        </div>
        
        <div className="flex items-center gap-4">
             {/* View Toggle */}
             <div className="flex bg-slate-100 p-1 rounded-lg">
                <button 
                    onClick={() => setViewMode('day')}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${viewMode === 'day' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    <List size={14} /> Day
                </button>
                <button 
                    onClick={() => setViewMode('month')}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${viewMode === 'month' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    <LayoutGrid size={14} /> Month
                </button>
             </div>

             {/* Date Nav */}
             <div className="flex items-center gap-2 bg-slate-100 rounded-lg p-1">
                 <button onClick={prevDay} className="p-1 hover:bg-white rounded shadow-sm transition-all"><ChevronLeft size={16}/></button>
                 <span className="w-32 text-center font-bold text-slate-700 text-sm">
                     {viewMode === 'day' 
                        ? currentDate.toLocaleDateString(undefined, { weekday: 'short', month: 'long', day: 'numeric' })
                        : currentDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
                     }
                 </span>
                 <button onClick={nextDay} className="p-1 hover:bg-white rounded shadow-sm transition-all"><ChevronRight size={16}/></button>
             </div>

             <button 
                onClick={handleOptimize}
                disabled={isOptimizing}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-lg hover:shadow-lg hover:shadow-indigo-200 transition-all font-medium text-sm disabled:opacity-70"
             >
                <Zap size={16} className={isOptimizing ? "animate-pulse" : ""} />
                {isOptimizing ? "Optimizing..." : "AI Auto-Schedule"}
             </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 overflow-hidden">
        {/* Left: Unscheduled Tasks (Repository) */}
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col h-full overflow-hidden">
           <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-700 flex items-center gap-2">
                  <CheckCircle size={16} className="text-slate-400"/> Task Repository
              </h3>
              <p className="text-xs text-slate-400 mt-1">Drag (or click) to schedule</p>
           </div>
           <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
               {unscheduledTasks.length === 0 && <div className="text-center py-10 text-slate-400 text-sm italic">All tasks scheduled!</div>}
               {unscheduledTasks.map(({ task, company }) => (
                   <div key={task.id} className="p-3 border border-slate-100 rounded-lg hover:border-indigo-200 hover:shadow-sm transition-all bg-white group relative">
                       <div className="flex justify-between items-start">
                           <div>
                                <span className={`text-[10px] uppercase font-bold text-${company.color}-600`}>{company.name}</span>
                                <p className="text-sm font-medium text-slate-800 line-clamp-2">{task.title}</p>
                                <span className="text-xs text-slate-400 flex items-center gap-1 mt-1"><Clock size={10}/> {task.estimatedHours || 1}h</span>
                           </div>
                           <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute right-2 top-2 bg-white shadow-md p-1 rounded border border-slate-100 flex flex-col gap-1 z-10">
                               <button onClick={() => handleAssignTaskToSlot(task, 9)} className="text-xs text-indigo-600 hover:bg-indigo-50 p-1 rounded whitespace-nowrap">Schedule @ 9am</button>
                               <button onClick={() => handleAssignTaskToSlot(task, 13)} className="text-xs text-indigo-600 hover:bg-indigo-50 p-1 rounded whitespace-nowrap">Schedule @ 1pm</button>
                           </div>
                       </div>
                   </div>
               ))}
           </div>
        </div>

        {/* Right: Time Grid (Calendar) */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 flex flex-col h-full overflow-hidden relative">
            {viewMode === 'day' ? (
                <div className="flex-1 overflow-y-auto custom-scrollbar relative">
                    {/* Grid Lines */}
                    {HOURS.map(hour => (
                        <div key={hour} className="flex min-h-[80px] border-b border-slate-100 relative group">
                            {/* Time Label */}
                            <div className="w-16 flex-shrink-0 border-r border-slate-100 p-2 text-xs text-slate-400 font-medium text-right pr-3">
                                {hour > 12 ? `${hour - 12} PM` : hour === 12 ? '12 PM' : `${hour} AM`}
                            </div>
                            
                            {/* Droppable Area (Click to add) */}
                            <div 
                                className="flex-1 hover:bg-slate-50 transition-colors relative cursor-pointer"
                                onClick={() => handleCreateEvent(hour)}
                            >
                                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 flex items-center justify-center pointer-events-none">
                                    <span className="text-slate-300 text-sm flex items-center gap-1"><PlusCircle size={16}/> Add Event</span>
                                </div>
                            </div>
                        </div>
                    ))}
                    
                    {/* Events Overlay */}
                    {/* We map events to absolute positions. For simplicity in this v1, we just render them IN the slot if they match the hour exactly, 
                        OR we can use absolute positioning logic. Let's use absolute positioning based on start time relative to 8 AM. */}
                    {filteredEvents.map(event => {
                        const start = new Date(event.start);
                        const end = new Date(event.end);
                        
                        const startHour = start.getHours() + (start.getMinutes() / 60);
                        const endHour = end.getHours() + (end.getMinutes() / 60);
                        
                        // Filter out events not in view (8am - 8pm)
                        if (startHour < 8 || startHour >= 21) return null;
                        
                        const top = (startHour - 8) * 80; // 80px per hour
                        const height = (endHour - startHour) * 80;
                        
                        return (
                            <div 
                                key={event.id}
                                className={`absolute left-16 right-4 rounded-md border-l-4 shadow-sm p-2 text-xs cursor-pointer hover:brightness-95 transition-all overflow-hidden z-10
                                    ${event.type === 'task_block' ? 'bg-indigo-50 border-indigo-500 text-indigo-900' : 'bg-emerald-50 border-emerald-500 text-emerald-900'}
                                `}
                                style={{ top: `${top}px`, height: `${height}px` }}
                                onClick={(e) => { e.stopPropagation(); }}
                            >
                                <div className="flex justify-between items-start">
                                    <div>
                                        <strong className="block truncate">{event.title}</strong>
                                        <span className="opacity-75">{start.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - {end.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                                    </div>
                                    <button onClick={() => handleDeleteEvent(event.id)} className="text-slate-400 hover:text-red-500"><MinusCircle size={14}/></button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="flex-1 flex flex-col">
                    {/* Days Header */}
                    <div className="grid grid-cols-7 border-b border-slate-200">
                        {DAYS_OF_WEEK.map(d => (
                            <div key={d} className="p-2 text-center text-xs font-bold text-slate-500 uppercase">{d}</div>
                        ))}
                    </div>
                    {/* Month Grid */}
                    <div className="flex-1 grid grid-cols-7 auto-rows-fr">
                        {getDaysInMonth().map((d, i) => {
                            if (!d) return <div key={i} className="bg-slate-50/50 border-b border-r border-slate-100"></div>;
                            
                            const dayEvents = filteredEvents.filter(e => {
                                const eDate = new Date(e.start);
                                return eDate.getDate() === d.getDate() && 
                                       eDate.getMonth() === d.getMonth() && 
                                       eDate.getFullYear() === d.getFullYear();
                            });

                            const isToday = d.toDateString() === new Date().toDateString();

                            return (
                                <div key={i} className={`border-b border-r border-slate-100 p-2 min-h-[100px] flex flex-col gap-1 hover:bg-slate-50 transition-colors ${isToday ? 'bg-indigo-50/30' : ''}`}>
                                    <span className={`text-xs font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full ${isToday ? 'bg-indigo-600 text-white' : 'text-slate-500'}`}>
                                        {d.getDate()}
                                    </span>
                                    {dayEvents.slice(0, 3).map(e => (
                                        <div key={e.id} className={`text-[10px] px-1.5 py-0.5 rounded truncate border-l-2 ${
                                            e.type === 'task_block' 
                                                ? 'bg-indigo-50 border-indigo-500 text-indigo-700' 
                                                : 'bg-emerald-50 border-emerald-500 text-emerald-700'
                                        }`}>
                                            {e.title}
                                        </div>
                                    ))}
                                    {dayEvents.length > 3 && (
                                        <div className="text-[10px] text-slate-400 pl-1">
                                            + {dayEvents.length - 3} more
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
            
            {/* Legend / Scopes */}
            <div className="p-3 border-t border-slate-200 bg-slate-50 flex items-center gap-4 text-xs font-medium text-slate-600">
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-indigo-50 border border-indigo-500 rounded sm"></div> Task</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-emerald-50 border border-emerald-500 rounded sm"></div> Meeting</div>
                <div className="flex-1"></div>
                <span className="text-slate-400">Scopes:</span>
                <button onClick={() => setSelectedScope('all')} className={`${selectedScope === 'all' ? 'text-indigo-600 font-bold' : ''}`}>All</button>
                <button onClick={() => setSelectedScope('personal')} className={`${selectedScope === 'personal' ? 'text-indigo-600 font-bold' : ''}`}>Personal</button>
            </div>
        </div>
      </div>
    </div>
  )
};

