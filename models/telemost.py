import requests
import json
from flask import current_app, session
import urllib.parse
from datetime import datetime


class TelemostAPI:
    def __init__(self):
        # We'll load config values on-demand instead of during initialization
        self.api_base = None
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.oauth_token = None

    def _load_config(self):
        """Load configuration from current app context"""
        if self.api_base is None:
            from flask import current_app
            self.api_base = current_app.config.get('YANDEX_API_BASE', 'https://telemost.yandex.ru/api/v1')
            self.client_id = current_app.config.get('YANDEX_CLIENT_ID')
            self.client_secret = current_app.config.get('YANDEX_CLIENT_SECRET')
            self.redirect_uri = current_app.config.get('YANDEX_REDIRECT_URI')
            # Get the permanent OAuth token from config
            self.oauth_token = current_app.config.get('YANDEX_OAUTH_TOKEN')
    
    def get_access_token(self, auth_code):
        """Exchange authorization code for access token"""
        self._load_config()
        if not self.client_id or not self.client_secret:
            return {'error': 'Yandex client credentials not configured'}

        from flask import current_app, session
        url = current_app.config.get('YANDEX_TOKEN_URL', 'https://oauth.yandex.ru/token')
        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': auth_code,
            'redirect_uri': self.redirect_uri
        }

        try:
            response = requests.post(url, data=params)
            response.raise_for_status()
            token_data = response.json()

            # Store tokens in session
            session['yandex_access_token'] = token_data.get('access_token')
            session['yandex_refresh_token'] = token_data.get('refresh_token')

            return token_data
        except requests.exceptions.RequestException as e:
            return {'error': f'Failed to get access token: {str(e)}'}
    
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        self._load_config()
        from flask import current_app, session
        refresh_token = session.get('yandex_refresh_token')
        if not refresh_token or not self.client_id or not self.client_secret:
            return None

        url = current_app.config.get('YANDEX_TOKEN_URL', 'https://oauth.yandex.ru/token')
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
            session['yandex_access_token'] = token_data.get('access_token')
            session['yandex_refresh_token'] = token_data.get('refresh_token', refresh_token)

            return token_data
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Failed to refresh Yandex tokens: {str(e)}')
            return None
    
    def api_call(self, method, endpoint, access_token=None, data=None, params=None):
        """Make an API call to Yandex Telemost"""
        self._load_config()
        from flask import session
        if not access_token:
            access_token = session.get('yandex_access_token')
            # If no access token in session, try to use permanent token from config
            if not access_token:
                access_token = self.oauth_token

        if not access_token:
            return {'error': 'No access token available'}

        # For Yandex OAuth, use the specific token format
        headers = {
            'Authorization': f'OAuth {access_token}',
            'Content-Type': 'application/json'
        }

        # Use the correct Yandex Telemost API endpoint according to documentation
        # The endpoint should be https://cloud-api.yandex.net/v1/telemost-api/conferences
        if 'conferences' in endpoint.lower():
            url = "https://cloud-api.yandex.net/v1/telemost-api/conferences"
        else:
            # For other endpoints, use the original format
            url = f"{self.api_base}/{endpoint}"

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                # Transform data to match Yandex API format
                if 'conferences' in endpoint.lower():
                    # Transform our data to match Yandex API requirements
                    yandex_format_data = {
                        'waiting_room_level': 'PUBLIC',  # Default to public access
                    }

                    # Add live stream if this is a broadcast
                    if data and data.get('type') == 'broadcast':
                        yandex_format_data['live_stream'] = {
                            'title': data.get('liveStreamTitle', data.get('live_stream_title', '')),
                            'description': data.get('liveStreamDescription', data.get('live_stream_description', ''))
                        }

                    # Add cohosts if provided
                    cohosts_data = data.get('cohosts', data.get('cohosts', []))
                    if cohosts_data:
                        yandex_format_data['cohosts'] = [{'email': email} for email in cohosts_data if '@' in email]

                    response = requests.post(url, headers=headers, json=yandex_format_data, params=params)
                else:
                    response = requests.post(url, headers=headers, json=data, params=params)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                return {'error': f'Unsupported HTTP method: {method}'}

            # We shouldn't raise_for_status yet, as we need to check the content first
            if response.status_code != 200 and response.status_code != 201:
                # Handle error responses
                try:
                    error_response = response.json()
                except json.JSONDecodeError:
                    error_response = {'error': 'Response was not JSON', 'status_code': response.status_code}
                return {'error': error_response, 'status_code': response.status_code}

            # Handle empty response
            if response.content:
                try:
                    result = response.json()

                    # For conference creation, ensure we return the correct format expected by the frontend
                    if method.upper() == 'POST' and 'conferences' in url:
                        # Yandex API returns conference data with link
                        # Result should contain conference information including the join link
                        yandex_conf_data = result

                        # Transform Yandex response to our expected format
                        conf_data = {
                            'id': yandex_conf_data.get('id', yandex_conf_data.get('ID')),
                            'name': data.get('name') if data else yandex_conf_data.get('name', ''),
                            'type': data.get('type', 'conference') if data else yandex_conf_data.get('type', 'conference'),
                            'description': data.get('description', '') if data else yandex_conf_data.get('description', ''),
                            'startDate': data.get('startDate', '') if data else yandex_conf_data.get('start_date', ''),
                            'startTime': data.get('startTime', '') if data else yandex_conf_data.get('start_time', ''),
                            'cohosts': data.get('cohosts', []) if data else yandex_conf_data.get('cohosts', []),
                            'createCalendarEvent': data.get('createCalendarEvent', False) if data else yandex_conf_data.get('create_calendar_event', False),
                            'inviteUsers': data.get('inviteUsers', False) if data else yandex_conf_data.get('invite_users', False),
                            'liveStreamTitle': data.get('liveStreamTitle', '') if data else yandex_conf_data.get('live_stream_title', ''),
                            'liveStreamDescription': data.get('liveStreamDescription', '') if data else yandex_conf_data.get('live_stream_description', ''),
                            'status': 'scheduled',
                            'link': yandex_conf_data.get('link', yandex_conf_data.get('JOIN_URL', yandex_conf_data.get('join_url', f"https://telemost.yandex.ru/j/{yandex_conf_data.get('id', yandex_conf_data.get('ID', 'new'))}"))),
                            'createdAt': datetime.now().isoformat()
                        }

                        return conf_data
                    else:
                        return result
                except json.JSONDecodeError:
                    # If response is not JSON, return as text
                    return {'result': response.text}
            else:
                return {'success': True, 'status_code': response.status_code}

        except requests.exceptions.RequestException as e:
            return {'error': f'Request failed: {str(e)}', 'status_code': getattr(e.response, 'status_code', None)}
    
    def list_conferences(self, access_token=None, params=None):
        """Get list of conferences from Yandex Telemost"""
        # Since we don't have exact API documentation, I'll implement based on common API patterns
        # This is a placeholder - the actual endpoint may be different
        return self.api_call('GET', 'conferences', access_token=access_token, params=params)
    
    def get_conference(self, access_token, conf_id):
        """Get details of a specific conference"""
        return self.api_call('GET', f'conferences/{conf_id}', access_token=access_token)
    
    def create_conference(self, access_token, conference_data):
        """Create a new conference in Yandex Telemost"""
        # Based on common API patterns, the endpoint might be conferences or similar
        return self.api_call('POST', 'conferences', access_token=access_token, data=conference_data)
    
    def update_conference(self, access_token, conf_id, conference_data):
        """Update a conference in Yandex Telemost"""
        return self.api_call('PUT', f'conferences/{conf_id}', access_token=access_token, data=conference_data)
    
    def delete_conference(self, access_token, conf_id):
        """Delete a conference from Yandex Telemost"""
        return self.api_call('DELETE', f'conferences/{conf_id}', access_token=access_token)
    
    def create_broadcast(self, access_token, broadcast_data):
        """Create a new broadcast in Yandex Telemost"""
        # Create a conference with broadcast settings
        return self.create_conference(access_token, broadcast_data)
    
    def get_conferences(self, access_token):
        """Get list of conferences from Yandex Telemost"""
        headers = {
            'Authorization': f'OAuth {access_token}',
            'Content-Type': 'application/json'
        }

        # Use the correct Yandex Telemost API endpoint according to documentation
        url = "https://cloud-api.yandex.net/v1/telemost-api/conferences"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            if response.content:
                result = response.json()
                return result
            else:
                return []
        except requests.exceptions.RequestException as e:
            return {'error': f'Request failed: {str(e)}', 'status_code': getattr(e.response, 'status_code', None)}

    def get_user_profile(self, access_token):
        """Get user profile from Yandex Telemost"""
        return self.api_call('GET', 'user', access_token=access_token)