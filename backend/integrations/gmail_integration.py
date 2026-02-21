import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import pickle

class GmailIntegration:
    """
    Integration with Gmail API to fetch emails
    """
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API"""
        token_path = 'token.pickle'
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                self.creds = pickle.load(token)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                print("Gmail credentials not found. Please set up OAuth2 credentials.")
                return
        
        if self.creds:
            self.service = build('gmail', 'v1', credentials=self.creds)
    
    def fetch_emails(self, query='', max_results=100):
        """
        Fetch emails from Gmail
        
        Args:
            query: Gmail search query (e.g., 'subject:requirements after:2024/01/01')
            max_results: Maximum number of emails to fetch
        
        Returns:
            List of email dictionaries
        """
        if not self.service:
            return []
        
        emails = []
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                email_data = self._parse_email(msg)
                emails.append(email_data)
        
        except Exception as e:
            print(f"Error fetching emails: {e}")
        
        return emails
    
    def _parse_email(self, msg):
        """Parse email message"""
        headers = msg['payload']['headers']
        
        subject = ''
        sender = ''
        date = ''
        
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            elif header['name'] == 'From':
                sender = header['value']
            elif header['name'] == 'Date':
                date = header['value']
        
        body = self._get_email_body(msg['payload'])
        
        return {
            'id': msg['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'body': body,
            'metadata': {
                'thread_id': msg.get('threadId', ''),
                'labels': msg.get('labelIds', [])
            }
        }
    
    def _get_email_body(self, payload):
        """Extract email body from payload"""
        body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
                        break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8')
        
        return body
    
    def search_project_emails(self, project_name, days=30):
        """
        Search for emails related to a specific project
        
        Args:
            project_name: Name of the project
            days: Number of days to look back
        
        Returns:
            List of relevant emails
        """
        from datetime import datetime, timedelta
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
        
        query = f'subject:"{project_name}" OR "{project_name}" after:{start_date}'
        
        return self.fetch_emails(query=query)
