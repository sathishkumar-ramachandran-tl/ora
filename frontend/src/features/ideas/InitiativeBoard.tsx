import React, { useState } from 'react';
import { Company, Project, Task } from '../../types';
import { SpatialCanvas } from '../canvas/SpatialCanvas';
import { saveWhiteboard } from '../../api/projects';
import { Layout, Globe, ArrowUpRight, BarChart3, Plus } from 'lucide-react';

interface InitiativeBoardProps {
  company: Company;
  onNavigateProject: (projectId: string) => void;
  onUpdateCompany: (c: Company) => void; // For optimistic UI
  onCreateProject?: (project: Project, companyId: string) => Promise<void>;
}

export const InitiativeBoard: React.FC<InitiativeBoardProps> = ({ company, onNavigateProject, onUpdateCompany, onCreateProject }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'canvas'>('overview');
  const [showNewProjectForm, setShowNewProjectForm] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectMission, setProjectMission] = useState('');

  const handleSaveCanvas = async (items: any[]) => {
      // Optimistic update
      onUpdateCompany({ ...company, whiteboard: items });
      // Persist
      await saveWhiteboard('company', company.id, items);
  };

  const handleCreateProject = async () => {
    if (!projectName.trim() || !onCreateProject) return;
    
    const newProject: Project = {
      id: crypto.randomUUID(),
      workspaceId: company.workspaceId,
      companyId: company.id,
      name: projectName,
      type: 'build',
      mission: projectMission,
      progress: 0,
      tasks: [],
      whiteboard: []
    };
    
    try {
      await onCreateProject(newProject, company.id);
      setShowNewProjectForm(false);
      setProjectName('');
      setProjectMission('');
    } catch (e) {
      console.error('Failed to create project', e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-ora-canvas">
      {/* Header */}
      <div className="h-16 border-b border-ora-border flex items-center justify-between px-8 bg-ora-canvas z-10">
         <div className="flex items-center gap-4">
             <div className="w-10 h-10 rounded-lg bg-ora-accent-soft flex items-center justify-center text-ora-accent">
                 <Globe size={20} />
             </div>
             <div>
                 <h2 className="text-xl font-bold text-ora-primary">{company.name}</h2>
                 <p className="text-xs text-ora-secondary">Initiative Level View</p>
             </div>
         </div>
         <div className="flex bg-ora-subtle p-1 rounded-lg">
             <button 
                onClick={() => setActiveTab('overview')}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'overview' ? 'bg-ora-surface text-ora-primary shadow-sm' : 'text-ora-secondary hover:text-ora-primary'}`}
             >
                 Dashboard
             </button>
             <button 
                onClick={() => setActiveTab('canvas')}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${activeTab === 'canvas' ? 'bg-ora-surface text-ora-accent shadow-sm' : 'text-ora-secondary hover:text-ora-primary'}`}
             >
                 <Layout size={14} /> Spatial Canvas
             </button>
         </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
          {activeTab === 'canvas' ? (
              <SpatialCanvas 
                initialItems={company.whiteboard || []} 
                onSave={handleSaveCanvas} 
                contextName={company.name}
              />
          ) : (
              <div className="p-8 h-full overflow-y-auto bg-ora-canvas">
                  <div className="max-w-5xl mx-auto space-y-8">
                      {/* Mission Card */}
                      <div className="bg-ora-surface/70 p-6 rounded-lg border border-ora-border">
                          <h3 className="text-sm font-bold text-ora-tertiary uppercase tracking-wider mb-2">Strategic Mission</h3>
                          <p className="text-xl text-ora-primary leading-relaxed font-light">"{company.mission}"</p>
                      </div>

                      {/* Projects Grid */}
                      <div>
                          <div className="flex items-center justify-between mb-4">
                              <h3 className="text-lg font-bold text-ora-primary">Active Projects</h3>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                              {company.projects.map(project => (
                                  <div 
                                    key={project.id} 
                                    onClick={() => onNavigateProject(project.id)}
                                    className="bg-ora-surface p-5 rounded-lg border border-ora-border hover:border-ora-accent/40 transition-all cursor-pointer group"
                                  >
                                      <div className="flex justify-between items-start mb-4">
                                          <div className="p-2 rounded-lg bg-ora-subtle text-ora-secondary group-hover:bg-ora-accent-soft group-hover:text-ora-accent transition-colors">
                                              <BarChart3 size={20} />
                                          </div>
                                          <ArrowUpRight size={18} className="text-ora-tertiary group-hover:text-ora-accent transition-colors" />
                                      </div>
                                      <h4 className="font-bold text-ora-primary mb-1">{project.name}</h4>
                                      <p className="text-sm text-ora-secondary line-clamp-2 mb-4">{project.mission}</p>
                                      
                                      <div className="w-full bg-ora-subtle h-1.5 rounded-full overflow-hidden">
                                          <div className="bg-ora-accent h-full" style={{ width: `${project.progress}%` }}></div>
                                      </div>
                                      <div className="flex justify-between mt-2 text-xs text-ora-tertiary">
                                          <span>{project.tasks.length} Tasks</span>
                                          <span>{project.progress}% Done</span>
                                      </div>
                                  </div>
                              ))}
                              
                              {/* Add Project Placeholder */}
                              <button 
                                onClick={() => setShowNewProjectForm(true)}
                                className="border-2 border-dashed border-ora-border rounded-lg flex flex-col items-center justify-center p-6 text-ora-tertiary hover:border-ora-accent/50 hover:text-ora-accent transition-all hover:bg-ora-surface">
                                  <Plus size={32} className="mb-2" />
                                  <span className="font-medium">New Project</span>
                              </button>
                              
                              {/* New Project Form Modal */}
                              {showNewProjectForm && (
                                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                                  <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
                                    <h3 className="text-lg font-bold text-slate-800">Create New Project</h3>
                                    <input
                                      type="text"
                                      placeholder="Project Name"
                                      value={projectName}
                                      onChange={(e) => setProjectName(e.target.value)}
                                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                                    />
                                    <textarea
                                      placeholder="Project Mission"
                                      value={projectMission}
                                      onChange={(e) => setProjectMission(e.target.value)}
                                      rows={3}
                                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                                    />
                                    <div className="flex gap-2 justify-end pt-4">
                                      <button
                                        onClick={() => setShowNewProjectForm(false)}
                                        className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        onClick={handleCreateProject}
                                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                                      >
                                        Create
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}
                          </div>
                      </div>
                  </div>
              </div>
          )}
      </div>
    </div>
  );
};
