// Shared visual language for the Modules feature — Fluent-inspired soft-accent
// tokens for category, difficulty and priority, reused across Marketplace and Review.
import { BookOpen, Rocket, Target, Repeat, Layers, LucideIcon } from 'lucide-react';
import { ModuleCategory, ModuleDifficulty, Priority } from '../../types';

export interface CategoryVisual {
  label: string;
  icon: LucideIcon;
  iconWrap: string;
  iconColor: string;
  ring: string;
}

export const CATEGORY_VISUALS: Record<ModuleCategory, CategoryVisual> = {
  exam_prep: { label: 'Exam Prep', icon: Target, iconWrap: 'bg-violet-50', iconColor: 'text-violet-600', ring: 'group-hover:ring-violet-200' },
  course: { label: 'Course', icon: BookOpen, iconWrap: 'bg-blue-50', iconColor: 'text-blue-600', ring: 'group-hover:ring-blue-200' },
  project: { label: 'Project', icon: Rocket, iconWrap: 'bg-brand-50', iconColor: 'text-brand-600', ring: 'group-hover:ring-brand-200' },
  habit: { label: 'Habit', icon: Repeat, iconWrap: 'bg-emerald-50', iconColor: 'text-emerald-600', ring: 'group-hover:ring-emerald-200' },
  general: { label: 'General', icon: Layers, iconWrap: 'bg-slate-100', iconColor: 'text-slate-600', ring: 'group-hover:ring-slate-200' },
};

export const DIFFICULTY_LABEL: Record<ModuleDifficulty, string> = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
};

export const DIFFICULTY_DOT: Record<ModuleDifficulty, string> = {
  beginner: 'bg-emerald-500',
  intermediate: 'bg-amber-500',
  advanced: 'bg-rose-500',
};

export interface PriorityVisual {
  label: string;
  dot: string;
  chip: string;
}

export const PRIORITY_VISUALS: Record<Priority, PriorityVisual> = {
  low: { label: 'Low', dot: 'bg-slate-400', chip: 'bg-slate-100 text-slate-600 border-slate-200' },
  medium: { label: 'Medium', dot: 'bg-blue-500', chip: 'bg-blue-50 text-blue-700 border-blue-200' },
  high: { label: 'High', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700 border-amber-200' },
  critical: { label: 'Critical', dot: 'bg-rose-500', chip: 'bg-rose-50 text-rose-700 border-rose-200' },
};
