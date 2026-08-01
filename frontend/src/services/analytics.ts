import { logEvent } from "./db";

// Analytics Service for Sindhai
// Persists events to NeonDB 'activity_logs' table

type EventName = 
  | 'APP_LOAD'
  | 'AUTH_LOGIN'
  | 'AUTH_SIGNUP_START'
  | 'AUTH_SIGNUP_COMPLETE'
  | 'SESSION_RESTORED'
  | 'SESSION_RESTORATION_FAILED'
  | 'VIEW_CHANGED'
  | 'AI_AGENT_START'
  | 'AI_AGENT_COMPLETE'
  | 'AI_VOICE_SESSION_START'
  | 'TASK_CREATED'
  | 'TASK_COMPLETED'
  | 'PROJECT_CREATED'
  | 'SCHEDULE_CREATED'
  | 'DOCUMENT_UPLOADED'
  | 'TEAM_MEMBER_ADDED'
  | 'TEAM_MEMBER_ASSIGNED_TO_PROJECT'
  | 'TEAM_MEMBER_REMOVED_FROM_PROJECT'
  | 'TEAM_MEMBER_REMOVED';

interface EventProperties {
  [key: string]: any;
}

export const trackEvent = (event: EventName, properties?: EventProperties) => {
  const timestamp = new Date();
  
  // SECURITY: Only log to console in explicit development environments to prevent PII leakage
  // In a real production build, ensure NODE_ENV is set to 'production'
  if (process.env.NODE_ENV === 'development') {
      console.groupCollapsed(`[Sindhai Analytics] ${event}`);
      console.log('Timestamp:', timestamp.toISOString());
      console.log('Properties:', properties);
      console.groupEnd();
  }

  // 2. Persist to DB
  try {
      logEvent({
          id: crypto.randomUUID(),
          eventName: event,
          properties: properties || {},
          timestamp: timestamp
      });
  } catch (e) {
      // Fail silently in production to avoid console noise
      if (process.env.NODE_ENV === 'development') {
        console.warn("Analytics Sync Failed", e);
      }
  }
};

export const identifyUser = (userId: string, traits?: EventProperties) => {
  if (process.env.NODE_ENV === 'development') {
    console.log(`[Sindhai Analytics] Identify: ${userId}`, traits);
  }
};