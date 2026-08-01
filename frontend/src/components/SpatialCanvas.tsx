import React, { useState, useRef, useEffect } from 'react';
import { CanvasItem, CanvasItemType } from '../types';
import { Plus, Type, Image as ImageIcon, Link as LinkIcon, Columns, Trash2, Maximize2, Move } from 'lucide-react';

interface SpatialCanvasProps {
  initialItems: CanvasItem[];
  onSave: (items: CanvasItem[]) => void;
  contextName: string; // Used for "Home > Context" breadcrumb
}

export const SpatialCanvas: React.FC<SpatialCanvasProps> = ({ initialItems, onSave, contextName }) => {
  const [items, setItems] = useState<CanvasItem[]>(initialItems);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragItem, setDragItem] = useState<{ id: string, startX: number, startY: number } | null>(null);
  const [panStart, setPanStart] = useState<{ x: number, y: number } | null>(null);
  
  // Save debouncer
  useEffect(() => {
    const timer = setTimeout(() => {
      onSave(items);
    }, 1000);
    return () => clearTimeout(timer);
  }, [items, onSave]);

  const containerRef = useRef<HTMLDivElement>(null);

  // --- Spatial Navigation ---
  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      // Zoom
      e.preventDefault();
      const zoomSensitivity = 0.001;
      const newScale = Math.min(Math.max(0.1, view.scale - e.deltaY * zoomSensitivity), 3);
      setView(prev => ({ ...prev, scale: newScale }));
    } else {
      // Pan
      setView(prev => ({ ...prev, x: prev.x - e.deltaX, y: prev.y - e.deltaY }));
    }
  };

  const startPan = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.shiftKey)) { // Middle click or Shift+Click
        setPanStart({ x: e.clientX, y: e.clientY });
        e.preventDefault();
    }
  };

  // --- Item Interaction ---
  const addItem = (type: CanvasItemType) => {
    // Add to center of current view
    const viewportCenter = {
        x: (-view.x + (containerRef.current?.clientWidth || 800) / 2) / view.scale,
        y: (-view.y + (containerRef.current?.clientHeight || 600) / 2) / view.scale
    };

    const newItem: CanvasItem = {
      id: crypto.randomUUID(),
      type,
      x: viewportCenter.x,
      y: viewportCenter.y,
      w: type === 'column' ? 300 : 200,
      h: type === 'column' ? 400 : 120,
      content: type === 'note' ? 'New Note' : type === 'link' ? 'https://' : '',
      title: type === 'column' ? 'New Group' : undefined,
      children: []
    };
    setItems([...items, newItem]);
  };

  const updateItem = (id: string, updates: Partial<CanvasItem>) => {
    setItems(items.map(it => it.id === id ? { ...it, ...updates } : it));
  };

  const deleteItem = (id: string) => {
    setItems(items.filter(it => it.id !== id));
  };

  // --- Drag & Drop Logic ---
  const handleMouseDownItem = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (e.button !== 0) return; // Only left click
    setDragItem({ id, startX: e.clientX, startY: e.clientY });
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (panStart) {
        const dx = e.clientX - panStart.x;
        const dy = e.clientY - panStart.y;
        setView(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }));
        setPanStart({ x: e.clientX, y: e.clientY });
        return;
    }

    if (dragItem) {
        const dx = (e.clientX - dragItem.startX) / view.scale;
        const dy = (e.clientY - dragItem.startY) / view.scale;
        
        setItems(prev => prev.map(it => {
            if (it.id === dragItem.id) {
                return { ...it, x: it.x + dx, y: it.y + dy };
            }
            return it;
        }));
        setDragItem({ ...dragItem, startX: e.clientX, startY: e.clientY });
    }
  };

  const handleMouseUp = () => {
    setPanStart(null);
    if (dragItem) {
        // Snapping Logic
        const item = items.find(i => i.id === dragItem.id);
        if (item) {
            const snappedX = Math.round(item.x / 20) * 20;
            const snappedY = Math.round(item.y / 20) * 20;
            
            // Collision / Docking Logic (Simple Version: If center is inside a column)
            let finalX = snappedX;
            let finalY = snappedY;
            
            // Identify Columns
            const columns = items.filter(i => i.type === 'column' && i.id !== item.id);
            const itemCenterX = item.x + item.w / 2;
            const itemCenterY = item.y + item.h / 2;

            const hitColumn = columns.find(col => 
                itemCenterX > col.x && itemCenterX < col.x + col.w &&
                itemCenterY > col.y && itemCenterY < col.y + col.h
            );

            if (hitColumn && item.type !== 'column') {
                // Docking logic visual feedback or actual nesting?
                // For this version, we will just snap it to a grid inside the column visually
                // A full magnetic list is complex, we will stick to spatial placement
            }

            updateItem(dragItem.id, { x: finalX, y: finalY });
        }
    }
    setDragItem(null);
    setIsDragging(false);
  };

  // --- Touch Support ---
  const handleTouchStartItem = (e: React.TouchEvent, id: string) => {
    e.stopPropagation();
    const touch = e.touches[0];
    setDragItem({ id, startX: touch.clientX, startY: touch.clientY });
    setIsDragging(true);
  };

  const handleTouchStartPan = (e: React.TouchEvent) => {
      if (e.touches.length === 1) {
          const touch = e.touches[0];
          setPanStart({ x: touch.clientX, y: touch.clientY });
      }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
      const touch = e.touches[0];
      
      if (panStart) {
          const dx = touch.clientX - panStart.x;
          const dy = touch.clientY - panStart.y;
          setView(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }));
          setPanStart({ x: touch.clientX, y: touch.clientY });
          return;
      }

      if (dragItem) {
          const dx = (touch.clientX - dragItem.startX) / view.scale;
          const dy = (touch.clientY - dragItem.startY) / view.scale;
          
          setItems(prev => prev.map(it => {
              if (it.id === dragItem.id) {
                  return { ...it, x: it.x + dx, y: it.y + dy };
              }
              return it;
          }));
          setDragItem({ ...dragItem, startX: touch.clientX, startY: touch.clientY });
      }
  };

  return (
    <div className="flex h-full bg-slate-50 relative overflow-hidden flex-1">
       {/* Sidebar Toolbox */}
       <div className="w-16 bg-white border-r border-slate-200 z-20 flex flex-col items-center py-4 gap-4 shadow-sm">
           <ToolButton icon={Type} label="Note" onClick={() => addItem('note')} />
           <ToolButton icon={LinkIcon} label="Link" onClick={() => addItem('link')} />
           <ToolButton icon={Columns} label="Group" onClick={() => addItem('column')} />
           <div className="h-px w-8 bg-slate-200"></div>
           <div className="text-[10px] text-slate-400 font-mono rotate-90 whitespace-nowrap mt-4">
               SPACE + DRAG TO PAN
           </div>
       </div>

       {/* Canvas Area */}
       <div 
         ref={containerRef}
         className="flex-1 relative cursor-grab active:cursor-grabbing overflow-hidden bg-[#f4f4f5] touch-none"
         onWheel={handleWheel}
         onMouseDown={startPan}
         onMouseMove={handleMouseMove}
         onMouseUp={handleMouseUp}
         onMouseLeave={handleMouseUp}
         onTouchStart={handleTouchStartPan}
         onTouchMove={handleTouchMove}
         onTouchEnd={handleMouseUp}
       >
           {/* Dot Grid Background */}
           <div 
             className="absolute inset-0 pointer-events-none"
             style={{
                backgroundSize: `${20 * view.scale}px ${20 * view.scale}px`,
                backgroundImage: `radial-gradient(#cbd5e1 1px, transparent 1px)`,
                backgroundPosition: `${view.x}px ${view.y}px`,
                opacity: 0.5
             }}
           />

           {/* Infinite World */}
           <div 
             className="absolute top-0 left-0 w-full h-full origin-top-left"
             style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
           >
               {/* Render Columns (Background Layer) */}
               {items.filter(i => i.type === 'column').map(item => (
                   <div 
                    key={item.id}
                    className="absolute bg-slate-100/50 border-2 border-dashed border-slate-300 rounded-xl"
                    style={{ left: item.x, top: item.y, width: item.w, height: item.h }}
                    onMouseDown={(e) => handleMouseDownItem(e, item.id)}                    onTouchStart={(e) => handleTouchStartItem(e, item.id)}                   >
                       <div className="p-2 border-b border-slate-200/50 flex justify-between items-center handle cursor-grab">
                           <input 
                             value={item.title} 
                             onChange={(e) => updateItem(item.id, { title: e.target.value })}
                             className="bg-transparent font-bold text-slate-500 uppercase tracking-wider text-xs outline-none"
                           />
                           <button onClick={() => deleteItem(item.id)} className="text-slate-400 hover:text-red-500"><Trash2 size={12}/></button>
                       </div>
                   </div>
               ))}

               {/* Render Items */}
               {items.filter(i => i.type !== 'column').map(item => (
                   <div 
                    key={item.id}
                    className={`absolute bg-white shadow-sm hover:shadow-lg transition-shadow rounded-lg overflow-hidden border border-slate-200 group flex flex-col ${item.type === 'note' ? 'p-0' : 'p-2'}`}
                    style={{ left: item.x, top: item.y, width: item.w, minHeight: item.h }}
                    onMouseDown={(e) => handleMouseDownItem(e, item.id)}
                    onTouchStart={(e) => handleTouchStartItem(e, item.id)}
                   >
                       {/* Drag Handle */}
                       <div className="h-4 w-full bg-slate-50 border-b border-slate-100 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab flex justify-end px-1 items-center">
                            <button onClick={() => deleteItem(item.id)} className="text-slate-300 hover:text-red-500"><XIcon /></button>
                       </div>

                       {item.type === 'note' && (
                           <textarea 
                             className="w-full h-full p-4 resize-none outline-none text-sm text-slate-700 leading-relaxed bg-transparent"
                             value={item.content}
                             onChange={(e) => updateItem(item.id, { content: e.target.value })}
                             placeholder="Start typing..."
                           />
                       )}

                       {item.type === 'link' && (
                           <div className="flex flex-col h-full">
                               <input 
                                 className="text-xs text-blue-500 underline bg-transparent outline-none mb-2" 
                                 value={item.content}
                                 onChange={(e) => updateItem(item.id, { content: e.target.value })}
                                 placeholder="https://..."
                               />
                               <div className="flex-1 bg-slate-50 rounded flex items-center justify-center text-slate-400">
                                   <LinkIcon size={24} />
                               </div>
                           </div>
                       )}
                   </div>
               ))}
           </div>
       </div>

       {/* Breadcrumb / Overlay */}
       <div className="absolute top-4 left-20 bg-white/90 backdrop-blur px-4 py-1.5 rounded-full border border-slate-200 shadow-sm text-xs font-medium text-slate-600 pointer-events-none">
           Home <span className="text-slate-300 mx-1">/</span> {contextName}
       </div>
    </div>
  );
};

const ToolButton = ({ icon: Icon, label, onClick }: any) => (
    <button onClick={onClick} className="group flex flex-col items-center gap-1">
        <div className="w-10 h-10 rounded-lg bg-white border border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-600 flex items-center justify-center transition-all shadow-sm">
            <Icon size={20} />
        </div>
        <span className="text-[10px] text-slate-400 font-medium">{label}</span>
    </button>
);

const XIcon = () => <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>;
