import React, { useState, useEffect, useRef } from 'react';
import { Project, Task, Status, Priority, Note, TaskResource } from '../types';
import { Plus, Loader2, Sparkles, Pin, Play, Bot, X, Check, Book, Trash2, Save, FileText, ChevronRight, Paperclip, Link, MessageSquare, CalendarClock, Layout, Kanban, Tag, Bug, Star, BookOpen, Calendar } from 'lucide-react';
import { generateProjectTasks } from '../services/geminiService';
import { addTasks, updateTaskStatus, toggleTaskDailyFocus, createNote, getNotes, deleteNote, updateTaskResources, saveWhiteboard, getProjectMembers, assignUserToProject, createEvent } from '../services/db';
import { CreateTaskModal } from './CreationModals';
import { trackEvent } from '../services/analytics';
import { SpatialCanvas } from './SpatialCanvas';
import { PlanningChatDialog } from './PlanningChatDialog';

interface AgileBoardProps {
  project: Project;
  companyMission: string;
  onUpdateProject: (updatedProject: Project) => void;
  onStartFocus: (task: Task) => void;
}

const COLUMNS: { id: Status; label: string }[] = [
  { id: 'todo', label: 'To Do' },
  { id: 'in-progress', label: 'In Progress' },
  { id: 'review', label: 'Review' },
  { id: 'done', label: 'Done' },
];

export const AgileBoard: React.FC<AgileBoardProps> = ({ project, companyMission, onUpdateProject, onStartFocus }) => {
  const [viewMode, setViewMode] = useState<'kanban' | 'canvas'>('kanban');

  const [isGenerating, setIsGenerating] = useState(false);
  const [agentStatus, setAgentStatus] = useState("");
  const [isTaskModalOpen, setTaskModalOpen] = useState(false);
  
  // Project Notebook State
  const [showNotebook, setShowNotebook] = useState(false);
  const [notes, setNotes] = useState<Note[]>([]);
  const [newNote, setNewNote] = useState("");
  const [loadingNotes, setLoadingNotes] = useState(false);

  // Multi-discussion planning dialog (replaces single-shot guidance modal)
  const [planningDialogOpen, setPlanningDialogOpen] = useState(false);

  // Legacy single-shot Human-in-the-Loop States (kept for fallback)
  const [guidanceModalOpen, setGuidanceModalOpen] = useState(false);
  const [userGuidance, setUserGuidance] = useState("");
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [proposedTasks, setProposedTasks] = useState<Task[]>([]);

  // Task Detail Modal State
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  useEffect(() => {
    if (showNotebook) loadNotes();
  }, [showNotebook, project.id]);

  const loadNotes = async () => {
      setLoadingNotes(true);
      try {
          const fetchedNotes = await getNotes(project.workspaceId, project.id);
          setNotes(fetchedNotes);
      } catch (e) {
          console.error("Failed to load notes", e);
      } finally {
          setLoadingNotes(false);
      }
  };

  const handleSaveCanvas = async (items: any[]) => {
    onUpdateProject({ ...project, whiteboard: items });
    await saveWhiteboard('project', project.id, items);
  };

  const handleAddNote = async () => {
      if (!newNote.trim()) return;
      
      const note: Note = {
          id: crypto.randomUUID(),
          workspaceId: project.workspaceId,
          contextId: project.id,
          content: newNote,
          createdAt: new Date()
      };

      try {
          await createNote(note);
          setNotes([note, ...notes]);
          setNewNote("");
          trackEvent('DOCUMENT_UPLOADED', { type: 'note', projectId: project.id });
      } catch (e) {
          console.error("Failed to save note", e);
      }
  };

  const handleDeleteNote = async (noteId: string) => {
      try {
          await deleteNote(noteId);
          setNotes(notes.filter(n => n.id !== noteId));
      } catch (e) {
          console.error("Failed to delete note", e);
      }
  };

  const startAIGeneration = () => {
    // Open multi-discussion planning dialog (new agentic flow)
    setPlanningDialogOpen(true);
  };

  const runAgents = async () => {
    // setGuidanceModalOpen(false); // Don't close immediately
    setIsGenerating(true);
    setAgentStatus("Initializing Neural Link...");

    try {
      trackEvent('AI_AGENT_START', { agent: 'ProjectPlanner', projectId: project.id });
      const tasks = await generateProjectTasks(
        project, 
        companyMission, 
        userGuidance, 
        'general', 
        'en',
        (status) => setAgentStatus(status)
      );
      
      if (Array.isArray(tasks) && tasks.length > 0) {
        // Augment AI tasks with system fields
        const enrichedTasks: Task[] = tasks.map((t: any) => ({
            ...t,
            id: crypto.randomUUID(),
            workspaceId: project.workspaceId,
            projectId: project.id,
            status: 'todo', // Default to todo
            resources: []
        }));
        
        setProposedTasks(enrichedTasks);
        setGuidanceModalOpen(false); // Close guidance only on success
        setReviewModalOpen(true);
      } else {
        throw new Error("No tasks generated");
      }
    } catch (e) {
      console.error(e);
      alert("AI Agents failed to generate plan. Please try again.");
    } finally {
      setIsGenerating(false);
      trackEvent('AI_AGENT_COMPLETE', { agent: 'ProjectPlanner' });
    }
  };

  const confirmPlan = async () => {
    await addTasks(proposedTasks, project.id);
    const updatedProject = {
      ...project,
      tasks: [...project.tasks, ...proposedTasks]
    };
    onUpdateProject(updatedProject);
    setReviewModalOpen(false);
    setUserGuidance("");
  };

  const handleCreateTask = async (task: Task) => {
    const taskWithProject = { ...task, projectId: project.id, workspaceId: project.workspaceId, resources: [] };
    await addTasks([taskWithProject], project.id);
    onUpdateProject({
      ...project,
      tasks: [...project.tasks, taskWithProject]
    });
    trackEvent('TASK_CREATED', { projectId: project.id });
  };

  const moveTask = async (e: React.MouseEvent, taskId: string, newStatus: Status) => {
      e.stopPropagation(); // Prevent opening modal
      const updatedTasks = project.tasks.map(t => 
          t.id === taskId ? { ...t, status: newStatus } : t
      );
      onUpdateProject({ ...project, tasks: updatedTasks });
      await updateTaskStatus(taskId, newStatus);
      if (newStatus === 'done') {
          trackEvent('TASK_COMPLETED', { taskId });
      }
  };

  const togglePin = async (e: React.MouseEvent, taskId: string, currentStatus: boolean) => {
      e.stopPropagation();
      const updatedTasks = project.tasks.map(t => 
          t.id === taskId ? { ...t, isDailyFocus: !currentStatus } : t
      );
      onUpdateProject({ ...project, tasks: updatedTasks });
      await toggleTaskDailyFocus(taskId, !currentStatus);
  };

  const handleTaskUpdate = (updatedTask: Task) => {
      const updatedTasks = project.tasks.map(t => t.id === updatedTask.id ? updatedTask : t);
      onUpdateProject({ ...project, tasks: updatedTasks });
      setSelectedTask(updatedTask); // Update modal state
  };

  return (
    <div className="flex h-full gap-6 relative flex-col">
       {/* Header with View Toggle */}
       <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-4 mb-4 flex-shrink-0">
            <div>
                <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                    {project.name}
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                        project.type === 'build' ? 'bg-blue-50 text-blue-700 border-blue-200' : 
                        project.type === 'learning' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        'bg-violet-50 text-violet-700 border-violet-200'
                    }`}>
                        {project.type.toUpperCase()}
                    </span>
                </h1>
                <p className="text-slate-500 text-sm mt-1">{project.mission}</p>
            </div>
            <div className="flex items-center gap-3">
                 <div className="flex bg-slate-100 p-1 rounded-lg">
                    <button 
                        onClick={() => setViewMode('kanban')}
                        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${viewMode === 'kanban' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                        <Kanban size={14} /> Board
                    </button>
                    <button 
                        onClick={() => setViewMode('canvas')}
                        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${viewMode === 'canvas' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                        <Layout size={14} /> Canvas
                    </button>
                </div>

                <div className="h-6 w-px bg-slate-200"></div>

                <div className="flex gap-2">
                    <button 
                        onClick={() => setShowNotebook(!showNotebook)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors border whitespace-nowrap ${showNotebook ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
                    >
                        <Book size={16} /> Note
                    </button>
                    <button 
                        onClick={startAIGeneration}
                        className="flex items-center gap-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-2 rounded-lg text-sm font-medium transition-colors border border-indigo-100 whitespace-nowrap"
                    >
                        <Sparkles size={16} /> AI Plan
                    </button>
                    <button 
                        onClick={() => setTaskModalOpen(true)}
                        className="flex items-center gap-2 bg-slate-900 text-white hover:bg-slate-800 px-3 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
                    >
                        <Plus size={16} /> Task
                    </button>
                </div>
            </div>
        </div>

      {/* Main Board Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {viewMode === 'canvas' ? (
             <SpatialCanvas 
                initialItems={project.whiteboard || []} 
                onSave={handleSaveCanvas} 
                contextName={project.name}
            />
        ) : (
            <div className="flex-1 overflow-x-auto overflow-y-hidden snap-x snap-mandatory">
                <div className="flex gap-4 h-full px-4 md:px-0 pb-4 md:min-w-[1000px]">
                    {COLUMNS.map(col => {
                        const tasks = project.tasks.filter(t => t.status === col.id);
                        return (
                            <div key={col.id} className="snap-center min-w-[85vw] sm:min-w-[320px] md:flex-1 flex flex-col bg-slate-100/50 rounded-xl border border-slate-200/60 shadow-inner md:shadow-none">
                                <div className="p-3 border-b border-slate-200/60 flex justify-between items-center bg-slate-50/50 rounded-t-xl sticky top-0 z-10 backdrop-blur-sm">
                                    <h3 className="font-semibold text-slate-700 text-sm">{col.label}</h3>
                                    <span className="text-xs text-slate-400 font-mono bg-slate-200/50 px-1.5 py-0.5 rounded">{tasks.length}</span>
                                </div>
                                <div className="flex-1 p-2 overflow-y-auto custom-scrollbar space-y-2">
                                    {tasks.map(task => (
                                        <div
                                            key={task.id}
                                            onClick={() => setSelectedTask(task)}
                                            className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm hover:shadow-md transition-all group cursor-pointer active:scale-[0.98]"
                                        >
                                            <div className="flex justify-between items-start mb-2">
                                                <div className="flex items-center gap-1 flex-wrap">
                                                    <IssueTypeBadge type={task.issueType || 'task'} />
                                                    <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                                                        task.priority === 'critical' ? 'bg-red-100 text-red-700' :
                                                        task.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                                                        'bg-slate-100 text-slate-600'
                                                    }`}>
                                                        {task.priority}
                                                    </span>
                                                </div>
                                                <div className="flex gap-1 md:opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button onClick={(e) => togglePin(e, task.id, !!task.isDailyFocus)} className={`p-1 rounded hover:bg-slate-100 ${task.isDailyFocus ? 'text-amber-500 opacity-100' : 'text-slate-400'}`}>
                                                        <Pin size={14} fill={task.isDailyFocus ? "currentColor" : "none"} />
                                                    </button>
                                                    <button onClick={(e) => { e.stopPropagation(); onStartFocus(task); }} className="p-1 rounded hover:bg-indigo-50 text-indigo-600" title="Start Focus Session">
                                                        <Play size={14} fill="currentColor" />
                                                    </button>
                                                </div>
                                            </div>
                                            <h4 className="text-sm font-medium text-slate-800 leading-snug mb-2">{task.title}</h4>

                                            {/* Labels */}
                                            {task.labels && task.labels.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mb-2">
                                                    {task.labels.slice(0, 3).map(label => (
                                                        <span key={label} className="text-[10px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded-full border border-indigo-100">{label}</span>
                                                    ))}
                                                </div>
                                            )}

                                            <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-50">
                                                <div className="flex items-center gap-2">
                                                    {task.dueDate && (
                                                        <span className={`text-[10px] flex items-center gap-1 ${
                                                            new Date(task.dueDate) < new Date() ? 'text-red-500' : 'text-slate-400'
                                                        }`}>
                                                            <Calendar size={10} />
                                                            {new Date(task.dueDate).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                                        </span>
                                                    )}
                                                    {!task.dueDate && task.estimatedHours && (
                                                        <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                                            <CalendarClock size={10}/> {task.estimatedHours}h
                                                        </span>
                                                    )}
                                                    {task.resources && task.resources.length > 0 && (
                                                        <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                                            <Paperclip size={10} /> {task.resources.length}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex gap-1">
                                                    {col.id !== 'todo' && (
                                                        <button onClick={(e) => moveTask(e, task.id, COLUMNS[COLUMNS.findIndex(c => c.id === col.id) - 1].id)} className="p-1 hover:bg-slate-100 rounded text-slate-400">
                                                            <ChevronRight size={14} className="rotate-180" />
                                                        </button>
                                                    )}
                                                    {col.id !== 'done' && (
                                                        <button onClick={(e) => moveTask(e, task.id, COLUMNS[COLUMNS.findIndex(c => c.id === col.id) + 1].id)} className="p-1 hover:bg-slate-100 rounded text-slate-400">
                                                            <ChevronRight size={14} />
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        )}

      {/* Project Notebook Sidebar */}
      {showNotebook && (
          <div className="w-80 bg-white border-l border-slate-200 flex flex-col shadow-xl animate-in slide-in-from-right-10 duration-300 z-20 absolute right-0 top-0 bottom-0 lg:relative lg:shadow-none">
              <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2"><Book size={16} /> Project Log</h3>
                  <button onClick={() => setShowNotebook(false)} className="lg:hidden text-slate-400"><X size={18}/></button>
              </div>
              
              <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                  {loadingNotes ? (
                      <div className="flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>
                  ) : notes.length === 0 ? (
                      <div className="text-center text-slate-400 text-sm py-8 italic">
                          No logs yet. <br/> Record your progress.
                      </div>
                  ) : (
                      notes.map(note => (
                          <div key={note.id} className="group relative pl-4 border-l-2 border-indigo-100 hover:border-indigo-400 transition-colors">
                              <p className="text-xs text-slate-400 mb-1 flex items-center gap-1 font-mono">
                                  {new Date(note.createdAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </p>
                              <p className="text-sm text-slate-700 whitespace-pre-wrap">{note.content}</p>
                              <button 
                                onClick={() => handleDeleteNote(note.id)}
                                className="absolute top-0 right-0 p-1 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                  <Trash2 size={12} />
                              </button>
                          </div>
                      ))
                  )}
              </div>

              <div className="p-4 border-t border-slate-200 bg-slate-50">
                  <textarea 
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Log a query, decision, or thought..."
                    className="w-full text-sm p-3 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none bg-white"
                    rows={3}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleAddNote();
                        }
                    }}
                  />
                  <div className="flex justify-between items-center mt-2">
                      <span className="text-[10px] text-slate-400">Cmd+Enter to save</span>
                      <button 
                        onClick={handleAddNote}
                        disabled={!newNote.trim()}
                        className="bg-indigo-600 text-white p-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                          <Save size={16} />
                      </button>
                  </div>
              </div>
          </div>
      )}
      </div>

      {/* Task Detail Modal */}
      {selectedTask && (
          <TaskDetailModal
            task={selectedTask}
            project={project}
            onClose={() => setSelectedTask(null)}
            onUpdate={handleTaskUpdate}
          />
      )}

      {/* Multi-Discussion AI Planning Dialog */}
      <PlanningChatDialog
        isOpen={planningDialogOpen}
        onClose={() => setPlanningDialogOpen(false)}
        projectId={project.id}
        projectName={project.name}
        projectType={project.type}
        workspaceId={project.workspaceId}
        companyMission={companyMission}
        onPlanExecuted={() => {
          // Reload project data after agent creates tasks
          setPlanningDialogOpen(false);
          // Parent triggers a reload via onUpdateProject with a flag
          onUpdateProject({ ...project, _needsRefresh: true } as any);
        }}
      />

      {/* AI Guidance and Review Modals */}
      {guidanceModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg p-6 animate-in fade-in zoom-in-95 overflow-hidden relative">
             {isGenerating ? (
                 <div className="flex flex-col items-center justify-center py-8 text-center animate-in fade-in duration-300">
                     <div className="relative">
                        <div className="absolute inset-0 bg-indigo-500 rounded-full blur-xl opacity-20 animate-pulse"></div>
                        <Loader2 className="w-12 h-12 animate-spin text-indigo-600 mb-4 relative z-10" />
                     </div>
                     <h3 className="text-lg font-bold text-slate-800 bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-violet-600">
                         {agentStatus}
                     </h3>
                     <p className="text-slate-500 text-sm mt-2 max-w-xs mx-auto">
                        Decomposing project requirements into actionable atomic tasks...
                     </p>
                 </div>
             ) : (
                <>
                    <h3 className="text-lg font-bold text-slate-800 mb-2 flex items-center gap-2"><Bot className="text-indigo-500"/> Brief the Chief of Staff</h3>
                    <p className="text-slate-500 text-sm mb-4">Provide context for the current phase. The AI will decompose this into milestones.</p>
                    <textarea 
                        className="w-full p-4 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none min-h-[120px]"
                        placeholder="e.g. We need to build the authentication flow using Firebase..."
                        value={userGuidance}
                        onChange={(e) => setUserGuidance(e.target.value)}
                        autoFocus
                    />
                    <div className="flex justify-end gap-3 mt-4">
                    <button onClick={() => setGuidanceModalOpen(false)} className="text-slate-500 hover:text-slate-800 font-medium text-sm">Cancel</button>
                    <button onClick={runAgents} className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 flex items-center gap-2">
                        Generate Plan <Sparkles size={16} />
                    </button>
                    </div>
                </>
             )}
          </div>
        </div>
      )}

      {/* Full screen loader removed to keep context within modal */}
      
      {reviewModalOpen && (
         <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col animate-in fade-in zoom-in-95">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <div>
                        <h3 className="text-lg font-bold text-slate-800">Proposed Strategy</h3>
                        <p className="text-slate-500 text-sm">Review tasks before adding to board.</p>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                        <span className="font-bold text-indigo-600">{proposedTasks.length}</span> Tasks Generated
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-6 bg-slate-50 space-y-3">
                    {proposedTasks.map((task, idx) => (
                        <div key={idx} className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-start gap-4">
                            <div className="mt-1"><CheckCircleIcon priority={task.priority} /></div>
                            <div>
                                <h4 className="font-bold text-slate-800">{task.title}</h4>
                                <p className="text-sm text-slate-600 mt-1">{task.description}</p>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="p-6 border-t border-slate-100 flex justify-end gap-3">
                    <button onClick={() => setReviewModalOpen(false)} className="px-4 py-2 text-slate-500 hover:text-slate-800">Discard</button>
                    <button onClick={confirmPlan} className="bg-slate-900 text-white px-6 py-2 rounded-lg font-medium hover:bg-slate-800 flex items-center gap-2">
                        <Check size={18} /> Approve & Execute
                    </button>
                </div>
            </div>
         </div>
      )}

      <CreateTaskModal isOpen={isTaskModalOpen} onClose={() => setTaskModalOpen(false)} onSubmit={handleCreateTask} />
    </div>
  );
};

// --- Sub-Components ---

const TaskDetailModal = ({ task, project, onClose, onUpdate }: { task: Task, project: Project, onClose: () => void, onUpdate: (t: Task) => void }) => {
    const [activeTab, setActiveTab] = useState<'overview' | 'notes' | 'resources'>('overview');
    const [taskNotes, setTaskNotes] = useState<Note[]>([]);
    const [noteInput, setNoteInput] = useState('');
    const [resourceTitle, setResourceTitle] = useState('');
    const [resourceUrl, setResourceUrl] = useState('');
    const [members, setMembers] = useState<any[]>([]);

    useEffect(() => {
        getProjectMembers(project.id).then(setMembers).catch(console.error);
    }, [project.id]);
    
    // Load notes when tab switches
    useEffect(() => {
        if (activeTab === 'notes') {
            getNotes(task.workspaceId || project.workspaceId, task.id).then(setTaskNotes);
        }
    }, [activeTab, task.id, task.workspaceId, project.workspaceId]);

    const saveNote = async () => {
        if(!noteInput.trim()) return;
        const note: Note = {
            id: crypto.randomUUID(),
            workspaceId: task.workspaceId || project.workspaceId,
            contextId: task.id,
            content: noteInput,
            createdAt: new Date(),
            type: 'general',
            color: 'blue'
        };
        await createNote(note);
        setTaskNotes([note, ...taskNotes]);
        setNoteInput('');
    };

    const addResource = async (type: 'link' | 'attachment') => {
        if (!resourceTitle.trim() || !resourceUrl.trim()) return;
        
        const newRes: TaskResource = {
            id: crypto.randomUUID(),
            type,
            title: resourceTitle,
            url: resourceUrl, // For attachments, this would be a bucket path in a real app
            addedAt: new Date()
        };

        const updatedResources = [...(task.resources || []), newRes];
        await updateTaskResources(task.id, updatedResources);
        onUpdate({ ...task, resources: updatedResources });
        setResourceTitle('');
        setResourceUrl('');
    };

    const addToCalendar = async () => {
       const start = new Date();
       start.setDate(start.getDate() + 1); // Tomorrow
       start.setHours(9, 0, 0, 0); 
       
       const end = new Date(start);
       end.setHours(start.getHours() + (task.estimatedHours || 1));

       try {
           await createEvent(task.workspaceId || project.workspaceId, {
               id: crypto.randomUUID(),
               workspaceId: task.workspaceId || project.workspaceId,
               title: task.title,
               start: start.toISOString(),
               end: end.toISOString(),
               type: 'task',
               taskId: task.id,
               color: 'blue'
           });
           alert("Added to schedule (Tomorrow 9 AM). Check Schedule View.");
       } catch (e) {
           alert("Failed to schedule task.");
       }
    };

    const changeAssignee = (userId: string) => {
        // Here we would ideally persist this change to the backend
        onUpdate({ ...task, assignee: userId });
        // Assuming parent updates DB or we need updateTask API
    };

    return (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[70] flex justify-end">
            <div className="w-full md:w-[600px] bg-white h-full shadow-2xl animate-in slide-in-from-right duration-300 flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-slate-200 flex justify-between items-start bg-slate-50">
                    <div className="flex-1 pr-4">
                        <div className="flex items-center gap-2 mb-2">
                             <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                                task.priority === 'critical' ? 'bg-red-100 text-red-700' :
                                task.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                                'bg-slate-200 text-slate-600'
                            }`}>{task.priority}</span>
                             <span className="text-[10px] font-mono text-slate-400">ID: {task.id.substring(0,6)}</span>
                        </div>
                        <h2 className="text-xl font-bold text-slate-900 leading-snug">{task.title}</h2>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={24}/></button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-slate-200 px-6 gap-6">
                    {['overview', 'notes', 'resources'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab as any)}
                            className={`py-3 text-sm font-medium border-b-2 transition-colors capitalize ${activeTab === tab ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 bg-slate-50/30">
                    {activeTab === 'overview' && (
                        <div className="space-y-6">
                             <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                                 <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Description</h3>
                                 <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
                                     {task.description || "No description provided."}
                                 </p>
                             </div>
                             
                             <div className="grid grid-cols-2 gap-3">
                                 <div className="bg-white p-3 rounded-lg border border-slate-200">
                                     <span className="text-xs text-slate-400 block mb-1">Type</span>
                                     <IssueTypeBadge type={task.issueType || 'task'} />
                                 </div>
                                 <div className="bg-white p-3 rounded-lg border border-slate-200">
                                     <span className="text-xs text-slate-400 block mb-1">Status</span>
                                     <span className="capitalize text-slate-700 text-sm">{task.status.replace('-', ' ')}</span>
                                 </div>
                                 <div className="bg-white p-3 rounded-lg border border-slate-200">
                                     <span className="text-xs text-slate-400 block mb-1">Est. Hours</span>
                                     <span className="font-mono text-slate-700 text-sm">{task.estimatedHours || '—'}h</span>
                                 </div>
                                 <div className="bg-white p-3 rounded-lg border border-slate-200">
                                     <span className="text-xs text-slate-400 block mb-1">Due Date</span>
                                     <span className={`text-sm font-medium ${task.dueDate && new Date(task.dueDate) < new Date() ? 'text-red-600' : 'text-slate-700'}`}>
                                         {task.dueDate ? new Date(task.dueDate).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                                     </span>
                                 </div>
                             </div>

                             {task.labels && task.labels.length > 0 && (
                                 <div className="bg-white p-4 rounded-xl border border-slate-200">
                                     <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Labels</h3>
                                     <div className="flex flex-wrap gap-1.5">
                                         {task.labels.map(label => (
                                             <span key={label} className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full border border-indigo-100 font-medium">{label}</span>
                                         ))}
                                     </div>
                                 </div>
                             )}

                             <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Assignment & Schedule</h3>
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Assignee</label>
                                        <select 
                                            value={task.assignee || ''} 
                                            onChange={(e) => changeAssignee(e.target.value)}
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-500"
                                        >
                                            <option value="">Unassigned</option>
                                            <option value="Me">Me</option>
                                            {members.map(m => (
                                                <option key={m.id} value={m.name || m.email}>{m.name || m.email}</option>
                                            ))}
                                        </select>
                                    </div>
                                    
                                    <button onClick={addToCalendar} className="w-full flex items-center justify-center gap-2 bg-indigo-50 text-indigo-700 p-2 rounded-lg hover:bg-indigo-100 transition-colors border border-indigo-200 font-medium text-sm">
                                        <CalendarClock size={16} /> Add to Schedule
                                    </button>
                                </div>
                             </div>
                        </div>
                    )}

                    {activeTab === 'notes' && (
                        <div className="flex flex-col h-full">
                            <div className="flex-1 space-y-3 mb-4 min-h-[200px]">
                                {taskNotes.length === 0 ? (
                                    <div className="text-center text-slate-400 py-10 text-sm">No notes for this task yet.</div>
                                ) : (
                                    taskNotes.map(n => (
                                        <div key={n.id} className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm text-sm">
                                            <p className="text-slate-700 whitespace-pre-wrap">{n.content}</p>
                                            <p className="text-[10px] text-slate-400 mt-2 text-right">{new Date(n.createdAt).toLocaleString()}</p>
                                        </div>
                                    ))
                                )}
                            </div>
                            <div className="mt-auto">
                                <textarea 
                                    value={noteInput}
                                    onChange={e => setNoteInput(e.target.value)}
                                    className="w-full p-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                                    placeholder="Add a quick note..."
                                    rows={3}
                                />
                                <button onClick={saveNote} disabled={!noteInput.trim()} className="w-full mt-2 bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                                    Save Note
                                </button>
                            </div>
                        </div>
                    )}

                    {activeTab === 'resources' && (
                        <div className="space-y-6">
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold text-slate-500 uppercase">Attached Resources</h3>
                                {(!task.resources || task.resources.length === 0) && (
                                    <div className="text-sm text-slate-400 italic bg-white p-4 rounded-lg border border-slate-200 border-dashed text-center">
                                        No links or files attached.
                                    </div>
                                )}
                                {task.resources?.map(res => (
                                    <a href={res.url} target="_blank" rel="noreferrer" key={res.id} className="flex items-center gap-3 bg-white p-3 rounded-lg border border-slate-200 hover:border-indigo-500 hover:shadow-md transition-all group">
                                        <div className={`p-2 rounded-lg ${res.type === 'link' ? 'bg-blue-50 text-blue-600' : 'bg-orange-50 text-orange-600'}`}>
                                            {res.type === 'link' ? <Link size={16}/> : <Paperclip size={16}/>}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-medium text-slate-800 text-sm truncate">{res.title}</p>
                                            <p className="text-xs text-slate-400 truncate">{res.url}</p>
                                        </div>
                                        <ChevronRight size={16} className="text-slate-300 group-hover:text-indigo-600"/>
                                    </a>
                                ))}
                            </div>

                            <div className="bg-slate-200 h-px w-full my-4"></div>

                            <div className="bg-white p-4 rounded-xl border border-slate-200">
                                <h3 className="text-sm font-bold text-slate-800 mb-3">Add Resource</h3>
                                <div className="space-y-3">
                                    <input 
                                        type="text" 
                                        placeholder="Title (e.g. Design Specs)" 
                                        value={resourceTitle}
                                        onChange={e => setResourceTitle(e.target.value)}
                                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:border-indigo-500"
                                    />
                                    <input 
                                        type="text" 
                                        placeholder="URL or File Path" 
                                        value={resourceUrl}
                                        onChange={e => setResourceUrl(e.target.value)}
                                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:border-indigo-500"
                                    />
                                    <div className="grid grid-cols-2 gap-3">
                                        <button onClick={() => addResource('link')} className="flex items-center justify-center gap-2 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-sm font-medium text-slate-600">
                                            <Link size={14} /> Add Link
                                        </button>
                                        <button onClick={() => addResource('attachment')} className="flex items-center justify-center gap-2 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-sm font-medium text-slate-600">
                                            <Paperclip size={14} /> Attach File
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

const ISSUE_TYPE_CONFIG = {
    task: { icon: Check, color: 'text-slate-500', bg: 'bg-slate-100', label: 'Task' },
    bug: { icon: Bug, color: 'text-red-600', bg: 'bg-red-50', label: 'Bug' },
    feature: { icon: Star, color: 'text-indigo-600', bg: 'bg-indigo-50', label: 'Feature' },
    story: { icon: BookOpen, color: 'text-emerald-600', bg: 'bg-emerald-50', label: 'Story' },
};

const IssueTypeBadge = ({ type }: { type: string }) => {
    const cfg = ISSUE_TYPE_CONFIG[type as keyof typeof ISSUE_TYPE_CONFIG] || ISSUE_TYPE_CONFIG.task;
    const Icon = cfg.icon;
    return (
        <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
            <Icon size={9} /> {cfg.label}
        </span>
    );
};

const CheckCircleIcon = ({ priority }: { priority: string }) => {
    let color = "text-slate-300";
    if (priority === 'critical') color = "text-red-500";
    if (priority === 'high') color = "text-orange-500";
    if (priority === 'medium') color = "text-blue-500";
    return <CheckCircle2 className={`w-5 h-5 ${color}`} />;
};

const CheckCircle2 = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
        <path d="m9 12 2 2 4-4" />
    </svg>
);
