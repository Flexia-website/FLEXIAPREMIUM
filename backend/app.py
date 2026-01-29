# backend/app.py - COMPLETE PRODUCTION READY v13.0
# FLEXIA Platform - FULLY FEATURED WITH ALL ENDPOINTS AND FIXES

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
import re
from datetime import datetime, timedelta, date
from decimal import Decimal
from flask import Flask, jsonify, request, send_from_directory, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired, TimedJSONWebSignatureSerializer
from functools import wraps
import threading
import time
import subprocess
import shutil
from logging.handlers import RotatingFileHandler, SMTPHandler
import psycopg2
from psycopg2.pool import ThreadedConnectionPool, SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import redis
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from werkzeug.middleware.proxy_fix import ProxyFix

# ======================= CONFIGURATION =======================
class Config:
    # Database
    if os.environ.get('DATABASE_URL'):
        DB_URL = os.environ.get('DATABASE_URL')
    else:
        DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flexia.db')
    
    # Redis for caching and rate limiting
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # File paths
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    LOGS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    BACKUP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    
    # Frontend
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
    PASSWORD_RESET_SECRET = os.environ.get('PASSWORD_RESET_SECRET', secrets.token_hex(32))
    
    # Game settings
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 7500
    TIKTOK_REWARD = 150
    SNAKE_REWARD = 200
    COIN_FLIP_MIN_BET = 100
    COIN_FLIP_MAX_BET = 50000
    PLINKO_MIN_BET = 100
    PLINKO_MAX_BET = 50000
    MAX_BALANCE = 10000000  # 10 million max balance
    SESSION_DURATION_HOURS = 24
    DEFAULT_WITHDRAWAL_DAYS = [7, 14, 25, 30]
    
    # Game daily limits
    GAME_DAILY_LIMITS = {
        'snake': 10,
        'coinflip': 5,
        'plinko': 5,
        'spin': 1,
        'tiktok': 1,
        'dice': 5,
        'scratch': 3
    }
    
    # Achievement rewards
    ACHIEVEMENT_REWARDS = {
        'first_game': 500,
        'gamer': 5000,
        'game_master': 15000,
        'snake_pro': 7500,
        'lucky_streak': 10000,
        'coin_flipper': 6000,
        'plinko_champion': 8000,
        'thousandaire': 1000,
        'millionaire_in_progress': 10000,
        'high_roller': 25000,
        'first_withdrawal': 5000,
        'daily_grinder': 3000,
        'addicted': 8000,
        'referral_starter': 10000,
        'referral_master': 30000,
        'transaction_veteran': 4000
    }
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate limiting
    RATE_LIMITS = {
        'login': 5,
        'register': 3,
        'game': 10,
        'withdrawal': 2,
        'api': 100
    }
    
    # Email settings (optional)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@flexia.com')
    
    # File upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # API keys (optional)
    CAPTCHA_SECRET = os.environ.get('CAPTCHA_SECRET')
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    
    # Maintenance mode
    MAINTENANCE_MODE = os.environ.get('MAINTENANCE_MODE', 'False').lower() == 'true'

CONFIG = Config()

app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = CONFIG.MAX_CONTENT_LENGTH

# Add ProxyFix for proper IP handling behind proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# ======================= SETUP LOGGING =======================
def setup_logging():
    """Setup comprehensive logging"""
    # Create directories if they don't exist
    for folder in [CONFIG.LOGS_FOLDER, CONFIG.BACKUP_FOLDER, CONFIG.UPLOAD_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    # JSON formatter for structured logging
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                'timestamp': self.formatTime(record),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.threadName,
            }
            
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
            
            # Add request context if available
            if hasattr(g, 'request_id'):
                log_data['request_id'] = g.request_id
            
            return json.dumps(log_data)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(CONFIG.LOGS_FOLDER, 'flexia.log'), 
        maxBytes=10485760,  # 10MB
        backupCount=50
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.INFO)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        os.path.join(CONFIG.LOGS_FOLDER, 'error.log'),
        maxBytes=10485760,
        backupCount=20
    )
    error_handler.setFormatter(JSONFormatter())
    error_handler.setLevel(logging.ERROR)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if os.getenv('ENV') != 'production' else logging.INFO)
    
    # Email handler for critical errors (optional)
    if CONFIG.MAIL_USERNAME and CONFIG.MAIL_PASSWORD:
        mail_handler = SMTPHandler(
            mailhost=(CONFIG.MAIL_SERVER, CONFIG.MAIL_PORT),
            fromaddr=CONFIG.MAIL_DEFAULT_SENDER,
            toaddrs=[CONFIG.MAIL_USERNAME],
            subject='FLEXIA Critical Error',
            credentials=(CONFIG.MAIL_USERNAME, CONFIG.MAIL_PASSWORD),
            secure=() if CONFIG.MAIL_USE_TLS else None
        )
        mail_handler.setLevel(logging.CRITICAL)
        mail_handler.setFormatter(logging.Formatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
'''))
        app.logger.addHandler(mail_handler)
    
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Add our handlers
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    
    # Set log levels
    app.logger.setLevel(logging.DEBUG if os.getenv('ENV') != 'production' else logging.INFO)
    
    # Set werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.addHandler(error_handler)
    werkzeug_logger.setLevel(logging.WARNING)
    
    # Log startup
    app.logger.info('Logging system initialized', extra={
        'environment': os.getenv('ENV', 'development'),
        'log_level': app.logger.level
    })

setup_logging()

# ======================= REDIS SETUP =======================
redis_client = None
try:
    if CONFIG.REDIS_URL:
        redis_client = redis.from_url(CONFIG.REDIS_URL, decode_responses=True)
        app.logger.info('Redis connected successfully')
except Exception as e:
    app.logger.warning(f'Redis connection failed: {e}. Using in-memory cache.')

# ======================= HELPER FUNCTIONS =======================
class Cache:
    """Cache helper using Redis or in-memory fallback"""
    @staticmethod
    def get(key):
        if redis_client:
            try:
                value = redis_client.get(key)
                if value:
                    return json.loads(value)
            except:
                pass
        return None
    
    @staticmethod
    def set(key, value, expire=3600):
        if redis_client:
            try:
                redis_client.setex(key, expire, json.dumps(value))
            except:
                pass
    
    @staticmethod
    def delete(key):
        if redis_client:
            try:
                redis_client.delete(key)
            except:
                pass
    
    @staticmethod
    def incr(key, amount=1):
        if redis_client:
            try:
                return redis_client.incrby(key, amount)
            except:
                return None
        return None
    
    @staticmethod
    def decr(key, amount=1):
        if redis_client:
            try:
                return redis_client.decrby(key, amount)
            except:
                return None
        return None

class RateLimiter:
    """Rate limiting with Redis support"""
    @staticmethod
    def is_limited(key, limit, period=60):
        """Check if rate limit exceeded"""
        if not redis_client:
            return False
        
        try:
            current = redis_client.get(key)
            if current and int(current) >= limit:
                return True
            return False
        except:
            return False
    
    @staticmethod
    def increment(key, period=60):
        """Increment rate limit counter"""
        if not redis_client:
            return
        
        try:
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, period)
            pipe.execute()
        except:
            pass

def generate_request_id():
    """Generate unique request ID"""
    return str(uuid.uuid4())

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    # Remove non-digit characters
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10

def sanitize_input(text, max_length=255):
    """Sanitize input to prevent XSS and SQL injection"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Escape special characters
    text = text.replace("'", "''").replace('"', '\"')
    
    # Trim and limit length
    text = text.strip()[:max_length]
    
    return text

def format_currency(amount):
    """Format currency amount"""
    return f"₦{amount:,.2f}"

def humanize_time(dt):
    """Convert datetime to human readable format"""
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 365:
        return f"{diff.days // 365} year{'s' if diff.days // 365 > 1 else ''} ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month{'s' if diff.days // 30 > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hour{'s' if diff.seconds // 3600 > 1 else ''} ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minute{'s' if diff.seconds // 60 > 1 else ''} ago"
    else:
        return "just now"

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in CONFIG.ALLOWED_EXTENSIONS

def save_file(file, subfolder=''):
    """Save uploaded file"""
    if file and allowed_file(file.filename):
        filename = secrets.token_hex(8) + '.' + file.filename.rsplit('.', 1)[1].lower()
        folder = os.path.join(CONFIG.UPLOAD_FOLDER, subfolder)
        
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return f"/uploads/{subfolder}/{filename}" if subfolder else f"/uploads/{filename}"
    
    return None

# ======================= REQUEST HOOKS =======================
@app.before_request
def before_request():
    """Run before each request"""
    # Generate request ID
    g.request_id = generate_request_id()
    g.start_time = time.time()
    
    # Check maintenance mode
    if CONFIG.MAINTENANCE_MODE and not request.path.startswith('/api/health'):
        return jsonify({
            "success": False,
            "message": "System is under maintenance. Please try again later.",
            "maintenance": True
        }), 503
    
    # Add request to logs
    app.logger.info(f"Request started: {request.method} {request.path}", extra={
        'request_id': g.request_id,
        'ip': request.remote_addr,
        'user_agent': request.user_agent.string[:200] if request.user_agent else 'Unknown'
    })
    
    # Rate limiting for API endpoints
    if request.path.startswith('/api/'):
        ip_key = f"rate_limit:{request.remote_addr}"
        if RateLimiter.is_limited(ip_key, CONFIG.RATE_LIMITS['api']):
            app.logger.warning(f"Rate limit exceeded for IP: {request.remote_addr}")
            return jsonify({
                "success": False,
                "message": "Too many requests. Please slow down.",
                "retry_after": 60
            }), 429
        
        RateLimiter.increment(ip_key)

@app.after_request
def after_request(response):
    """Run after each request"""
    # Calculate request duration
    duration = time.time() - g.start_time
    
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['X-Request-ID'] = g.request_id
    
    # Add CORS headers
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    
    # Add CSP header
    csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self';"
    response.headers['Content-Security-Policy'] = csp
    
    # Log response
    app.logger.info(f"Request completed: {request.method} {request.path} - {response.status_code}", extra={
        'request_id': g.request_id,
        'duration': f"{duration:.3f}s",
        'status': response.status_code,
        'response_size': len(response.get_data())
    })
    
    return response

@app.teardown_request
def teardown_request(exception=None):
    """Cleanup after request"""
    if exception:
        app.logger.error(f"Request error: {exception}", extra={
            'request_id': g.request_id,
            'error': str(exception)
        })

# ======================= ERROR HANDLERS =======================
class APIError(Exception):
    """Custom API error class"""
    def __init__(self, message, status_code=400, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

@app.errorhandler(APIError)
def handle_api_error(error):
    """Handle API errors"""
    response = {
        "success": False,
        "message": error.message,
        "error_code": error.error_code,
        "status_code": error.status_code
    }
    
    if error.details:
        response["details"] = error.details
    
    app.logger.warning(f"API Error: {error.message}", extra={
        'request_id': g.request_id,
        'status_code': error.status_code,
        'error_code': error.error_code
    })
    
    return jsonify(response), error.status_code

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        raise APIError("Endpoint not found", 404, "NOT_FOUND")
    
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(405)
def method_not_allowed_error(error):
    """Handle 405 errors"""
    raise APIError("Method not allowed", 405, "METHOD_NOT_ALLOWED")

@app.errorhandler(413)
def request_too_large_error(error):
    """Handle 413 errors"""
    raise APIError("File too large. Maximum size is 16MB.", 413, "FILE_TOO_LARGE")

@app.errorhandler(429)
def too_many_requests_error(error):
    """Handle 429 errors"""
    raise APIError("Too many requests. Please slow down.", 429, "RATE_LIMITED")

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f"Internal server error: {error}", extra={
        'request_id': g.request_id,
        'traceback': traceback.format_exc()
    })
    
    if request.path.startswith('/api/'):
        raise APIError("Internal server error. Please try again later.", 500, "INTERNAL_ERROR")
    
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= DATABASE CONNECTION =======================
db_pool = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    
    if os.environ.get('DATABASE_URL'):
        try:
            db_pool = ThreadedConnectionPool(
                5,  # min connections
                50, # max connections
                dsn=os.environ['DATABASE_URL'],
                cursor_factory=RealDictCursor
            )
            app.logger.info('Database connection pool initialized')
        except Exception as e:
            app.logger.error(f'Failed to initialize connection pool: {e}')
            db_pool = None
    else:
        app.logger.info('SQLite mode - connection pooling not needed')

def get_db():
    """Get database connection"""
    global db_pool
    
    if 'db' not in g:
        if db_pool:
            try:
                g.db = db_pool.getconn()
                g.db.autocommit = False
            except Exception as e:
                app.logger.error(f'Error getting connection from pool: {e}')
                g.db = get_db_direct()
        else:
            g.db = get_db_direct()
    
    return g.db

def get_db_direct():
    """Get direct database connection (fallback)"""
    if os.environ.get('DATABASE_URL'):
        try:
            conn = psycopg2.connect(
                os.environ['DATABASE_URL'],
                cursor_factory=RealDictCursor
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            app.logger.error(f'Direct PostgreSQL connection failed: {e}')
            raise APIError("Database connection failed", 500, "DB_CONNECTION_FAILED")
    else:
        if os.getenv('ENV') == 'production':
            raise APIError("SQLite not allowed in production", 500, "DB_CONFIG_ERROR")
        import sqlite3
        from sqlite3 import Row
        
        conn = sqlite3.connect(CONFIG.DB_FILE, check_same_thread=False)
        conn.row_factory = Row
        return conn

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    
    if db is not None:
        if db_pool:
            try:
                db_pool.putconn(db)
            except:
                db.close()
        else:
            db.close()

@app.teardown_appcontext
def teardown_db(exception=None):
    """Close database at end of request"""
    close_db()

# ======================= AUTHENTICATION =======================
def create_session_token(user_id, is_admin=False):
    """Create JWT session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    payload = {
        'user_id': user_id,
        'is_admin': is_admin,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=CONFIG.SESSION_DURATION_HOURS)
    }
    return s.dumps(payload)

def verify_session_token(token):
    """Verify JWT session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        payload = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return payload.get('user_id'), payload.get('is_admin', False)
    except (BadSignature, SignatureExpired) as e:
        app.logger.warning(f'Invalid session token: {e}')
        return None, False

def create_password_reset_token(email):
    """Create password reset token"""
    s = TimedJSONWebSignatureSerializer(CONFIG.PASSWORD_RESET_SECRET, expires_in=3600)
    return s.dumps({'email': email}).decode('utf-8')

def verify_password_reset_token(token):
    """Verify password reset token"""
    s = TimedJSONWebSignatureSerializer(CONFIG.PASSWORD_RESET_SECRET)
    try:
        data = s.loads(token)
        return data.get('email')
    except:
        return None

def get_current_user():
    """Get current user from session"""
    token = request.cookies.get('session_token')
    if not token:
        return None
    
    user_id, is_admin = verify_session_token(token)
    if not user_id:
        return None
    
    conn = get_db()
    try:
        if os.environ.get('DATABASE_URL'):
            conn.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        else:
            conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = conn.fetchone()
        return dict(user) if user else None
    except Exception as e:
        app.logger.error(f'Error getting current user: {e}')
        return None
    finally:
        conn.close()

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise APIError("Authentication required", 401, "UNAUTHORIZED")
        
        # Check if account is suspended
        if user.get('suspended', False):
            raise APIError("Account suspended. Contact support.", 403, "ACCOUNT_SUSPENDED")
        
        # Check if email verified (if required)
        if user.get('email_verified') == False and request.path not in ['/api/user/verify-email', '/api/user/resend-verification']:
            raise APIError("Email verification required", 403, "EMAIL_NOT_VERIFIED")
        
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise APIError("Authentication required", 401, "UNAUTHORIZED")
        
        if not user.get('is_admin'):
            raise APIError("Admin access required", 403, "FORBIDDEN")
        
        return f(*args, **kwargs)
    return decorated

def require_2fa(f):
    """Decorator to require 2FA verification"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise APIError("Authentication required", 401, "UNAUTHORIZED")
        
        # Check if 2FA is enabled and verified
        if user.get('two_factor_enabled') and not session.get('2fa_verified'):
            raise APIError("2FA verification required", 403, "2FA_REQUIRED")
        
        return f(*args, **kwargs)
    return decorated

# ======================= DATABASE INITIALIZATION =======================
def init_db():
    """Initialize database with all tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    
    # Users table (expanded with all needed fields)
    users_table = '''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE,
        phone VARCHAR(20),
        password TEXT NOT NULL,
        balance DECIMAL(15, 2) DEFAULT 0.00,
        referral_code VARCHAR(20) UNIQUE,
        referred_by VARCHAR(20),
        is_admin BOOLEAN DEFAULT FALSE,
        is_super_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        last_active TIMESTAMP,
        last_ip VARCHAR(45),
        login_attempts INTEGER DEFAULT 0,
        locked_until TIMESTAMP,
        email_verified BOOLEAN DEFAULT FALSE,
        phone_verified BOOLEAN DEFAULT FALSE,
        verified_at TIMESTAMP,
        two_factor_enabled BOOLEAN DEFAULT FALSE,
        two_factor_secret VARCHAR(255),
        two_factor_backup_codes TEXT,
        profile_picture TEXT,
        cover_picture TEXT,
        bio TEXT,
        location VARCHAR(100),
        website VARCHAR(255),
        date_of_birth DATE,
        gender VARCHAR(20),
        ui_theme VARCHAR(20) DEFAULT 'light',
        language VARCHAR(10) DEFAULT 'en',
        timezone VARCHAR(50) DEFAULT 'UTC',
        notification_settings JSONB DEFAULT '{}',
        privacy_settings JSONB DEFAULT '{}',
        game_stats JSONB DEFAULT '{}',
        claimed_achievements JSONB DEFAULT '[]',
        achievements_progress JSONB DEFAULT '{}',
        points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        experience INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_daily_login DATE,
        total_earned DECIMAL(15, 2) DEFAULT 0.00,
        total_withdrawn DECIMAL(15, 2) DEFAULT 0.00,
        total_deposited DECIMAL(15, 2) DEFAULT 0.00,
        withdrawal_pin VARCHAR(255),
        withdrawal_restricted BOOLEAN DEFAULT FALSE,
        withdrawal_limit DECIMAL(15, 2) DEFAULT 0.00,
        custom_withdrawal_days JSONB,
        deposit_limit DECIMAL(15, 2) DEFAULT 0.00,
        max_bet_limit DECIMAL(15, 2) DEFAULT 0.00,
        session_token TEXT,
        reset_token TEXT,
        reset_token_expires TIMESTAMP,
        verification_token TEXT,
        verification_token_expires TIMESTAMP,
        security_questions JSONB,
        trusted_devices JSONB DEFAULT '[]',
        suspicious_activity_count INTEGER DEFAULT 0,
        account_status VARCHAR(20) DEFAULT 'active',
        suspension_reason TEXT,
        suspension_end TIMESTAMP,
        notes TEXT,
        metadata JSONB DEFAULT '{}',
        deleted_at TIMESTAMP,
        CONSTRAINT chk_balance CHECK (balance >= 0),
        CONSTRAINT chk_points CHECK (points >= 0)
    )''' if is_postgres else '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        phone TEXT,
        password TEXT NOT NULL,
        balance REAL DEFAULT 0.00,
        referral_code TEXT UNIQUE,
        referred_by TEXT,
        is_admin BOOLEAN DEFAULT 0,
        is_super_admin BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT,
        last_active TEXT,
        last_ip TEXT,
        login_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        email_verified BOOLEAN DEFAULT 0,
        phone_verified BOOLEAN DEFAULT 0,
        verified_at TEXT,
        two_factor_enabled BOOLEAN DEFAULT 0,
        two_factor_secret TEXT,
        two_factor_backup_codes TEXT,
        profile_picture TEXT,
        cover_picture TEXT,
        bio TEXT,
        location TEXT,
        website TEXT,
        date_of_birth TEXT,
        gender TEXT,
        ui_theme TEXT DEFAULT 'light',
        language TEXT DEFAULT 'en',
        timezone TEXT DEFAULT 'UTC',
        notification_settings TEXT DEFAULT '{}',
        privacy_settings TEXT DEFAULT '{}',
        game_stats TEXT DEFAULT '{}',
        claimed_achievements TEXT DEFAULT '[]',
        achievements_progress TEXT DEFAULT '{}',
        points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        experience INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_daily_login TEXT,
        total_earned REAL DEFAULT 0.00,
        total_withdrawn REAL DEFAULT 0.00,
        total_deposited REAL DEFAULT 0.00,
        withdrawal_pin TEXT,
        withdrawal_restricted BOOLEAN DEFAULT 0,
        withdrawal_limit REAL DEFAULT 0.00,
        custom_withdrawal_days TEXT,
        deposit_limit REAL DEFAULT 0.00,
        max_bet_limit REAL DEFAULT 0.00,
        session_token TEXT,
        reset_token TEXT,
        reset_token_expires TEXT,
        verification_token TEXT,
        verification_token_expires TEXT,
        security_questions TEXT,
        trusted_devices TEXT DEFAULT '[]',
        suspicious_activity_count INTEGER DEFAULT 0,
        account_status TEXT DEFAULT 'active',
        suspension_reason TEXT,
        suspension_end TEXT,
        notes TEXT,
        metadata TEXT DEFAULT '{}',
        deleted_at TEXT,
        CHECK (balance >= 0),
        CHECK (points >= 0)
    )'''
    
    # Create all tables
    tables = [
        users_table,
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            id VARCHAR(50) PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            status VARCHAR(20) NOT NULL,
            details JSONB,
            reference VARCHAR(100),
            gateway VARCHAR(50),
            gateway_response TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_transactions_user_id (user_id),
            INDEX idx_transactions_type (type),
            INDEX idx_transactions_status (status),
            INDEX idx_transactions_created_at (created_at)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            reference TEXT,
            gateway TEXT,
            gateway_response TEXT,
            ip_address TEXT,
            user_agent TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS game_plays (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            game_type VARCHAR(50) NOT NULL,
            bet_amount DECIMAL(15, 2),
            win_amount DECIMAL(15, 2),
            result JSONB,
            details JSONB,
            ip_address VARCHAR(45),
            device_info TEXT,
            play_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_game_plays_user_date (user_id, play_date),
            INDEX idx_game_plays_game_type (game_type)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS game_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_type TEXT NOT NULL,
            bet_amount REAL,
            win_amount REAL,
            result TEXT,
            details TEXT,
            ip_address TEXT,
            device_info TEXT,
            play_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS achievements (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            category VARCHAR(50),
            icon VARCHAR(100),
            reward_amount DECIMAL(15, 2) NOT NULL,
            reward_points INTEGER NOT NULL,
            requirement_type VARCHAR(50),
            requirement_value INTEGER,
            requirement_data JSONB,
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            category TEXT,
            icon TEXT,
            reward_amount REAL NOT NULL,
            reward_points INTEGER NOT NULL,
            requirement_type TEXT,
            requirement_value INTEGER,
            requirement_data TEXT,
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS user_achievements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            claimed_at TIMESTAMP,
            reward_given BOOLEAN DEFAULT FALSE,
            progress_current INTEGER DEFAULT 0,
            progress_target INTEGER,
            is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
            UNIQUE(user_id, achievement_id),
            INDEX idx_user_achievements_user_id (user_id)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            claimed_at TEXT,
            reward_given BOOLEAN DEFAULT 0,
            progress_current INTEGER DEFAULT 0,
            progress_target INTEGER,
            is_completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
            UNIQUE(user_id, achievement_id)
        )''',
        '''
        CREATE TABLE IF NOT EXISTS coupons (
            code VARCHAR(50) PRIMARY KEY,
            type VARCHAR(20) NOT NULL,
            amount DECIMAL(15, 2),
            percentage DECIMAL(5, 2),
            max_users INTEGER,
            used_count INTEGER DEFAULT 0,
            max_uses_per_user INTEGER DEFAULT 1,
            min_deposit DECIMAL(15, 2) DEFAULT 0,
            valid_from TIMESTAMP,
            valid_until TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB,
            INDEX idx_coupons_validity (valid_until, is_active)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            amount REAL,
            percentage REAL,
            max_users INTEGER,
            used_count INTEGER DEFAULT 0,
            max_uses_per_user INTEGER DEFAULT 1,
            min_deposit REAL DEFAULT 0,
            valid_from TEXT,
            valid_until TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )''',
        '''
        CREATE TABLE IF NOT EXISTS coupon_redemptions (
            id SERIAL PRIMARY KEY,
            coupon_code VARCHAR(50) NOT NULL,
            user_id INTEGER NOT NULL,
            amount DECIMAL(15, 2),
            transaction_id VARCHAR(50),
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(45),
            FOREIGN KEY (coupon_code) REFERENCES coupons(code) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_coupon_redemptions_user (user_id),
            INDEX idx_coupon_redemptions_coupon (coupon_code)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS coupon_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL,
            transaction_id TEXT,
            redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (coupon_code) REFERENCES coupons(code) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS banks (
            code VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            short_name VARCHAR(50),
            logo_url TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS banks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            short_name TEXT,
            logo_url TEXT,
            is_active BOOLEAN DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS user_banks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            bank_code VARCHAR(10) NOT NULL,
            account_number VARCHAR(20) NOT NULL,
            account_name VARCHAR(100) NOT NULL,
            is_default BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            verified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (bank_code) REFERENCES banks(code) ON DELETE CASCADE,
            UNIQUE(user_id, bank_code, account_number),
            INDEX idx_user_banks_user (user_id)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS user_banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bank_code TEXT NOT NULL,
            account_number TEXT NOT NULL,
            account_name TEXT NOT NULL,
            is_default BOOLEAN DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            verified_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (bank_code) REFERENCES banks(code) ON DELETE CASCADE,
            UNIQUE(user_id, bank_code, account_number)
        )''',
        '''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id SERIAL PRIMARY KEY,
            key VARCHAR(100) UNIQUE NOT NULL,
            value JSONB,
            description TEXT,
            category VARCHAR(50),
            is_public BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            description TEXT,
            category TEXT,
            is_public BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS tiktok_daily (
            id SERIAL PRIMARY KEY,
            date DATE UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount DECIMAL(15, 2) DEFAULT 150.00,
            is_active BOOLEAN DEFAULT TRUE,
            views_required INTEGER DEFAULT 100,
            likes_required INTEGER DEFAULT 50,
            shares_required INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS tiktok_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount REAL DEFAULT 150.00,
            is_active BOOLEAN DEFAULT 1,
            views_required INTEGER DEFAULT 100,
            likes_required INTEGER DEFAULT 50,
            shares_required INTEGER DEFAULT 10,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            data JSONB,
            is_read BOOLEAN DEFAULT FALSE,
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_notifications_user (user_id, is_read),
            INDEX idx_notifications_created (created_at)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT,
            is_read BOOLEAN DEFAULT 0,
            read_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id VARCHAR(50),
            old_value JSONB,
            new_value JSONB,
            ip_address VARCHAR(45),
            user_agent TEXT,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_audit_logs_user (user_id),
            INDEX idx_audit_logs_action (action),
            INDEX idx_audit_logs_created (created_at)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            user_agent TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            ticket_id VARCHAR(50) UNIQUE NOT NULL,
            subject VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            category VARCHAR(50),
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'open',
            assigned_to INTEGER,
            resolved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_support_tickets_status (status),
            INDEX idx_support_tickets_user (user_id)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticket_id TEXT UNIQUE NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            assigned_to INTEGER,
            resolved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
        )''',
        '''
        CREATE TABLE IF NOT EXISTS ticket_replies (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            attachments JSONB,
            is_internal BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_ticket_replies_ticket (ticket_id)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS ticket_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            attachments TEXT,
            is_internal BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id SERIAL PRIMARY KEY,
            number VARCHAR(20) UNIQUE NOT NULL,
            label VARCHAR(100),
            country_code VARCHAR(5),
            is_active BOOLEAN DEFAULT TRUE,
            is_default BOOLEAN DEFAULT FALSE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            label TEXT,
            country_code TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_default BOOLEAN DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS system_logs (
            id SERIAL PRIMARY KEY,
            level VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            context JSONB,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_system_logs_level (level),
            INDEX idx_system_logs_created (created_at)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            context TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            key VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            user_id INTEGER,
            permissions JSONB,
            last_used TIMESTAMP,
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_api_keys_key (key)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            user_id INTEGER,
            permissions TEXT,
            last_used TEXT,
            expires_at TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            device_info JSONB,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_sessions_token (session_token),
            INDEX idx_user_sessions_user (user_id, is_active)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            device_info TEXT,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            period VARCHAR(20) NOT NULL, -- daily, weekly, monthly, all_time
            game_type VARCHAR(50),
            score DECIMAL(15, 2) NOT NULL,
            rank INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, period, game_type),
            INDEX idx_leaderboard_period (period, game_type, score DESC)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            period TEXT NOT NULL,
            game_type TEXT,
            score REAL NOT NULL,
            rank INTEGER,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, period, game_type)
        )''',
        '''
        CREATE TABLE IF NOT EXISTS game_tournaments (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            game_type VARCHAR(50) NOT NULL,
            entry_fee DECIMAL(15, 2),
            prize_pool DECIMAL(15, 2),
            max_players INTEGER,
            current_players INTEGER DEFAULT 0,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            status VARCHAR(20) DEFAULT 'upcoming',
            rules JSONB,
            prizes JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_tournaments_status (status, start_time)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS game_tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            game_type TEXT NOT NULL,
            entry_fee REAL,
            prize_pool REAL,
            max_players INTEGER,
            current_players INTEGER DEFAULT 0,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT DEFAULT 'upcoming',
            rules TEXT,
            prizes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''',
        '''
        CREATE TABLE IF NOT EXISTS tournament_participants (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score DECIMAL(15, 2) DEFAULT 0,
            rank INTEGER,
            prize_won DECIMAL(15, 2) DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES game_tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, user_id),
            INDEX idx_tournament_participants_tournament (tournament_id, score DESC)
        )''' if is_postgres else '''
        CREATE TABLE IF NOT EXISTS tournament_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score REAL DEFAULT 0,
            rank INTEGER,
            prize_won REAL DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (tournament_id) REFERENCES game_tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, user_id)
        )'''
    ]
    
    # Execute all table creation statements
    for table_sql in tables:
        try:
            cursor.execute(table_sql)
        except Exception as e:
            app.logger.error(f"Error creating table: {e}")
    
    # Insert default data
    insert_default_data(cursor, is_postgres)
    
    conn.commit()
    app.logger.info("Database initialization completed successfully!")

def insert_default_data(cursor, is_postgres):
    """Insert default data into tables"""
    
    # Insert default banks
    banks = [
        ("057", "Zenith Bank Plc", "ZENITH"),
        ("058", "GTBank", "GTB"),
        ("044", "Access Bank", "ACCESS"),
        ("033", "UBA", "UBA"),
        ("011", "First Bank", "FIRSTBANK"),
        ("070", "Fidelity Bank", "FIDELITY"),
        ("050", "Ecobank", "ECOBANK"),
        ("039", "Stanbic IBTC", "STANBIC"),
        ("214", "FCMB", "FCMB"),
        ("232", "Sterling Bank", "STERLING"),
        ("032", "Union Bank", "UNION"),
        ("035", "Wema Bank", "WEMA"),
        ("082", "Keystone Bank", "KEYSTONE"),
        ("215", "Unity Bank", "UNITY"),
        ("076", "Polaris Bank", "POLARIS"),
        ("565", "OPay", "OPAY"),
        ("100", "PalmPay", "PALMPAY"),
        ("50211", "Kuda Bank", "KUDA"),
        ("566", "VBank", "VBANK"),
        ("035A", "ALAT by Wema", "ALAT")
    ]
    
    for bank in banks:
        try:
            cursor.execute('''
            INSERT INTO banks (code, name, short_name, is_active, sort_order)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                is_active = EXCLUDED.is_active
            ''', (bank[0], bank[1], bank[2], True, len(banks)))
        except Exception as e:
            app.logger.error(f"Error inserting bank {bank[0]}: {e}")
    
    # Insert default admin settings
    default_settings = [
        ('app_name', 'FLEXIA Gaming Platform', 'General', 'Application name'),
        ('app_version', '13.0', 'General', 'Application version'),
        ('contact_email', 'support@flexia.com', 'General', 'Contact email'),
        ('support_phone', '+2348160881049', 'General', 'Support phone'),
        ('withdrawal_min', '100000', 'Withdrawal', 'Minimum withdrawal amount'),
        ('withdrawal_max', '10000000', 'Withdrawal', 'Maximum withdrawal amount'),
        ('referral_bonus', '7500', 'Referral', 'Referral bonus amount'),
        ('tiktok_reward', '150', 'Games', 'TikTok daily reward'),
        ('snake_reward', '200', 'Games', 'Snake game reward per apple'),
        ('coinflip_min_bet', '100', 'Games', 'Coin flip minimum bet'),
        ('coinflip_max_bet', '50000', 'Games', 'Coin flip maximum bet'),
        ('plinko_min_bet', '100', 'Games', 'Plinko minimum bet'),
        ('plinko_max_bet', '50000', 'Games', 'Plinko maximum bet'),
        ('global_withdrawal_days', '[7, 14, 25, 30]', 'Withdrawal', 'Global withdrawal days'),
        ('maintenance_mode', 'false', 'System', 'Maintenance mode status'),
        ('registration_enabled', 'true', 'System', 'Registration enabled'),
        ('email_verification_required', 'false', 'Security', 'Email verification required'),
        ('max_login_attempts', '5', 'Security', 'Maximum login attempts'),
        ('account_lock_duration', '15', 'Security', 'Account lock duration (minutes)'),
        ('session_timeout', '24', 'Security', 'Session timeout (hours)')
    ]
    
    for setting in default_settings:
        try:
            cursor.execute('''
            INSERT INTO admin_settings (key, value, category, description, is_public)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
            ''', (setting[0], setting[1], setting[2], setting[3], True))
        except Exception as e:
            app.logger.error(f"Error inserting setting {setting[0]}: {e}")
    
    # Insert default achievements
    achievements = [
        ("First Game", "Play your first game", "beginner", "fas fa-gamepad", 500, 10, "game_plays", 1, '{"game_types": ["snake", "coinflip", "plinko", "spin"]}'),
        ("Gamer", "Play 50 games", "gaming", "fas fa-gamepad", 5000, 50, "game_plays", 50, '{}'),
        ("Game Master", "Play 200 games", "gaming", "fas fa-gamepad", 15000, 150, "game_plays", 200, '{}'),
        ("Snake Pro", "Snake high score 1000+", "gaming", "fas fa-gamepad", 7500, 75, "snake_score", 1000, '{}'),
        ("Lucky Streak", "10+ coin flip win streak", "gaming", "fas fa-coins", 10000, 100, "coinflip_streak", 10, '{}'),
        ("Coin Flipper", "100+ coin flips", "gaming", "fas fa-coins", 6000, 60, "coinflip_total", 100, '{}'),
        ("Plinko Champion", "50+ Plinko wins", "gaming", "fas fa-bullseye", 8000, 80, "plinko_wins", 50, '{}'),
        ("Thousandaire", "Balance ₦1,000+", "earnings", "fas fa-money-bill-wave", 1000, 15, "balance", 1000, '{}'),
        ("Millionaire in Progress", "Balance ₦50,000+", "earnings", "fas fa-money-bill-wave", 10000, 100, "balance", 50000, '{}'),
        ("High Roller", "Balance ₦200,000+", "earnings", "fas fa-money-bill-wave", 25000, 200, "balance", 200000, '{}'),
        ("First Withdrawal", "Make first withdrawal", "earnings", "fas fa-wallet", 5000, 50, "withdrawals", 1, '{}'),
        ("Daily Grinder", "Play 5 games in a day", "streaks", "fas fa-calendar-day", 3000, 30, "daily_games", 5, '{}'),
        ("Addicted", "Play 20 games in a day", "streaks", "fas fa-calendar-day", 8000, 80, "daily_games", 20, '{}'),
        ("Referral Starter", "Refer 5 users", "referral", "fas fa-users", 10000, 100, "referrals", 5, '{}'),
        ("Referral Master", "Refer 20 users", "referral", "fas fa-users", 30000, 300, "referrals", 20, '{}'),
        ("Transaction Veteran", "10+ transactions", "general", "fas fa-exchange-alt", 4000, 40, "transactions", 10, '{}'),
        ("Welcome Bonus", "Claim welcome bonus", "beginner", "fas fa-gift", 1000, 10, "welcome_bonus", 1, '{}'),
        ("Daily Login", "Login for 7 consecutive days", "streaks", "fas fa-sign-in-alt", 5000, 50, "daily_streak", 7, '{}'),
        ("Social Butterfly", "Follow all social media", "social", "fas fa-share-alt", 3000, 30, "social_follows", 4, '{}'),
        ("Feedback Provider", "Submit feedback", "general", "fas fa-comment", 1000, 10, "feedback", 1, '{}')
    ]
    
    for achievement in achievements:
        try:
            cursor.execute('''
            INSERT INTO achievements (name, description, category, icon, reward_amount, reward_points, requirement_type, requirement_value, requirement_data, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                reward_amount = EXCLUDED.reward_amount,
                reward_points = EXCLUDED.reward_points
            ''', (*achievement, True))
        except Exception as e:
            app.logger.error(f"Error inserting achievement {achievement[0]}: {e}")
    
    # Insert default WhatsApp numbers
    whatsapp_numbers = [
        ("+2348160881049", "Primary Support", "+234", True, True, 1),
        ("+2349030000000", "Secondary Support", "+234", True, False, 2),
        ("+2349020000000", "Sales", "+234", True, False, 3)
    ]
    
    for number in whatsapp_numbers:
        try:
            cursor.execute('''
            INSERT INTO whatsapp_numbers (number, label, country_code, is_active, is_default, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (number) DO UPDATE SET
                label = EXCLUDED.label,
                is_active = EXCLUDED.is_active
            ''', number)
        except Exception as e:
            app.logger.error(f"Error inserting WhatsApp number {number[0]}: {e}")
    
    # Check if admin user exists, create if not
    cursor.execute('SELECT id FROM users WHERE username = %s', ('flexiaadmin',))
    if not cursor.fetchone():
        admin_pass = generate_password_hash("Flexiaadmin@2024")
        admin_referral = "ADM0001"
        game_stats = json.dumps({
            "snake": {"high_score": 1200, "total_score": 5000, "games_played": 50},
            "coinflip": {"wins": 25, "losses": 18, "current_streak": 3, "total_bets": 4300},
            "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000},
            "spin": {"total_spins": 30, "total_won": 7500},
            "tiktok": {"total_follows": 15, "total_earned": 2250}
        })
        
        pin_hash = generate_password_hash("4567")
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
        INSERT INTO users (
            username, password, balance, referral_code, is_admin, is_super_admin,
            created_at, last_login, game_stats, withdrawal_pin, email_verified,
            two_factor_enabled, level, points, total_earned
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            "flexiaadmin", admin_pass, 500000.00, admin_referral, True, True,
            now, now, game_stats, pin_hash, True, False, 100, 10000, 1000000.00
        ))
        
        app.logger.warning("""
╔═══════════════════════════════════════════════════════════════╗
║                    ADMIN ACCOUNT CREATED                      ║
╠═══════════════════════════════════════════════════════════════╣
║ Username: flexiaadmin                                         ║
║ Password: Flexiaadmin@2024                                    ║
║ Withdrawal PIN: 4567                                          ║
║                                                               ║
║ ⚠️  CHANGE BOTH PASSWORD AND PIN AFTER FIRST LOGIN!          ║
╚═══════════════════════════════════════════════════════════════╝
        """)
    
    # Load coupons from file
    if os.path.exists(CONFIG.COUPON_FILE):
        try:
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            
            if codes:
                for code in codes:
                    try:
                        cursor.execute('''
                        INSERT INTO coupons (code, type, amount, is_active, valid_until)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        ''', (
                            code, 'fixed', 1000.00, True,
                            (datetime.utcnow() + timedelta(days=365)).isoformat()
                        ))
                    except:
                        continue
                
                app.logger.info(f"Loaded {len(codes)} coupons from file")
        except Exception as e:
            app.logger.error(f"Error loading coupons: {e}")
    else:
        # Create default coupons
        default_coupons = [
            ('WELCOME123', 'fixed', 1000.00),
            ('SIGNUP456', 'fixed', 500.00),
            ('REGISTER789', 'fixed', 750.00),
            ('FLEXIA2024', 'fixed', 1500.00),
            ('BONUS500', 'fixed', 500.00)
        ]
        
        for coupon in default_coupons:
            try:
                cursor.execute('''
                INSERT INTO coupons (code, type, amount, is_active, valid_until)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (code) DO NOTHING
                ''', (
                    coupon[0], coupon[1], coupon[2], True,
                    (datetime.utcnow() + timedelta(days=365)).isoformat()
                ))
            except:
                continue
        
        app.logger.info(f"Created {len(default_coupons)} default coupons")

# ======================= BACKUP SYSTEM =======================
def backup_database():
    """Create a backup of the database"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if os.environ.get('DATABASE_URL'):
            # PostgreSQL backup
            backup_file = os.path.join(CONFIG.BACKUP_FOLDER, f'backup_flexia_{timestamp}.sql')
            
            # Extract connection details from DATABASE_URL
            parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
            
            # Run pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = parsed.password
            
            result = subprocess.run([
                'pg_dump',
                '-h', parsed.hostname,
                '-p', str(parsed.port),
                '-U', parsed.username,
                '-d', parsed.path[1:],
                '-f', backup_file,
                '--no-password',
                '--format=custom'  # Binary format for faster backup/restore
            ], env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                app.logger.info(f'PostgreSQL backup created: {backup_file}')
                
                # Compress the backup
                compressed_file = f'{backup_file}.gz'
                subprocess.run(['gzip', backup_file])
                
                return compressed_file
            else:
                app.logger.error(f'PostgreSQL backup failed: {result.stderr}')
                return None
                
        else:
            # SQLite backup
            backup_file = os.path.join(CONFIG.BACKUP_FOLDER, f'backup_flexia_{timestamp}.db')
            
            shutil.copy2(CONFIG.DB_FILE, backup_file)
            
            # Compress the backup
            compressed_file = f'{backup_file}.gz'
            subprocess.run(['gzip', backup_file])
            
            app.logger.info(f'SQLite backup created: {compressed_file}')
            return compressed_file
            
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}')
        app.logger.error(traceback.format_exc())
        return None

def run_backup_scheduler():
    """Run backup scheduler in background thread"""
    def schedule():
        app.logger.info('Backup scheduler started')
        
        while True:
            try:
                # Run backup daily at 2 AM UTC
                now = datetime.utcnow()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now > next_run:
                    next_run += timedelta(days=1)
                
                time_to_sleep = (next_run - now).total_seconds()
                app.logger.info(f'Next backup scheduled in {time_to_sleep/3600:.1f} hours')
                time.sleep(time_to_sleep)
                
                # Perform backup
                backup_file = backup_database()
                if backup_file:
                    app.logger.info(f'Daily backup completed: {backup_file}')
                    
                    # Cleanup old backups (keep last 30 days)
                    cleanup_old_backups()
                else:
                    app.logger.error('Daily backup failed')
                    
            except Exception as e:
                app.logger.error(f'Backup scheduler error: {str(e)}')
                time.sleep(3600)  # Sleep 1 hour on error
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

def cleanup_old_backups():
    """Remove backups older than 30 days"""
    try:
        if not os.path.exists(CONFIG.BACKUP_FOLDER):
            return
        
        cutoff_time = datetime.now() - timedelta(days=30)
        
        for filename in os.listdir(CONFIG.BACKUP_FOLDER):
            filepath = os.path.join(CONFIG.BACKUP_FOLDER, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_time:
                    os.remove(filepath)
                    app.logger.info(f'Removed old backup: {filename}')
                    
    except Exception as e:
        app.logger.error(f'Cleanup old backups error: {str(e)}')

# ======================= HEALTH CHECK =======================
@app.route('/api/health', methods=['GET'])
def api_health():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "FLEXIA API v13.0",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "13.0",
        "environment": os.getenv('ENV', 'development'),
        "components": {}
    }
    
    # Check database
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        health_status["components"]["database"] = {
            "status": "connected",
            "type": "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite"
        }
        conn.close()
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Redis
    if redis_client:
        try:
            redis_client.ping()
            health_status["components"]["redis"] = {
                "status": "connected"
            }
        except Exception as e:
            health_status["components"]["redis"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"
    else:
        health_status["components"]["redis"] = {
            "status": "disabled"
        }
    
    # Check disk space
    try:
        stat = shutil.disk_usage('/')
        health_status["components"]["disk"] = {
            "status": "ok",
            "total_gb": round(stat.total / (1024**3), 2),
            "used_gb": round(stat.used / (1024**3), 2),
            "free_gb": round(stat.free / (1024**3), 2),
            "free_percent": round((stat.free / stat.total) * 100, 2)
        }
    except Exception as e:
        health_status["components"]["disk"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Get system stats
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE')
        today_users = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = %s', ('PENDING',))
        pending_withdrawals = cursor.fetchone()['count']
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()['sum'] or 0
        
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE play_date = CURRENT_DATE')
        today_games = cursor.fetchone()['count']
        
        health_status["stats"] = {
            "total_users": total_users,
            "today_users": today_users,
            "pending_withdrawals": pending_withdrawals,
            "total_balance": float(total_balance),
            "today_games": today_games
        }
        
        conn.close()
    except Exception as e:
        app.logger.error(f"Health check stats error: {e}")
    
    app.logger.info(f"Health check: {health_status['status']}")
    return jsonify(health_status)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    # Rate limiting
    ip_key = f"register:{request.remote_addr}"
    if RateLimiter.is_limited(ip_key, CONFIG.RATE_LIMITS['register']):
        raise APIError("Too many registration attempts", 429, "RATE_LIMITED")
    
    RateLimiter.increment(ip_key)
    
    data = request.get_json()
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    # Validate input
    username = sanitize_input(data.get('username', '').strip().lower())
    email = sanitize_input(data.get('email', '').strip().lower())
    phone = sanitize_input(data.get('phone', ''))
    password = data.get('password', '')
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    referral_code = sanitize_input(data.get('referral_code', ''))
    captcha_token = data.get('captcha_token')
    
    # Validation
    if not username or len(username) < 3:
        raise APIError("Username must be at least 3 characters", 400, "INVALID_USERNAME")
    
    if not re.match(r'^[a-z0-9_]+$', username):
        raise APIError("Username can only contain lowercase letters, numbers, and underscores", 400, "INVALID_USERNAME_FORMAT")
    
    if email and not validate_email(email):
        raise APIError("Invalid email address", 400, "INVALID_EMAIL")
    
    if phone and not validate_phone(phone):
        raise APIError("Invalid phone number", 400, "INVALID_PHONE")
    
    if not password or len(password) < 8:
        raise APIError("Password must be at least 8 characters", 400, "WEAK_PASSWORD")
    
    if not coupon_code:
        raise APIError("Coupon code required", 400, "COUPON_REQUIRED")
    
    # CAPTCHA verification (optional)
    if CONFIG.CAPTCHA_SECRET and captcha_token:
        try:
            captcha_response = requests.post(
                'https://www.google.com/recaptcha/api/siteverify',
                data={
                    'secret': CONFIG.CAPTCHA_SECRET,
                    'response': captcha_token
                }
            ).json()
            
            if not captcha_response.get('success'):
                raise APIError("CAPTCHA verification failed", 400, "CAPTCHA_FAILED")
        except Exception as e:
            app.logger.error(f"CAPTCHA verification error: {e}")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if username already exists
        cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            raise APIError("Username already taken", 409, "USERNAME_EXISTS")
        
        # Check if email already exists
        if email:
            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                raise APIError("Email already registered", 409, "EMAIL_EXISTS")
        
        # Check if phone already exists
        if phone:
            cursor.execute('SELECT id FROM users WHERE phone = %s', (phone,))
            if cursor.fetchone():
                raise APIError("Phone number already registered", 409, "PHONE_EXISTS")
        
        # Validate coupon
        cursor.execute('''
        SELECT * FROM coupons 
        WHERE code = %s AND is_active = TRUE 
        AND (valid_until IS NULL OR valid_until > CURRENT_TIMESTAMP)
        AND (max_users IS NULL OR used_count < max_users)
        ''', (coupon_code,))
        
        coupon = cursor.fetchone()
        if not coupon:
            raise APIError("Invalid or expired coupon code", 400, "INVALID_COUPON")
        
        # Validate referral code
        referred_by = None
        if referral_code:
            cursor.execute('SELECT id FROM users WHERE referral_code = %s', (referral_code,))
            ref_user = cursor.fetchone()
            if not ref_user:
                raise APIError("Invalid referral code", 400, "INVALID_REFERRAL")
            referred_by = referral_code
        
        # Generate referral code for new user
        user_referral_code = f"{username[:3].upper()}{secrets.randbelow(10000):04d}"
        
        # Generate verification token if email provided
        verification_token = None
        if email:
            verification_token = secrets.token_urlsafe(32)
        
        # Create user
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0, "games_played": 0},
            "coinflip": {"wins": 0, "losses": 0, "current_streak": 0, "total_bets": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0},
            "spin": {"total_spins": 0, "total_won": 0},
            "tiktok": {"total_follows": 0, "total_earned": 0},
            "dice": {"total_rolls": 0, "total_won": 0},
            "scratch": {"total_scratches": 0, "total_won": 0}
        })
        
        notification_settings = json.dumps({
            "email": {"marketing": True, "transactions": True, "achievements": True},
            "push": {"marketing": True, "transactions": True, "achievements": True},
            "in_app": {"marketing": True, "transactions": True, "achievements": True}
        })
        
        privacy_settings = json.dumps({
            "profile_visibility": "public",
            "show_balance": False,
            "show_achievements": True,
            "show_recent_activity": True
        })
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
        INSERT INTO users (
            username, email, phone, password, referral_code, referred_by,
            game_stats, notification_settings, privacy_settings,
            verification_token, verification_token_expires,
            created_at, updated_at, last_login, last_active, last_ip
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        ''', (
            username, email, phone, generate_password_hash(password), 
            user_referral_code, referred_by, game_stats, notification_settings, 
            privacy_settings, verification_token,
            (datetime.utcnow() + timedelta(hours=24)).isoformat() if verification_token else None,
            now, now, now, now, request.remote_addr
        ))
        
        user_id = cursor.fetchone()['id']
        
        # Update coupon usage
        cursor.execute('''
        UPDATE coupons 
        SET used_count = used_count + 1 
        WHERE code = %s
        ''', (coupon_code,))
        
        # Record coupon redemption
        redemption_id = f"COUPON-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO coupon_redemptions (coupon_code, user_id, amount, ip_address)
        VALUES (%s, %s, %s, %s)
        ''', (coupon_code, user_id, coupon['amount'], request.remote_addr))
        
        # Give welcome bonus from coupon
        if coupon['amount'] and coupon['amount'] > 0:
            # Update user balance
            cursor.execute('''
            UPDATE users 
            SET balance = balance + %s, total_earned = total_earned + %s 
            WHERE id = %s
            ''', (coupon['amount'], coupon['amount'], user_id))
            
            # Record transaction
            tx_id = f"WELCOME-{secrets.token_hex(8)}"
            cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user_id, 'WELCOME_BONUS', coupon['amount'], 'COMPLETED',
                json.dumps({"coupon": coupon_code, "source": "registration"}),
                request.remote_addr
            ))
        
        # Give referral bonus to referrer
        if referred_by:
            cursor.execute('''
            UPDATE users 
            SET balance = balance + %s, total_earned = total_earned + %s 
            WHERE referral_code = %s
            ''', (CONFIG.REFERRAL_BONUS, CONFIG.REFERRAL_BONUS, referred_by))
            
            # Record referral transaction
            ref_tx_id = f"REF-{secrets.token_hex(8)}"
            cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
            VALUES (%s, (SELECT id FROM users WHERE referral_code = %s), %s, %s, %s, %s, %s)
            ''', (
                ref_tx_id, referred_by, 'REFERRAL_BONUS', CONFIG.REFERRAL_BONUS, 'COMPLETED',
                json.dumps({"referred_user": username, "referred_user_id": user_id}),
                request.remote_addr
            ))
        
        # Create session token
        token = create_session_token(user_id, False)
        
        # Create session record
        cursor.execute('''
        INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_id, token, request.remote_addr, 
            request.user_agent.string[:500] if request.user_agent else None,
            datetime.utcnow() + timedelta(hours=CONFIG.SESSION_DURATION_HOURS)
        ))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address, user_agent)
        VALUES (%s, %s, %s, %s)
        ''', (user_id, 'USER_REGISTER', request.remote_addr, 
              request.user_agent.string[:500] if request.user_agent else None))
        
        conn.commit()
        
        # Send welcome email (optional)
        if email and CONFIG.MAIL_USERNAME and verification_token:
            try:
                send_verification_email(email, username, verification_token)
            except Exception as e:
                app.logger.error(f"Failed to send verification email: {e}")
        
        app.logger.info(f"New user registered: {username} (ID: {user_id})", extra={
            'user_id': user_id,
            'username': username,
            'email': email,
            'referral_code': user_referral_code
        })
        
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": user_id,
                "username": username,
                "referral_code": user_referral_code,
                "email": email,
                "email_verified": False,
                "balance": float(coupon['amount']) if coupon['amount'] else 0.00
            },
            "requires_verification": bool(email and verification_token)
        })
        
        # Set session cookie
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie(
            'session_token', token,
            httponly=True,
            secure=secure_cookie,
            samesite='Lax',
            max_age=86400 * CONFIG.SESSION_DURATION_HOURS,
            path='/'
        )
        
        return response
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Registration error: {e}")
        raise APIError("Registration failed. Please try again.", 500, "REGISTRATION_FAILED")
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    # Rate limiting
    ip_key = f"login:{request.remote_addr}"
    if RateLimiter.is_limited(ip_key, CONFIG.RATE_LIMITS['login']):
        raise APIError("Too many login attempts", 429, "RATE_LIMITED")
    
    RateLimiter.increment(ip_key)
    
    data = request.get_json()
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    remember_me = data.get('remember_me', False)
    
    if not identifier or not password:
        raise APIError("Username and password required", 400, "CREDENTIALS_REQUIRED")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Find user by username, email, or phone
        cursor.execute('''
        SELECT * FROM users 
        WHERE (username = %s OR email = %s OR phone = %s) 
        AND deleted_at IS NULL
        ''', (identifier, identifier, identifier))
        
        user = cursor.fetchone()
        if not user:
            # Increment failed login attempts for IP
            fail_key = f"login_fail:{request.remote_addr}"
            Cache.incr(fail_key)
            Cache.set(fail_key, Cache.get(fail_key) or 1, 300)
            
            raise APIError("Invalid credentials", 401, "INVALID_CREDENTIALS")
        
        # Check if account is locked
        if user['locked_until'] and datetime.fromisoformat(user['locked_until']) > datetime.utcnow():
            raise APIError("Account is temporarily locked. Try again later.", 423, "ACCOUNT_LOCKED")
        
        # Check if account is suspended
        if user['account_status'] == 'suspended':
            raise APIError("Account suspended. Contact support.", 403, "ACCOUNT_SUSPENDED")
        
        # Verify password
        if not check_password_hash(user['password'], password):
            # Increment login attempts
            cursor.execute('''
            UPDATE users 
            SET login_attempts = login_attempts + 1,
                last_ip = %s
            WHERE id = %s
            ''', (request.remote_addr, user['id']))
            
            # Lock account after too many attempts
            if user['login_attempts'] + 1 >= 5:  # Configurable
                lock_until = datetime.utcnow() + timedelta(minutes=15)
                cursor.execute('''
                UPDATE users 
                SET locked_until = %s 
                WHERE id = %s
                ''', (lock_until.isoformat(), user['id']))
            
            conn.commit()
            
            # Also increment IP-based failures
            fail_key = f"login_fail:{request.remote_addr}"
            Cache.incr(fail_key)
            Cache.set(fail_key, Cache.get(fail_key) or 1, 300)
            
            raise APIError("Invalid credentials", 401, "INVALID_CREDENTIALS")
        
        # Reset login attempts on successful login
        cursor.execute('''
        UPDATE users 
        SET login_attempts = 0,
            locked_until = NULL,
            last_login = %s,
            last_active = %s,
            last_ip = %s
        WHERE id = %s
        ''', (
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            request.remote_addr,
            user['id']
        ))
        
        # Check daily login streak
        today = datetime.utcnow().date()
        last_login_date = user['last_daily_login']
        
        if last_login_date:
            last_login_date = datetime.fromisoformat(last_login_date).date()
            if (today - last_login_date).days == 1:
                # Consecutive day
                new_streak = user['daily_streak'] + 1
                
                # Give streak bonus every 7 days
                if new_streak % 7 == 0:
                    streak_bonus = 5000
                    cursor.execute('''
                    UPDATE users 
                    SET balance = balance + %s,
                        daily_streak = %s,
                        last_daily_login = %s,
                        points = points + 50
                    WHERE id = %s
                    ''', (streak_bonus, new_streak, today.isoformat(), user['id']))
                    
                    # Record streak bonus transaction
                    tx_id = f"STREAK-{secrets.token_hex(8)}"
                    cursor.execute('''
                    INSERT INTO transactions (id, user_id, type, amount, status, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (
                        tx_id, user['id'], 'DAILY_STREAK_BONUS', streak_bonus, 'COMPLETED',
                        json.dumps({"streak_days": new_streak, "bonus_type": "weekly"})
                    ))
                else:
                    cursor.execute('''
                    UPDATE users 
                    SET daily_streak = %s,
                        last_daily_login = %s
                    WHERE id = %s
                    ''', (new_streak, today.isoformat(), user['id']))
            elif (today - last_login_date).days > 1:
                # Streak broken
                cursor.execute('''
                UPDATE users 
                SET daily_streak = 1,
                    last_daily_login = %s
                WHERE id = %s
                ''', (today.isoformat(), user['id']))
            else:
                # Already logged in today
                pass
        else:
            # First login
            cursor.execute('''
            UPDATE users 
            SET daily_streak = 1,
                last_daily_login = %s
            WHERE id = %s
            ''', (today.isoformat(), user['id']))
        
        # Create session token
        token = create_session_token(user['id'], user['is_admin'])
        
        # Create session record
        cursor.execute('''
        INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user['id'], token, request.remote_addr,
            request.user_agent.string[:500] if request.user_agent else None,
            datetime.utcnow() + timedelta(
                hours=CONFIG.SESSION_DURATION_HOURS * (7 if remember_me else 1)
            )
        ))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address, user_agent)
        VALUES (%s, %s, %s, %s)
        ''', (user['id'], 'USER_LOGIN', request.remote_addr, 
              request.user_agent.string[:500] if request.user_agent else None))
        
        conn.commit()
        
        # Get updated user data
        cursor.execute('SELECT * FROM users WHERE id = %s', (user['id'],))
        updated_user = cursor.fetchone()
        
        app.logger.info(f"User logged in: {user['username']} (ID: {user['id']})", extra={
            'user_id': user['id'],
            'username': user['username'],
            'ip': request.remote_addr
        })
        
        response_data = {
            "success": True,
            "user": {
                "id": updated_user['id'],
                "username": updated_user['username'],
                "email": updated_user['email'],
                "email_verified": updated_user['email_verified'],
                "phone": updated_user['phone'],
                "phone_verified": updated_user['phone_verified'],
                "balance": float(updated_user['balance']),
                "referral_code": updated_user['referral_code'],
                "is_admin": updated_user['is_admin'],
                "is_super_admin": updated_user['is_super_admin'],
                "profile_picture": updated_user['profile_picture'],
                "ui_theme": updated_user['ui_theme'],
                "language": updated_user['language'],
                "timezone": updated_user['timezone'],
                "points": updated_user['points'],
                "level": updated_user['level'],
                "daily_streak": updated_user['daily_streak'],
                "two_factor_enabled": updated_user['two_factor_enabled']
            }
        }
        
        # Add 2FA requirement if enabled
        if updated_user['two_factor_enabled']:
            session['2fa_user_id'] = updated_user['id']
            session['2fa_required'] = True
            response_data['requires_2fa'] = True
            response_data['message'] = "2FA verification required"
        else:
            session['2fa_verified'] = True
        
        response = jsonify(response_data)
        
        # Set session cookie
        secure_cookie = (os.getenv('ENV') == 'production')
        max_age = 86400 * CONFIG.SESSION_DURATION_HOURS * (7 if remember_me else 1)
        
        response.set_cookie(
            'session_token', token,
            httponly=True,
            secure=secure_cookie,
            samesite='Lax',
            max_age=max_age,
            path='/'
        )
        
        return response
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Login error: {e}")
        raise APIError("Login failed. Please try again.", 500, "LOGIN_FAILED")
    finally:
        conn.close()

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    user = get_current_user()
    token = request.cookies.get('session_token')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Invalidate session
        if token:
            cursor.execute('''
            UPDATE user_sessions 
            SET is_active = FALSE 
            WHERE session_token = %s AND user_id = %s
            ''', (token, user['id']))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address, user_agent)
        VALUES (%s, %s, %s, %s)
        ''', (user['id'], 'USER_LOGOUT', request.remote_addr, 
              request.user_agent.string[:500] if request.user_agent else None))
        
        conn.commit()
        
        app.logger.info(f"User logged out: {user['username']} (ID: {user['id']})")
        
        response = jsonify({
            "success": True,
            "message": "Logged out successfully"
        })
        
        # Clear session cookie
        response.set_cookie('session_token', '', expires=0)
        
        # Clear session data
        session.clear()
        
        return response
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Logout error: {e}")
        raise APIError("Logout failed", 500, "LOGOUT_FAILED")
    finally:
        conn.close()

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    identifier = sanitize_input(data.get('email', '').strip().lower())
    
    if not identifier:
        raise APIError("Email address required", 400, "EMAIL_REQUIRED")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Find user by email
        cursor.execute('SELECT id, username, email FROM users WHERE email = %s', (identifier,))
        user = cursor.fetchone()
        
        if not user:
            # Don't reveal if user exists for security
            app.logger.info(f"Password reset requested for non-existent email: {identifier}")
            return jsonify({
                "success": True,
                "message": "If an account exists with this email, you will receive reset instructions."
            })
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.utcnow() + timedelta(hours=1)
        
        # Store reset token
        cursor.execute('''
        UPDATE users 
        SET reset_token = %s,
            reset_token_expires = %s
        WHERE id = %s
        ''', (reset_token, reset_expires.isoformat(), user['id']))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address)
        VALUES (%s, %s, %s)
        ''', (user['id'], 'PASSWORD_RESET_REQUESTED', request.remote_addr))
        
        conn.commit()
        
        # Send reset email (optional)
        if CONFIG.MAIL_USERNAME:
            try:
                send_password_reset_email(user['email'], user['username'], reset_token)
            except Exception as e:
                app.logger.error(f"Failed to send reset email: {e}")
        
        app.logger.info(f"Password reset requested for user: {user['username']}")
        
        return jsonify({
            "success": True,
            "message": "If an account exists with this email, you will receive reset instructions."
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Forgot password error: {e}")
        raise APIError("Failed to process request", 500, "REQUEST_FAILED")
    finally:
        conn.close()

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    data = request.get_json()
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    token = data.get('token')
    new_password = data.get('new_password')
    
    if not token or not new_password:
        raise APIError("Token and new password required", 400, "DATA_REQUIRED")
    
    if len(new_password) < 8:
        raise APIError("Password must be at least 8 characters", 400, "WEAK_PASSWORD")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Find user with valid reset token
        cursor.execute('''
        SELECT id, username FROM users 
        WHERE reset_token = %s 
        AND reset_token_expires > %s
        ''', (token, datetime.utcnow().isoformat()))
        
        user = cursor.fetchone()
        if not user:
            raise APIError("Invalid or expired reset token", 400, "INVALID_TOKEN")
        
        # Update password
        cursor.execute('''
        UPDATE users 
        SET password = %s,
            reset_token = NULL,
            reset_token_expires = NULL,
            login_attempts = 0,
            locked_until = NULL
        WHERE id = %s
        ''', (generate_password_hash(new_password), user['id']))
        
        # Invalidate all active sessions
        cursor.execute('''
        UPDATE user_sessions 
        SET is_active = FALSE 
        WHERE user_id = %s AND is_active = TRUE
        ''', (user['id'],))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address)
        VALUES (%s, %s, %s)
        ''', (user['id'], 'PASSWORD_RESET_COMPLETED', request.remote_addr))
        
        conn.commit()
        
        app.logger.info(f"Password reset completed for user: {user['username']}")
        
        return jsonify({
            "success": True,
            "message": "Password reset successful. You can now login with your new password."
        })
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Reset password error: {e}")
        raise APIError("Failed to reset password", 500, "RESET_FAILED")
    finally:
        conn.close()

# ======================= USER PROFILE ENDPOINTS =======================
@app.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get current user profile"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get fresh user data
        cursor.execute('SELECT * FROM users WHERE id = %s', (user['id'],))
        fresh_user = cursor.fetchone()
        
        if not fresh_user:
            raise APIError("User not found", 404, "USER_NOT_FOUND")
        
        # Get referral count
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE referred_by = %s', (fresh_user['referral_code'],))
        referrals = cursor.fetchone()['count']
        
        # Get transaction summary
        cursor.execute('''
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN type = 'WITHDRAWAL' AND status = 'COMPLETED' THEN amount ELSE 0 END) as total_withdrawn,
            SUM(CASE WHEN type IN ('SNAKE_REWARD', 'COINFLIP_WIN', 'PLINKO_WIN', 'SPIN_REWARD', 'TIKTOK_DAILY', 'REFERRAL_BONUS', 'WELCOME_BONUS', 'ACHIEVEMENT_REWARD') THEN amount ELSE 0 END) as total_earned
        FROM transactions 
        WHERE user_id = %s
        ''', (user['id'],))
        
        tx_summary = cursor.fetchone()
        
        # Get recent transactions
        cursor.execute('''
        SELECT id, type, amount, status, details, created_at 
        FROM transactions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 20
        ''', (user['id'],))
        
        recent_transactions = []
        for tx in cursor.fetchall():
            recent_transactions.append(dict(tx))
        
        # Get game stats
        game_stats = json.loads(fresh_user['game_stats'] or '{}')
        
        # Get claimed achievements
        claimed_achievements = json.loads(fresh_user['claimed_achievements'] or '[]')
        
        # Get active achievements progress
        cursor.execute('''
        SELECT a.*, ua.progress_current, ua.progress_target, ua.is_completed
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = %s
        ORDER BY a.priority DESC, ua.unlocked_at DESC
        LIMIT 10
        ''', (user['id'],))
        
        achievements_progress = []
        for ach in cursor.fetchall():
            achievements_progress.append(dict(ach))
        
        # Get notifications
        cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id = %s AND is_read = FALSE 
        ORDER BY created_at DESC 
        LIMIT 10
        ''', (user['id'],))
        
        notifications = []
        for notif in cursor.fetchall():
            notifications.append(dict(notif))
        
        # Get withdrawal eligibility
        today_day = datetime.utcnow().day
        can_withdraw = False
        withdrawal_days = []
        
        if fresh_user['withdrawal_restricted']:
            can_withdraw = False
        else:
            if fresh_user['custom_withdrawal_days']:
                try:
                    withdrawal_days = json.loads(fresh_user['custom_withdrawal_days'])
                    can_withdraw = today_day in withdrawal_days
                except:
                    pass
            
            if not withdrawal_days:
                # Get global withdrawal days
                cursor.execute('SELECT value FROM admin_settings WHERE key = %s', ('global_withdrawal_days',))
                setting = cursor.fetchone()
                if setting:
                    try:
                        withdrawal_days = json.loads(setting['value'])
                        can_withdraw = today_day in withdrawal_days
                    except:
                        withdrawal_days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
                        can_withdraw = today_day in withdrawal_days
                else:
                    withdrawal_days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
                    can_withdraw = today_day in withdrawal_days
        
        response_data = {
            "success": True,
            "user": {
                "id": fresh_user['id'],
                "username": fresh_user['username'],
                "email": fresh_user['email'],
                "email_verified": fresh_user['email_verified'],
                "phone": fresh_user['phone'],
                "phone_verified": fresh_user['phone_verified'],
                "balance": float(fresh_user['balance']),
                "referral_code": fresh_user['referral_code'],
                "profile_picture": fresh_user['profile_picture'],
                "cover_picture": fresh_user['cover_picture'],
                "bio": fresh_user['bio'],
                "location": fresh_user['location'],
                "website": fresh_user['website'],
                "date_of_birth": fresh_user['date_of_birth'],
                "gender": fresh_user['gender'],
                "ui_theme": fresh_user['ui_theme'],
                "language": fresh_user['language'],
                "timezone": fresh_user['timezone'],
                "points": fresh_user['points'],
                "level": fresh_user['level'],
                "experience": fresh_user['experience'],
                "daily_streak": fresh_user['daily_streak'],
                "total_earned": float(fresh_user['total_earned'] or 0),
                "total_withdrawn": float(fresh_user['total_withdrawn'] or 0),
                "total_deposited": float(fresh_user['total_deposited'] or 0),
                "withdrawal_restricted": fresh_user['withdrawal_restricted'],
                "withdrawal_limit": float(fresh_user['withdrawal_limit'] or 0),
                "deposit_limit": float(fresh_user['deposit_limit'] or 0),
                "max_bet_limit": float(fresh_user['max_bet_limit'] or 0),
                "two_factor_enabled": fresh_user['two_factor_enabled'],
                "account_status": fresh_user['account_status'],
                "created_at": fresh_user['created_at'],
                "last_login": fresh_user['last_login']
            },
            "stats": {
                "referrals": referrals,
                "total_transactions": tx_summary['total_transactions'] or 0,
                "total_withdrawn": float(tx_summary['total_withdrawn'] or 0),
                "total_earned": float(tx_summary['total_earned'] or 0),
                "unclaimed_referral_bonus": max(0, referrals * CONFIG.REFERRAL_BONUS - (int(fresh_user.get('claimed_bonuses') or 0)))
            },
            "game_stats": game_stats,
            "withdrawal_info": {
                "can_withdraw": can_withdraw,
                "withdrawal_days": withdrawal_days,
                "today": today_day,
                "min_withdrawal": CONFIG.MIN_WITHDRAWAL,
                "has_withdrawal_pin": bool(fresh_user['withdrawal_pin'])
            },
            "achievements": {
                "claimed": claimed_achievements,
                "progress": achievements_progress
            },
            "notifications": notifications,
            "recent_transactions": recent_transactions
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Get profile error: {e}")
        raise APIError("Failed to load profile", 500, "PROFILE_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/user/profile', methods=['PUT'])
@require_auth
def update_profile():
    """Update user profile"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    # Extract updatable fields
    updatable_fields = [
        'email', 'phone', 'bio', 'location', 'website', 
        'date_of_birth', 'gender', 'ui_theme', 'language', 'timezone'
    ]
    
    updates = {}
    for field in updatable_fields:
        if field in data:
            if field in ['email', 'phone']:
                # Validate email/phone
                if field == 'email' and data[field]:
                    if not validate_email(data[field]):
                        raise APIError("Invalid email address", 400, "INVALID_EMAIL")
                elif field == 'phone' and data[field]:
                    if not validate_phone(data[field]):
                        raise APIError("Invalid phone number", 400, "INVALID_PHONE")
                
                # Check for duplicates
                conn = get_db()
                cursor = conn.cursor()
                try:
                    cursor.execute(f'SELECT id FROM users WHERE {field} = %s AND id != %s', (data[field], user['id']))
                    if cursor.fetchone():
                        raise APIError(f"{field.capitalize()} already registered", 409, f"{field.upper()}_EXISTS")
                finally:
                    conn.close()
            
            updates[field] = sanitize_input(data[field]) if data[field] else None
    
    # Handle profile picture separately (could be file upload)
    profile_picture = data.get('profile_picture')
    if profile_picture:
        updates['profile_picture'] = sanitize_input(profile_picture)
    
    if not updates:
        raise APIError("No valid fields to update", 400, "NO_UPDATES")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build update query
        set_clause = ', '.join([f"{field} = %s" for field in updates.keys()])
        set_clause += ', updated_at = %s'
        
        values = list(updates.values())
        values.append(datetime.utcnow().isoformat())
        values.append(user['id'])
        
        cursor.execute(f'''
        UPDATE users 
        SET {set_clause}
        WHERE id = %s
        RETURNING username, email, phone, bio, location, website, 
                  date_of_birth, gender, ui_theme, language, timezone, profile_picture
        ''', values)
        
        updated_user = cursor.fetchone()
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_value, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'PROFILE_UPDATE', 'user', user['id'],
            json.dumps(updates), request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"User profile updated: {user['username']}", extra={
            'user_id': user['id'],
            'updates': updates
        })
        
        return jsonify({
            "success": True,
            "message": "Profile updated successfully",
            "user": dict(updated_user)
        })
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Update profile error: {e}")
        raise APIError("Failed to update profile", 500, "UPDATE_FAILED")
    finally:
        conn.close()

@app.route('/api/user/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        raise APIError("Current and new password required", 400, "PASSWORDS_REQUIRED")
    
    if len(new_password) < 8:
        raise APIError("New password must be at least 8 characters", 400, "WEAK_PASSWORD")
    
    if current_password == new_password:
        raise APIError("New password must be different from current password", 400, "SAME_PASSWORD")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get fresh user with password
        cursor.execute('SELECT password FROM users WHERE id = %s', (user['id'],))
        fresh_user = cursor.fetchone()
        
        if not fresh_user:
            raise APIError("User not found", 404, "USER_NOT_FOUND")
        
        # Verify current password
        if not check_password_hash(fresh_user['password'], current_password):
            raise APIError("Current password is incorrect", 400, "INVALID_CURRENT_PASSWORD")
        
        # Update password
        cursor.execute('''
        UPDATE users 
        SET password = %s,
            updated_at = %s,
            reset_token = NULL,
            reset_token_expires = NULL
        WHERE id = %s
        ''', (generate_password_hash(new_password), datetime.utcnow().isoformat(), user['id']))
        
        # Invalidate all other sessions
        cursor.execute('''
        UPDATE user_sessions 
        SET is_active = FALSE 
        WHERE user_id = %s AND is_active = TRUE
        ''', (user['id'],))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address)
        VALUES (%s, %s, %s)
        ''', (user['id'], 'PASSWORD_CHANGE', request.remote_addr))
        
        conn.commit()
        
        app.logger.info(f"User changed password: {user['username']}")
        
        return jsonify({
            "success": True,
            "message": "Password changed successfully"
        })
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Change password error: {e}")
        raise APIError("Failed to change password", 500, "PASSWORD_CHANGE_FAILED")
    finally:
        conn.close()

@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@require_auth
def set_withdrawal_pin():
    """Set or change withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    pin = data.get('pin', '')
    
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise APIError("PIN must be 4-6 digits", 400, "INVALID_PIN")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE users 
        SET withdrawal_pin = %s,
            updated_at = %s
        WHERE id = %s
        ''', (generate_password_hash(pin), datetime.utcnow().isoformat(), user['id']))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address)
        VALUES (%s, %s, %s)
        ''', (user['id'], 'WITHDRAWAL_PIN_SET', request.remote_addr))
        
        conn.commit()
        
        app.logger.info(f"User set withdrawal PIN: {user['username']}")
        
        return jsonify({
            "success": True,
            "message": "Withdrawal PIN set successfully"
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Set withdrawal PIN error: {e}")
        raise APIError("Failed to set PIN", 500, "PIN_SET_FAILED")
    finally:
        conn.close()

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
def verify_withdrawal_pin():
    """Verify withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    pin = data.get('pin', '')
    
    if not pin:
        raise APIError("PIN required", 400, "PIN_REQUIRED")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT withdrawal_pin FROM users WHERE id = %s', (user['id'],))
        result = cursor.fetchone()
        
        if not result or not result['withdrawal_pin']:
            raise APIError("Withdrawal PIN not set", 400, "PIN_NOT_SET")
        
        if not check_password_hash(result['withdrawal_pin'], pin):
            # Log failed attempt
            cursor.execute('''
            INSERT INTO audit_logs (user_id, action, ip_address, details)
            VALUES (%s, %s, %s, %s)
            ''', (
                user['id'], 'WITHDRAWAL_PIN_FAILED', request.remote_addr,
                json.dumps({"attempt": "failed"})
            ))
            
            conn.commit()
            
            raise APIError("Invalid PIN", 400, "INVALID_PIN")
        
        # Log successful verification
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, ip_address, details)
        VALUES (%s, %s, %s, %s)
        ''', (
            user['id'], 'WITHDRAWAL_PIN_VERIFIED', request.remote_addr,
            json.dumps({"attempt": "success"})
        ))
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "PIN verified successfully"
        })
        
    except APIError:
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Verify PIN error: {e}")
        raise APIError("Failed to verify PIN", 500, "PIN_VERIFICATION_FAILED")
    finally:
        conn.close()

# ======================= GAME ENDPOINTS =======================
@app.route('/api/games/limits', methods=['GET'])
@require_auth
def get_game_limits():
    """Get user's game play limits for today"""
    user = get_current_user()
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        limits = {}
        total_played_today = 0
        
        for game_type, max_plays in CONFIG.GAME_DAILY_LIMITS.items():
            cursor.execute('''
            SELECT COUNT(*) as count 
            FROM game_plays 
            WHERE user_id = %s AND game_type = %s AND play_date = %s
            ''', (user['id'], game_type, today))
            
            played = cursor.fetchone()['count']
            remaining = max(0, max_plays - played)
            
            limits[game_type] = {
                "played": played,
                "max": max_plays,
                "remaining": remaining,
                "can_play": remaining > 0
            }
            
            total_played_today += played
        
        # Calculate time until reset
        now = datetime.utcnow()
        midnight = datetime(now.year, now.month, now.day, 23, 59, 59)
        seconds_until_reset = (midnight - now).total_seconds()
        
        return jsonify({
            "success": True,
            "limits": limits,
            "total_played_today": total_played_today,
            "reset_time": midnight.isoformat(),
            "seconds_until_reset": seconds_until_reset,
            "friendly_reset": "Midnight (00:00 UTC)"
        })
        
    except Exception as e:
        app.logger.error(f"Get game limits error: {e}")
        raise APIError("Failed to get game limits", 500, "LIMITS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake():
    """Report snake game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    apples = int(data.get('apples_eaten', 0))
    score = int(data.get('score', 0))
    
    # Validate input
    if apples <= 0 or apples > 100:
        raise APIError("Invalid apple count (1-100)", 400, "INVALID_APPLES")
    
    if score <= 0 or score > 10000:
        raise APIError("Invalid score", 400, "INVALID_SCORE")
    
    # Rate limiting
    game_key = f"game:snake:{user['id']}"
    if RateLimiter.is_limited(game_key, 1, 2):  # 1 request per 2 seconds
        raise APIError("Please wait between games", 429, "GAME_COOLDOWN")
    
    RateLimiter.increment(game_key, 2)
    
    # Check daily limit
    today = datetime.utcnow().date()
    max_plays = CONFIG.GAME_DAILY_LIMITS.get('snake', 10)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT COUNT(*) as count 
        FROM game_plays 
        WHERE user_id = %s AND game_type = %s AND play_date = %s
        ''', (user['id'], 'snake', today))
        
        played_today = cursor.fetchone()['count']
        
        if played_today >= max_plays:
            raise APIError(f"Max {max_plays} snake plays per day reached", 403, "DAILY_LIMIT_REACHED")
        
        # Calculate reward
        reward = apples * CONFIG.SNAKE_REWARD
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance atomically
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (reward, reward, datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Update game stats
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        snake_stats = game_stats.get('snake', {
            'high_score': 0,
            'total_score': 0,
            'games_played': 0,
            'total_apples': 0,
            'total_reward': 0
        })
        
        snake_stats['high_score'] = max(snake_stats['high_score'], score)
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        snake_stats['games_played'] = snake_stats.get('games_played', 0) + 1
        snake_stats['total_apples'] = snake_stats.get('total_apples', 0) + apples
        snake_stats['total_reward'] = snake_stats.get('total_reward', 0) + reward
        
        game_stats['snake'] = snake_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Record game play
        cursor.execute('''
        INSERT INTO game_plays (user_id, game_type, win_amount, result, details, ip_address, play_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'snake', reward,
            json.dumps({"apples": apples, "score": score, "reward_per_apple": CONFIG.SNAKE_REWARD}),
            json.dumps({"version": "1.0", "device": data.get('device', 'web')}),
            request.remote_addr, today
        ))
        
        # Record transaction
        tx_id = f"SNK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED',
            json.dumps({
                "game": "snake",
                "apples": apples,
                "score": score,
                "reward_per_apple": CONFIG.SNAKE_REWARD,
                "play_id": cursor.lastrowid
            }),
            request.remote_addr
        ))
        
        # Check for achievements
        check_snake_achievements(user['id'], snake_stats, cursor)
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'GAME_PLAY', 'snake', cursor.lastrowid,
            json.dumps({"apples": apples, "score": score, "reward": reward}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Snake game played: {user['username']} - {apples} apples, ₦{reward}", extra={
            'user_id': user['id'],
            'game': 'snake',
            'apples': apples,
            'score': score,
            'reward': reward
        })
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": float(new_balance),
            "apples": apples,
            "score": score,
            "transaction_id": tx_id,
            "message": f"Success! Claimed ₦{reward} for {apples} apples",
            "stats": {
                "high_score": snake_stats['high_score'],
                "total_score": snake_stats['total_score'],
                "games_played": snake_stats['games_played'],
                "total_apples": snake_stats['total_apples']
            }
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Snake game error: {e}")
        raise APIError("Failed to process game result", 500, "GAME_PROCESSING_FAILED")
    finally:
        conn.close()

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip():
    """Report coin flip game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    bet = float(data.get('bet', 0))
    choice = data.get('choice', 'heads')  # 'heads' or 'tails'
    result = data.get('result', 'heads')  # Actual result
    won = data.get('won', False)
    
    # Validate input
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > CONFIG.COIN_FLIP_MAX_BET:
        raise APIError(f"Bet must be between ₦{CONFIG.COIN_FLIP_MIN_BET} and ₦{CONFIG.COIN_FLIP_MAX_BET}", 400, "INVALID_BET")
    
    if choice not in ['heads', 'tails']:
        raise APIError("Choice must be 'heads' or 'tails'", 400, "INVALID_CHOICE")
    
    # Rate limiting
    game_key = f"game:coinflip:{user['id']}"
    if RateLimiter.is_limited(game_key, 1, 2):
        raise APIError("Please wait between games", 429, "GAME_COOLDOWN")
    
    RateLimiter.increment(game_key, 2)
    
    # Check daily limit
    today = datetime.utcnow().date()
    max_plays = CONFIG.GAME_DAILY_LIMITS.get('coinflip', 5)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT COUNT(*) as count 
        FROM game_plays 
        WHERE user_id = %s AND game_type = %s AND play_date = %s
        ''', (user['id'], 'coinflip', today))
        
        played_today = cursor.fetchone()['count']
        
        if played_today >= max_plays:
            raise APIError(f"Max {max_plays} coin flips per day reached", 403, "DAILY_LIMIT_REACHED")
        
        # Check user balance
        cursor.execute('SELECT balance FROM users WHERE id = %s', (user['id'],))
        balance = cursor.fetchone()['balance']
        
        if float(balance) < bet:
            raise APIError("Insufficient balance", 400, "INSUFFICIENT_BALANCE")
        
        # Calculate result
        payout = bet * 2 if won else 0
        net_change = payout - bet
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (net_change, max(0, payout), datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Update game stats
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        coinflip_stats = game_stats.get('coinflip', {
            'wins': 0,
            'losses': 0,
            'current_streak': 0,
            'max_streak': 0,
            'total_bets': 0,
            'total_won': 0,
            'total_lost': 0
        })
        
        if won:
            coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
            coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
            coinflip_stats['max_streak'] = max(coinflip_stats.get('max_streak', 0), coinflip_stats['current_streak'])
            coinflip_stats['total_won'] = coinflip_stats.get('total_won', 0) + payout
        else:
            coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
            coinflip_stats['current_streak'] = 0
            coinflip_stats['total_lost'] = coinflip_stats.get('total_lost', 0) + bet
        
        coinflip_stats['total_bets'] = coinflip_stats.get('total_bets', 0) + bet
        
        game_stats['coinflip'] = coinflip_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Record game play
        cursor.execute('''
        INSERT INTO game_plays (user_id, game_type, bet_amount, win_amount, result, details, ip_address, play_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'coinflip', bet, payout,
            json.dumps({"choice": choice, "result": result, "won": won}),
            json.dumps({"version": "1.0", "device": data.get('device', 'web')}),
            request.remote_addr, today
        ))
        
        # Record transaction
        tx_type = 'COINFLIP_WIN' if won else 'COINFLIP_LOSS'
        tx_id = f"COIN-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({
                "game": "coinflip",
                "bet": bet,
                "choice": choice,
                "result": result,
                "won": won,
                "payout": payout,
                "play_id": cursor.lastrowid
            }),
            request.remote_addr
        ))
        
        # Check for achievements
        check_coinflip_achievements(user['id'], coinflip_stats, cursor)
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'GAME_PLAY', 'coinflip', cursor.lastrowid,
            json.dumps({"bet": bet, "choice": choice, "result": result, "won": won, "payout": payout}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Coin flip played: {user['username']} - bet ₦{bet}, {'won' if won else 'lost'} ₦{payout}", extra={
            'user_id': user['id'],
            'game': 'coinflip',
            'bet': bet,
            'won': won,
            'payout': payout
        })
        
        return jsonify({
            "success": True,
            "won": won,
            "payout": payout,
            "net_change": net_change,
            "new_balance": float(new_balance),
            "transaction_id": tx_id,
            "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}₦{abs(net_change):,.2f}",
            "stats": {
                "wins": coinflip_stats['wins'],
                "losses": coinflip_stats['losses'],
                "current_streak": coinflip_stats['current_streak'],
                "max_streak": coinflip_stats['max_streak'],
                "total_bets": coinflip_stats['total_bets']
            }
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Coin flip error: {e}")
        raise APIError("Failed to process game result", 500, "GAME_PROCESSING_FAILED")
    finally:
        conn.close()

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko():
    """Report plinko game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    bet = float(data.get('bet', 0))
    multiplier = float(data.get('multiplier', 0))
    position = data.get('position', 0)  # Position where ball landed
    
    # Validate input
    if bet < CONFIG.PLINKO_MIN_BET or bet > CONFIG.PLINKO_MAX_BET:
        raise APIError(f"Bet must be between ₦{CONFIG.PLINKO_MIN_BET} and ₦{CONFIG.PLINKO_MAX_BET}", 400, "INVALID_BET")
    
    if multiplier not in [0.5, 1, 2, 3, 5, 10]:
        raise APIError("Invalid multiplier", 400, "INVALID_MULTIPLIER")
    
    # Rate limiting
    game_key = f"game:plinko:{user['id']}"
    if RateLimiter.is_limited(game_key, 1, 2):
        raise APIError("Please wait between games", 429, "GAME_COOLDOWN")
    
    RateLimiter.increment(game_key, 2)
    
    # Check daily limit
    today = datetime.utcnow().date()
    max_plays = CONFIG.GAME_DAILY_LIMITS.get('plinko', 5)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT COUNT(*) as count 
        FROM game_plays 
        WHERE user_id = %s AND game_type = %s AND play_date = %s
        ''', (user['id'], 'plinko', today))
        
        played_today = cursor.fetchone()['count']
        
        if played_today >= max_plays:
            raise APIError(f"Max {max_plays} plinko plays per day reached", 403, "DAILY_LIMIT_REACHED")
        
        # Check user balance
        cursor.execute('SELECT balance FROM users WHERE id = %s', (user['id'],))
        balance = cursor.fetchone()['balance']
        
        if float(balance) < bet:
            raise APIError("Insufficient balance", 400, "INSUFFICIENT_BALANCE")
        
        # Calculate result
        win_amount = bet * multiplier
        net_change = win_amount - bet
        won = net_change > 0
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (net_change, max(0, win_amount), datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Update game stats
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        plinko_stats = game_stats.get('plinko', {
            'total_wins': 0,
            'total_losses': 0,
            'total_bets': 0,
            'total_won': 0,
            'total_lost': 0,
            'highest_win': 0,
            'highest_multiplier': 0
        })
        
        plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
        
        if won:
            plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
            plinko_stats['total_won'] = plinko_stats.get('total_won', 0) + win_amount
            plinko_stats['highest_win'] = max(plinko_stats.get('highest_win', 0), win_amount)
            plinko_stats['highest_multiplier'] = max(plinko_stats.get('highest_multiplier', 0), multiplier)
        else:
            plinko_stats['total_losses'] = plinko_stats.get('total_losses', 0) + 1
            plinko_stats['total_lost'] = plinko_stats.get('total_lost', 0) + bet
        
        game_stats['plinko'] = plinko_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Record game play
        cursor.execute('''
        INSERT INTO game_plays (user_id, game_type, bet_amount, win_amount, result, details, ip_address, play_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'plinko', bet, win_amount,
            json.dumps({"position": position, "multiplier": multiplier, "won": won}),
            json.dumps({"version": "1.0", "device": data.get('device', 'web')}),
            request.remote_addr, today
        ))
        
        # Record transaction
        tx_type = 'PLINKO_WIN' if won else 'PLINKO_LOSS'
        tx_id = f"PLK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({
                "game": "plinko",
                "bet": bet,
                "multiplier": multiplier,
                "position": position,
                "won": won,
                "win_amount": win_amount,
                "play_id": cursor.lastrowid
            }),
            request.remote_addr
        ))
        
        # Check for achievements
        check_plinko_achievements(user['id'], plinko_stats, cursor)
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'GAME_PLAY', 'plinko', cursor.lastrowid,
            json.dumps({"bet": bet, "multiplier": multiplier, "position": position, "won": won, "win_amount": win_amount}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Plinko played: {user['username']} - bet ₦{bet}, multiplier {multiplier}x, {'won' if won else 'lost'} ₦{win_amount}", extra={
            'user_id': user['id'],
            'game': 'plinko',
            'bet': bet,
            'multiplier': multiplier,
            'won': won,
            'win_amount': win_amount
        })
        
        return jsonify({
            "success": True,
            "won": won,
            "win_amount": win_amount,
            "net_change": net_change,
            "new_balance": float(new_balance),
            "transaction_id": tx_id,
            "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}₦{net_change:,.2f}",
            "stats": {
                "total_wins": plinko_stats['total_wins'],
                "total_losses": plinko_stats['total_losses'],
                "total_bets": plinko_stats['total_bets'],
                "highest_win": plinko_stats['highest_win'],
                "highest_multiplier": plinko_stats['highest_multiplier']
            }
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Plinko error: {e}")
        raise APIError("Failed to process game result", 500, "GAME_PROCESSING_FAILED")
    finally:
        conn.close()

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
def report_spin():
    """Report spin wheel game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    reward = float(data.get('reward', 0))
    segment = data.get('segment', 0)
    
    # Validate reward amount
    valid_rewards = [0, 50, 100, 200, 500, 1000, 5000]
    if reward not in valid_rewards:
        raise APIError("Invalid spin reward", 400, "INVALID_REWARD")
    
    # Rate limiting
    game_key = f"game:spin:{user['id']}"
    if RateLimiter.is_limited(game_key, 1, 2):
        raise APIError("Please wait between spins", 429, "GAME_COOLDOWN")
    
    RateLimiter.increment(game_key, 2)
    
    # Check daily limit
    today = datetime.utcnow().date()
    max_plays = CONFIG.GAME_DAILY_LIMITS.get('spin', 1)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT COUNT(*) as count 
        FROM game_plays 
        WHERE user_id = %s AND game_type = %s AND play_date = %s
        ''', (user['id'], 'spin', today))
        
        played_today = cursor.fetchone()['count']
        
        if played_today >= max_plays:
            raise APIError(f"Max {max_plays} spin per day reached", 403, "DAILY_LIMIT_REACHED")
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (reward, reward, datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Update game stats
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        spin_stats = game_stats.get('spin', {
            'total_spins': 0,
            'total_won': 0,
            'highest_win': 0,
            'free_spins': 0
        })
        
        spin_stats['total_spins'] = spin_stats.get('total_spins', 0) + 1
        spin_stats['total_won'] = spin_stats.get('total_won', 0) + reward
        spin_stats['highest_win'] = max(spin_stats.get('highest_win', 0), reward)
        
        game_stats['spin'] = spin_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Record game play
        cursor.execute('''
        INSERT INTO game_plays (user_id, game_type, win_amount, result, details, ip_address, play_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'spin', reward,
            json.dumps({"segment": segment, "reward": reward}),
            json.dumps({"version": "1.0", "device": data.get('device', 'web')}),
            request.remote_addr, today
        ))
        
        # Record transaction
        tx_id = f"SPIN-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            json.dumps({
                "game": "spin",
                "segment": segment,
                "reward": reward,
                "play_id": cursor.lastrowid
            }),
            request.remote_addr
        ))
        
        # Check for achievements
        check_spin_achievements(user['id'], spin_stats, cursor)
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'GAME_PLAY', 'spin', cursor.lastrowid,
            json.dumps({"segment": segment, "reward": reward}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Spin wheel played: {user['username']} - won ₦{reward}", extra={
            'user_id': user['id'],
            'game': 'spin',
            'reward': reward,
            'segment': segment
        })
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": float(new_balance),
            "segment": segment,
            "transaction_id": tx_id,
            "message": f"Congratulations! You won ₦{reward:,.2f}!",
            "stats": {
                "total_spins": spin_stats['total_spins'],
                "total_won": spin_stats['total_won'],
                "highest_win": spin_stats['highest_win']
            }
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Spin error: {e}")
        raise APIError("Failed to process spin result", 500, "GAME_PROCESSING_FAILED")
    finally:
        conn.close()

# ======================= TIKTOK DAILY ENDPOINTS =======================
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily():
    """Get today's TikTok daily task"""
    user = get_current_user()
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get today's TikTok task
        cursor.execute('SELECT * FROM tiktok_daily WHERE date = %s AND is_active = TRUE', (today,))
        task = cursor.fetchone()
        
        if not task:
            raise APIError("No TikTok task available today", 404, "NO_TASK_AVAILABLE")
        
        # Check if already claimed today
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = 'TIKTOK_DAILY' 
        AND DATE(created_at) = %s
        ''', (user['id'], today))
        
        already_claimed = cursor.fetchone() is not None
        
        response_data = {
            "success": True,
            "task": {
                "date": task['date'].isoformat() if isinstance(task['date'], date) else task['date'],
                "tiktok_link": task['tiktok_link'],
                "reward_amount": float(task['reward_amount']),
                "views_required": task['views_required'],
                "likes_required": task['likes_required'],
                "shares_required": task['shares_required']
            },
            "already_claimed": already_claimed
        }
        
        return jsonify(response_data)
        
    except APIError:
        raise
    except Exception as e:
        app.logger.error(f"Get TikTok daily error: {e}")
        raise APIError("Failed to get TikTok task", 500, "TIKTOK_TASK_FAILED")
    finally:
        conn.close()

@app.route('/api/games/tiktok/claim', methods=['POST'])
@require_auth
def claim_tiktok_daily():
    """Claim TikTok daily reward"""
    user = get_current_user()
    today = datetime.utcnow().date()
    
    # Rate limiting
    tiktok_key = f"tiktok:{user['id']}"
    if RateLimiter.is_limited(tiktok_key, 1, 2):
        raise APIError("Please wait before claiming", 429, "TIKTOK_COOLDOWN")
    
    RateLimiter.increment(tiktok_key, 2)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check daily limit
        max_plays = CONFIG.GAME_DAILY_LIMITS.get('tiktok', 1)
        
        cursor.execute('''
        SELECT COUNT(*) as count 
        FROM game_plays 
        WHERE user_id = %s AND game_type = %s AND play_date = %s
        ''', (user['id'], 'tiktok', today))
        
        played_today = cursor.fetchone()['count']
        
        if played_today >= max_plays:
            raise APIError(f"Already claimed TikTok reward today", 403, "DAILY_LIMIT_REACHED")
        
        # Get today's TikTok task
        cursor.execute('SELECT * FROM tiktok_daily WHERE date = %s AND is_active = TRUE', (today,))
        task = cursor.fetchone()
        
        if not task:
            raise APIError("No TikTok task available today", 404, "NO_TASK_AVAILABLE")
        
        # Check if already claimed via transactions
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = 'TIKTOK_DAILY' 
        AND DATE(created_at) = %s
        ''', (user['id'], today))
        
        if cursor.fetchone():
            raise APIError("Already claimed TikTok reward today", 400, "ALREADY_CLAIMED")
        
        reward = float(task['reward_amount'])
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (reward, reward, datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Update game stats
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        tiktok_stats = game_stats.get('tiktok', {
            'total_follows': 0,
            'total_earned': 0,
            'last_follow': None
        })
        
        tiktok_stats['total_follows'] = tiktok_stats.get('total_follows', 0) + 1
        tiktok_stats['total_earned'] = tiktok_stats.get('total_earned', 0) + reward
        tiktok_stats['last_follow'] = datetime.utcnow().isoformat()
        
        game_stats['tiktok'] = tiktok_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Record game play
        cursor.execute('''
        INSERT INTO game_plays (user_id, game_type, win_amount, result, details, ip_address, play_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'tiktok', reward,
            json.dumps({"task_id": task['id'], "reward": reward}),
            json.dumps({"version": "1.0", "device": "web"}),
            request.remote_addr, today
        ))
        
        # Record transaction
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED',
            json.dumps({
                "game": "tiktok",
                "task_id": task['id'],
                "tiktok_link": task['tiktok_link'],
                "reward": reward,
                "play_id": cursor.lastrowid
            }),
            request.remote_addr
        ))
        
        # Check for achievements
        check_tiktok_achievements(user['id'], tiktok_stats, cursor)
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'TIKTOK_CLAIM', 'tiktok', cursor.lastrowid,
            json.dumps({"task_id": task['id'], "reward": reward, "tiktok_link": task['tiktok_link']}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"TikTok daily claimed: {user['username']} - ₦{reward}", extra={
            'user_id': user['id'],
            'game': 'tiktok',
            'reward': reward,
            'task_id': task['id']
        })
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": float(new_balance),
            "transaction_id": tx_id,
            "message": f"Success! Claimed ₦{reward} for following TikTok",
            "stats": {
                "total_follows": tiktok_stats['total_follows'],
                "total_earned": tiktok_stats['total_earned']
            }
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"TikTok claim error: {e}")
        raise APIError("Failed to claim TikTok reward", 500, "TIKTOK_CLAIM_FAILED")
    finally:
        conn.close()

# ======================= ACHIEVEMENT ENDPOINTS =======================
def check_snake_achievements(user_id, snake_stats, cursor):
    """Check and award snake game achievements"""
    # First Game achievement
    if snake_stats['games_played'] == 1:
        award_achievement(user_id, 'First Game', cursor)
    
    # Snake Pro achievement
    if snake_stats['high_score'] >= 1000:
        award_achievement(user_id, 'Snake Pro', cursor)
    
    # Gamer achievement (handled by general game plays)

def check_coinflip_achievements(user_id, coinflip_stats, cursor):
    """Check and award coin flip achievements"""
    # Lucky Streak achievement
    if coinflip_stats['current_streak'] >= 10:
        award_achievement(user_id, 'Lucky Streak', cursor)
    
    # Coin Flipper achievement
    if coinflip_stats['total_bets'] >= 100:
        award_achievement(user_id, 'Coin Flipper', cursor)

def check_plinko_achievements(user_id, plinko_stats, cursor):
    """Check and award plinko achievements"""
    # Plinko Champion achievement
    if plinko_stats['total_wins'] >= 50:
        award_achievement(user_id, 'Plinko Champion', cursor)

def check_spin_achievements(user_id, spin_stats, cursor):
    """Check and award spin wheel achievements"""
    # First Game achievement handled separately
    pass

def check_tiktok_achievements(user_id, tiktok_stats, cursor):
    """Check and award TikTok achievements"""
    # Social Butterfly achievement (partially)
    if tiktok_stats['total_follows'] >= 7:
        # Check other social follows in user achievements
        cursor.execute('''
        SELECT progress_current FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = %s AND a.name = 'Social Butterfly'
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result:
            current = result['progress_current'] + 1
            cursor.execute('''
            UPDATE user_achievements ua
            SET progress_current = %s
            FROM achievements a
            WHERE ua.achievement_id = a.id 
            AND ua.user_id = %s 
            AND a.name = 'Social Butterfly'
            ''', (current, user_id))

def award_achievement(user_id, achievement_name, cursor):
    """Award an achievement to a user"""
    try:
        # Get achievement details
        cursor.execute('SELECT * FROM achievements WHERE name = %s AND is_active = TRUE', (achievement_name,))
        achievement = cursor.fetchone()
        
        if not achievement:
            return
        
        # Check if already awarded
        cursor.execute('''
        SELECT 1 FROM user_achievements 
        WHERE user_id = %s AND achievement_id = %s
        ''', (user_id, achievement['id']))
        
        if cursor.fetchone():
            return
        
        # Award achievement
        cursor.execute('''
        INSERT INTO user_achievements (user_id, achievement_id, unlocked_at, is_completed)
        VALUES (%s, %s, %s, %s)
        ''', (user_id, achievement['id'], datetime.utcnow().isoformat(), True))
        
        # Give reward
        if achievement['reward_amount'] > 0:
            # Update user balance and points
            cursor.execute('''
            UPDATE users 
            SET balance = balance + %s,
                points = points + %s,
                total_earned = total_earned + %s
            WHERE id = %s
            ''', (
                achievement['reward_amount'], 
                achievement['reward_points'],
                achievement['reward_amount'],
                user_id
            ))
            
            # Record transaction
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user_id, 'ACHIEVEMENT_REWARD', 
                achievement['reward_amount'], 'COMPLETED',
                json.dumps({
                    "achievement": achievement_name,
                    "achievement_id": achievement['id'],
                    "reward_points": achievement['reward_points']
                })
            ))
        
        # Update claimed achievements list
        cursor.execute('SELECT claimed_achievements FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        claimed = json.loads(user['claimed_achievements'] or '[]')
        claimed.append(achievement['id'])
        
        cursor.execute('''
        UPDATE users 
        SET claimed_achievements = %s 
        WHERE id = %s
        ''', (json.dumps(claimed), user_id))
        
        # Create notification
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_id, 'achievement',
            'Achievement Unlocked!',
            f'You unlocked the "{achievement_name}" achievement and earned ₦{achievement["reward_amount"]:,.2f}!',
            json.dumps({"achievement_id": achievement['id'], "reward": achievement['reward_amount']})
        ))
        
        app.logger.info(f"Achievement awarded: {achievement_name} to user {user_id}")
        
    except Exception as e:
        app.logger.error(f"Award achievement error: {e}")

@app.route('/api/achievements', methods=['GET'])
@require_auth
def get_achievements():
    """Get user achievements"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user's game stats
        cursor.execute('SELECT game_stats, points, level, claimed_achievements FROM users WHERE id = %s', (user['id'],))
        user_data = cursor.fetchone()
        
        game_stats = json.loads(user_data['game_stats'] or '{}')
        claimed_achievements = json.loads(user_data['claimed_achievements'] or '[]')
        
        # Get all achievements
        cursor.execute('''
        SELECT a.*, 
               CASE WHEN ua.user_id IS NOT NULL THEN TRUE ELSE FALSE END as unlocked,
               ua.unlocked_at,
               ua.progress_current,
               ua.progress_target,
               ua.is_completed
        FROM achievements a
        LEFT JOIN user_achievements ua ON a.id = ua.achievement_id AND ua.user_id = %s
        WHERE a.is_active = TRUE
        ORDER BY a.category, a.priority DESC, a.id
        ''', (user['id'],))
        
        achievements = []
        unlocked_count = 0
        total_rewards = 0
        total_points = 0
        
        for ach in cursor.fetchall():
            achievement = dict(ach)
            
            # Calculate progress based on game stats
            progress = calculate_achievement_progress(achievement, game_stats, user_data)
            achievement['progress'] = progress
            
            if achievement['unlocked']:
                unlocked_count += 1
                total_rewards += float(achievement['reward_amount'])
                total_points += achievement['reward_points']
            
            achievements.append(achievement)
        
        return jsonify({
            "success": True,
            "achievements": achievements,
            "stats": {
                "total": len(achievements),
                "unlocked": unlocked_count,
                "remaining": len(achievements) - unlocked_count,
                "total_rewards": total_rewards,
                "total_points": total_points,
                "user_points": user_data['points'],
                "user_level": user_data['level']
            }
        })
        
    except Exception as e:
        app.logger.error(f"Get achievements error: {e}")
        raise APIError("Failed to load achievements", 500, "ACHIEVEMENTS_LOAD_FAILED")
    finally:
        conn.close()

def calculate_achievement_progress(achievement, game_stats, user_data):
    """Calculate achievement progress percentage"""
    requirement_type = achievement['requirement_type']
    requirement_value = achievement['requirement_value'] or 1
    
    if achievement['unlocked']:
        return 100
    
    current = 0
    
    if requirement_type == 'game_plays':
        # Total game plays across all games
        total_plays = 0
        for game in ['snake', 'coinflip', 'plinko', 'spin', 'tiktok', 'dice', 'scratch']:
            stats = game_stats.get(game, {})
            if game == 'snake':
                total_plays += stats.get('games_played', 0)
            elif game == 'coinflip':
                total_plays += stats.get('wins', 0) + stats.get('losses', 0)
            elif game == 'plinko':
                total_plays += stats.get('total_wins', 0) + stats.get('total_losses', 0)
            elif game == 'spin':
                total_plays += stats.get('total_spins', 0)
            elif game == 'tiktok':
                total_plays += stats.get('total_follows', 0)
        
        current = total_plays
    
    elif requirement_type == 'snake_score':
        current = game_stats.get('snake', {}).get('high_score', 0)
    
    elif requirement_type == 'coinflip_streak':
        current = game_stats.get('coinflip', {}).get('current_streak', 0)
    
    elif requirement_type == 'coinflip_total':
        stats = game_stats.get('coinflip', {})
        current = stats.get('wins', 0) + stats.get('losses', 0)
    
    elif requirement_type == 'plinko_wins':
        current = game_stats.get('plinko', {}).get('total_wins', 0)
    
    elif requirement_type == 'balance':
        current = float(user_data.get('balance', 0))
    
    elif requirement_type == 'withdrawals':
        # This would need transaction count
        current = 0  # Simplified
    
    elif requirement_type == 'daily_games':
        # This would need daily tracking
        current = 0  # Simplified
    
    elif requirement_type == 'referrals':
        # This would need referral count
        current = 0  # Simplified
    
    elif requirement_type == 'daily_streak':
        current = user_data.get('daily_streak', 0)
    
    progress_percentage = min(100, (current / requirement_value) * 100) if requirement_value > 0 else 0
    
    return {
        "current": current,
        "target": requirement_value,
        "percentage": progress_percentage
    }

@app.route('/api/achievements/claim-all', methods=['POST'])
@require_auth
def claim_all_achievements():
    """Claim all unlocked but unclaimed achievements"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get unlocked but unclaimed achievements
        cursor.execute('''
        SELECT a.*, ua.id as user_achievement_id
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = %s 
        AND ua.is_completed = TRUE 
        AND ua.reward_given = FALSE
        ''', (user['id'],))
        
        achievements = cursor.fetchall()
        
        if not achievements:
            raise APIError("No achievements to claim", 400, "NO_ACHIEVEMENTS_TO_CLAIM")
        
        total_reward = 0
        total_points = 0
        claimed_ids = []
        
        # Start transaction
        cursor.execute('BEGIN')
        
        for ach in achievements:
            reward = float(ach['reward_amount'])
            points = ach['reward_points']
            
            total_reward += reward
            total_points += points
            
            # Mark as reward given
            cursor.execute('''
            UPDATE user_achievements 
            SET reward_given = TRUE,
                claimed_at = %s
            WHERE id = %s
            ''', (datetime.utcnow().isoformat(), ach['user_achievement_id']))
            
            claimed_ids.append(ach['id'])
        
        # Update user balance and points
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            points = points + %s,
            total_earned = total_earned + %s
        WHERE id = %s
        RETURNING balance, points
        ''', (total_reward, total_points, total_reward, user['id']))
        
        result = cursor.fetchone()
        new_balance = result['balance']
        new_points = result['points']
        
        # Record transaction
        tx_id = f"ACH-ALL-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
            json.dumps({
                "source": "batch_claim",
                "achievement_ids": claimed_ids,
                "total_points": total_points,
                "count": len(claimed_ids)
            })
        ))
        
        # Create notification
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user['id'], 'achievement',
            'Achievements Claimed!',
            f'You claimed {len(claimed_ids)} achievements and earned ₦{total_reward:,.2f}!',
            json.dumps({"count": len(claimed_ids), "reward": total_reward, "points": total_points})
        ))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, details, ip_address)
        VALUES (%s, %s, %s, %s)
        ''', (
            user['id'], 'ACHIEVEMENTS_CLAIMED', 
            json.dumps({"count": len(claimed_ids), "reward": total_reward, "points": total_points}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Achievements claimed: {user['username']} - {len(claimed_ids)} achievements, ₦{total_reward}", extra={
            'user_id': user['id'],
            'achievement_count': len(claimed_ids),
            'total_reward': total_reward,
            'total_points': total_points
        })
        
        return jsonify({
            "success": True,
            "message": f"Claimed {len(claimed_ids)} achievements",
            "total_reward": total_reward,
            "total_points": total_points,
            "new_balance": float(new_balance),
            "new_points": new_points,
            "count": len(claimed_ids)
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Claim achievements error: {e}")
        raise APIError("Failed to claim achievements", 500, "ACHIEVEMENTS_CLAIM_FAILED")
    finally:
        conn.close()

# ======================= REFERRAL ENDPOINTS =======================
@app.route('/api/referrals', methods=['GET'])
@require_auth
def get_referrals():
    """Get user's referral information"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get referral count
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE referred_by = %s', (user['referral_code'],))
        referrals_count = cursor.fetchone()['count']
        
        # Get referral list
        cursor.execute('''
        SELECT id, username, created_at, balance 
        FROM users 
        WHERE referred_by = %s 
        ORDER BY created_at DESC 
        LIMIT 50
        ''', (user['referral_code'],))
        
        referrals = []
        for ref in cursor.fetchall():
            referrals.append({
                "id": ref['id'],
                "username": ref['username'],
                "joined": ref['created_at'],
                "balance": float(ref['balance'])
            })
        
        # Get claimed bonus amount
        cursor.execute('''
        SELECT SUM(amount) as total_claimed 
        FROM transactions 
        WHERE user_id = %s AND type = 'REFERRAL_BONUS'
        ''', (user['id'],))
        
        total_claimed = cursor.fetchone()['total_claimed'] or 0
        
        # Calculate available bonus
        total_bonus = referrals_count * CONFIG.REFERRAL_BONUS
        available_bonus = max(0, total_bonus - float(total_claimed))
        
        return jsonify({
            "success": True,
            "referral_code": user['referral_code'],
            "referral_url": f"https://flexia.com/register?ref={user['referral_code']}",
            "stats": {
                "total_referrals": referrals_count,
                "total_bonus": total_bonus,
                "claimed_bonus": float(total_claimed),
                "available_bonus": available_bonus,
                "bonus_per_referral": CONFIG.REFERRAL_BONUS
            },
            "referrals": referrals
        })
        
    except Exception as e:
        app.logger.error(f"Get referrals error: {e}")
        raise APIError("Failed to load referral data", 500, "REFERRALS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/referrals/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    """Claim referral bonus"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get referral count
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE referred_by = %s', (user['referral_code'],))
        referrals_count = cursor.fetchone()['count']
        
        if referrals_count == 0:
            raise APIError("No referrals to claim bonus from", 400, "NO_REFERRALS")
        
        # Get already claimed bonus
        cursor.execute('''
        SELECT SUM(amount) as total_claimed 
        FROM transactions 
        WHERE user_id = %s AND type = 'REFERRAL_BONUS'
        ''', (user['id'],))
        
        total_claimed = cursor.fetchone()['total_claimed'] or 0
        
        # Calculate available bonus
        total_bonus = referrals_count * CONFIG.REFERRAL_BONUS
        available_bonus = max(0, total_bonus - float(total_claimed))
        
        if available_bonus <= 0:
            raise APIError("No bonus available to claim", 400, "NO_BONUS_AVAILABLE")
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (available_bonus, available_bonus, datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Record transaction
        tx_id = f"REF-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'REFERRAL_BONUS', available_bonus, 'COMPLETED',
            json.dumps({
                "referrals": referrals_count,
                "bonus_per_referral": CONFIG.REFERRAL_BONUS,
                "total_claimed": float(total_claimed),
                "new_total": total_bonus
            })
        ))
        
        # Check for referral achievements
        cursor.execute('SELECT game_stats FROM users WHERE id = %s', (user['id'],))
        game_stats = json.loads(cursor.fetchone()['game_stats'] or '{}')
        
        # Update referral stats in game stats
        referral_stats = game_stats.get('referrals', {
            'total_referrals': 0,
            'total_bonus': 0
        })
        
        referral_stats['total_referrals'] = referrals_count
        referral_stats['total_bonus'] = total_bonus
        
        game_stats['referrals'] = referral_stats
        
        cursor.execute('''
        UPDATE users 
        SET game_stats = %s 
        WHERE id = %s
        ''', (json.dumps(game_stats), user['id']))
        
        # Check achievements
        if referrals_count >= 5:
            award_achievement(user['id'], 'Referral Starter', cursor)
        if referrals_count >= 20:
            award_achievement(user['id'], 'Referral Master', cursor)
        
        # Create notification
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user['id'], 'referral',
            'Referral Bonus Claimed!',
            f'You claimed ₦{available_bonus:,.2f} referral bonus!',
            json.dumps({"bonus": available_bonus, "referrals": referrals_count})
        ))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, details, ip_address)
        VALUES (%s, %s, %s, %s)
        ''', (
            user['id'], 'REFERRAL_BONUS_CLAIMED',
            json.dumps({"bonus": available_bonus, "referrals": referrals_count}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Referral bonus claimed: {user['username']} - ₦{available_bonus} for {referrals_count} referrals", extra={
            'user_id': user['id'],
            'bonus': available_bonus,
            'referrals': referrals_count
        })
        
        return jsonify({
            "success": True,
            "message": f"Claimed ₦{available_bonus:,.2f} referral bonus",
            "bonus": available_bonus,
            "new_balance": float(new_balance),
            "referrals": referrals_count
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Claim referral bonus error: {e}")
        raise APIError("Failed to claim referral bonus", 500, "REFERRAL_CLAIM_FAILED")
    finally:
        conn.close()

# ======================= BANKING & WITHDRAWAL ENDPOINTS =======================
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    """Get list of banks"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT code, name, short_name, logo_url 
        FROM banks 
        WHERE is_active = TRUE 
        ORDER BY sort_order, name
        ''')
        
        banks = []
        for bank in cursor.fetchall():
            banks.append({
                "code": bank['code'],
                "name": bank['name'],
                "short_name": bank['short_name'],
                "logo_url": bank['logo_url']
            })
        
        return jsonify({
            "success": True,
            "banks": banks
        })
        
    except Exception as e:
        app.logger.error(f"Get banks error: {e}")
        raise APIError("Failed to load banks", 500, "BANKS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/banking/user-banks', methods=['GET'])
@require_auth
def get_user_banks():
    """Get user's saved bank accounts"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT ub.*, b.name as bank_name, b.short_name, b.logo_url
        FROM user_banks ub
        JOIN banks b ON ub.bank_code = b.code
        WHERE ub.user_id = %s
        ORDER BY ub.is_default DESC, ub.created_at DESC
        ''', (user['id'],))
        
        banks = []
        for bank in cursor.fetchall():
            banks.append({
                "id": bank['id'],
                "bank_code": bank['bank_code'],
                "bank_name": bank['bank_name'],
                "short_name": bank['short_name'],
                "logo_url": bank['logo_url'],
                "account_number": bank['account_number'],
                "account_name": bank['account_name'],
                "is_default": bank['is_default'],
                "is_verified": bank['is_verified'],
                "created_at": bank['created_at']
            })
        
        return jsonify({
            "success": True,
            "banks": banks
        })
        
    except Exception as e:
        app.logger.error(f"Get user banks error: {e}")
        raise APIError("Failed to load bank accounts", 500, "USER_BANKS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/banking/user-banks', methods=['POST'])
@require_auth
def add_user_bank():
    """Add a bank account"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    bank_code = data.get('bank_code')
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    
    if not bank_code or not account_number or not account_name:
        raise APIError("Bank code, account number and name required", 400, "BANK_DETAILS_REQUIRED")
    
    if not account_number.isdigit() or len(account_number) < 10:
        raise APIError("Invalid account number", 400, "INVALID_ACCOUNT_NUMBER")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Verify bank exists and is active
        cursor.execute('SELECT 1 FROM banks WHERE code = %s AND is_active = TRUE', (bank_code,))
        if not cursor.fetchone():
            raise APIError("Invalid bank code", 400, "INVALID_BANK_CODE")
        
        # Check if account already exists
        cursor.execute('''
        SELECT 1 FROM user_banks 
        WHERE user_id = %s AND bank_code = %s AND account_number = %s
        ''', (user['id'], bank_code, account_number))
        
        if cursor.fetchone():
            raise APIError("Bank account already exists", 400, "BANK_ACCOUNT_EXISTS")
        
        # Set as default if first account
        cursor.execute('SELECT COUNT(*) as count FROM user_banks WHERE user_id = %s', (user['id'],))
        count = cursor.fetchone()['count']
        
        is_default = count == 0
        
        # If setting as default, unset other defaults
        if is_default:
            cursor.execute('''
            UPDATE user_banks 
            SET is_default = FALSE 
            WHERE user_id = %s
            ''', (user['id'],))
        
        # Add bank account
        cursor.execute('''
        INSERT INTO user_banks (user_id, bank_code, account_number, account_name, is_default)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        ''', (user['id'], bank_code, account_number, account_name, is_default))
        
        bank_id = cursor.fetchone()['id']
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_value, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'BANK_ACCOUNT_ADDED', 'user_bank', bank_id,
            json.dumps({"bank_code": bank_code, "account_number": account_number, "account_name": account_name}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Bank account added: {user['username']} - {bank_code}:{account_number}", extra={
            'user_id': user['id'],
            'bank_code': bank_code,
            'account_number': account_number[:4] + '****'  # Mask for logs
        })
        
        return jsonify({
            "success": True,
            "message": "Bank account added successfully",
            "bank_id": bank_id
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Add bank account error: {e}")
        raise APIError("Failed to add bank account", 500, "BANK_ADD_FAILED")
    finally:
        conn.close()

@app.route('/api/banking/user-banks/<int:bank_id>', methods=['DELETE'])
@require_auth
def delete_user_bank(bank_id):
    """Delete a bank account"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Verify ownership
        cursor.execute('SELECT is_default FROM user_banks WHERE id = %s AND user_id = %s', (bank_id, user['id']))
        bank = cursor.fetchone()
        
        if not bank:
            raise APIError("Bank account not found", 404, "BANK_NOT_FOUND")
        
        if bank['is_default']:
            # Can't delete default account without setting a new one
            cursor.execute('SELECT COUNT(*) as count FROM user_banks WHERE user_id = %s', (user['id'],))
            count = cursor.fetchone()['count']
            
            if count > 1:
                raise APIError("Set another account as default before deleting", 400, "CANT_DELETE_DEFAULT")
        
        # Delete bank account
        cursor.execute('DELETE FROM user_banks WHERE id = %s AND user_id = %s', (bank_id, user['id']))
        
        if cursor.rowcount == 0:
            raise APIError("Bank account not found", 404, "BANK_NOT_FOUND")
        
        # If default was deleted, set another as default
        if bank['is_default']:
            cursor.execute('''
            UPDATE user_banks 
            SET is_default = TRUE 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 1
            ''', (user['id'],))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, ip_address)
        VALUES (%s, %s, %s, %s, %s)
        ''', (user['id'], 'BANK_ACCOUNT_DELETED', 'user_bank', bank_id, request.remote_addr))
        
        conn.commit()
        
        app.logger.info(f"Bank account deleted: {user['username']} - bank_id: {bank_id}")
        
        return jsonify({
            "success": True,
            "message": "Bank account deleted successfully"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Delete bank account error: {e}")
        raise APIError("Failed to delete bank account", 500, "BANK_DELETE_FAILED")
    finally:
        conn.close()

@app.route('/api/banking/withdraw', methods=['POST'])
@require_auth
def withdraw():
    """Request withdrawal"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    amount = float(data.get('amount', 0))
    bank_id = data.get('bank_id')
    pin = data.get('pin', '')
    
    if not amount or not bank_id or not pin:
        raise APIError("Amount, bank account and PIN required", 400, "WITHDRAWAL_DETAILS_REQUIRED")
    
    # Rate limiting
    withdraw_key = f"withdraw:{user['id']}"
    if RateLimiter.is_limited(withdraw_key, CONFIG.RATE_LIMITS['withdrawal']):
        raise APIError("Too many withdrawal requests", 429, "WITHDRAWAL_LIMITED")
    
    RateLimiter.increment(withdraw_key)
    
    # Validate amount
    if amount < CONFIG.MIN_WITHDRAWAL:
        raise APIError(f"Minimum withdrawal is ₦{CONFIG.MIN_WITHDRAWAL:,}", 400, "MIN_WITHDRAWAL")
    
    # Check user balance
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT balance, withdrawal_pin, withdrawal_restricted, withdrawal_limit FROM users WHERE id = %s', (user['id'],))
        user_data = cursor.fetchone()
        
        balance = float(user_data['balance'])
        
        if balance < amount:
            raise APIError("Insufficient balance", 400, "INSUFFICIENT_BALANCE")
        
        # Verify withdrawal PIN
        if not user_data['withdrawal_pin'] or not check_password_hash(user_data['withdrawal_pin'], pin):
            raise APIError("Invalid PIN", 400, "INVALID_PIN")
        
        # Check withdrawal restrictions
        if user_data['withdrawal_restricted']:
            raise APIError("Withdrawals are restricted for your account", 403, "WITHDRAWAL_RESTRICTED")
        
        # Check withdrawal limit
        withdrawal_limit = float(user_data['withdrawal_limit'] or 0)
        if withdrawal_limit > 0 and amount > withdrawal_limit:
            raise APIError(f"Maximum withdrawal limit is ₦{withdrawal_limit:,}", 400, "WITHDRAWAL_LIMIT_EXCEEDED")
        
        # Check withdrawal day
        today_day = datetime.utcnow().day
        
        # Check custom withdrawal days
        cursor.execute('SELECT custom_withdrawal_days FROM users WHERE id = %s', (user['id'],))
        custom_days_str = cursor.fetchone()['custom_withdrawal_days']
        
        can_withdraw = False
        withdrawal_days = []
        
        if custom_days_str:
            try:
                withdrawal_days = json.loads(custom_days_str)
                can_withdraw = today_day in withdrawal_days
            except:
                pass
        
        if not withdrawal_days:
            # Get global withdrawal days
            cursor.execute('SELECT value FROM admin_settings WHERE key = %s', ('global_withdrawal_days',))
            setting = cursor.fetchone()
            if setting:
                try:
                    withdrawal_days = json.loads(setting['value'])
                    can_withdraw = today_day in withdrawal_days
                except:
                    withdrawal_days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
                    can_withdraw = today_day in withdrawal_days
            else:
                withdrawal_days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
                can_withdraw = today_day in withdrawal_days
        
        if not can_withdraw:
            raise APIError(f"Withdrawals only allowed on days: {', '.join(map(str, sorted(withdrawal_days)))}", 403, "NOT_WITHDRAWAL_DAY")
        
        # Get bank account details
        cursor.execute('''
        SELECT ub.*, b.name as bank_name 
        FROM user_banks ub 
        JOIN banks b ON ub.bank_code = b.code
        WHERE ub.id = %s AND ub.user_id = %s
        ''', (bank_id, user['id']))
        
        bank = cursor.fetchone()
        if not bank:
            raise APIError("Bank account not found", 404, "BANK_NOT_FOUND")
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Deduct from user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance - %s,
            total_withdrawn = total_withdrawn + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (amount, amount, datetime.utcnow().isoformat(), user['id']))
        
        new_balance = cursor.fetchone()['balance']
        
        # Record withdrawal transaction
        tx_id = f"WTH-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING',
            json.dumps({
                "bank_id": bank_id,
                "bank_code": bank['bank_code'],
                "bank_name": bank['bank_name'],
                "account_number": bank['account_number'],
                "account_name": bank['account_name'],
                "user_balance_before": balance,
                "user_balance_after": new_balance
            }),
            request.remote_addr
        ))
        
        # Check for first withdrawal achievement
        cursor.execute('''
        SELECT COUNT(*) as count FROM transactions 
        WHERE user_id = %s AND type = 'WITHDRAWAL' AND status = 'COMPLETED'
        ''', (user['id'],))
        
        completed_withdrawals = cursor.fetchone()['count']
        if completed_withdrawals == 0:
            # This is their first withdrawal request
            award_achievement(user['id'], 'First Withdrawal', cursor)
        
        # Create notification for user
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user['id'], 'withdrawal',
            'Withdrawal Requested',
            f'Your withdrawal request for ₦{amount:,.2f} has been submitted and is pending approval.',
            json.dumps({"amount": amount, "transaction_id": tx_id, "status": "pending"})
        ))
        
        # Create notification for admins (simplified - in real app, would notify specific admins)
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        SELECT id, 'admin_withdrawal', 'New Withdrawal Request',
               'User %s requested withdrawal of ₦%s',
               %s
        FROM users WHERE is_admin = TRUE
        ''', (user['username'], amount, json.dumps({
            "user_id": user['id'],
            "username": user['username'],
            "amount": amount,
            "transaction_id": tx_id,
            "bank_details": {
                "bank_name": bank['bank_name'],
                "account_number": bank['account_number'],
                "account_name": bank['account_name']
            }
        })))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'WITHDRAWAL_REQUESTED', 'transaction', tx_id,
            json.dumps({"amount": amount, "bank_id": bank_id, "balance_before": balance, "balance_after": new_balance}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Withdrawal requested: {user['username']} - ₦{amount} to {bank['bank_name']}:{bank['account_number'][:4]}****", extra={
            'user_id': user['id'],
            'amount': amount,
            'bank_id': bank_id,
            'transaction_id': tx_id
        })
        
        return jsonify({
            "success": True,
            "message": "Withdrawal request submitted successfully",
            "transaction_id": tx_id,
            "new_balance": float(new_balance),
            "amount": amount,
            "status": "pending"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Withdrawal error: {e}")
        raise APIError("Failed to process withdrawal", 500, "WITHDRAWAL_FAILED")
    finally:
        conn.close()

@app.route('/api/banking/withdrawals', methods=['GET'])
@require_auth
def get_withdrawals():
    """Get user's withdrawal history"""
    user = get_current_user()
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    offset = (page - 1) * limit
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get total count
        cursor.execute('SELECT COUNT(*) as total FROM transactions WHERE user_id = %s AND type = %s', (user['id'], 'WITHDRAWAL'))
        total = cursor.fetchone()['total']
        
        # Get withdrawals
        cursor.execute('''
        SELECT id, amount, status, details, created_at, completed_at
        FROM transactions 
        WHERE user_id = %s AND type = 'WITHDRAWAL'
        ORDER BY created_at DESC 
        LIMIT %s OFFSET %s
        ''', (user['id'], limit, offset))
        
        withdrawals = []
        for tx in cursor.fetchall():
            details = json.loads(tx['details'] or '{}')
            withdrawals.append({
                "id": tx['id'],
                "amount": float(tx['amount']),
                "status": tx['status'],
                "bank_name": details.get('bank_name', ''),
                "account_number": details.get('account_number', '')[:4] + '****' + details.get('account_number', '')[-4:] if details.get('account_number') else '',
                "requested_at": tx['created_at'],
                "completed_at": tx['completed_at']
            })
        
        return jsonify({
            "success": True,
            "withdrawals": withdrawals,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Get withdrawals error: {e}")
        raise APIError("Failed to load withdrawal history", 500, "WITHDRAWALS_LOAD_FAILED")
    finally:
        conn.close()

# ======================= TRANSACTION ENDPOINTS =======================
@app.route('/api/transactions', methods=['GET'])
@require_auth
def get_transactions():
    """Get user's transaction history"""
    user = get_current_user()
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    offset = (page - 1) * limit
    
    type_filter = request.args.get('type')
    status_filter = request.args.get('status')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = 'SELECT * FROM transactions WHERE user_id = %s'
        params = [user['id']]
        
        if type_filter:
            query += ' AND type = %s'
            params.append(type_filter)
        
        if status_filter:
            query += ' AND status = %s'
            params.append(status_filter)
        
        # Get total count
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as total', 1)
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        # Get transactions
        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        transactions = []
        for tx in cursor.fetchall():
            transaction = dict(tx)
            transaction['amount'] = float(transaction['amount'])
            
            # Parse details if present
            if transaction['details']:
                try:
                    transaction['details'] = json.loads(transaction['details'])
                except:
                    pass
            
            transactions.append(transaction)
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Get transactions error: {e}")
        raise APIError("Failed to load transactions", 500, "TRANSACTIONS_LOAD_FAILED")
    finally:
        conn.close()

# ======================= NOTIFICATION ENDPOINTS =======================
@app.route('/api/notifications', methods=['GET'])
@require_auth
def get_notifications():
    """Get user's notifications"""
    user = get_current_user()
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    offset = (page - 1) * limit
    
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = 'SELECT * FROM notifications WHERE user_id = %s'
        params = [user['id']]
        
        if unread_only:
            query += ' AND is_read = FALSE'
        
        # Get total count
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as total', 1)
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        # Get notifications
        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        notifications = []
        for notif in cursor.fetchall():
            notification = dict(notif)
            
            # Parse data if present
            if notification['data']:
                try:
                    notification['data'] = json.loads(notification['data'])
                except:
                    pass
            
            notifications.append(notification)
        
        # Get unread count
        cursor.execute('SELECT COUNT(*) as unread FROM notifications WHERE user_id = %s AND is_read = FALSE', (user['id'],))
        unread = cursor.fetchone()['unread']
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "unread_count": unread,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Get notifications error: {e}")
        raise APIError("Failed to load notifications", 500, "NOTIFICATIONS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@require_auth
def mark_notification_read(notification_id):
    """Mark notification as read"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE notifications 
        SET is_read = TRUE, read_at = %s
        WHERE id = %s AND user_id = %s
        ''', (datetime.utcnow().isoformat(), notification_id, user['id']))
        
        if cursor.rowcount == 0:
            raise APIError("Notification not found", 404, "NOTIFICATION_NOT_FOUND")
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Notification marked as read"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Mark notification read error: {e}")
        raise APIError("Failed to mark notification as read", 500, "NOTIFICATION_READ_FAILED")
    finally:
        conn.close()

@app.route('/api/notifications/read-all', methods=['POST'])
@require_auth
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user = get_current_user()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE notifications 
        SET is_read = TRUE, read_at = %s
        WHERE user_id = %s AND is_read = FALSE
        ''', (datetime.utcnow().isoformat(), user['id']))
        
        updated = cursor.rowcount
        
        conn.commit()
        
        app.logger.info(f"Marked all notifications as read: {user['username']} - {updated} notifications")
        
        return jsonify({
            "success": True,
            "message": f"Marked {updated} notifications as read"
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Mark all notifications read error: {e}")
        raise APIError("Failed to mark notifications as read", 500, "NOTIFICATIONS_READ_FAILED")
    finally:
        conn.close()

# ======================= ADMIN ENDPOINTS =======================
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    """Admin: Get all users"""
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    offset = (page - 1) * limit
    
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = '''
        SELECT id, username, email, phone, balance, referral_code, referred_by,
               is_admin, is_super_admin, created_at, last_login, last_active,
               email_verified, phone_verified, two_factor_enabled,
               withdrawal_restricted, withdrawal_limit, account_status,
               points, level, total_earned, total_withdrawn
        FROM users 
        WHERE deleted_at IS NULL
        '''
        params = []
        
        if search:
            query += ' AND (username ILIKE %s OR email ILIKE %s OR phone ILIKE %s)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        if status:
            query += ' AND account_status = %s'
            params.append(status)
        
        # Get total count
        count_query = query.replace('SELECT id, username', 'SELECT COUNT(*) as total', 1)
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        # Get users
        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        users = []
        for user in cursor.fetchall():
            user_data = dict(user)
            user_data['balance'] = float(user_data['balance'])
            user_data['total_earned'] = float(user_data['total_earned'] or 0)
            user_data['total_withdrawn'] = float(user_data['total_withdrawn'] or 0)
            user_data['withdrawal_limit'] = float(user_data['withdrawal_limit'] or 0)
            users.append(user_data)
        
        # Get stats
        cursor.execute('''
        SELECT 
            COUNT(*) as total_users,
            COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_users,
            COUNT(CASE WHEN account_status = 'suspended' THEN 1 END) as suspended_users,
            COUNT(CASE WHEN is_admin = TRUE THEN 1 END) as admin_users,
            SUM(balance) as total_balance
        FROM users 
        WHERE deleted_at IS NULL
        ''')
        
        stats = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "users": users,
            "stats": {
                "total_users": stats['total_users'],
                "today_users": stats['today_users'],
                "suspended_users": stats['suspended_users'],
                "admin_users": stats['admin_users'],
                "total_balance": float(stats['total_balance'] or 0)
            },
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Admin get users error: {e}")
        raise APIError("Failed to load users", 500, "ADMIN_USERS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@require_admin
def admin_get_user(user_id):
    """Admin: Get user details"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise APIError("User not found", 404, "USER_NOT_FOUND")
        
        # Convert numeric fields
        user_data = dict(user)
        for field in ['balance', 'total_earned', 'total_withdrawn', 'total_deposited', 'withdrawal_limit', 'deposit_limit', 'max_bet_limit']:
            if user_data.get(field):
                user_data[field] = float(user_data[field])
        
        # Parse JSON fields
        for field in ['game_stats', 'claimed_achievements', 'achievements_progress', 'notification_settings', 'privacy_settings', 'custom_withdrawal_days', 'security_questions', 'trusted_devices', 'metadata']:
            if user_data.get(field):
                try:
                    user_data[field] = json.loads(user_data[field])
                except:
                    pass
        
        return jsonify({
            "success": True,
            "user": user_data
        })
        
    except APIError:
        raise
    except Exception as e:
        app.logger.error(f"Admin get user error: {e}")
        raise APIError("Failed to load user", 500, "ADMIN_USER_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@require_admin
def admin_update_user(user_id):
    """Admin: Update user"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    # Define allowed fields for admin update
    allowed_fields = [
        'email', 'phone', 'balance', 'points', 'level', 'experience',
        'withdrawal_restricted', 'withdrawal_limit', 'deposit_limit', 'max_bet_limit',
        'account_status', 'suspension_reason', 'suspension_end', 'notes',
        'is_admin', 'custom_withdrawal_days'
    ]
    
    updates = {}
    for field in allowed_fields:
        if field in data:
            if field in ['balance', 'withdrawal_limit', 'deposit_limit', 'max_bet_limit']:
                updates[field] = float(data[field])
            elif field in ['points', 'level', 'experience']:
                updates[field] = int(data[field])
            elif field == 'custom_withdrawal_days' and data[field]:
                updates[field] = json.dumps(data[field])
            elif field == 'suspension_end' and data[field]:
                updates[field] = data[field]  # ISO date string
            else:
                updates[field] = data[field]
    
    if not updates:
        raise APIError("No valid fields to update", 400, "NO_UPDATES")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise APIError("User not found", 404, "USER_NOT_FOUND")
        
        # Build update query
        set_clause = ', '.join([f"{field} = %s" for field in updates.keys()])
        set_clause += ', updated_at = %s'
        
        values = list(updates.values())
        values.append(datetime.utcnow().isoformat())
        values.append(user_id)
        
        cursor.execute(f'''
        UPDATE users 
        SET {set_clause}
        WHERE id = %s
        ''', values)
        
        # Log audit
        admin_user = get_current_user()
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_value, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            admin_user['id'], 'ADMIN_USER_UPDATE', 'user', user_id,
            json.dumps(updates), request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Admin updated user: {user['username']} (ID: {user_id})", extra={
            'admin_id': admin_user['id'],
            'user_id': user_id,
            'updates': updates
        })
        
        return jsonify({
            "success": True,
            "message": "User updated successfully"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Admin update user error: {e}")
        raise APIError("Failed to update user", 500, "ADMIN_USER_UPDATE_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/users/<int:user_id>/balance', methods=['POST'])
@require_admin
def admin_adjust_balance(user_id):
    """Admin: Adjust user balance"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    amount = float(data.get('amount', 0))
    action = data.get('action', 'add')  # 'add' or 'subtract'
    reason = data.get('reason', '')
    
    if amount <= 0:
        raise APIError("Amount must be positive", 400, "INVALID_AMOUNT")
    
    if action not in ['add', 'subtract']:
        raise APIError("Action must be 'add' or 'subtract'", 400, "INVALID_ACTION")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute('SELECT username, balance FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise APIError("User not found", 404, "USER_NOT_FOUND")
        
        # Calculate adjustment
        adjustment = amount if action == 'add' else -amount
        
        # Check if subtraction would result in negative balance
        if action == 'subtract' and float(user['balance']) < amount:
            raise APIError("Insufficient balance to subtract", 400, "INSUFFICIENT_BALANCE")
        
        # Start transaction
        cursor.execute('BEGIN')
        
        # Update user balance
        cursor.execute('''
        UPDATE users 
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = %s
        RETURNING balance
        ''', (
            adjustment,
            max(0, adjustment),  # Only add to total_earned if positive
            datetime.utcnow().isoformat(),
            user_id
        ))
        
        new_balance = cursor.fetchone()['balance']
        
        # Record transaction
        tx_type = 'ADMIN_ADJUSTMENT_ADD' if action == 'add' else 'ADMIN_ADJUSTMENT_SUBTRACT'
        tx_id = f"ADJ-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user_id, tx_type, adjustment, 'COMPLETED',
            json.dumps({
                "reason": reason,
                "admin_action": True,
                "old_balance": float(user['balance']),
                "new_balance": new_balance
            })
        ))
        
        # Create notification for user
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_id, 'balance_adjustment',
            'Balance Adjusted',
            f'Your balance was {"increased" if action == "add" else "decreased"} by ₦{amount:,.2f} by an administrator.',
            json.dumps({
                "action": action,
                "amount": amount,
                "reason": reason,
                "old_balance": float(user['balance']),
                "new_balance": new_balance
            })
        ))
        
        # Log audit
        admin_user = get_current_user()
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            admin_user['id'], 'ADMIN_BALANCE_ADJUSTMENT', 'user', user_id,
            json.dumps({
                "action": action,
                "amount": amount,
                "reason": reason,
                "old_balance": float(user['balance']),
                "new_balance": new_balance,
                "user_username": user['username']
            }),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Admin adjusted balance: {user['username']} - {action} ₦{amount}", extra={
            'admin_id': admin_user['id'],
            'user_id': user_id,
            'action': action,
            'amount': amount,
            'reason': reason
        })
        
        return jsonify({
            "success": True,
            "message": f"Balance {action}ed successfully",
            "adjustment": adjustment,
            "new_balance": float(new_balance)
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Admin adjust balance error: {e}")
        raise APIError("Failed to adjust balance", 500, "BALANCE_ADJUSTMENT_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/transactions', methods=['GET'])
@require_admin
def admin_get_transactions():
    """Admin: Get all transactions"""
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    offset = (page - 1) * limit
    
    type_filter = request.args.get('type')
    status_filter = request.args.get('status')
    user_id = request.args.get('user_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = '''
        SELECT t.*, u.username, u.email
        FROM transactions t
        LEFT JOIN users u ON t.user_id = u.id
        WHERE 1=1
        '''
        params = []
        
        if type_filter:
            query += ' AND t.type = %s'
            params.append(type_filter)
        
        if status_filter:
            query += ' AND t.status = %s'
            params.append(status_filter)
        
        if user_id:
            query += ' AND t.user_id = %s'
            params.append(int(user_id))
        
        # Get total count
        count_query = query.replace('SELECT t.*, u.username, u.email', 'SELECT COUNT(*) as total', 1)
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        # Get transactions
        query += ' ORDER BY t.created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        transactions = []
        for tx in cursor.fetchall():
            transaction = dict(tx)
            transaction['amount'] = float(transaction['amount'])
            
            # Parse details if present
            if transaction['details']:
                try:
                    transaction['details'] = json.loads(transaction['details'])
                except:
                    pass
            
            transactions.append(transaction)
        
        # Get stats
        cursor.execute('''
        SELECT 
            COUNT(*) as total_transactions,
            COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending_transactions,
            COUNT(CASE WHEN type = 'WITHDRAWAL' AND status = 'PENDING' THEN 1 END) as pending_withdrawals,
            SUM(CASE WHEN type = 'WITHDRAWAL' AND status = 'COMPLETED' THEN amount ELSE 0 END) as total_withdrawn,
            SUM(CASE WHEN type IN ('SNAKE_REWARD', 'COINFLIP_WIN', 'PLINKO_WIN', 'SPIN_REWARD', 'TIKTOK_DAILY', 'REFERRAL_BONUS', 'WELCOME_BONUS', 'ACHIEVEMENT_REWARD') THEN amount ELSE 0 END) as total_rewards_given
        FROM transactions
        ''')
        
        stats = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "stats": {
                "total_transactions": stats['total_transactions'],
                "pending_transactions": stats['pending_transactions'],
                "pending_withdrawals": stats['pending_withdrawals'],
                "total_withdrawn": float(stats['total_withdrawn'] or 0),
                "total_rewards_given": float(stats['total_rewards_given'] or 0)
            },
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Admin get transactions error: {e}")
        raise APIError("Failed to load transactions", 500, "ADMIN_TRANSACTIONS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/transactions/<transaction_id>', methods=['PUT'])
@require_admin
def admin_update_transaction(transaction_id):
    """Admin: Update transaction status"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    status = data.get('status')
    notes = data.get('notes', '')
    
    if status not in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED']:
        raise APIError("Invalid status", 400, "INVALID_STATUS")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get transaction details
        cursor.execute('''
        SELECT t.*, u.username, u.balance 
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = %s
        ''', (transaction_id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            raise APIError("Transaction not found", 404, "TRANSACTION_NOT_FOUND")
        
        # Check if it's a withdrawal and we're rejecting it
        if transaction['type'] == 'WITHDRAWAL' and status in ['FAILED', 'CANCELLED'] and transaction['status'] == 'PENDING':
            # Refund the amount to user
            refund_amount = float(transaction['amount'])
            
            cursor.execute('BEGIN')
            
            # Update user balance
            cursor.execute('''
            UPDATE users 
            SET balance = balance + %s,
                total_withdrawn = total_withdrawn - %s,
                updated_at = %s
            WHERE id = %s
            ''', (refund_amount, refund_amount, datetime.utcnow().isoformat(), transaction['user_id']))
            
            # Record refund transaction
            refund_id = f"REFUND-{secrets.token_hex(8)}"
            cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                refund_id, transaction['user_id'], 'WITHDRAWAL_REFUND', refund_amount, 'COMPLETED',
                json.dumps({
                    "original_transaction": transaction_id,
                    "reason": "Withdrawal rejected",
                    "notes": notes
                })
            ))
            
            # Create notification for user
            cursor.execute('''
            INSERT INTO notifications (user_id, type, title, message, data)
            VALUES (%s, %s, %s, %s, %s)
            ''', (
                transaction['user_id'], 'withdrawal',
                'Withdrawal Rejected',
                f'Your withdrawal request for ₦{refund_amount:,.2f} was rejected. The amount has been refunded to your balance.',
                json.dumps({
                    "amount": refund_amount,
                    "transaction_id": transaction_id,
                    "status": status,
                    "notes": notes,
                    "refund_transaction_id": refund_id
                })
            ))
        
        # Update transaction status
        cursor.execute('''
        UPDATE transactions 
        SET status = %s,
            completed_at = CASE WHEN %s IN ('COMPLETED', 'FAILED', 'CANCELLED') THEN %s ELSE completed_at END,
            details = CASE WHEN %s != '' THEN jsonb_set(details, '{admin_notes}', %s::jsonb) ELSE details END,
            updated_at = %s
        WHERE id = %s
        ''', (
            status,
            status, datetime.utcnow().isoformat(),
            notes, json.dumps(notes),
            datetime.utcnow().isoformat(),
            transaction_id
        ))
        
        # Log audit
        admin_user = get_current_user()
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            admin_user['id'], 'ADMIN_TRANSACTION_UPDATE', 'transaction', transaction_id,
            json.dumps({
                "old_status": transaction['status'],
                "new_status": status,
                "notes": notes,
                "user_id": transaction['user_id'],
                "amount": float(transaction['amount'])
            }),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Admin updated transaction: {transaction_id} - {transaction['status']} -> {status}", extra={
            'admin_id': admin_user['id'],
            'transaction_id': transaction_id,
            'old_status': transaction['status'],
            'new_status': status,
            'user_id': transaction['user_id']
        })
        
        return jsonify({
            "success": True,
            "message": "Transaction updated successfully"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Admin update transaction error: {e}")
        raise APIError("Failed to update transaction", 500, "TRANSACTION_UPDATE_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
def admin_get_settings():
    """Admin: Get all settings"""
    category = request.args.get('category')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        query = 'SELECT * FROM admin_settings'
        params = []
        
        if category:
            query += ' WHERE category = %s'
            params.append(category)
        
        query += ' ORDER BY category, key'
        
        cursor.execute(query, params)
        
        settings = []
        for setting in cursor.fetchall():
            setting_data = dict(setting)
            
            # Parse value if it's JSON
            if setting_data['value']:
                try:
                    setting_data['value'] = json.loads(setting_data['value'])
                except:
                    pass
            
            settings.append(setting_data)
        
        # Group by category
        grouped_settings = {}
        for setting in settings:
            category = setting['category']
            if category not in grouped_settings:
                grouped_settings[category] = []
            grouped_settings[category].append(setting)
        
        return jsonify({
            "success": True,
            "settings": grouped_settings
        })
        
    except Exception as e:
        app.logger.error(f"Admin get settings error: {e}")
        raise APIError("Failed to load settings", 500, "SETTINGS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/settings/<key>', methods=['PUT'])
@require_admin
def admin_update_setting(key):
    """Admin: Update a setting"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    value = data.get('value')
    description = data.get('description')
    
    if value is None:
        raise APIError("Value required", 400, "VALUE_REQUIRED")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if setting exists
        cursor.execute('SELECT key FROM admin_settings WHERE key = %s', (key,))
        if not cursor.fetchone():
            raise APIError("Setting not found", 404, "SETTING_NOT_FOUND")
        
        # Convert value to string if it's not already
        if not isinstance(value, str):
            value = json.dumps(value)
        
        # Update setting
        cursor.execute('''
        UPDATE admin_settings 
        SET value = %s,
            description = COALESCE(%s, description),
            updated_at = %s
        WHERE key = %s
        ''', (value, description, datetime.utcnow().isoformat(), key))
        
        # Log audit
        admin_user = get_current_user()
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_value, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            admin_user['id'], 'ADMIN_SETTING_UPDATE', 'setting', key,
            json.dumps({"value": value, "description": description}),
            request.remote_addr
        ))
        
        conn.commit()
        
        app.logger.info(f"Admin updated setting: {key}", extra={
            'admin_id': admin_user['id'],
            'key': key,
            'value': value[:100]  # Log first 100 chars
        })
        
        return jsonify({
            "success": True,
            "message": "Setting updated successfully"
        })
        
    except APIError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Admin update setting error: {e}")
        raise APIError("Failed to update setting", 500, "SETTING_UPDATE_FAILED")
    finally:
        conn.close()

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_get_stats():
    """Admin: Get platform statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get time ranges
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        this_week_start = today - timedelta(days=today.weekday())
        this_month_start = today.replace(day=1)
        
        # User stats
        cursor.execute('''
        SELECT 
            -- Total users
            COUNT(*) as total_users,
            -- Today's registrations
            COUNT(CASE WHEN created_at::date = %s THEN 1 END) as today_registrations,
            -- This week's registrations
            COUNT(CASE WHEN created_at::date >= %s THEN 1 END) as week_registrations,
            -- This month's registrations
            COUNT(CASE WHEN created_at::date >= %s THEN 1 END) as month_registrations,
            -- Active today (logged in today)
            COUNT(CASE WHEN last_login::date = %s THEN 1 END) as active_today,
            -- Active this week
            COUNT(CASE WHEN last_login::date >= %s THEN 1 END) as active_week,
            -- Verified email
            COUNT(CASE WHEN email_verified = TRUE THEN 1 END) as verified_users,
            -- Admins
            COUNT(CASE WHEN is_admin = TRUE THEN 1 END) as admin_users
        FROM users 
        WHERE deleted_at IS NULL
        ''', (today, this_week_start, this_month_start, today, this_week_start))
        
        user_stats = cursor.fetchone()
        
        # Financial stats
        cursor.execute('''
        SELECT 
            -- Total balance
            COALESCE(SUM(balance), 0) as total_balance,
            -- Total earned
            COALESCE(SUM(total_earned), 0) as total_earned,
            -- Total withdrawn
            COALESCE(SUM(total_withdrawn), 0) as total_withdrawn,
            -- Total deposited
            COALESCE(SUM(total_deposited), 0) as total_deposited
        FROM users 
        WHERE deleted_at IS NULL
        ''')
        
        financial_stats = cursor.fetchone()
        
        # Transaction stats
        cursor.execute('''
        SELECT 
            -- Total transactions
            COUNT(*) as total_transactions,
            -- Today's transactions
            COUNT(CASE WHEN created_at::date = %s THEN 1 END) as today_transactions,
            -- Pending withdrawals
            COUNT(CASE WHEN type = 'WITHDRAWAL' AND status = 'PENDING' THEN 1 END) as pending_withdrawals,
            -- Total withdrawal amount pending
            COALESCE(SUM(CASE WHEN type = 'WITHDRAWAL' AND status = 'PENDING' THEN amount ELSE 0 END), 0) as pending_withdrawal_amount,
            -- Total completed withdrawals
            COALESCE(SUM(CASE WHEN type = 'WITHDRAWAL' AND status = 'COMPLETED' THEN amount ELSE 0 END), 0) as total_withdrawn_amount,
            -- Total rewards given
            COALESCE(SUM(CASE WHEN type IN ('SNAKE_REWARD', 'COINFLIP_WIN', 'PLINKO_WIN', 'SPIN_REWARD', 'TIKTOK_DAILY', 'REFERRAL_BONUS', 'WELCOME_BONUS', 'ACHIEVEMENT_REWARD') THEN amount ELSE 0 END), 0) as total_rewards_given
        FROM transactions
        ''', (today,))
        
        transaction_stats = cursor.fetchone()
        
        # Game stats
        cursor.execute('''
        SELECT 
            -- Total game plays
            COUNT(*) as total_game_plays,
            -- Today's game plays
            COUNT(CASE WHEN play_date = %s THEN 1 END) as today_game_plays,
            -- Game distribution
            game_type,
            COUNT(*) as game_count
        FROM game_plays 
        WHERE play_date >= %s
        GROUP BY game_type
        ORDER BY game_count DESC
        ''', (today, this_week_start))
        
        game_stats_raw = cursor.fetchall()
        
        game_stats = {
            "total_game_plays": 0,
            "today_game_plays": 0,
            "by_game": {}
        }
        
        for stat in game_stats_raw:
            if stat['game_type']:
                game_stats['by_game'][stat['game_type']] = stat['game_count']
        
        if game_stats_raw:
            game_stats['total_game_plays'] = sum(stat['game_count'] for stat in game_stats_raw)
            game_stats['today_game_plays'] = next((stat['game_count'] for stat in game_stats_raw if stat['play_date'] == today), 0)
        
        # Recent activity (last 24 hours)
        cursor.execute('''
        SELECT 
            'registration' as type,
            COUNT(*) as count
        FROM users 
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        UNION ALL
        SELECT 
            'withdrawal_request' as type,
            COUNT(*) as count
        FROM transactions 
        WHERE type = 'WITHDRAWAL' AND created_at >= NOW() - INTERVAL '24 hours'
        UNION ALL
        SELECT 
            'game_play' as type,
            COUNT(*) as count
        FROM game_plays 
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        UNION ALL
        SELECT 
            'login' as type,
            COUNT(*) as count
        FROM users 
        WHERE last_login >= NOW() - INTERVAL '24 hours'
        ''')
        
        recent_activity = {}
        for activity in cursor.fetchall():
            recent_activity[activity['type']] = activity['count']
        
        # Assemble response
        stats = {
            "users": {
                "total": user_stats['total_users'],
                "today_registrations": user_stats['today_registrations'],
                "week_registrations": user_stats['week_registrations'],
                "month_registrations": user_stats['month_registrations'],
                "active_today": user_stats['active_today'],
                "active_week": user_stats['active_week'],
                "verified": user_stats['verified_users'],
                "admins": user_stats['admin_users']
            },
            "financial": {
                "total_balance": float(financial_stats['total_balance']),
                "total_earned": float(financial_stats['total_earned']),
                "total_withdrawn": float(financial_stats['total_withdrawn']),
                "total_deposited": float(financial_stats['total_deposited'])
            },
            "transactions": {
                "total": transaction_stats['total_transactions'],
                "today": transaction_stats['today_transactions'],
                "pending_withdrawals": transaction_stats['pending_withdrawals'],
                "pending_withdrawal_amount": float(transaction_stats['pending_withdrawal_amount']),
                "total_withdrawn_amount": float(transaction_stats['total_withdrawn_amount']),
                "total_rewards_given": float(transaction_stats['total_rewards_given'])
            },
            "games": game_stats,
            "recent_activity_24h": recent_activity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify({
            "success": True,
            "stats": stats
        })
        
    except Exception as e:
        app.logger.error(f"Admin get stats error: {e}")
        raise APIError("Failed to load statistics", 500, "STATS_LOAD_FAILED")
    finally:
        conn.close()

# ======================= WHATSAPP ENDPOINTS =======================
@app.route('/api/whatsapp/numbers', methods=['GET'])
def get_whatsapp_numbers():
    """Get active WhatsApp numbers"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT number, label, country_code 
        FROM whatsapp_numbers 
        WHERE is_active = TRUE 
        ORDER BY is_default DESC, sort_order, id
        ''')
        
        numbers = []
        for num in cursor.fetchall():
            numbers.append({
                "number": num['number'],
                "label": num['label'] or 'Support',
                "country_code": num['country_code'] or '+234',
                "formatted": f"{num['country_code'] or '+234'}{num['number']}"
            })
        
        return jsonify({
            "success": True,
            "numbers": numbers
        })
        
    except Exception as e:
        app.logger.error(f"Get WhatsApp numbers error: {e}")
        raise APIError("Failed to load WhatsApp numbers", 500, "WHATSAPP_LOAD_FAILED")
    finally:
        conn.close()

# ======================= SUPPORT ENDPOINTS =======================
@app.route('/api/support/tickets', methods=['GET'])
@require_auth
def get_support_tickets():
    """Get user's support tickets"""
    user = get_current_user()
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    offset = (page - 1) * limit
    
    status = request.args.get('status')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = '''
        SELECT * FROM support_tickets 
        WHERE user_id = %s
        '''
        params = [user['id']]
        
        if status:
            query += ' AND status = %s'
            params.append(status)
        
        # Get total count
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as total', 1)
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        # Get tickets
        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        tickets = []
        for ticket in cursor.fetchall():
            tickets.append(dict(ticket))
        
        return jsonify({
            "success": True,
            "tickets": tickets,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        })
        
    except Exception as e:
        app.logger.error(f"Get support tickets error: {e}")
        raise APIError("Failed to load support tickets", 500, "TICKETS_LOAD_FAILED")
    finally:
        conn.close()

@app.route('/api/support/tickets', methods=['POST'])
@require_auth
def create_support_ticket():
    """Create a support ticket"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    subject = sanitize_input(data.get('subject', ''))
    message = sanitize_input(data.get('message', ''))
    category = data.get('category', 'general')
    priority = data.get('priority', 'medium')
    
    if not subject or not message:
        raise APIError("Subject and message required", 400, "TICKET_DETAILS_REQUIRED")
    
    if len(subject) > 200:
        raise APIError("Subject too long (max 200 characters)", 400, "SUBJECT_TOO_LONG")
    
    if len(message) > 5000:
        raise APIError("Message too long (max 5000 characters)", 400, "MESSAGE_TOO_LONG")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Generate ticket ID
        ticket_id = f"TKT-{secrets.token_hex(6).upper()}"
        
        # Create ticket
        cursor.execute('''
        INSERT INTO support_tickets (user_id, ticket_id, subject, message, category, priority)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        ''', (user['id'], ticket_id, subject, message, category, priority))
        
        ticket_db_id = cursor.fetchone()['id']
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'SUPPORT_TICKET_CREATED', 'support_ticket', ticket_db_id,
            json.dumps({"subject": subject, "category": category, "priority": priority}),
            request.remote_addr
        ))
        
        # Create notification for admins
        cursor.execute('''
        INSERT INTO notifications (user_id, type, title, message, data)
        SELECT id, 'support_ticket', 'New Support Ticket',
               'User %s created a new support ticket: %s',
               %s
        FROM users WHERE is_admin = TRUE
        ''', (user['username'], subject, json.dumps({
            "ticket_id": ticket_id,
            "user_id": user['id'],
            "username": user['username'],
            "subject": subject,
            "category": category,
            "priority": priority
        })))
        
        conn.commit()
        
        app.logger.info(f"Support ticket created: {user['username']} - {ticket_id}", extra={
            'user_id': user['id'],
            'ticket_id': ticket_id,
            'subject': subject,
            'category': category
        })
        
        return jsonify({
            "success": True,
            "message": "Support ticket created successfully",
            "ticket_id": ticket_id
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Create support ticket error: {e}")
        raise APIError("Failed to create support ticket", 500, "TICKET_CREATE_FAILED")
    finally:
        conn.close()

# ======================= FILE UPLOAD ENDPOINTS =======================
@app.route('/api/upload/profile-picture', methods=['POST'])
@require_auth
def upload_profile_picture():
    """Upload profile picture"""
    user = get_current_user()
    
    if 'file' not in request.files:
        raise APIError("No file provided", 400, "NO_FILE")
    
    file = request.files['file']
    
    if file.filename == '':
        raise APIError("No file selected", 400, "NO_FILE_SELECTED")
    
    if not allowed_file(file.filename):
        raise APIError("File type not allowed. Allowed types: PNG, JPG, JPEG, GIF, WEBP", 400, "INVALID_FILE_TYPE")
    
    try:
        # Save file
        filename = secrets.token_hex(8) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filepath = os.path.join(CONFIG.UPLOAD_FOLDER, 'profile_pictures', filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        file.save(filepath)
        
        # Create URL path
        file_url = f"/uploads/profile_pictures/{filename}"
        
        # Update user profile picture in database
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE users 
        SET profile_picture = %s,
            updated_at = %s
        WHERE id = %s
        ''', (file_url, datetime.utcnow().isoformat(), user['id']))
        
        # Log audit
        cursor.execute('''
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_value, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user['id'], 'PROFILE_PICTURE_UPLOADED', 'user', user['id'],
            json.dumps({"file_url": file_url, "filename": filename}),
            request.remote_addr
        ))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"Profile picture uploaded: {user['username']} - {filename}")
        
        return jsonify({
            "success": True,
            "message": "Profile picture uploaded successfully",
            "file_url": file_url
        })
        
    except Exception as e:
        app.logger.error(f"Upload profile picture error: {e}")
        raise APIError("Failed to upload profile picture", 500, "UPLOAD_FAILED")

# ======================= UTILITY ENDPOINTS =======================
@app.route('/api/utils/validate-coupon', methods=['POST'])
def validate_coupon():
    """Validate a coupon code"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    
    if not coupon_code:
        raise APIError("Coupon code required", 400, "COUPON_REQUIRED")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT * FROM coupons 
        WHERE code = %s AND is_active = TRUE 
        AND (valid_until IS NULL OR valid_until > CURRENT_TIMESTAMP)
        AND (max_users IS NULL OR used_count < max_users)
        ''', (coupon_code,))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            return jsonify({
                "success": False,
                "valid": False,
                "message": "Invalid or expired coupon code"
            })
        
        # Check if user has already used this coupon (if user_id provided)
        user_id = data.get('user_id')
        if user_id:
            cursor.execute('''
            SELECT 1 FROM coupon_redemptions 
            WHERE coupon_code = %s AND user_id = %s
            ''', (coupon_code, user_id))
            
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "valid": False,
                    "message": "You have already used this coupon"
                })
        
        return jsonify({
            "success": True,
            "valid": True,
            "coupon": {
                "code": coupon['code'],
                "type": coupon['type'],
                "amount": float(coupon['amount'] or 0),
                "percentage": float(coupon['percentage'] or 0),
                "max_uses_per_user": coupon['max_uses_per_user'],
                "min_deposit": float(coupon['min_deposit'] or 0),
                "valid_until": coupon['valid_until']
            },
            "message": "Coupon is valid"
        })
        
    except Exception as e:
        app.logger.error(f"Validate coupon error: {e}")
        raise APIError("Failed to validate coupon", 500, "COUPON_VALIDATION_FAILED")
    finally:
        conn.close()

@app.route('/api/utils/check-username', methods=['POST'])
def check_username():
    """Check if username is available"""
    data = request.get_json()
    
    if not data:
        raise APIError("No data provided", 400, "NO_DATA")
    
    username = sanitize_input(data.get('username', '').strip().lower())
    
    if not username:
        raise APIError("Username required", 400, "USERNAME_REQUIRED")
    
    if len(username) < 3:
        return jsonify({
            "success": True,
            "available": False,
            "message": "Username must be at least 3 characters"
        })
    
    if not re.match(r'^[a-z0-9_]+$', username):
        return jsonify({
            "success": True,
            "available": False,
            "message": "Username can only contain lowercase letters, numbers, and underscores"
        })
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT 1 FROM users WHERE username = %s', (username,))
        
        if cursor.fetchone():
            return jsonify({
                "success": True,
                "available": False,
                "message": "Username is already taken"
            })
        
        return jsonify({
            "success": True,
            "available": True,
            "message": "Username is available"
        })
        
    except Exception as e:
        app.logger.error(f"Check username error: {e}")
        raise APIError("Failed to check username", 500, "USERNAME_CHECK_FAILED")
    finally:
        conn.close()

# ======================= EMAIL FUNCTIONS =======================
def send_verification_email(email, username, token):
    """Send verification email"""
    if not CONFIG.MAIL_USERNAME or not CONFIG.MAIL_PASSWORD:
        app.logger.warning("Email credentials not configured. Skipping verification email.")
        return
    
    try:
        # Create message
        subject = "Verify Your FLEXIA Account"
        verification_url = f"https://flexia.com/verify-email?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">FLEXIA Gaming Platform</h1>
            </div>
            <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e0e0e0;">
                <h2 style="color: #333; margin-top: 0;">Welcome to FLEXIA, {username}!</h2>
                <p>Thank you for registering with FLEXIA. To complete your registration and start earning rewards, please verify your email address by clicking the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Verify Email Address</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; word-break: break-all;">
                    {verification_url}
                </p>
                <p>This verification link will expire in 24 hours.</p>
                <p>If you didn't create an account with FLEXIA, you can safely ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                <p style="color: #666; font-size: 14px;">
                    Best regards,<br>
                    The FLEXIA Team
                </p>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
                <p>© {datetime.now().year} FLEXIA Gaming Platform. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to FLEXIA, {username}!
        
        Thank you for registering with FLEXIA. To complete your registration and start earning rewards, please verify your email address by visiting:
        
        {verification_url}
        
        This verification link will expire in 24 hours.
        
        If you didn't create an account with FLEXIA, you can safely ignore this email.
        
        Best regards,
        The FLEXIA Team
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG.MAIL_DEFAULT_SENDER
        msg['To'] = email
        
        # Attach parts
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(CONFIG.MAIL_SERVER, CONFIG.MAIL_PORT) as server:
            if CONFIG.MAIL_USE_TLS:
                server.starttls()
            server.login(CONFIG.MAIL_USERNAME, CONFIG.MAIL_PASSWORD)
            server.send_message(msg)
        
        app.logger.info(f"Verification email sent to {email}")
        
    except Exception as e:
        app.logger.error(f"Failed to send verification email: {e}")

def send_password_reset_email(email, username, token):
    """Send password reset email"""
    if not CONFIG.MAIL_USERNAME or not CONFIG.MAIL_PASSWORD:
        app.logger.warning("Email credentials not configured. Skipping password reset email.")
        return
    
    try:
        # Create message
        subject = "Reset Your FLEXIA Password"
        reset_url = f"https://flexia.com/reset-password?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">FLEXIA Gaming Platform</h1>
            </div>
            <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e0e0e0;">
                <h2 style="color: #333; margin-top: 0;">Password Reset Request</h2>
                <p>Hello {username},</p>
                <p>We received a request to reset your password for your FLEXIA account. To reset your password, please click the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Reset Password</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; word-break: break-all;">
                    {reset_url}
                </p>
                <p>This password reset link will expire in 1 hour.</p>
                <p>If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.</p>
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                <p style="color: #666; font-size: 14px;">
                    Best regards,<br>
                    The FLEXIA Team
                </p>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
                <p>© {datetime.now().year} FLEXIA Gaming Platform. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        Hello {username},
        
        We received a request to reset your password for your FLEXIA account. To reset your password, please visit:
        
        {reset_url}
        
        This password reset link will expire in 1 hour.
        
        If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
        
        Best regards,
        The FLEXIA Team
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG.MAIL_DEFAULT_SENDER
        msg['To'] = email
        
        # Attach parts
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(CONFIG.MAIL_SERVER, CONFIG.MAIL_PORT) as server:
            if CONFIG.MAIL_USE_TLS:
                server.starttls()
            server.login(CONFIG.MAIL_USERNAME, CONFIG.MAIL_PASSWORD)
            server.send_message(msg)
        
        app.logger.info(f"Password reset email sent to {email}")
        
    except Exception as e:
        app.logger.error(f"Failed to send password reset email: {e}")

# ======================= STATIC FILE SERVING =======================
@app.route('/')
def index():
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    try:
        return send_from_directory(CONFIG.UPLOAD_FOLDER, filename)
    except FileNotFoundError:
        raise APIError("File not found", 404, "FILE_NOT_FOUND")

# ======================= CATCH-ALL FOR SPA =======================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route for SPA"""
    if path.startswith('api/'):
        raise APIError("API endpoint not found", 404, "ENDPOINT_NOT_FOUND")
    
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= INITIALIZATION =======================
with app.app_context():
    try:
        # Initialize database connection pool
        init_db_pool()
        
        # Initialize database
        init_db()
        
        # Start backup scheduler
        run_backup_scheduler()
        
        # Log successful startup
        app.logger.info("""
╔═══════════════════════════════════════════════════════════════╗
║                FLEXIA PLATFORM v13.0 STARTED                  ║
╠═══════════════════════════════════════════════════════════════╣
║ Database:      {:<45} ║
║ Environment:   {:<45} ║
║ Logging:       {:<45} ║
║ Redis:         {:<45} ║
║ Backup System: {:<45} ║
║ Game Limits:   Enabled ({:<38}) ║
╚═══════════════════════════════════════════════════════════════╝
        """.format(
            "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite",
            os.getenv('ENV', 'development'),
            "Structured JSON + File Rotation",
            "Connected" if redis_client else "Disabled",
            "Enabled (Daily at 2 AM UTC)",
            ", ".join([f"{k}: {v}" for k, v in CONFIG.GAME_DAILY_LIMITS.items()])
        ))
        
    except Exception as e:
        app.logger.critical(f"Failed to initialize application: {e}")
        app.logger.critical(traceback.format_exc())
        raise

# ======================= MAIN ENTRY POINT =======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    
    app.logger.info(f"🚀 Starting FLEXIA Platform v13.0 on port {port} (debug: {debug})")
    
    if os.getenv('ENV') == 'production':
        # Production: use gunicorn or similar
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Development
        app.run(host='0.0.0.0', port=port, debug=debug)
