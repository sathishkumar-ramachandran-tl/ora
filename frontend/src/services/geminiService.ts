import axios from 'axios';
import { API_BASE_URL, getAuthHeader } from '../config';
import { Company, Project, Task, Persona, Language } from "../types";

// The AI Logic is now protected on the backend. 
// This file serves as a bridge to the Python 'Cortex'.

const aiClient = axios.create({
  baseURL: API_BASE_URL + '/api/v1/agents',
});

aiClient.interceptors.request.use((config) => {
  const { Authorization } = getAuthHeader() as { Authorization?: string };
  if (Authorization) {
    config.headers.Authorization = Authorization;
  }
  return config;
});

// --- Agent Bridges ---

export const generateProjectTasks = async (
    project: Project, 
    companyMission: string, 
    userGuidance: string, 
    persona: Persona = 'general', 
    lang: Language = 'en',
    onStatusUpdate?: (status: string) => void
): Promise<Task[]> => {
  try {
    if (onStatusUpdate) onStatusUpdate("Connecting to Ora Cortex...");
    
    // The backend handles the Agent Chain (Strategist -> Tactician -> Risk)
    const response = await aiClient.post('/generate-plan', {
        project,
        companyMission,
        userGuidance,
        persona,
        language: lang
    });

    if (onStatusUpdate) onStatusUpdate("Plan downloaded.");
    
    return response.data.tasks;

  } catch (error) {
    console.error("AI Agent Error:", error);
    return [];
  }
};

export const generateExecutiveSummary = async (companies: Company[], persona: Persona = 'general', lang: Language = 'en'): Promise<{ summary: string; risks: string[] }> => {
  try {
    const response = await aiClient.post('/executive-summary', {
        companies,
        persona,
        language: lang
    });
    return response.data;
  } catch (e) {
    return { summary: "Backend connectivity issue.", risks: ["System offline"] };
  }
};

export const generateWeeklyScheduleAdvice = async (companies: Company[], persona: Persona = 'general'): Promise<string> => {
   try {
    const response = await aiClient.post('/scheduler-advice', {
        companies,
        persona
    });
    return response.data.advice;
   } catch (e) {
     return "Schedule generation unavailable.";
   }
}
