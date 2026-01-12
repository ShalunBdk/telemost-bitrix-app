import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///telemost_bitrix.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Base path for reverse proxy (e.g., /telemost-bitrix)
    BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')
    APPLICATION_ROOT = os.environ.get('SCRIPT_NAME', '').rstrip('/')
    
    # Bitrix24 Configuration
    BITRIX24_CLIENT_ID = os.environ.get('BITRIX24_CLIENT_ID')
    BITRIX24_CLIENT_SECRET = os.environ.get('BITRIX24_CLIENT_SECRET')
    BITRIX24_WEBHOOK_URL = os.environ.get('BITRIX24_WEBHOOK_URL')  # Alternative to client credentials
    
    # Yandex Telemost Configuration
    YANDEX_CLIENT_ID = os.environ.get('YANDEX_CLIENT_ID')
    YANDEX_CLIENT_SECRET = os.environ.get('YANDEX_CLIENT_SECRET')
    YANDEX_REDIRECT_URI = os.environ.get('YANDEX_REDIRECT_URI') or 'http://localhost:5000/auth/yandex/callback'
    YANDEX_AUTH_URL = 'https://oauth.yandex.ru/authorize'
    YANDEX_TOKEN_URL = 'https://oauth.yandex.ru/token'
    YANDEX_API_BASE = 'https://telemost.yandex.ru/api/v1'
    YANDEX_OAUTH_TOKEN = os.environ.get('YANDEX_OAUTH_TOKEN')
    
    # Session configuration for iframe support (Bitrix24)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    # Use 'None' for iframe support with HTTPS (required for Bitrix24 iframe)
    SESSION_COOKIE_SAMESITE = 'None'
    # SESSION_COOKIE_SECURE must be True when SameSite=None (works with HTTPS tunnel)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = 'telemost_session'

    # Logging
    LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL') or 'INFO'