from flask import Flask, request, jsonify, session, render_template, redirect, url_for, make_response, current_app
from config import Config
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import json
from urllib.parse import parse_qs

# Import the database functions
from database import (
    save_conference, get_user_conferences, get_all_conferences,
    get_conference_by_id, update_conference, delete_conference,
    get_conferences_by_type
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Set up logging (always enabled)
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # File handler
    file_handler = logging.FileHandler('logs/telemost_bitrix_app.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    # Console handler for debugging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    app.logger.addHandler(console_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Telemost-Bitrix application startup')

    # Middleware для поддержки BASE_PATH (reverse proxy)
    class PrefixMiddleware:
        def __init__(self, app, prefix=''):
            self.app = app
            self.prefix = prefix.rstrip('/')

        def __call__(self, environ, start_response):
            if self.prefix and environ['PATH_INFO'].startswith(self.prefix):
                environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
                environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)

    # Применяем middleware если указан BASE_PATH
    base_path = app.config.get('BASE_PATH', '')
    if base_path:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=base_path)
        app.logger.info(f'Application configured with BASE_PATH: {base_path}')

    # Import models here to avoid circular imports
    from models.bitrix24 import Bitrix24API
    from models.telemost import TelemostAPI
    
    # Alternative approach - initialize on demand
    def get_bitrix_api():
        if not hasattr(app, 'bitrix_api'):
            app.bitrix_api = Bitrix24API()
        return app.bitrix_api

    def get_telemost_api():
        if not hasattr(app, 'telemost_api'):
            app.telemost_api = TelemostAPI()
        return app.telemost_api
    
    def merge_params():
        """Merge GET and POST parameters like in the working Node.js app"""
        params = {}

        # Add GET parameters
        params.update(request.args.to_dict())

        # Add POST parameters (form or JSON)
        if request.is_json:
            json_data = request.get_json() or {}
            params.update(json_data)
        elif request.form:
            params.update(request.form.to_dict())
        else:
            # Parse raw data if it looks like form data
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data and '=' in raw_data:
                    form_data = parse_qs(raw_data)
                    params.update({k: v[0] if len(v) == 1 else v for k, v in form_data.items()})
            except:
                pass

        return params

    def get_member_id():
        """Get member_id from request params or session"""
        # Try to get from request params first
        params = merge_params()
        member_id = params.get('member_id')

        if member_id:
            # Store in session for future requests
            session['member_id'] = member_id
            return member_id

        # Fallback to session
        return session.get('member_id')


    def get_user_from_request():
        """Get user info from request parameters (sent from frontend via BX24 SDK)"""
        params = merge_params()
        user_id = params.get('user_id', 'unknown')
        user_name = params.get('user_name', 'Unknown User')

        app.logger.info(f'User from request: ID={user_id}, Name={user_name}')

        return {
            'id': user_id,
            'name': user_name
        }

    @app.route('/', methods=['GET', 'POST'])
    def index():
        """Main application page - handles both GET and POST (from Bitrix24)"""
        # Handle POST requests (when app is opened in Bitrix24)
        if request.method == 'POST':
            params = merge_params()
            app.logger.info(f"POST to / received params: {params}")

            # Extract and store Bitrix24 auth tokens if provided
            domain = params.get('DOMAIN')
            auth_id = params.get('AUTH_ID')
            refresh_id = params.get('REFRESH_ID')
            expires = params.get('AUTH_EXPIRES', '3600')
            member_id = params.get('member_id')

            if domain and auth_id:
                # Сохранить member_id в session для совместимости
                if member_id:
                    session['member_id'] = member_id
                    app.logger.info(f'Saved member_id to session: {member_id}')

                app.logger.info(f'Saved auth data. Domain: {domain}, MemberID: {member_id}')

            # Also continue to render the page
            # Bitrix auth is handled by BX24 SDK on frontend
            bitrix_auth = True  # Always true when opened via Bitrix24
            # Check if Yandex token is configured in environment
            telemost_configured = app.config.get('YANDEX_OAUTH_TOKEN') is not None
            # If permanent token is configured but not in session, add it to session
            if telemost_configured and not session.get('yandex_access_token'):
                session['yandex_access_token'] = app.config.get('YANDEX_OAUTH_TOKEN')
            telemost_auth = session.get('yandex_access_token') is not None

            return render_template('index.html',
                                 bitrix_auth=bitrix_auth,
                                 telemost_auth=telemost_auth)

        # Handle GET requests (direct access)
        # Bitrix auth is handled by BX24 SDK on frontend
        bitrix_auth = True  # Assume opened via Bitrix24
        # Check if Yandex token is configured in environment
        telemost_configured = current_app.config.get('YANDEX_OAUTH_TOKEN') is not None
        # If permanent token is configured but not in session, add it to session
        if telemost_configured and not session.get('yandex_access_token'):
            session['yandex_access_token'] = current_app.config.get('YANDEX_OAUTH_TOKEN')
        telemost_auth = session.get('yandex_access_token') is not None

        return render_template('index.html',
                             bitrix_auth=bitrix_auth,
                             telemost_auth=telemost_auth)

    @app.route('/install', methods=['GET', 'POST'])
    def install():
        """Installation endpoint for Bitrix24 application - following the working Node.js pattern"""
        params = merge_params()
        print(f"Install route - received params: {params}")
        
        event = params.get('event')
        placement = params.get('PLACEMENT')
        
        # Handle installation via ONAPPINSTALL event
        if event == 'ONAPPINSTALL' and 'auth' in params:
            auth = params['auth']
            if isinstance(auth, dict) and 'domain' in auth and 'access_token' in auth:
                # Store authentication data
                session['bitrix_access_token'] = auth.get('access_token')
                session['bitrix_refresh_token'] = auth.get('refresh_token', '')
                session['bitrix_domain'] = auth.get('domain', '')
                session['bitrix_member_id'] = auth.get('member_id', '')
                session['bitrix_expires_in'] = auth.get('expires_in', 3600)
                
                # Return installation finish page
                html_content = '''
                <!DOCTYPE html>
                <html>
                  <head>
                    <meta charset="UTF-8">
                    <title>Установка приложения</title>
                    <script src="//api.bitrix24.com/api/v1/"></script>
                  </head>
                  <body>
                    <script>
                      BX24.init(function() {
                        BX24.installFinish();
                      });
                    </script>
                    <h2>Приложение "Yandex Telemost" успешно установлено!</h2>
                    <p>Теперь вы можете использовать приложение из меню Битрикс24.</p>
                  </body>
                </html>
                '''
                response = make_response(html_content)
                response.headers['Content-Type'] = 'text/html; charset=utf-8'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response

        # Handle installation via DEFAULT placement
        if placement == 'DEFAULT':
            domain = params.get('DOMAIN')
            auth_id = params.get('AUTH_ID')
            refresh_id = params.get('REFRESH_ID')
            expires = params.get('AUTH_EXPIRES', '3600')
            member_id = params.get('member_id')
            
            if domain and auth_id:
                # Store authentication data
                session['bitrix_access_token'] = auth_id
                session['bitrix_refresh_token'] = refresh_id or ''
                session['bitrix_domain'] = domain
                session['bitrix_member_id'] = member_id or ''
                session['bitrix_expires_in'] = int(expires) if expires.isdigit() else 3600
                
                # Return installation finish page
                html_content = '''
                <!DOCTYPE html>
                <html>
                  <head>
                    <meta charset="UTF-8">
                    <title>Установка приложения</title>
                    <script src="//api.bitrix24.com/api/v1/"></script>
                  </head>
                  <body>
                    <script>
                      BX24.init(function() {
                        BX24.installFinish();
                      });
                    </script>
                    <h2>Приложение "Yandex Telemost" успешно установлено!</h2>
                  </body>
                </html>
                '''
                response = make_response(html_content)
                response.headers['Content-Type'] = 'text/html; charset=utf-8'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response

        # If parameters don't match, return error page
        html_content = f'''
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="UTF-8">
            <title>Ошибка установки</title>
          </head>
          <body>
            <h2>Ошибка установки приложения</h2>
            <p>Не удалось получить данные авторизации от Битрикс24.</p>
            <pre>{json.dumps(params, indent=2, ensure_ascii=False)}</pre>
          </body>
        </html>
        '''
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response, 400

    @app.route('/index', methods=['GET', 'POST'])
    def index_page():
        """Handle first opening of the application"""
        params = merge_params()

        domain = params.get('DOMAIN')
        auth_id = params.get('AUTH_ID')
        refresh_id = params.get('REFRESH_ID')
        expires = params.get('AUTH_EXPIRES', '3600')
        member_id = params.get('member_id')

        # Store tokens if available
        if domain and auth_id:
            # Сохранить member_id в session для совместимости
            if member_id:
                session['member_id'] = member_id
                app.logger.info(f'Saved member_id to session: {member_id}')

            app.logger.info(f'Saved auth data on /index. Domain: {domain}, MemberID: {member_id}')

        # Redirect to the app
        return redirect(url_for('index'))

    @app.route('/auth/bitrix24')
    def auth_bitrix24():
        """Handle Bitrix24 OAuth callback"""
        # This would handle the callback after Bitrix24 authentication
        code = request.args.get('code')
        if code:
            # Exchange code for tokens using Bitrix24 API
            bitrix_api = get_bitrix_api()
            token_data = bitrix_api.get_access_token(code)
            if token_data and 'access_token' in token_data:
                session['bitrix_access_token'] = token_data['access_token']
                session['bitrix_refresh_token'] = token_data['refresh_token']
                session['bitrix_domain'] = token_data.get('domain', '')
                session.permanent = True
                return redirect(url_for('index'))
        return redirect(url_for('index'))
    
    @app.route('/auth/yandex')
    def auth_yandex():
        """Initiate Yandex OAuth flow"""
        # Redirect to Yandex OAuth authorization page
        import urllib.parse
        params = {
            'response_type': 'code',
            'client_id': app.config['YANDEX_CLIENT_ID'],
            'redirect_uri': app.config['YANDEX_REDIRECT_URI'],
            'scope': 'telemost:manage'
        }
        auth_url = f"{app.config['YANDEX_AUTH_URL']}?{urllib.parse.urlencode(params)}"
        return redirect(auth_url)
    
    @app.route('/auth/yandex/callback')
    def auth_yandex_callback():
        """Handle Yandex OAuth callback"""
        code = request.args.get('code')
        if code:
            # Exchange code for tokens
            telemost_api = get_telemost_api()
            token_data = telemost_api.get_access_token(code)
            if token_data and 'access_token' in token_data:
                session['yandex_access_token'] = token_data['access_token']
                session['yandex_refresh_token'] = token_data.get('refresh_token', '')
                session.permanent = True
                return redirect(url_for('index'))
        return redirect(url_for('index'))
    
    @app.route('/api/conferences')
    def get_conferences():
        """Get list of conferences - only for current user"""
        # Get current user info from request parameters (sent from frontend)
        user_info = get_user_from_request()
        user_id = user_info['id']

        # Check if we have Yandex token to get actual conferences
        yandex_token = session.get('yandex_access_token') or current_app.config.get('YANDEX_OAUTH_TOKEN')

        if yandex_token:
            # Try to get real conferences from Yandex API
            try:
                telemost_api = get_telemost_api()
                yandex_conferences = telemost_api.get_conferences(yandex_token)

                if 'error' not in yandex_conferences:
                    # Sync with our local database - save all conferences returned by Yandex
                    if isinstance(yandex_conferences, list):
                        for conf in yandex_conferences:
                            # Format conference data to match our database schema
                            conf_data = {
                                'id': conf.get('id', conf.get('ID')),
                                'name': conf.get('name'),
                                'type': conf.get('type', 'conference'),
                                'description': conf.get('description', ''),
                                'startDate': conf.get('start_date', conf.get('startDate', '')),
                                'startTime': conf.get('start_time', conf.get('startTime', '')),
                                'cohosts': conf.get('cohosts', conf.get('participants', [])),
                                'createCalendarEvent': conf.get('create_calendar_event', conf.get('createCalendarEvent', False)),
                                'inviteUsers': conf.get('invite_users', conf.get('inviteUsers', False)),
                                'liveStreamTitle': conf.get('live_stream_title', conf.get('liveStreamTitle', '')),
                                'liveStreamDescription': conf.get('live_stream_description', conf.get('liveStreamDescription', '')),
                                'ownerId': user_id,
                                'ownerName': user_info['name'],
                                'status': conf.get('status', 'scheduled'),
                                'link': conf.get('link', conf.get('LINK', '')),
                                'createdAt': conf.get('created_at', conf.get('createdAt'))
                            }

                            # Save to database (upsert)
                            try:
                                save_conference(conf_data)
                            except:
                                pass  # Continue if individual save fails

                        # Return conferences only for this user
                        local_conferences = get_user_conferences(user_id)
                        return jsonify(local_conferences)
                    else:
                        # If response is not a list but has conferences in another format
                        # Check if it's wrapped in a result object
                        if isinstance(yandex_conferences, dict):
                            if 'result' in yandex_conferences and isinstance(yandex_conferences['result'], list):
                                conferences_list = yandex_conferences['result']
                                # Process and sync conferences...
                                for conf in conferences_list:
                                    conf_data = {
                                        'id': conf.get('id', conf.get('ID')),
                                        'name': conf.get('name'),
                                        'type': conf.get('type', 'conference'),
                                        'description': conf.get('description', ''),
                                        'startDate': conf.get('start_date', conf.get('startDate', '')),
                                        'startTime': conf.get('start_time', conf.get('startTime', '')),
                                        'cohosts': conf.get('cohosts', conf.get('participants', [])),
                                        'createCalendarEvent': conf.get('create_calendar_event', conf.get('createCalendarEvent', False)),
                                        'inviteUsers': conf.get('invite_users', conf.get('inviteUsers', False)),
                                        'liveStreamTitle': conf.get('live_stream_title', conf.get('liveStreamTitle', '')),
                                        'liveStreamDescription': conf.get('live_stream_description', conf.get('liveStreamDescription', '')),
                                        'ownerId': user_id,
                                        'ownerName': user_info['name'],
                                        'status': conf.get('status', 'scheduled'),
                                        'link': conf.get('link', conf.get('LINK', '')),
                                        'createdAt': conf.get('created_at', conf.get('createdAt'))
                                    }

                                    try:
                                        save_conference(conf_data)
                                    except:
                                        pass  # Continue if individual save fails

                                # Return conferences only for this user
                                local_conferences = get_user_conferences(user_id)
                                return jsonify(local_conferences)

                        # Return whatever format was received (but filter by user)
                        local_conferences = get_user_conferences(user_id)
                        return jsonify(local_conferences)
                else:
                    # Failed to get from Yandex, fall back to local database
                    local_conferences = get_user_conferences(user_id)
                    return jsonify(local_conferences)
            except Exception as e:
                # If there's an error with Yandex API, fall back to local database
                local_conferences = get_user_conferences(user_id)
                return jsonify(local_conferences)
        else:
            # No Yandex token, get from local database
            local_conferences = get_user_conferences(user_id)
            return jsonify(local_conferences)
    
    @app.route('/api/conferences', methods=['POST'])
    def create_conference():
        """Create a new conference - in Yandex if token available, otherwise just store locally"""
        data = request.get_json()

        # Get current user info from request parameters (sent from frontend)
        user_info = get_user_from_request()
        user_id = user_info['id']
        user_name = user_info['name']

        # Check if we have Yandex token to make actual API call
        yandex_token = session.get('yandex_access_token') or current_app.config.get('YANDEX_OAUTH_TOKEN')

        if yandex_token:
            # Make actual call to Yandex API
            # Only send name and cohosts as per requirements
            try:
                telemost_api = get_telemost_api()
                result = telemost_api.api_call(
                    'POST',
                    'conferences',
                    access_token=yandex_token,
                    data={
                        'type': data.get('type', 'conference'),
                        'name': data.get('name'),
                        'cohosts': data.get('cohosts', [])
                    }
                )

                # Check if the API call was successful
                if 'error' not in result:
                    # Successfully created in Yandex, now save to our database with the real link
                    conference_data = {
                        'type': data.get('type', 'conference'),
                        'name': data.get('name'),
                        'description': '',
                        'startDate': '',
                        'startTime': '',
                        'cohosts': data.get('cohosts', []),
                        'createCalendarEvent': False,
                        'inviteUsers': False,
                        'liveStreamTitle': '',
                        'liveStreamDescription': '',
                        'ownerId': user_id,
                        'ownerName': user_name,
                        'status': 'scheduled',
                        # Use the actual link from Yandex API response
                        'link': result.get('link', result.get('LINK', f"https://telemost.yandex.ru/j/{result.get('id', result.get('ID', len(get_user_conferences(user_id)) + 1))}")),
                        'id': result.get('id', result.get('ID', len(get_user_conferences(user_id)) + 1))
                    }

                    # Save to database
                    try:
                        save_conference(conference_data)
                        return jsonify(conference_data)
                    except Exception as e:
                        # Still return the conference data from Yandex API even if DB save fails
                        return jsonify(result)
                else:
                    # API call failed, return the error
                    return jsonify(result), 400
            except Exception as e:
                # If there's an error calling Yandex API, return error
                return jsonify({'error': f'API call failed: {str(e)}'}), 500
        else:
            # No Yandex token, just save locally
            conference_data = {
                'type': data.get('type', 'conference'),
                'name': data.get('name'),
                'description': '',
                'startDate': '',
                'startTime': '',
                'cohosts': data.get('cohosts', []),
                'createCalendarEvent': False,
                'inviteUsers': False,
                'liveStreamTitle': '',
                'liveStreamDescription': '',
                'ownerId': user_id,
                'ownerName': user_name,
                'status': 'scheduled',
                'link': f"https://telemost.yandex.ru/j/{len(get_user_conferences(user_id)) + 1}"  # fallback link
            }

            # Save to database
            try:
                conference_id = save_conference(conference_data)
                conference_data['id'] = int(conference_id) if conference_id else len(get_all_conferences())
                return jsonify(conference_data)
            except Exception as e:
                return jsonify({'error': f'Failed to save conference: {str(e)}'}), 500
    
    @app.route('/api/conferences/<int:conf_id>', methods=['DELETE'])
    def delete_conference(conf_id):
        """Delete a conference only from our database (Yandex Telemost doesn't have delete API)"""
        # Delete from local database only (there's no API for deleting conferences in Yandex Telemost)
        try:
            success = delete_conference(conf_id)  # Using function from database module
            if success:
                return jsonify({'success': True, 'message': 'Conference deleted successfully'})
            else:
                return jsonify({'error': 'Conference not found'}), 404
        except Exception as e:
            return jsonify({'error': f'Failed to delete conference: {str(e)}'}), 500

    @app.route('/api/conferences/<int:conf_id>', methods=['PUT'])
    def update_conference(conf_id):
        """Update a conference in database and in Yandex if token available"""
        data = request.get_json()

        # Check if we have Yandex token to make actual API call
        yandex_token = session.get('yandex_access_token') or current_app.config.get('YANDEX_OAUTH_TOKEN')

        if yandex_token:
            # Make actual call to Yandex API to update the conference
            try:
                telemost_api = get_telemost_api()
                result = telemost_api.api_call(
                    'PUT',
                    f'conferences/{conf_id}',
                    access_token=yandex_token,
                    data=data
                )

                # Don't return immediately if API call succeeds, also update our DB
                # This allows us to maintain sync between Yandex and our local DB
            except:
                # If API call fails, continue to update local DB
                pass

        # Update local database
        try:
            success = update_conference(conf_id, data)
            if success:
                updated_conf = get_conference_by_id(conf_id)
                return jsonify(updated_conf)
            else:
                return jsonify({'error': 'Conference not found'}), 404
        except Exception as e:
            return jsonify({'error': f'Failed to update conference: {str(e)}'}), 500
    
    @app.route('/api/users/current')
    def current_user():
        """Get current Bitrix24 user info"""
        # Get user info from request parameters (sent from frontend)
        user_info = get_user_from_request()

        return jsonify({
            'user': user_info,
            'note': 'User info is now obtained from request parameters (user_id, user_name) sent from frontend via BX24 SDK'
        })
    
    @app.route('/logout')
    def logout():
        """Logout user and clear session"""
        session.clear()
        return redirect(url_for('index'))
    
    # Health check endpoint
    @app.route('/health')
    def health():
        """Health check endpoint for Docker and load balancers"""
        return jsonify({
            'status': 'healthy',
            'service': 'telemost-bitrix-app',
            'base_path': app.config.get('BASE_PATH', '')
        }), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)