import os
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from flask import current_app

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class GmailService:
    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        # NOTE: In a server environment, you usually provide the token.json directly
        # or use a Service Account (if Workspace). For simplicity here, we assume
        # token.json exists or we log that it's missing.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    self.creds = None
            
            if not self.creds:
                 # We cannot run local server flow in a headless backend easily without
                 # manual intervention. We will look for credentials.json to allow
                 # manual generation if needed, but primarily we expect token.json
                 if os.path.exists('credentials.json'):
                     print("Credentials found. If token.json is missing, run a local script to generate it.")
                 else:
                     print("No credentials.json or token.json found.")
                     return

        if self.creds:
            self.service = build('gmail', 'v1', credentials=self.creds)

    def send_email(self, recipient, subject, body):
        if not self.service:
            print("Gmail service not initialized. Check credentials.")
            return False

        try:
            message = MIMEText(body)
            message['to'] = recipient
            message['subject'] = subject
            
            # Encode the message (base64url)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body = {'raw': raw}

            message = self.service.users().messages().send(userId="me", body=body).execute()
            print(f"Message Id: {message['id']}")
            return True
        except Exception as error:
            print(f"An error occurred: {error}")
            return False

    def send_welcome_email(self, to_email, user_name):
        """Sends a welcome email to a new user."""
        subject = "Welcome to Sindhai!"
        body = f"""
        Hi {user_name},

        Welcome to Sindhai! We're thrilled to have you on board.
        
        Sindhai is designed to be your cognitive operating system, helping you manage initiatives, projects, and knowledge with AI-driven insights.

        Get started by creating your first workspace and setting up your first initiative.

        Best,
        The Sindhai Team
        """
        return self.send_email(to_email, subject, body)
