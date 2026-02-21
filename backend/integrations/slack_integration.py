import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta

class SlackIntegration:
    """
    Integration with Slack API to fetch messages
    """
    
    def __init__(self):
        self.token = os.getenv('SLACK_BOT_TOKEN')
        self.client = None
        
        if self.token:
            self.client = WebClient(token=self.token)
    
    def fetch_messages(self, channel, days=30, limit=100):
        """
        Fetch messages from a Slack channel
        
        Args:
            channel: Channel ID or name
            days: Number of days to look back
            limit: Maximum number of messages
        
        Returns:
            List of message dictionaries
        """
        if not self.client:
            print("Slack client not initialized. Please set SLACK_BOT_TOKEN.")
            return []
        
        messages = []
        
        try:
            oldest = (datetime.now() - timedelta(days=days)).timestamp()
            
            result = self.client.conversations_history(
                channel=channel,
                oldest=str(oldest),
                limit=limit
            )
            
            for message in result['messages']:
                msg_data = self._parse_message(message, channel)
                messages.append(msg_data)
        
        except SlackApiError as e:
            print(f"Error fetching Slack messages: {e.response['error']}")
        
        return messages
    
    def _parse_message(self, message, channel):
        """Parse Slack message"""
        return {
            'ts': message['ts'],
            'text': message.get('text', ''),
            'user': message.get('user', ''),
            'channel': channel,
            'metadata': {
                'type': message.get('type', ''),
                'subtype': message.get('subtype', ''),
                'reactions': message.get('reactions', []),
                'thread_ts': message.get('thread_ts', '')
            }
        }
    
    def fetch_thread(self, channel, thread_ts):
        """
        Fetch all messages in a thread
        
        Args:
            channel: Channel ID
            thread_ts: Thread timestamp
        
        Returns:
            List of messages in thread
        """
        if not self.client:
            return []
        
        messages = []
        
        try:
            result = self.client.conversations_replies(
                channel=channel,
                ts=thread_ts
            )
            
            for message in result['messages']:
                msg_data = self._parse_message(message, channel)
                messages.append(msg_data)
        
        except SlackApiError as e:
            print(f"Error fetching thread: {e.response['error']}")
        
        return messages
    
    def search_messages(self, query, count=100):
        """
        Search for messages across all channels
        
        Args:
            query: Search query
            count: Number of results
        
        Returns:
            List of matching messages
        """
        if not self.client:
            return []
        
        messages = []
        
        try:
            result = self.client.search_messages(
                query=query,
                count=count
            )
            
            for match in result['messages']['matches']:
                messages.append({
                    'ts': match['ts'],
                    'text': match.get('text', ''),
                    'user': match.get('user', ''),
                    'channel': match.get('channel', {}).get('id', ''),
                    'metadata': {
                        'permalink': match.get('permalink', ''),
                        'channel_name': match.get('channel', {}).get('name', '')
                    }
                })
        
        except SlackApiError as e:
            print(f"Error searching messages: {e.response['error']}")
        
        return messages
    
    def get_channel_list(self):
        """Get list of all channels"""
        if not self.client:
            return []
        
        try:
            result = self.client.conversations_list()
            return result['channels']
        except SlackApiError as e:
            print(f"Error fetching channels: {e.response['error']}")
            return []
    
    def get_user_info(self, user_id):
        """Get information about a user"""
        if not self.client:
            return {}
        
        try:
            result = self.client.users_info(user=user_id)
            return result['user']
        except SlackApiError as e:
            print(f"Error fetching user info: {e.response['error']}")
            return {}
