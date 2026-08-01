export type Status = 'backlog' | 'todo' | 'in-progress' | 'review' | 'done';
export type Priority = 'low' | 'medium' | 'high' | 'critical';
export type Persona = 'general' | 'student_mit' | 'phd_researcher' | 'software_engineer' | 'politician' | 'writer' | 'freelancer' | 'upsc_aspirant';
export type Language = 'en' | 'es' | 'fr' | 'hi' | 'zh';

// Flexible Permission System
export interface CustomRole {
  id: string;
  name: string;
  color: string;
  permissions: ('create_project' | 'manage_team' | 'view_financials' | 'approve_tasks')[];
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  roleId?: string; // Links to CustomRole
  role?: string; // For workspace/project member roles
  
  // Profile Fields
  is_onboarded?: boolean;
  gender?: string;
  phone?: string;
  age?: number;
  location?: string;
}

export interface Organization {
  id: string;
  name: string;
  domain?: string;
  role: 'owner' | 'admin' | 'member';
}

export interface Workspace {
  id: string;
  name: string;
  
  // New Architecture Fields
  context: 'personal' | 'company';
  type: 'study' | 'project';
  organizationId?: string; // If company context
  
  // Legacy/Backwards Compat (mapped from backend)
  persona: Persona; 
  members: { userId: string; roleId: string; joinedAt: Date }[];
  customRoles: CustomRole[]; 
  
  // Enterprise Details
  companyWebsite?: string;
  location?: string;
  employeeCount?: string;
  category?: string;
  aiContextDescription?: string;
}

export interface Document {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: Date;
  bucketPath: string; 
  tags: string[];
}

export interface TaskResource {
  id: string;
  type: 'link' | 'attachment';
  title: string;
  url: string;
  addedAt: Date;
}

export interface Task {
  id: string;
  workspaceId: string;
  title: string;
  description?: string;
  status: Status;
  priority: Priority;
  assignee?: string; 
  estimatedHours?: number;
  isDailyFocus?: boolean;
  resources?: TaskResource[]; 
}

// --- MILANOTE / SPATIAL CANVAS TYPES ---
export type CanvasItemType = 'note' | 'image' | 'link' | 'column' | 'board';

export interface CanvasItem {
  id: string;
  type: CanvasItemType;
  x: number;
  y: number;
  w: number;
  h: number; // For columns/images
  content?: string; // Text for notes, URL for links/images
  title?: string;
  children?: string[]; // IDs of items docked inside (for Columns)
  color?: string;
}

export interface Project {
  id: string;
  workspaceId: string;
  name: string;
  type: 'build' | 'learning' | 'client' | 'research' | 'campaign';
  mission?: string;
  tasks: Task[];
  progress: number; 
  riskLevel?: 'low' | 'medium' | 'high';
  tags?: string[];
  companyId?: string; 
  whiteboard?: CanvasItem[]; // Persisted spatial data
}

export interface Company {
  id: string;
  workspaceId: string;
  name: string;
  mission: string;
  projects: Project[];
  color: string;
  whiteboard?: CanvasItem[]; // Persisted spatial data
}

export interface Note {
  id: string;
  workspaceId: string;
  contextId: string; // Can be ProjectID or TaskID
  content: string;
  createdAt: Date;
  type?: 'general' | 'idea'; // Added type for Idea Board
  color?: string; // For Idea Board visualization
}

export interface LogEntry {
  id: string;
  eventName: string;
  properties: any;
  timestamp: Date;
}

export interface AppState {
  user: User | null;
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  companies: Company[];
  language: Language;
}