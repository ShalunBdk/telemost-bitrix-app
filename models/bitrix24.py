import requests
import json
from flask import current_app, session
import time


class Bitrix24API:
    def __init__(self):
        self.base_url = None
        self.client_id = None
        self.client_secret = None
        self.webhook_url = None
        self.domain = None

    def _load_config(self):
        """Load configuration from current app context"""
        if self.client_id is None:
            from flask import current_app
            self.client_id = current_app.config.get('BITRIX24_CLIENT_ID')
            self.client_secret = current_app.config.get('BITRIX24_CLIENT_SECRET')
            self.webhook_url = current_app.config.get('BITRIX24_WEBHOOK_URL')
            self.domain = current_app.config.get('BITRIX24_DOMAIN')
    
    def get_base_url(self):
        """Get the Bitrix24 API base URL"""
        self._load_config()
        if self.webhook_url:
            return self.webhook_url
        else:
            # For OAuth apps, we need to get the domain from the session or config
            from flask import session, current_app
            domain = session.get('bitrix_domain') or self.domain
            if domain:
                return f"https://{domain}/rest/"
        return None
    
    def call_method(self, method, params=None, use_auth=True):
        """Call a Bitrix24 REST API method"""
        from flask import session, current_app
        base_url = self.get_base_url()
        if not base_url:
            return {'error': 'No Bitrix24 URL configured'}

        # Build the URL
        if self.webhook_url:
            # For webhook, the URL is already complete
            url = f"{base_url}{method}"
        else:
            # For OAuth, append method and format
            url = f"{base_url}{method}.json"

        # Prepare the parameters
        if params is None:
            params = {}

        # Add authentication token if required and available
        if use_auth and not self.webhook_url:
            access_token = session.get('bitrix_access_token')
            if access_token:
                params['auth'] = access_token
            else:
                return {'error': 'No access token available'}

        try:
            response = requests.post(url, data=params)
            response.raise_for_status()
            result = response.json()

            # Handle token expiration error
            if 'error' in result and result['error'] in ['expired_token', 'invalid_token']:
                # Try to refresh the token
                refresh_result = self.refresh_tokens()
                if refresh_result and 'access_token' in refresh_result:
                    # Retry the request with new token
                    params['auth'] = refresh_result['access_token']
                    session['bitrix_access_token'] = refresh_result['access_token']
                    response = requests.post(url, data=params)
                    response.raise_for_status()
                    result = response.json()

            return result
        except requests.exceptions.RequestException as e:
            return {'error': f'Request failed: {str(e)}'}
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON response'}
    
    def get_access_token(self, auth_code):
        """Exchange authorization code for access token"""
        self._load_config()
        if not self.client_id or not self.client_secret:
            return {'error': 'Client credentials not configured'}

        from flask import session
        url = 'https://oauth.bitrix.info/oauth/token/'
        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': auth_code
        }

        try:
            response = requests.post(url, data=params)
            response.raise_for_status()
            token_data = response.json()

            # Store tokens in session
            session['bitrix_access_token'] = token_data.get('access_token')
            session['bitrix_refresh_token'] = token_data.get('refresh_token')
            session['bitrix_domain'] = token_data.get('domain', '')

            return token_data
        except requests.exceptions.RequestException as e:
            return {'error': f'Failed to get access token: {str(e)}'}
    
    def refresh_tokens(self):
        """Refresh access tokens using refresh token"""
        self._load_config()
        from flask import session, current_app
        refresh_token = session.get('bitrix_refresh_token')
        if not refresh_token or not self.client_id or not self.client_secret:
            return None

        url = 'https://oauth.bitrix.info/oauth/token/'
        params = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token
        }

        try:
            response = requests.post(url, data=params)
            response.raise_for_status()
            token_data = response.json()

            # Update session with new tokens
            session['bitrix_access_token'] = token_data.get('access_token')
            session['bitrix_refresh_token'] = token_data.get('refresh_token')

            return token_data
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Failed to refresh Bitrix24 tokens: {str(e)}')
            return None
    
    def get_current_user(self, access_token=None):
        """Get current user information"""
        return self.call_method('user.current')
    
    def create_calendar_event(self, event_data):
        """Create a calendar event in Bitrix24"""
        # event_data should contain the event details
        return self.call_method('calendar.event.add', event_data)
    
    def get_calendar_events(self, params=None):
        """Get calendar events from Bitrix24"""
        if params is None:
            params = {}
        return self.call_method('calendar.event.get', params)
    
    def get_users(self):
        """Get list of users from Bitrix24"""
        return self.call_method('user.get')
    
    def get_departments(self):
        """Get list of departments from Bitrix24"""
        return self.call_method('department.get')
    
    def get_user_by_id(self, user_id):
        """Get user by ID from Bitrix24"""
        params = {'ID': user_id}
        return self.call_method('user.get', params)

    def set_auth_data(self, auth_data):
        """Store authentication data in session"""
        from flask import session
        try:
            session['bitrix_access_token'] = auth_data.get('access_token')
            session['bitrix_refresh_token'] = auth_data.get('refresh_token')
            session['bitrix_domain'] = auth_data.get('domain', '')
            session['bitrix_client_endpoint'] = auth_data.get('client_endpoint', '')
            session['bitrix_application_token'] = auth_data.get('application_token')
            session['bitrix_expires_in'] = auth_data.get('expires_in')
            return True
        except Exception as e:
            print(f"Error setting auth data: {e}")
            return False