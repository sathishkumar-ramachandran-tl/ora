import React, { useState, useEffect } from 'react';
import { Play, Pause, X, RotateCcw, Flame } from 'lucide-react';
import { Task } from '../../types';

interface FocusTimerProps {
  activeTask: Task | null;
  onClearTask: () => void;
}

const FOCUS_DURATION = 25 * 60; // 25 minutes in seconds

export const FocusTimer: React.FC<FocusTimerProps> = ({ activeTask, onClearTask }) => {
  const [timeLeft, setTimeLeft] = useState(FOCUS_DURATION);
  const [isActive, setIsActive] = useState(false);

  useEffect(() => {
    let interval: any = null;
    if (isActive && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(timeLeft - 1);
      }, 1000);
    } else if (timeLeft === 0) {
      setIsActive(false);
      // Could play a sound here
    }
    return () => clearInterval(interval);
  }, [isActive, timeLeft]);

  const toggleTimer = () => setIsActive(!isActive);
  const resetTimer = () => {
    setIsActive(false);
    setTimeLeft(FOCUS_DURATION);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  if (!activeTask) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
      <div className="bg-slate-900 text-white rounded-2xl shadow-2xl p-4 w-72 border border-slate-700">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2 text-indigo-400">
            <Flame className={`w-4 h-4 ${isActive ? 'animate-pulse' : ''}`} />
            <span className="text-xs font-bold uppercase tracking-wider">Deep Work Mode</span>
          </div>
          <button onClick={onClearTask} className="text-slate-500 hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="mb-4">
          <p className="text-sm font-medium line-clamp-1 text-slate-200" title={activeTask.title}>
            {activeTask.title}
          </p>
          <p className="text-xs text-slate-500">Focus Session</p>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-3xl font-mono font-bold tracking-tight">
            {formatTime(timeLeft)}
          </div>
          <div className="flex gap-2">
            <button 
              onClick={toggleTimer}
              className={`p-2 rounded-full transition-colors ${isActive ? 'bg-amber-500/20 text-amber-500 hover:bg-amber-500/30' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}`}
            >
              {isActive ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
            </button>
            <button 
              onClick={resetTimer}
              className="p-2 rounded-full bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
            >
              <RotateCcw size={18} />
            </button>
          </div>
        </div>
        
        {/* Progress Bar */}
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
          <div 
            className="bg-indigo-500 h-full transition-all duration-1000 ease-linear" 
            style={{ width: `${((FOCUS_DURATION - timeLeft) / FOCUS_DURATION) * 100}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
};
