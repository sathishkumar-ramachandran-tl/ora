import os
import json
from google import genai
from google.genai import types


class AIService:
    def __init__(self):
        self.api_key = os.environ.get('API_KEY')
        print(f"AI Service API Key: {'Set' if self.api_key else 'Not Set'}")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            print("Warning: No API Key for AI Service")

    def _generate(self, model: str, contents, config=None):
        """Unified generate call compatible with google-genai >= 1.0."""
        kwargs = {"model": model, "contents": contents}
        if config:
            kwargs["config"] = types.GenerateContentConfig(**config)
        return self.client.models.generate_content(**kwargs)

    def generate_project_plan(self, project, company_mission, guidance, persona):
        if not self.api_key:
            return []

        prompt = f"""
        Role: Project Manager for a {persona}.
        Mission: {company_mission}
        Project: {project['name']} ({project['type']})
        Guidance: {guidance}

        Task: Break this project into 5-10 concrete, actionable tasks.
        Output JSON array: [{{"title": string, "description": string, "priority": "low"|"medium"|"high"|"critical", "estimatedHours": number}}]
        """

        try:
            response = self._generate(
                model='gemini-3-flash-preview',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "title": {"type": "STRING"},
                                "description": {"type": "STRING"},
                                "priority": {"type": "STRING", "enum": ["low", "medium", "high", "critical"]},
                                "estimatedHours": {"type": "NUMBER"}
                            },
                            "required": ["title", "description", "priority", "estimatedHours"]
                        }
                    }
                }
            )
            # google-genai >= 1.0 returns .parsed for JSON mode
            if hasattr(response, 'parsed') and response.parsed is not None:
                return response.parsed
            return json.loads(response.text)
        except Exception as e:
            print(f"AI Error: {e}")
            return []

    def generate_summary(self, companies, persona):
        if not self.api_key:
            return {"summary": "AI Offline", "risks": []}

        context = [{"name": c['name'], "projects": len(c['projects'])} for c in companies]
        prompt = f"Act as {persona}. Analyze ecosystem: {context}. Give 1 sentence summary and 3 risks."

        try:
            response = self._generate(
                model='gemini-3-flash-preview',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': {
                        "type": "OBJECT",
                        "properties": {
                            "summary": {"type": "STRING"},
                            "risks": {"type": "ARRAY", "items": {"type": "STRING"}}
                        }
                    }
                }
            )
            if hasattr(response, 'parsed') and response.parsed is not None:
                return response.parsed
            return json.loads(response.text)
        except Exception as e:
            print(f"Summary Error: {e}")
            return {"summary": "Analysis Failed", "risks": []}

    def generate_schedule(self, companies, persona):
        if not self.api_key:
            return "Focus on your top priority task."

        prompt = f"""
        Act as a productivity expert for a {persona}.
        Projects/Initiatives: {[c['name'] for c in companies]}.

        Suggest a weekly time-block strategy.
        Keep it concise and actionable.
        Use simple HTML formatting (<b>, <ul>, <li>, <br>) for the output.
        """

        try:
            response = self._generate(model='gemini-3-flash-preview', contents=prompt)
            return response.text
        except Exception as e:
            print(f"Schedule Error: {e}")
            return "Unable to generate schedule."

    def optimize_daily_schedule(self, tasks, date_str):
        if not self.api_key:
            return []

        prompt = f"""
        Role: Productivity Master.
        Date: {date_str}
        Tasks: {tasks}

        Create an optimized daily schedule (08:00 to 20:00).
        Assign tasks based on priority and energy flow (deep work in morning).
        Leave buffer times.

        Output JSON: [{{"title": string, "start": "HH:MM", "end": "HH:MM", "type": "task_block"|"meeting"|"break", "taskId": string_or_null}}]
        """

        try:
            response = self._generate(
                model='gemini-3-flash-preview',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "title": {"type": "STRING"},
                                "start": {"type": "STRING"},
                                "end": {"type": "STRING"},
                                "type": {"type": "STRING"},
                                "taskId": {"type": "STRING"}
                            },
                            "required": ["title", "start", "end", "type"]
                        }
                    }
                }
            )
            if hasattr(response, 'parsed') and response.parsed is not None:
                return response.parsed
            return json.loads(response.text)
        except Exception as e:
            print(f"Optimization Error: {e}")
            return []
