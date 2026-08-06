export type Status = 'backlog' | 'todo' | 'in-progress' | 'review' | 'done';
export type Priority = 'low' | 'medium' | 'high' | 'critical';
export type IssueType = 'task' | 'bug' | 'feature' | 'story';
export type Persona = 'general' | 'student_mit' | 'phd_researcher' | 'software_engineer' | 'politician' | 'writer' | 'freelancer' | 'upsc_aspirant';
export type Language = 'en' | 'es' | 'fr' | 'hi' | 'zh';

// Flexible Permission System
export interface CustomRole {
  id: string;
  name: string;
  color: string;
  permissions: ('create_project' | 'manage_team' | 'view_financials' | 'approve_tasks')[];
}

export type Purpose = 'learning' | 'freelancing' | 'personal' | 'startup' | 'enterprise';

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  roleId?: string;
  role?: string;
  // Profile Fields
  is_onboarded?: boolean;
  email_verified?: boolean;
  gender?: string;
  phone?: string;
  age?: number;
  location?: string;
  country?: string;
  purpose?: Purpose;
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
  assigneeId?: string;
  estimatedHours?: number;
  isDailyFocus?: boolean;
  resources?: TaskResource[];
  // Jira-style
  dueDate?: string;        // ISO string
  labels?: string[];
  issueType?: IssueType;
  // Project Management (Phase 3)
  projectId?: string;
  milestoneId?: string;
  sprintId?: string;
  parentTaskId?: string;
}

// --- Agentic Project Management (Phase 3) ---

export type MilestoneStatus = 'pending' | 'in_progress' | 'done';
export type SprintStatus = 'planned' | 'active' | 'completed';
export type DependencyType = 'blocks' | 'blocked_by' | 'relates_to';

export interface Milestone {
  id: string;
  projectId: string;
  title: string;
  description?: string;
  dueDate?: string;
  status: MilestoneStatus;
  order: number;
}

export interface Sprint {
  id: string;
  projectId: string;
  name: string;
  startDate?: string;
  endDate?: string;
  status: SprintStatus;
}

export interface TaskDependency {
  id: string;
  taskId: string;
  dependsOnTaskId: string;
  type: DependencyType;
}

export interface DependencyTaskRef {
  dependencyId: string;
  type: DependencyType;
  task: { id: string; title: string; status: Status } | null;
}

export interface TaskDependencies {
  dependsOn: DependencyTaskRef[];
  blockedBy: DependencyTaskRef[];
}

export interface BlockedTaskEntry {
  taskId: string;
  blockedByTasks: { id: string; title: string; status: Status }[];
}

export interface ReplanResult {
  summary: string;
  steps: { description: string; status: string; result: unknown }[];
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

export interface Company {
    id: string;
    workspaceId: string;
    name: string;
    mission: string;
    color: string;
    projects: Project[];
    whiteboard?: CanvasItem[]; // Persisted spatial data
}

export interface Project {
  id: string;
  workspaceId: string;
  companyId?: string;
  name: string;
  type: 'build' | 'learning' | 'client' | 'research' | 'campaign';
  mission?: string;
  tasks: Task[];
  progress: number;
  whiteboard?: CanvasItem[]; // Persisted spatial data
}

export interface LogEntry {
  id: string;
  eventName: string;
  properties: any;
  timestamp: Date;
}

export interface Note {
  id: string;
  workspaceId: string;
  contextId?: string;
  content: string;
  type?: 'general' | 'idea';
  color?: string;
  visibility?: 'private' | 'public' | 'team';
  ownerId?: string;
  createdAt: Date;
}

export interface CalendarEvent {
  id: string;
  workspaceId: string;
  ownerId?: string;
  title: string;
  start: string; // ISO String often better for serializing, but we will cast to Date in frontend services
  end: string;
  type: 'block' | 'meeting' | 'personal' | 'task_block' | 'reminder';
  scope: 'personal' | 'workspace' | 'company';
  taskId?: string;
  color: string;
  isAutoGenerated?: boolean;
  timezone?: string;
  recurrenceRule?: string; // RFC5545 RRULE text, e.g. 'FREQ=WEEKLY;BYDAY=MO,WE,FR'
  attendees?: string[];
  isRecurringOccurrence?: boolean;
  organizationId?: string;
}

// --- Agentic Module Generation (Phase 1) ---

export type ModuleCategory = 'exam_prep' | 'course' | 'project' | 'habit' | 'general';
export type ModuleDifficulty = 'beginner' | 'intermediate' | 'advanced';
export type ModuleGenerationStatus = 'pending' | 'generating' | 'ready' | 'failed';

export interface ModuleSummary {
  id: string;
  title: string;
  slug: string;
  description: string;
  category: ModuleCategory;
  difficulty: ModuleDifficulty;
  source: string;
  isPublished: boolean;
  installCount: number;
  metadata?: Record<string, unknown>;
}

export interface ModuleTaskSpec {
  title: string;
  description: string;
  priority: Priority;
  estimated_hours: number;
}

export interface ModuleMilestoneSpec {
  title: string;
  description: string;
  order: number;
  tasks: ModuleTaskSpec[];
}

export interface ModuleDetail extends ModuleSummary {
  structure: { milestones: ModuleMilestoneSpec[] } | null;
  generationStatus: ModuleGenerationStatus | null;
}

export interface ModuleGenerationDraft {
  moduleTemplateId: string;
  moduleTemplateVersionId: string;
  status: string;
}

export interface ModuleProgress {
  moduleTemplateVersionId: string;
  status: ModuleGenerationStatus;
  error: string | null;
  milestoneCount: number;
  taskCount: number;
}

export interface ModuleInstance {
  id: string;
  moduleTemplateId: string;
  projectId: string;
  status: 'installing' | 'active' | 'completed' | 'archived' | 'failed';
  progressPct: number;
  totalTasks: number;
  completedTasks: number;
}
