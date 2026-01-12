from functools import wraps
from flask import session, redirect, url_for, request, jsonify
import jwt
from datetime import datetime, timedelta


def login_required(f):
    """Decorator to require login for specific routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'bitrix_access_token' not in session and 'yandex_access_token' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def bitrix_auth_required(f):
    """Decorator to require Bitrix24 authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'bitrix_access_token' not in session:
            return jsonify({'error': 'Bitrix24 authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def telemost_auth_required(f):
    """Decorator to require Yandex Telemost authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'yandex_access_token' not in session:
            return jsonify({'error': 'Yandex Telemost authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def generate_csrf_token():
    """Generate a CSRF token for form protection"""
    if '_csrf_token' not in session:
        import secrets
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']


def validate_csrf_token():
    """Validate the CSRF token from the request"""
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    return token and token == session.get('_csrf_token')


def is_valid_email(email):
    """Simple email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def format_datetime_for_display(dt_str):
    """Format datetime string for display"""
    if not dt_str:
        return ""
    
    try:
        # Parse various datetime formats
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(dt_str)
        
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return dt_str


def format_duration(seconds):
    """Format duration in seconds to HH:MM:SS format"""
    if not seconds:
        return "00:00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"