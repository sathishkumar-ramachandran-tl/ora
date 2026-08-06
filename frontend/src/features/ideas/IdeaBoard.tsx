import React, { useState, useEffect } from 'react';
import { Note, Company } from '../../types';
import { Plus, Lightbulb, ArrowUpRight, Trash2, Palette, Loader2, Sparkles } from 'lucide-react';
import { createNote, getNotes, deleteNote } from '../../api/workspace';
import { CreateCompanyModal } from '../../components/shared/CreationModals';

interface IdeaBoardProps {
  workspaceId: string;
  onCreateCompany: (company: Company) => Promise<void>;
}

const COLORS = [
  { id: 'white', bg: 'bg-white', border: 'border-slate-200' },
  { id: 'yellow', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  { id: 'green', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  { id: 'purple', bg: 'bg-purple-50', border: 'border-purple-200' },
  { id: 'blue', bg: 'bg-blue-50', border: 'border-blue-200' },
  { id: 'rose', bg: 'bg-rose-50', border: 'border-rose-200' }
];

export const IdeaBoard: React.FC<IdeaBoardProps> = ({ workspaceId, onCreateCompany }) => {
  const [ideas, setIdeas] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [newIdea, setNewIdea] = useState('');
  const [selectedColor, setSelectedColor] = useState('white');
  
  // Promotion State
  const [promoteModalOpen, setPromoteModalOpen] = useState(false);
  const [ideaToPromote, setIdeaToPromote] = useState<Note | null>(null);

  useEffect(() => {
    loadIdeas();
  }, [workspaceId]);

  const loadIdeas = async () => {
    setLoading(true);
    try {
      const data = await getNotes(workspaceId, 'idea');
      setIdeas(data);
    } catch (e) {
      console.error("Failed to load ideas", e);
    } finally {
      setLoading(false);
    }
  };

  const handleAddIdea = async () => {
    if (!newIdea.trim()) return;
    
    const note: Note = {
      id: crypto.randomUUID(),
      workspaceId,
      contextId: workspaceId, // Linked to workspace root
      content: newIdea,
      createdAt: new Date(),
      type: 'idea',
      color: selectedColor
    };

    try {
      await createNote(note);
      setIdeas([note, ...ideas]);
      setNewIdea('');
      setSelectedColor('white');
    } catch (e) {
      console.error("Failed to save idea", e);
    }
  };

  const handleDelete = async (id: string) => {
    await deleteNote(id);
    setIdeas(ideas.filter(i => i.id !== id));
  };

  const initPromote = (idea: Note) => {
    setIdeaToPromote(idea);
    setPromoteModalOpen(true);
  };

  const handlePromotionComplete = async (company: Company) => {
    await onCreateCompany(company);
    // Delete the idea after successful promotion
    if (ideaToPromote) {
       await handleDelete(ideaToPromote.id);
    }
    setPromoteModalOpen(false);
    setIdeaToPromote(null);
  };

  return (
    <div className="h-full flex flex-col bg-slate-50 relative">
      <div className="p-4 md:p-8 pb-4">
        <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <Lightbulb className="text-amber-500 fill-current" /> Incubator
        </h2>
        <p className="text-slate-500 mt-1">Capture raw thoughts. Promote the best ones to Initiatives.</p>
        
        {/* Input Area */}
        <div className="mt-6 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
          <textarea 
            value={newIdea}
            onChange={e => setNewIdea(e.target.value)}
            placeholder="What's on your mind? (e.g., 'Start a newsletter about AI Ethics')"
            className="w-full text-lg placeholder:text-slate-300 border-none outline-none resize-none mb-4"
            rows={2}
            onKeyDown={(e) => {
               if (e.key === 'Enter' && !e.shiftKey) {
                 e.preventDefault();
                 handleAddIdea();
               }
            }}
          />
          <div className="flex justify-between items-center">
            <div className="flex gap-2">
              {COLORS.map(c => (
                <button
                  key={c.id}
                  onClick={() => setSelectedColor(c.id)}
                  className={`w-6 h-6 rounded-full border ${c.bg} ${selectedColor === c.id ? 'ring-2 ring-indigo-500 ring-offset-2' : 'border-slate-200'}`}
                />
              ))}
            </div>
            <button 
              onClick={handleAddIdea}
              disabled={!newIdea.trim()}
              className="bg-slate-900 text-white px-4 py-2 rounded-lg font-medium text-sm hover:bg-slate-800 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              <Plus size={16} /> Add to Board
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 md:p-8 pt-0">
        {loading ? (
          <div className="flex justify-center py-20"><Loader2 className="animate-spin text-slate-300" /></div>
        ) : ideas.length === 0 ? (
          <div className="text-center py-20 text-slate-400 border-2 border-dashed border-slate-200 rounded-xl">
            <Sparkles className="mx-auto mb-4 opacity-50" />
            <p>Your incubator is empty. <br/> Great things start with a single note.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 auto-rows-max">
            {ideas.map(idea => {
               const colorTheme = COLORS.find(c => c.id === idea.color) || COLORS[0];
               return (
                 <div 
                   key={idea.id} 
                   className={`${colorTheme.bg} ${colorTheme.border} border p-5 rounded-xl shadow-sm hover:shadow-md transition-all group flex flex-col justify-between min-h-[160px] relative`}
                 >
                   <p className="text-slate-800 text-lg font-medium leading-relaxed mb-4 whitespace-pre-wrap">{idea.content}</p>
                   
                   <div className="flex justify-between items-center mt-auto pt-4 border-t border-black/5 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button 
                       onClick={() => handleDelete(idea.id)}
                       className="text-slate-400 hover:text-red-500 p-1 rounded"
                       title="Discard Idea"
                     >
                       <Trash2 size={16} />
                     </button>
                     <button 
                       onClick={() => initPromote(idea)}
                       className="flex items-center gap-1.5 text-xs font-bold text-indigo-600 bg-white/50 hover:bg-white px-3 py-1.5 rounded-lg border border-transparent hover:border-indigo-200 transition-all shadow-sm"
                     >
                       <ArrowUpRight size={14} /> Promote
                     </button>
                   </div>
                   
                   <div className="absolute top-4 right-4 text-[10px] text-slate-400 font-mono opacity-50">
                      {new Date(idea.createdAt).toLocaleDateString()}
                   </div>
                 </div>
               );
            })}
          </div>
        )}
      </div>

      <CreateCompanyModal 
        isOpen={promoteModalOpen} 
        onClose={() => setPromoteModalOpen(false)} 
        onSubmit={handlePromotionComplete}
        initialName={ideaToPromote?.content.substring(0, 50)}
        initialMission={ideaToPromote?.content}
      />
    </div>
  );
};