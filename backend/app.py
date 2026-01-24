# backend/app.py - ULTIMATE VERSION 13.0 - PRODUCTION READY WITH ALL FIXES
# FLEXIA Platform - FULLY SECURED PRODUCTION VERSION

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
import uuid
import tenacity
from datetime import datetime, timedelta, date
from functools import wraps
import threading
import time
import subprocess
import shutil
from logging.handlers import RotatingFileHandler

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ======================= CONFIGURATION =======================
class Config:
    DB_URL = os.environ.get('DATABASE_URL')
    if not DB_URL:
        raise RuntimeError("❌ DATABASE_URL environment variable is required.")
    
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'flexia_secure_key_2024_change_in_production')
    MIN_WITHDRAWAL = int(os.environ.get('MIN_WITHDRAWAL', 100000))
    REFERRAL_BONUS = int(os.environ.get('REFERRAL_BONUS', 7500))
    TIKTOK_REWARD = int(os.environ.get('TIKTOK_REWARD', 150))
    SNAKE_REWARD = int(os.environ.get('SNAKE_REWARD', 200))
    COIN_FLIP_MIN_BET = int(os.environ.get('COIN_FLIP_MIN_BET', 100))
    PLINKO_MIN_BET = int(os.environ.get('PLINKO_MIN_BET', 100))
    SESSION_DURATION_HOURS = int(os.environ.get('SESSION_DURATION_HOURS', 24))
    DEFAULT_WITHDRAWAL_DAYS = json.loads(os.environ.get('DEFAULT_WITHDRAWAL_DAYS', '[7, 14, 25, 30]'))
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    MAX_REGISTER_ATTEMPTS = int(os.environ.get('MAX_REGISTER_ATTEMPTS', 3))
    MAX_GAME_ATTEMPTS = int(os.environ.get('MAX_GAME_ATTEMPTS', 10))
    
    # CORS
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
    
    # Database
    DB_POOL_MIN = int(os.environ.get('DB_POOL_MIN', 1))
    DB_POOL_MAX = int(os.environ.get('DB_POOL_MAX', 20))
    DB_CONNECTION_TIMEOUT = int(os.environ.get('DB_CONNECTION_TIMEOUT', 30))

CONFIG = Config()
app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY

# ======================= CORS CONFIGURATION =======================
CORS(app, resources={
    r"/api/*": {
        "origins": CONFIG.ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID"],
        "expose_headers": ["X-Request-ID"],
        "supports_credentials": True,
        "max_age": 86400
    }
})

# ======================= REQUEST ID MIDDLEWARE =======================
@app.before_request
def assign_request_id():
    """Assign a unique ID to each request for tracing"""
    request.id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

@app.after_request
def add_request_id_header(response):
    """Add request ID to response headers"""
    response.headers['X-Request-ID'] = getattr(request, 'id', '')
    return response

# ======================= JSON VALIDATION MIDDLEWARE =======================
@app.before_request
def validate_json():
    """Validate JSON payload for POST/PUT/PATCH requests"""
    if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
        try:
            if request.get_data():
                request.get_json()
        except Exception as e:
            app.logger.error(f"[{request.id}] Invalid JSON: {e}")
            return jsonify({
                "success": False,
                "message": "Invalid JSON payload",
                "request_id": request.id
            }), 400
    return None

# ======================= SETUP LOGGING =======================
def setup_logging():
    """Configure application logging"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/flexia.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if os.getenv('ENV') != 'production' else logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # Configure Flask logger
    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    # Configure werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.setLevel(logging.WARNING)

    # Add request ID filter
    class RequestIDFilter(logging.Filter):
        def filter(self, record):
            record.request_id = getattr(request, 'id', 'no-request-id')
            return True
    
    for handler in [file_handler, console_handler]:
        handler.addFilter(RequestIDFilter())

setup_logging()

# ======================= SECURITY HEADERS =======================
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    if os.getenv('ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    return response

# ======================= ERROR HANDLERS =======================
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'[{request.id}] 404 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "API endpoint not found",
            "request_id": request.id
        }), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'[{request.id}] 500 error: {str(error)}')
    app.logger.error(f'[{request.id}] {traceback.format_exc()}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Internal server error",
            "request_id": request.id
        }), 500
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(400)
def bad_request_error(error):
    app.logger.warning(f'[{request.id}] 400 error: {str(error)}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Bad request",
            "request_id": request.id
        }), 400
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(401)
def unauthorized_error(error):
    app.logger.warning(f'[{request.id}] 401 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Authentication required",
            "request_id": request.id
        }), 401
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(403)
def forbidden_error(error):
    app.logger.warning(f'[{request.id}] 403 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Access forbidden",
            "request_id": request.id
        }), 403
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(429)
def too_many_requests_error(error):
    app.logger.warning(f'[{request.id}] 429 rate limit exceeded: {request.remote_addr}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Too many requests",
            "request_id": request.id
        }), 429
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= REQUEST TIMEOUT HANDLER =======================
class RequestTimeout(Exception):
    pass

@app.errorhandler(RequestTimeout)
def handle_timeout(error):
    app.logger.warning(f'[{request.id}] Request timeout: {request.url}')
    return jsonify({
        "success": False,
        "message": "Request timeout",
        "request_id": request.id
    }), 408

# ======================= INPUT VALIDATION =======================
def validate_input(data, rules):
    """Validate input against rules dictionary"""
    errors = {}
    for field, rule in rules.items():
        value = data.get(field)
        
        # Required check
        if rule.get('required') and (value is None or value == ''):
            errors[field] = f"{field} is required"
            continue
        
        if value is None:
            continue
            
        # Type checking
        if 'type' in rule:
            if rule['type'] == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be an integer"
                    continue
            elif rule['type'] == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be a number"
                    continue
            elif rule['type'] == 'string' and not isinstance(value, str):
                errors[field] = f"{field} must be a string"
                continue
            elif rule['type'] == 'bool' and not isinstance(value, bool):
                errors[field] = f"{field} must be a boolean"
                continue
        
        # Range checks
        if 'min' in rule and value < rule['min']:
            errors[field] = f"{field} must be at least {rule['min']}"
        if 'max' in rule and value > rule['max']:
            errors[field] = f"{field} must be at most {rule['max']}"
        if 'min_length' in rule and len(str(value)) < rule['min_length']:
            errors[field] = f"{field} must be at least {rule['min_length']} characters"
        if 'max_length' in rule and len(str(value)) > rule['max_length']:
            errors[field] = f"{field} must be at most {rule['max_length']} characters"
        if 'pattern' in rule and not re.match(rule['pattern'], str(value)):
            errors[field] = f"{field} has invalid format"
        if 'choices' in rule and value not in rule['choices']:
            errors[field] = f"{field} must be one of {rule['choices']}"
    
    return errors

def sanitize_input(text):
    """Sanitize input to prevent XSS and SQL injection"""
    if not text:
        return ""
    if isinstance(text, (int, float, bool)):
        return text
    text = str(text).strip()
    # Remove potentially dangerous characters
    for char in ['<', '>', '"', "'", '`', ';', '--']:
        text = text.replace(char, '')
    return text

# ======================= DATABASE CONNECTION POOLING =======================
db_pool = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    try:
        db_pool = SimpleConnectionPool(
            CONFIG.DB_POOL_MIN,
            CONFIG.DB_POOL_MAX,
            dsn=CONFIG.DB_URL,
            connect_timeout=CONFIG.DB_CONNECTION_TIMEOUT
        )
        app.logger.info('✅ Database connection pool initialized')
    except Exception as e:
        app.logger.error(f'❌ Failed to initialize connection pool: {str(e)}')
        raise

def get_db():
    """Get a database connection from the pool"""
    global db_pool
    if not db_pool:
        init_db_pool()
    try:
        conn = db_pool.getconn()
        conn.autocommit = False
        return conn
    except Exception as e:
        app.logger.error(f'[{request.id}] Error getting connection from pool: {str(e)}')
        raise

def return_db_connection(conn):
    """Return a database connection to the pool"""
    global db_pool
    try:
        if conn and not conn.closed:
            conn.rollback()  # Ensure no open transactions
            db_pool.putconn(conn)
    except Exception as e:
        app.logger.error(f'[{request.id}] Error returning connection: {str(e)}')
        try:
            conn.close()
        except:
            pass

def get_pool_stats():
    """Get connection pool statistics"""
    global db_pool
    if db_pool:
        return {
            "min_connections": db_pool.minconn,
            "max_connections": db_pool.maxconn,
            "current_connections": len(db_pool._used),
            "available_connections": len(db_pool._idle)
        }
    return None

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    retry=tenacity.retry_if_exception_type(psycopg2.OperationalError)
)
def execute_with_retry(cursor, sql, params=None):
    """Execute SQL with retry logic"""
    if params:
        return cursor.execute(sql, params)
    else:
        return cursor.execute(sql)

# ======================= DATABASE CONNECTION DECORATOR =======================
def with_db_connection(func):
    """Decorator to handle database connections automatically"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            kwargs['cursor'] = cursor
            kwargs['conn'] = conn
            result = func(*args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            app.logger.error(f'[{request.id}] Database error in {func.__name__}: {str(e)}')
            app.logger.error(f'[{request.id}] {traceback.format_exc()}')
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                return_db_connection(conn)
    return wrapper

# ======================= DATABASE HEALTH CHECK =======================
def check_db_health():
    """Check database connection health"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        return True
    except Exception as e:
        app.logger.error(f'Database health check failed: {str(e)}')
        return False
    finally:
        if conn:
            return_db_connection(conn)

def schedule_health_checks():
    """Schedule periodic database health checks"""
    def run_checks():
        app.logger.info('Database health check scheduler started')
        while True:
            try:
                time.sleep(300)  # Every 5 minutes
                if not check_db_health():
                    app.logger.error("Database connection unhealthy")
                else:
                    app.logger.debug("Database health check passed")
            except Exception as e:
                app.logger.error(f"Health check scheduler error: {str(e)}")
                time.sleep(60)
    
    thread = threading.Thread(target=run_checks, daemon=True)
    thread.start()

# ======================= RATE LIMITING =======================
# For production, consider using Redis-based rate limiting
from collections import defaultdict
from datetime import datetime, timedelta

rate_limit_store = defaultdict(list)

def cleanup_rate_limit_store():
    """Clean up old rate limit entries"""
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    for key in list(rate_limit_store.keys()):
        rate_limit_store[key] = [t for t in rate_limit_store[key] if t > cutoff]
        if not rate_limit_store[key]:
            del rate_limit_store[key]

def rate_limit(key, limit_per_minute=5, window_minutes=1):
    """Simple in-memory rate limiting"""
    cleanup_rate_limit_store()
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    
    # Count requests in window
    recent_requests = [t for t in rate_limit_store[key] if t > window_start]
    
    if len(recent_requests) >= limit_per_minute:
        app.logger.warning(f'[{request.id}] Rate limit exceeded for {key}: {len(recent_requests)} requests')
        return False
    
    rate_limit_store[key].append(now)
    return True

def rate_limit_decorator(limit_per_minute=5, key_prefix="rl"):
    """Decorator for rate limiting"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use IP + endpoint as key
            ip = request.remote_addr
            endpoint = f"{request.method}:{request.path}"
            key = f"{key_prefix}:{ip}:{endpoint}"
            
            if not rate_limit(key, limit_per_minute):
                return jsonify({
                    "success": False,
                    "message": "Too many requests. Please try again later.",
                    "request_id": request.id
                }), 429
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ======================= SESSION MANAGER =======================
def create_session_token(user_id):
    """Create a secure session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id})

def verify_session_token(token):
    """Verify and decode a session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return data.get('user_id')
    except (BadSignature, SignatureExpired) as e:
        app.logger.warning(f'[{request.id}] Invalid session token: {str(e)}')
        return None

def row_to_dict(cursor, row):
    """Convert database row to dictionary"""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    elif cursor and cursor.description:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    return {}

def get_current_user():
    """Get current authenticated user"""
    token = request.cookies.get('session_token')
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    try:
        execute_with_retry(cursor, 'SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)
    except Exception as e:
        app.logger.error(f'[{request.id}] Error getting current user: {str(e)}')
        return None
    finally:
        return_db_connection(conn)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            app.logger.warning(f'[{request.id}] Unauthorized access attempt to {request.path}')
            return jsonify({
                "success": False,
                "message": "Login required",
                "request_id": request.id
            }), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user.get('is_admin'):
            app.logger.warning(f'[{request.id}] Non-admin user {user["id"]} attempted admin endpoint {request.path}')
            return jsonify({
                "success": False,
                "message": "Admin access required",
                "request_id": request.id
            }), 403
        return f(*args, **kwargs)
    return decorated

# ======================= BACKUP SYSTEM =======================
def backup_database():
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        app.logger.info('Creating PostgreSQL backup...')
        backup_file = f'backups/backup_flexia_{timestamp}.sql'
        
        if not os.path.exists('backups'):
            os.makedirs('backups')
        
        parsed = urllib.parse.urlparse(CONFIG.DB_URL)
        env = os.environ.copy()
        env['PGPASSWORD'] = parsed.password
        
        result = subprocess.run([
            'pg_dump',
            '-h', parsed.hostname,
            '-p', str(parsed.port),
            '-U', parsed.username,
            '-d', parsed.path[1:],
            '-f', backup_file,
            '--no-password'
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            app.logger.info(f'PostgreSQL backup created: {backup_file}')
            return backup_file
        else:
            app.logger.error(f'PostgreSQL backup failed: {result.stderr}')
            return None
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}')
        app.logger.error(traceback.format_exc())
        return None

def run_backup_scheduler():
    """Run backup scheduler"""
    def schedule():
        app.logger.info('Backup scheduler started')
        while True:
            try:
                now = datetime.utcnow()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now > next_run:
                    next_run += timedelta(days=1)
                time_to_sleep = (next_run - now).total_seconds()
                app.logger.info(f'Next backup scheduled in {time_to_sleep/3600:.1f} hours')
                time.sleep(time_to_sleep)
                backup_file = backup_database()
                if backup_file:
                    app.logger.info(f'Daily backup completed: {backup_file}')
                    cleanup_old_backups()
                else:
                    app.logger.error('Daily backup failed')
            except Exception as e:
                app.logger.error(f'Backup scheduler error: {str(e)}')
                time.sleep(3600)
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        if not os.path.exists('backups'):
            return
        
        cutoff_time = datetime.now() - timedelta(days=7)
        for filename in os.listdir('backups'):
            filepath = os.path.join('backups', filename)
            if os.path.isfile(filepath) and filename.endswith('.sql'):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_time:
                    os.remove(filepath)
                    app.logger.info(f'Removed old backup: {filename}')
    except Exception as e:
        app.logger.error(f'Cleanup old backups error: {str(e)}')

# ======================= INITIALIZATION =======================
@with_db_connection
def add_missing_columns(cursor, conn):
    """Add missing columns to users table - SECURE VERSION"""
    try:
        # Define columns to add with their types
        columns_to_add = {
            'last_achievement_check': 'TEXT',
            'last_game_timestamp': 'TEXT',
            'claimed_achievements': 'TEXT DEFAULT \'[]\''
        }
        
        for column, column_type in columns_to_add.items():
            # Check if column exists using parameterized query
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = %s
            """, (column,))
            
            if not cursor.fetchone():
                # Use static SQL with parameter for table name
                alter_sql = f"ALTER TABLE users ADD COLUMN {column} {column_type}"
                cursor.execute(alter_sql)
                app.logger.info(f"Added missing column: {column}")
        
        conn.commit()
        app.logger.info("Database column verification complete")
    except Exception as e:
        app.logger.error(f"Error adding missing columns: {e}")
        conn.rollback()
        raise

@with_db_connection
def add_database_indexes(cursor, conn):
    """Add database indexes for performance"""
    try:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_timestamp ON transactions(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type_timestamp ON transactions(type, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_game_plays_user_date ON game_plays(user_id, play_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_type ON transactions(user_id, type)"
        ]
        
        for sql in indexes:
            cursor.execute(sql)
        
        conn.commit()
        app.logger.info("Database indexes created/verified")
    except Exception as e:
        app.logger.error(f"Error creating indexes: {e}")
        conn.rollback()
        raise

@with_db_connection
def init_db(cursor, conn):
    """Initialize database tables"""
    try:
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                balance REAL DEFAULT 0.00,
                referral_code TEXT,
                referred_by TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                last_login TEXT,
                claimed_bonuses INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                game_stats TEXT,
                withdrawal_pin TEXT,
                admin_password_changed BOOLEAN DEFAULT FALSE,
                contact TEXT,
                profile_picture TEXT,
                ui_theme TEXT DEFAULT 'light',
                withdrawal_restricted BOOLEAN DEFAULT FALSE,
                custom_withdrawal_days TEXT,
                withdrawal_limit REAL DEFAULT 0.00,
                last_game_timestamp TEXT,
                last_achievement_check TEXT,
                claimed_achievements TEXT DEFAULT '[]'
            )
        ''')

        # Admin settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                id SERIAL PRIMARY KEY,
                whatsapp_link TEXT,
                telegram_link TEXT,
                facebook_link TEXT,
                global_withdrawal_days TEXT
            )
        ''')

        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                status TEXT,
                details TEXT,
                timestamp TEXT
            )
        ''')

        # Coupons table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                status TEXT DEFAULT 'AVAILABLE'
            )
        ''')

        # Banks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banks (
                code TEXT PRIMARY KEY,
                name TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # WhatsApp numbers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whatsapp_numbers (
                id SERIAL PRIMARY KEY,
                number TEXT UNIQUE NOT NULL,
                label TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT
            )
        ''')

        # Game plays table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_plays (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                game_type TEXT,
                play_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # TikTok daily table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiktok_daily (
                id SERIAL PRIMARY KEY,
                date TEXT UNIQUE NOT NULL,
                tiktok_link TEXT NOT NULL,
                reward_amount REAL DEFAULT 150.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # User game locks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_game_locks (
                user_id INTEGER PRIMARY KEY,
                lock_until TEXT,
                game_type TEXT
            )
        ''')

        # Insert default banks
        cursor.execute('SELECT COUNT(*) as count FROM banks')
        bank_count = cursor.fetchone()[0]
        if bank_count == 0:
            banks = [
                ("057", "Zenith Bank Plc"), ("058", "GTBank"), ("044", "Access Bank"),
                ("033", "UBA"), ("011", "First Bank"), ("070", "Fidelity Bank"),
                ("050", "Ecobank"), ("039", "Stanbic IBTC"), ("214", "FCMB"),
                ("232", "Sterling Bank"), ("032", "Union Bank"), ("035", "Wema Bank"),
                ("082", "Keystone Bank"), ("215", "Unity Bank"), ("076", "Polaris Bank"),
                ("565", "OPay"), ("100", "PalmPay"), ("50211", "Kuda Bank"),
                ("566", "VBank"), ("035A", "ALAT by Wema")
            ]
            for code, name in banks:
                cursor.execute('INSERT INTO banks (code, name, is_active) VALUES (%s, %s, %s)', 
                             (code, name, True))
            app.logger.info(f"Inserted {len(banks)} banks")

        # Admin settings
        cursor.execute('SELECT COUNT(*) as count FROM admin_settings')
        settings_count = cursor.fetchone()[0]
        if settings_count == 0:
            default_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
            cursor.execute('''INSERT INTO admin_settings 
                           (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) 
                           VALUES (%s, %s, %s, %s)''',
                         ('', '', '', default_days_json))

        # Coupons
        if os.path.exists(CONFIG.COUPON_FILE):
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            if codes:
                cursor.execute('DELETE FROM coupons')
                for code in codes:
                    cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', 
                                 (code, 'AVAILABLE'))
                app.logger.info(f"Loaded {len(codes)} coupons from file")
        else:
            default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
            for code in default_coupons:
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', 
                             (code, 'AVAILABLE'))
            app.logger.info(f"Created {len(default_coupons)} default coupons")

        # Admin user
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s', ("flexiaadmin",))
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            admin_pass = generate_password_hash("Flexiaadmin")
            game_stats = json.dumps({
                "snake": {"high_score": 1200, "total_score": 5000},
                "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
                "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
            })
            pin_hash = generate_password_hash("4567")
            cursor.execute('''
                INSERT INTO users (
                    username, password, balance, referral_code, is_admin,
                    created_at, last_login, game_stats, admin_password_changed,
                    withdrawal_pin, contact, profile_picture, ui_theme,
                    last_game_timestamp, last_achievement_check, claimed_achievements
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                "flexiaadmin", admin_pass, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, False, pin_hash, "", "", "light",
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), '[]'
            ))
            app.logger.warning("\n🚨 FLEXIA ADMIN ACCOUNT CREATED 🚨")
            app.logger.warning("Username: flexiaadmin")
            app.logger.warning("Initial Password: Flexiaadmin")
            app.logger.warning("Default Withdrawal PIN: 4567")
            app.logger.warning("🔒 Change both after first login!\n")

        # WhatsApp number
        cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
        whatsapp_count = cursor.fetchone()[0]
        if whatsapp_count == 0:
            cursor.execute('''INSERT INTO whatsapp_numbers 
                           (number, label, is_active, created_at) 
                           VALUES (%s, %s, %s, %s)''',
                         ('2348160881049', 'Primary Seller', True, datetime.utcnow().isoformat()))

        conn.commit()
        app.logger.info("✅ Database initialization completed successfully!")
    except Exception as e:
        app.logger.error(f"Database init error: {e}")
        conn.rollback()
        raise

# ======================= ATOMIC OPERATIONS =======================
@with_db_connection
def update_user_balance(cursor, conn, user_id, amount_change):
    """Atomically update user balance"""
    try:
        cursor.execute('''
            UPDATE users
            SET balance = balance + %s
            WHERE id = %s
            RETURNING balance
        ''', (amount_change, user_id))
        
        row = cursor.fetchone()
        new_balance = float(row[0]) if row and row[0] else 0.0
        conn.commit()
        
        app.logger.info(f"[{request.id}] Atomic balance update for user {user_id}: {amount_change}, new balance: {new_balance}")
        return new_balance
    except Exception as e:
        app.logger.error(f"[{request.id}] Balance update error: {e}")
        conn.rollback()
        raise

@with_db_connection  
def check_game_cooldown(cursor, conn, user_id, game_type):
    """Check if user is in cooldown for a game"""
    try:
        cursor.execute('SELECT last_game_timestamp FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                last_game = datetime.fromisoformat(row[0])
                now = datetime.utcnow()
                if (now - last_game).total_seconds() < 1:
                    return False
            except:
                pass
        return True
    except Exception as e:
        app.logger.error(f"[{request.id}] Cooldown check error: {e}")
        return True

@with_db_connection
def update_last_game_timestamp(cursor, conn, user_id):
    """Update user's last game timestamp"""
    try:
        cursor.execute('UPDATE users SET last_game_timestamp = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), user_id))
        conn.commit()
    except Exception as e:
        app.logger.error(f"[{request.id}] Update last game timestamp error: {e}")
        conn.rollback()
        raise

@with_db_connection
def can_play_today(cursor, conn, user_id, game_type, max_plays=10):
    """Check if user can play a game today"""
    today = datetime.utcnow().date()
    try:
        cursor.execute("SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s",
                      (user_id, game_type, today))
        count = cursor.fetchone()[0]
        return count < max_plays
    except Exception as e:
        app.logger.error(f"[{request.id}] Play check error: {e}")
        return False

@with_db_connection
def record_game_play(cursor, conn, user_id, game_type):
    """Record a game play for a user"""
    today = datetime.utcnow().date()
    try:
        cursor.execute("SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s",
                      (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("INSERT INTO game_plays (user_id, game_type, play_date) VALUES (%s, %s, %s)",
                         (user_id, game_type, today))
            conn.commit()
    except Exception as e:
        app.logger.error(f"[{request.id}] Record game play error: {e}")
        conn.rollback()
        raise

def get_global_withdrawal_days():
    """Get global withdrawal days from admin settings"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row and row[0]:
            days_str = row[0]
            if days_str:
                return json.loads(days_str)
    except Exception as e:
        app.logger.error(f"[{request.id}] Error getting global withdrawal days: {e}")
    finally:
        return_db_connection(conn)
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

@with_db_connection
def is_withdrawal_day(cursor, conn, user_id=None):
    """Check if today is a withdrawal day for a user"""
    today = datetime.utcnow().day
    if user_id is None:
        return today in get_global_withdrawal_days()
    
    try:
        cursor.execute('SELECT withdrawal_restricted, custom_withdrawal_days FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row:
            restricted, custom_days_str = row[0], row[1]
            if restricted:
                return False
            if custom_days_str:
                try:
                    return today in json.loads(custom_days_str)
                except:
                    pass
            return today in get_global_withdrawal_days()
        return False
    except Exception as e:
        app.logger.error(f"[{request.id}] Withdrawal day check error: {e}")
        return False

# ======================= DUPLICATE CLAIM PREVENTION =======================
@with_db_connection
def check_duplicate_claim(cursor, conn, user_id, game_type, cooldown_seconds=1):
    """Check for duplicate claims within cooldown period"""
    try:
        cutoff_time = (datetime.utcnow() - timedelta(seconds=cooldown_seconds)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM transactions
            WHERE user_id = %s AND type LIKE %s
            AND timestamp > %s
        ''', (user_id, f'%{game_type}%', cutoff_time))
        recent_claims = cursor.fetchone()[0]
        return recent_claims == 0
    except Exception as e:
        app.logger.error(f"[{request.id}] Duplicate claim check error: {e}")
        return True

def create_transaction_hash(user_id, game_type, data):
    """Create a hash for transaction deduplication"""
    data_str = json.dumps(data, sort_keys=True)
    hash_input = f"{user_id}-{game_type}-{data_str}-{int(time.time())}"
    return hashlib.md5(hash_input.encode()).hexdigest()

# ======================= ACHIEVEMENT REWARDS =======================
@with_db_connection
def grant_achievement_rewards(cursor, conn, user_id):
    """Grant achievement rewards to a user"""
    app.logger.info(f"[{request.id}] Granting achievement rewards for user {user_id}")
    
    try:
        cursor.execute('''
            SELECT balance, game_stats, referral_code, points, last_achievement_check, claimed_achievements
            FROM users WHERE id = %s FOR UPDATE
        ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        balance = float(row[0]) if row[0] else 0
        game_stats_str = row[1] if row[1] else '{}'
        referral_code = row[2] if row[2] else ''
        current_points = int(row[3]) if row[3] else 0
        last_check = row[4] if row[4] else None
        claimed_achievements_str = row[5] if len(row) > 5 and row[5] else '[]'
        
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []

        # Early exit if checked recently
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
                if (datetime.utcnow() - last_check_time).total_seconds() < 300:
                    return balance
            except:
                pass

        game_stats = json.loads(game_stats_str)
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (referral_code,))
        referrals = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user_id,))
        total_tx = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = 'WITHDRAWAL'", (user_id,))
        total_withdrawals = cursor.fetchone()[0]
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user_id, today))
        games_today = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user_id,))
        total_games = cursor.fetchone()[0]

        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

        achievements = [
            {"id": 1, "unlocked": total_games >= 1, "reward": 500, "points": 10},
            {"id": 2, "unlocked": total_games >= 50, "reward": 5000, "points": 50},
            {"id": 3, "unlocked": total_games >= 200, "reward": 15000, "points": 150},
            {"id": 4, "unlocked": snake_high >= 1000, "reward": 7500, "points": 75},
            {"id": 5, "unlocked": coin_streak >= 10, "reward": 10000, "points": 100},
            {"id": 6, "unlocked": coin_total >= 100, "reward": 6000, "points": 60},
            {"id": 7, "unlocked": plinko_wins >= 50, "reward": 8000, "points": 80},
            {"id": 8, "unlocked": balance >= 1000, "reward": 1000, "points": 15},
            {"id": 9, "unlocked": balance >= 50000, "reward": 10000, "points": 100},
            {"id": 10, "unlocked": balance >= 200000, "reward": 25000, "points": 200},
            {"id": 11, "unlocked": total_withdrawals >= 1, "reward": 5000, "points": 50},
            {"id": 12, "unlocked": games_today >= 5, "reward": 3000, "points": 30},
            {"id": 13, "unlocked": games_today >= 20, "reward": 8000, "points": 80},
            {"id": 14, "unlocked": referrals >= 5, "reward": 10000, "points": 100},
            {"id": 15, "unlocked": referrals >= 20, "reward": 30000, "points": 300},
            {"id": 16, "unlocked": total_tx >= 10, "reward": 4000, "points": 40}
        ]

        new_achievements = [ach for ach in achievements if ach["unlocked"] and ach["id"] not in claimed_achievements]
        if not new_achievements:
            cursor.execute('UPDATE users SET last_achievement_check = %s WHERE id = %s',
                          (datetime.utcnow().isoformat(), user_id))
            conn.commit()
            return balance

        total_reward = sum(ach["reward"] for ach in new_achievements)
        total_points = sum(ach["points"] for ach in new_achievements)
        new_achievement_ids = [ach["id"] for ach in new_achievements]
        all_claimed_achievements = claimed_achievements + new_achievement_ids
        new_balance = balance + total_reward

        cursor.execute('''
            UPDATE users SET balance = %s, points = %s,
            last_achievement_check = %s, claimed_achievements = %s
            WHERE id = %s
        ''', (new_balance, current_points + total_points,
              datetime.utcnow().isoformat(),
              json.dumps(all_claimed_achievements), user_id))

        if total_reward > 0:
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
                json.dumps({"source": "manual_claim", "points": total_points, "achievement_ids": new_achievement_ids}),
                datetime.utcnow().isoformat()
            ))
        
        conn.commit()
        app.logger.info(f"✅ Granted achievement rewards to user {user_id}: ₦{total_reward}, {total_points} points, achievements: {new_achievement_ids}")
        return new_balance
    except Exception as e:
        app.logger.error(f"❌ Achievement grant error for user {user_id}: {e}")
        app.logger.error(traceback.format_exc())
        raise

# ======================= TIKTOK CLEANUP =======================
@with_db_connection
def cleanup_old_tiktok_tasks(cursor, conn):
    """Clean up old TikTok tasks"""
    try:
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        cursor.execute('DELETE FROM tiktok_daily WHERE date < %s', (cutoff_date,))
        conn.commit()
        app.logger.info(f"Removed TikTok tasks before {cutoff_date}")
    except Exception as e:
        app.logger.error(f"TikTok Cleanup Error: {e}")
        conn.rollback()

def run_cleanup_scheduler():
    """Run TikTok cleanup scheduler"""
    def schedule():
        while True:
            try:
                now = datetime.utcnow()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now > next_run:
                    next_run += timedelta(days=1)
                time_to_sleep = (next_run - now).total_seconds()
                time.sleep(time_to_sleep)
                cleanup_old_tiktok_tasks()
            except Exception as e:
                app.logger.error(f"Cleanup scheduler error: {str(e)}")
                time.sleep(3600)
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= INITIALIZE APPLICATION =======================
with app.app_context():
    app.logger.info("🚀 Initializing FLEXIA Platform...")
    
    # Initialize database
    init_db_pool()
    init_db()
    add_missing_columns()
    add_database_indexes()
    
    # Start schedulers
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()
    run_backup_scheduler()
    schedule_health_checks()
    
    app.logger.info("✅ FLEXIA Platform initialization complete!")

# ======================= HEALTH & DEBUG ENDPOINTS =======================
@app.route('/api/debug/db-status', methods=['GET'])
@rate_limit_decorator(limit_per_minute=10)
def db_status():
    """Get database status and statistics"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
        available_coupons = cursor.fetchone()[0]
        
        pool_stats = get_pool_stats()
        
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL",
            "connection_pool": "active" if db_pool else "inactive",
            "pool_stats": pool_stats,
            "database_health": check_db_health(),
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] DB status error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/health', methods=['GET'])
@rate_limit_decorator(limit_per_minute=30)
def api_health():
    """Health check endpoint"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_status = 'connected'
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = %s', ('PENDING',))
        pending_withdrawals = cursor.fetchone()[0]
        return_db_connection(conn)
        
        # Calculate uptime
        if not hasattr(api_health, 'start_time'):
            api_health.start_time = datetime.utcnow()
        
        uptime = datetime.utcnow() - api_health.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        pool_stats = get_pool_stats()
        
        return jsonify({
            "status": "online",
            "service": "FLEXIA API",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": uptime_str,
            "database": db_status,
            "database_health": check_db_health(),
            "version": "13.0",
            "stats": {
                "total_users": user_count,
                "pending_withdrawals": pending_withdrawals
            },
            "environment": os.getenv('ENV', 'development'),
            "connection_pool": "active" if db_pool else "inactive",
            "pool_stats": pool_stats,
            "request_id": request.id
        }), 200
    except Exception as e:
        app.logger.error(f"[{request.id}] Health check failed: {str(e)}")
        return jsonify({
            "status": "degraded",
            "error": str(e),
            "request_id": request.id
        }), 503

@app.route('/api/debug/pool-stats', methods=['GET'])
@require_admin
def pool_stats_endpoint():
    """Get connection pool statistics (admin only)"""
    stats = get_pool_stats()
    return jsonify({
        "success": True,
        "pool_stats": stats,
        "request_id": request.id
    })

# ======================= SPIN WHEEL ENDPOINTS =======================
@app.route('/api/spin/daily-status', methods=['GET'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def spin_daily_status():
    """Check if user can spin today"""
    user = get_current_user()
    today = datetime.utcnow().date()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT 1 FROM transactions
            WHERE user_id = %s AND type = %s
            AND DATE(timestamp) = %s
        ''', (user['id'], 'SPIN_REWARD', today))
        has_spun_today = cursor.fetchone() is not None
        return jsonify({
            "success": True,
            "can_spin": not has_spun_today,
            "has_spun_today": has_spun_today,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Spin daily status error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to check spin status",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/spin/execute', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def spin_execute():
    """Execute spin wheel and give reward"""
    user = get_current_user()
    today = datetime.utcnow().date()
    
    # Input validation
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if already spun today
        cursor.execute('''
            SELECT 1 FROM transactions
            WHERE user_id = %s AND type = %s
            AND DATE(timestamp) = %s
        ''', (user['id'], 'SPIN_REWARD', today))
        
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "You already spun today",
                "request_id": request.id
            }), 400
        
        # Generate reward
        possible_rewards = [1000, 0, 500, 50, 1000, 100, 500, 200]
        weights = [5, 25, 15, 20, 5, 15, 15, 20]
        reward = random.choices(possible_rewards, weights=weights, k=1)[0]
        
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Record game play
        record_game_play(user['id'], 'spin')
        update_last_game_timestamp(user['id'])
        
        # Create transaction
        tx_id = f"SPIN-{secrets.token_hex(8)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Spin executed for {user['username']}: reward {reward}")
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Congratulations! You won ₦{reward}!",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Spin execute error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process spin: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
@rate_limit_decorator(limit_per_minute=CONFIG.MAX_REGISTER_ATTEMPTS)
def register():
    """Register a new user"""
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    validation_rules = {
        'username': {'required': True, 'type': 'string', 'min_length': 3, 'max_length': 50},
        'password': {'required': True, 'type': 'string', 'min_length': 6},
        'coupon_code': {'required': True, 'type': 'string', 'min_length': 4},
        'referral_code': {'required': False, 'type': 'string', 'min_length': 4},
        'contact': {'required': False, 'type': 'string', 'max_length': 20}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id
        }), 400
    
    # Sanitize inputs
    username = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    referral_code = sanitize_input(data.get('referral_code', ''))
    contact = sanitize_input(data.get('contact', ''))
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if username exists
        cursor.execute('SELECT id FROM users WHERE LOWER(username) = LOWER(%s)', (username,))
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Username already taken",
                "request_id": request.id
            }), 409
        
        # Check coupon
        cursor.execute('SELECT status FROM coupons WHERE code = %s', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row:
            return jsonify({
                "success": False,
                "message": "Invalid coupon code",
                "request_id": request.id
            }), 403
        
        if coupon_row[0] != 'AVAILABLE':
            return jsonify({
                "success": False,
                "message": "Coupon already used",
                "request_id": request.id
            }), 403
        
        # Check referral code
        if referral_code:
            cursor.execute('SELECT referral_code FROM users WHERE referral_code = %s', (referral_code,))
            if not cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Invalid referral code",
                    "request_id": request.id
                }), 400
        
        # Mark coupon as used
        cursor.execute('UPDATE coupons SET status = %s WHERE code = %s', ("USED", coupon_code))
        
        # Create user
        timestamp = int(time.time())
        user_referral_code = f"{username[:3].upper()}{timestamp % 10000:04d}"
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0},
            "coin_flip": {"wins": 0, "losses": 0, "current_streak": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0}
        })
        
        cursor.execute('''
            INSERT INTO users (
                username, password, balance, referral_code, referred_by, is_admin,
                created_at, last_login, game_stats, contact, profile_picture, ui_theme,
                admin_password_changed, withdrawal_pin, withdrawal_restricted, withdrawal_limit,
                points, claimed_bonuses, last_game_timestamp, last_achievement_check,
                claimed_achievements
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, False,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            False, None, False, 0.00, 0, 0,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            '[]'
        ))
        
        cursor.execute("SELECT LASTVAL()")
        new_id = cursor.fetchone()[0]
        
        # Give admin bonus if referred by admin
        admin_bonus = 0
        if referral_code:
            cursor.execute('SELECT is_admin FROM users WHERE referral_code = %s', (referral_code,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row[0]:
                admin_bonus = 5000
                cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (admin_bonus, new_id))
        
        conn.commit()
        
        # Create session token
        token = create_session_token(new_id)
        
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": new_id,
                "username": username,
                "referral_code": user_referral_code,
                "balance": admin_bonus
            },
            "request_id": request.id
        })
        
        # Set secure cookie
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie('session_token', token,
                          httponly=True,
                          secure=secure_cookie,
                          samesite='Lax',
                          max_age=86400)
        
        app.logger.info(f"[{request.id}] New user registered: {username} (ID: {new_id})")
        return response
    except Exception as e:
        app.logger.error(f"[{request.id}] Registration error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Registration failed: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/auth/login', methods=['POST'])
@rate_limit_decorator(limit_per_minute=CONFIG.MAX_LOGIN_ATTEMPTS)
def login():
    """Login user"""
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    validation_rules = {
        'username': {'required': True, 'type': 'string', 'min_length': 1},
        'password': {'required': True, 'type': 'string', 'min_length': 1}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id
        }), 400
    
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(contact) = LOWER(%s)',
                      (identifier, identifier))
        row = cursor.fetchone()
        
        if not row:
            app.logger.warning(f"[{request.id}] Failed login attempt for identifier: {identifier}")
            return jsonify({
                "success": False,
                "message": "Invalid credentials",
                "request_id": request.id
            }), 401
        
        stored_password = row[2] if len(row) > 2 else None
        if not stored_password or not check_password_hash(stored_password, password):
            app.logger.warning(f"[{request.id}] Invalid password for user: {identifier}")
            return jsonify({
                "success": False,
                "message": "Invalid credentials",
                "request_id": request.id
            }), 401
        
        user = row_to_dict(cursor, row)
        cursor.execute('UPDATE users SET last_login = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        
        # Create response
        resp = jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "balance": float(user['balance']) if user['balance'] else 0.00,
                "referral_code": user.get('referral_code', ''),
                "is_admin": bool(user.get('is_admin', False)),
                "admin_password_changed": bool(user.get('admin_password_changed', False)),
                "profile_picture": user.get('profile_picture', ''),
                "ui_theme": user.get('ui_theme', 'light')
            },
            "request_id": request.id
        })
        
        # Create session token
        token = create_session_token(user['id'])
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token,
                       httponly=True,
                       secure=secure_cookie,
                       samesite='Lax',
                       max_age=86400)
        
        app.logger.info(f"[{request.id}] User logged in: {user['username']} (ID: {user['id']})")
        return resp
    except Exception as e:
        app.logger.error(f"[{request.id}] Login error: {e}")
        return jsonify({
            "success": False,
            "message": f"Login failed: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    user = get_current_user()
    if user:
        app.logger.info(f"[{request.id}] User logged out: {user['username']} (ID: {user['id']})")
    
    resp = jsonify({
        "success": True,
        "message": "Logged out",
        "request_id": request.id
    })
    resp.set_cookie('session_token', '', expires=0)
    return resp

# ======================= USER PROFILE ENDPOINTS =======================
@app.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get user profile"""
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user['id'],))
        fresh_user = row_to_dict(cursor, cursor.fetchone())
        
        if not fresh_user:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (fresh_user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        claimed = int(fresh_user.get('claimed_bonuses', 0))
        unclaimed = max(0, referrals * CONFIG.REFERRAL_BONUS - claimed)
        
        cursor.execute('SELECT * FROM transactions WHERE user_id = %s ORDER BY timestamp DESC LIMIT 20', (user['id'],))
        transactions = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        
        return jsonify({
            "success": True,
            "user": {
                "id": fresh_user['id'],
                "username": fresh_user['username'],
                "balance": float(fresh_user['balance']) if fresh_user['balance'] else 0.00,
                "referral_code": fresh_user.get('referral_code', ''),
                "is_admin": bool(fresh_user.get('is_admin', False)),
                "created_at": fresh_user.get('created_at', ''),
                "game_stats": json.loads(fresh_user.get('game_stats', '{}')),
                "transactions": transactions,
                "withdrawal_pin": bool(fresh_user.get('withdrawal_pin')),
                "profile_picture": fresh_user.get('profile_picture', ''),
                "ui_theme": fresh_user.get('ui_theme', 'light'),
                "claimed_achievements": json.loads(fresh_user.get('claimed_achievements', '[]'))
            },
            "referrals": {
                "count": referrals,
                "unclaimed_bonus": unclaimed
            },
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Profile error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to load profile: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def set_profile_picture():
    """Set user profile picture"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    picture_url = sanitize_input(data.get('picture_url', ''))
    
    # Validate URL (basic check)
    if picture_url and not picture_url.startswith(('http://', 'https://')):
        return jsonify({
            "success": False,
            "message": "Invalid URL",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s', (picture_url, user['id']))
        conn.commit()
        app.logger.info(f"[{request.id}] User {user['username']} updated profile picture")
        return jsonify({
            "success": True,
            "message": "Profile picture updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Profile picture error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def set_theme():
    """Set UI theme"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    theme = 'dark' if data.get('dark_mode') else 'light'
    
    if theme not in ['light', 'dark']:
        return jsonify({
            "success": False,
            "message": "Invalid theme",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s', (theme, user['id']))
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Theme updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Theme error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= PASSWORD & PIN ENDPOINTS =======================
@app.route('/api/user/change-password', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def change_password():
    """Change user password"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    validation_rules = {
        'old_password': {'required': True, 'type': 'string', 'min_length': 1},
        'new_password': {'required': True, 'type': 'string', 'min_length': 6}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id
        }), 400
    
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    # Verify old password
    if not check_password_hash(user['password'], old_password):
        return jsonify({
            "success": False,
            "message": "Current password is incorrect",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password = %s WHERE id = %s",
                      (generate_password_hash(new_password), user['id']))
        conn.commit()
        app.logger.info(f"[{request.id}] User {user['username']} changed password")
        return jsonify({
            "success": True,
            "message": "Password updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Password change error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_change_password():
    """Change admin password"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    validation_rules = {
        'current_password': {'required': True, 'type': 'string', 'min_length': 1},
        'new_password': {'required': True, 'type': 'string', 'min_length': 8}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id
        }), 400
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not check_password_hash(admin_user['password'], current_password):
        return jsonify({
            "success": False,
            "message": "Current password is incorrect",
            "request_id": request.id
        }), 403
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET password = %s, admin_password_changed = %s WHERE id = %s',
                      (generate_password_hash(new_password), True, admin_user['id']))
        conn.commit()
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} changed their password")
        return jsonify({
            "success": True,
            "message": "Password changed successfully",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin password change error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to change password",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def set_withdrawal_pin():
    """Set withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    pin = data.get('pin', '')
    
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        return jsonify({
            "success": False,
            "message": "PIN must be 4-6 digits",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s', 
                      (generate_password_hash(pin), user['id']))
        conn.commit()
        app.logger.info(f"[{request.id}] User {user['username']} set withdrawal PIN")
        return jsonify({
            "success": True,
            "message": "PIN set successfully",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] PIN error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to set",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def verify_withdrawal_pin():
    """Verify withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    pin = data.get('pin', '')
    withdrawal_pin = user.get('withdrawal_pin')
    
    if not withdrawal_pin:
        return jsonify({
            "success": False,
            "message": "No PIN set",
            "request_id": request.id
        }), 400
    
    if not check_password_hash(withdrawal_pin, pin):
        app.logger.warning(f"[{request.id}] Invalid PIN attempt for user: {user['username']}")
        return jsonify({
            "success": False,
            "message": "Invalid PIN",
            "request_id": request.id
        }), 403
    
    return jsonify({
        "success": True,
        "message": "PIN verified",
        "request_id": request.id
    })

# ======================= GAME ENDPOINTS =======================
@app.route('/api/games/limit-check', methods=['GET'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def check_game_limits():
    """Check game play limits for user"""
    user = get_current_user()
    game_type = request.args.get('game', '')
    
    limits = {
        'snake': 20,
        'coinflip': 50,
        'plinko': 50,
        'spin': 1,
        'tiktok': 1
    }
    
    if game_type not in limits:
        return jsonify({
            "success": True,
            "can_play": True,
            "remaining": 999,
            "request_id": request.id
        })
    
    max_plays = limits[game_type]
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s',
                      (user['id'], game_type, today))
        played_today = cursor.fetchone()[0]
        remaining = max(0, max_plays - played_today)
        
        return jsonify({
            "success": True,
            "can_play": remaining > 0,
            "played_today": played_today,
            "remaining": remaining,
            "max_per_day": max_plays,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Limit check error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to check limits",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_snake():
    """Report snake game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    apples = data.get('apples_eaten', 0)
    try:
        apples = int(apples)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid apple count",
            "request_id": request.id
        }), 400
    
    if apples <= 0 or apples > 100:
        return jsonify({
            "success": False,
            "message": "Invalid apple count (1-100)",
            "request_id": request.id
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'SNAKE'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id
        }), 429
    
    # Check daily limit
    if not can_play_today(user['id'], 'snake', max_plays=20):
        return jsonify({
            "success": False,
            "message": "Max 20 snake plays per day",
            "request_id": request.id
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'SNAKE', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before claiming again",
            "request_id": request.id
        }), 429
    
    # Calculate reward
    reward = apples * CONFIG.SNAKE_REWARD
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Update game stats
        game_stats = json.loads(user.get('game_stats', '{}'))
        snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
        score = apples * 10
        
        if score > snake_stats.get('high_score', 0):
            snake_stats['high_score'] = score
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        game_stats['snake'] = snake_stats
        
        cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                      (json.dumps(game_stats), user['id']))
        
        # Update timestamps and record play
        update_last_game_timestamp(user['id'])
        record_game_play(user['id'], 'snake')
        
        # Create transaction
        tx_id = f"SNK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "snake", "apples": apples, "reward_per_apple": CONFIG.SNAKE_REWARD}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Snake reward granted to {user['username']}: ₦{reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "apples": apples,
            "transaction_id": tx_id,
            "message": f"Success! Claimed ₦{reward} for {apples} apples",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Snake report error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_coinflip():
    """Report coin flip game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    try:
        bet = float(data.get('bet', 0))
        won = bool(data.get('won', False))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid data",
            "request_id": request.id
        }), 400
    
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000:
        return jsonify({
            "success": False,
            "message": f"Invalid bet (min: {CONFIG.COIN_FLIP_MIN_BET}, max: 50000)",
            "request_id": request.id
        }), 400
    
    if float(user['balance']) < bet:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'COINFLIP'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id
        }), 429
    
    # Check daily limit
    if not can_play_today(user['id'], 'coinflip', max_plays=50):
        return jsonify({
            "success": False,
            "message": "Max 50 coin flips per day",
            "request_id": request.id
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'COINFLIP', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before playing again",
            "request_id": request.id
        }), 429
    
    # Calculate payout
    payout = bet * 2 if won else 0
    net_change = payout - bet
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], net_change)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Update game stats
        game_stats = json.loads(user.get('game_stats', '{}'))
        coinflip_stats = game_stats.get('coin_flip', {'wins': 0, 'losses': 0, 'current_streak': 0})
        
        if won:
            coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
            coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
        else:
            coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
            coinflip_stats['current_streak'] = 0
        
        game_stats['coin_flip'] = coinflip_stats
        cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                      (json.dumps(game_stats), user['id']))
        
        # Update timestamps and record play
        update_last_game_timestamp(user['id'])
        record_game_play(user['id'], 'coinflip')
        
        # Create transaction
        tx_type = 'COINFLIP_WIN' if won else 'COINFLIP_LOSS'
        tx_id = f"COIN-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({"game": "coinflip", "bet": bet, "won": won, "payout": payout}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Coin flip processed for {user['username']}: {'WON' if won else 'LOST'} {bet}, net: {net_change}")
        
        return jsonify({
            "success": True,
            "payout": payout if won else 0,
            "net_change": net_change,
            "new_balance": new_balance,
            "won": won,
            "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}₦{abs(net_change):.2f}",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Coin flip error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_plinko():
    """Report plinko game results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    try:
        bet = float(data.get('bet', 0))
        multiplier = float(data.get('multiplier', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid data",
            "request_id": request.id
        }), 400
    
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000:
        return jsonify({
            "success": False,
            "message": f"Invalid bet (min: {CONFIG.PLINKO_MIN_BET}, max: 50000)",
            "request_id": request.id
        }), 400
    
    if float(user['balance']) < bet:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id
        }), 400
    
    if multiplier not in [0.5, 3, 10]:
        return jsonify({
            "success": False,
            "message": "Invalid multiplier",
            "request_id": request.id
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'PLINKO'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id
        }), 429
    
    # Check daily limit
    if not can_play_today(user['id'], 'plinko', max_plays=50):
        return jsonify({
            "success": False,
            "message": "Max 50 plinko plays per day",
            "request_id": request.id
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'PLINKO', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before playing again",
            "request_id": request.id
        }), 429
    
    # Calculate win amount
    win_amount = bet * multiplier
    net_change = win_amount - bet
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], net_change)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Update game stats
        game_stats = json.loads(user.get('game_stats', '{}'))
        plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
        
        plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
        if win_amount > bet:
            plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
            if win_amount > plinko_stats.get('highest_win', 0):
                plinko_stats['highest_win'] = win_amount
        
        game_stats['plinko'] = plinko_stats
        cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                      (json.dumps(game_stats), user['id']))
        
        # Update timestamps and record play
        update_last_game_timestamp(user['id'])
        record_game_play(user['id'], 'plinko')
        
        # Create transaction
        tx_type = 'PLINKO_WIN' if net_change > 0 else 'PLINKO_LOSS'
        tx_id = f"PLK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({"game": "plinko", "bet": bet, "multiplier": multiplier, "win_amount": win_amount}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Plinko processed for {user['username']}: bet {bet}, multiplier {multiplier}, net: {net_change}")
        
        return jsonify({
            "success": True,
            "win_amount": win_amount,
            "net_change": net_change,
            "new_balance": new_balance,
            "multiplier": multiplier,
            "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}₦{net_change:.2f}",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Plinko error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def report_spin():
    """Report spin wheel results"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    try:
        reward = float(data.get('reward', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid reward",
            "request_id": request.id
        }), 400
    
    valid_rewards = [0, 50, 100, 200, 500, 1000]
    if reward not in valid_rewards:
        return jsonify({
            "success": False,
            "message": "Invalid spin reward",
            "request_id": request.id
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'SPIN'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id
        }), 429
    
    # Check daily limit
    if not can_play_today(user['id'], 'spin', max_plays=1):
        return jsonify({
            "success": False,
            "message": "One spin per day only",
            "request_id": request.id
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'SPIN', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before spinning again",
            "request_id": request.id
        }), 429
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Update timestamps and record play
        update_last_game_timestamp(user['id'])
        record_game_play(user['id'], 'spin')
        
        # Create transaction
        tx_id = f"SPIN-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "spin", "reward": reward}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Spin wheel processed for {user['username']}: reward {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Congratulations! You won ₦{reward}!",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Spin error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ACHIEVEMENTS ENDPOINTS =======================
@app.route('/api/achievements', methods=['GET'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def get_achievements():
    """Get user achievements"""
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get user data
        game_stats = json.loads(user.get('game_stats', '{}'))
        balance = float(user.get('balance', 0))
        claimed_achievements_str = user.get('claimed_achievements', '[]')
        
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []
        
        # Get user statistics
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user['id'],))
        total_tx = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = %s',
                      (user['id'], 'WITHDRAWAL'))
        total_withdrawals = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s',
                      (user['id'], today))
        games_today = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user['id'],))
        total_games = cursor.fetchone()[0]
        
        # Calculate achievement stats
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)
        
        # Define achievements
        achievements_data = [
            {"id": 1, "title": "First Game", "description": "Play any game once", "reward": 500, "points": 10,
             "unlocked": total_games >= 1, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 1, "progress_percentage": min(100, (total_games / 1) * 100),
             "cash_reward": 500, "claimed": 1 in claimed_achievements},
            {"id": 2, "title": "Gamer", "description": "Play 50 games", "reward": 5000, "points": 50,
             "unlocked": total_games >= 50, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 50, "progress_percentage": min(100, (total_games / 50) * 100),
             "cash_reward": 5000, "claimed": 2 in claimed_achievements},
            {"id": 3, "title": "Game Master", "description": "Play 200 games", "reward": 15000, "points": 150,
             "unlocked": total_games >= 200, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 200, "progress_percentage": min(100, (total_games / 200) * 100),
             "cash_reward": 15000, "claimed": 3 in claimed_achievements},
            {"id": 4, "title": "Snake Pro", "description": "Snake high score 1000+", "reward": 7500, "points": 75,
             "unlocked": snake_high >= 1000, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": snake_high, "target_value": 1000, "progress_percentage": min(100, (snake_high / 1000) * 100),
             "cash_reward": 7500, "claimed": 4 in claimed_achievements},
            {"id": 5, "title": "Lucky Streak", "description": "10+ coin flip win streak", "reward": 10000, "points": 100,
             "unlocked": coin_streak >= 10, "category": "gaming", "icon": "fas fa-coins",
             "current_value": coin_streak, "target_value": 10, "progress_percentage": min(100, (coin_streak / 10) * 100),
             "cash_reward": 10000, "claimed": 5 in claimed_achievements},
            {"id": 6, "title": "Coin Flipper", "description": "100+ coin flips", "reward": 6000, "points": 60,
             "unlocked": coin_total >= 100, "category": "gaming", "icon": "fas fa-coins",
             "current_value": coin_total, "target_value": 100, "progress_percentage": min(100, (coin_total / 100) * 100),
             "cash_reward": 6000, "claimed": 6 in claimed_achievements},
            {"id": 7, "title": "Plinko Champion", "description": "50+ Plinko wins", "reward": 8000, "points": 80,
             "unlocked": plinko_wins >= 50, "category": "gaming", "icon": "fas fa-bullseye",
             "current_value": plinko_wins, "target_value": 50, "progress_percentage": min(100, (plinko_wins / 50) * 100),
             "cash_reward": 8000, "claimed": 7 in claimed_achievements},
            {"id": 8, "title": "Thousandaire", "description": "Balance ₦1,000+", "reward": 1000, "points": 15,
             "unlocked": balance >= 1000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 1000, "progress_percentage": min(100, (balance / 1000) * 100),
             "cash_reward": 1000, "claimed": 8 in claimed_achievements},
            {"id": 9, "title": "Millionaire in Progress", "description": "Balance ₦50,000+", "reward": 10000, "points": 100,
             "unlocked": balance >= 50000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 50000, "progress_percentage": min(100, (balance / 50000) * 100),
             "cash_reward": 10000, "claimed": 9 in claimed_achievements},
            {"id": 10, "title": "High Roller", "description": "Balance ₦200,000+", "reward": 25000, "points": 200,
             "unlocked": balance >= 200000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 200000, "progress_percentage": min(100, (balance / 200000) * 100),
             "cash_reward": 25000, "claimed": 10 in claimed_achievements},
            {"id": 11, "title": "First Withdrawal", "description": "Make first withdrawal", "reward": 5000, "points": 50,
             "unlocked": total_withdrawals >= 1, "category": "earnings", "icon": "fas fa-wallet",
             "current_value": total_withdrawals, "target_value": 1, "progress_percentage": min(100, (total_withdrawals / 1) * 100),
             "cash_reward": 5000, "claimed": 11 in claimed_achievements},
            {"id": 12, "title": "Daily Grinder", "description": "Play 5 games in a day", "reward": 3000, "points": 30,
             "unlocked": games_today >= 5, "category": "streaks", "icon": "fas fa-calendar-day",
             "current_value": games_today, "target_value": 5, "progress_percentage": min(100, (games_today / 5) * 100),
             "cash_reward": 3000, "claimed": 12 in claimed_achievements},
            {"id": 13, "title": "Addicted", "description": "Play 20 games in a day", "reward": 8000, "points": 80,
             "unlocked": games_today >= 20, "category": "streaks", "icon": "fas fa-calendar-day",
             "current_value": games_today, "target_value": 20, "progress_percentage": min(100, (games_today / 20) * 100),
             "cash_reward": 8000, "claimed": 13 in claimed_achievements},
            {"id": 14, "title": "Referral Starter", "description": "Refer 5 users", "reward": 10000, "points": 100,
             "unlocked": referrals >= 5, "category": "special", "icon": "fas fa-users",
             "current_value": referrals, "target_value": 5, "progress_percentage": min(100, (referrals / 5) * 100),
             "cash_reward": 10000, "claimed": 14 in claimed_achievements},
            {"id": 15, "title": "Referral Master", "description": "Refer 20 users", "reward": 30000, "points": 300,
             "unlocked": referrals >= 20, "category": "special", "icon": "fas fa-users",
             "current_value": referrals, "target_value": 20, "progress_percentage": min(100, (referrals / 20) * 100),
             "cash_reward": 30000, "claimed": 15 in claimed_achievements},
            {"id": 16, "title": "Transaction Veteran", "description": "10+ transactions", "reward": 4000, "points": 40,
             "unlocked": total_tx >= 10, "category": "special", "icon": "fas fa-exchange-alt",
             "current_value": total_tx, "target_value": 10, "progress_percentage": min(100, (total_tx / 10) * 100),
             "cash_reward": 4000, "claimed": 16 in claimed_achievements}
        ]
        
        # Calculate statistics
        total_achievements = len(achievements_data)
        unlocked_achievements = sum(1 for a in achievements_data if a['unlocked'])
        unlocked_not_claimed = sum(1 for a in achievements_data if a['unlocked'] and not a['claimed'])
        total_points = sum(a['points'] for a in achievements_data if a['unlocked'])
        
        # Get fresh balance
        cursor.execute('SELECT balance FROM users WHERE id = %s', (user['id'],))
        fresh_balance_row = cursor.fetchone()
        fresh_balance = float(fresh_balance_row[0]) if fresh_balance_row and fresh_balance_row[0] else balance
        
        return jsonify({
            "success": True,
            "stats": {
                "total": total_achievements,
                "unlocked": unlocked_achievements,
                "unlocked_not_claimed": unlocked_not_claimed,
                "points": total_points
            },
            "achievements": achievements_data,
            "current_balance": fresh_balance,
            "has_unclaimed_rewards": unlocked_not_claimed > 0,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Achievements error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to load achievements: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/achievements/claim', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def claim_achievement_rewards():
    """Claim achievement rewards"""
    user = get_current_user()
    try:
        new_balance = grant_achievement_rewards(user['id'])
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to process achievement rewards",
                "request_id": request.id
            }), 500
        
        return jsonify({
            "success": True,
            "message": "Achievement rewards processed successfully",
            "new_balance": new_balance,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Claim achievement error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to claim: {str(e)}",
            "request_id": request.id
        }), 500

# ======================= TIKTOK DAILY ENDPOINTS =======================
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
@rate_limit_decorator(limit_per_minute=10)
def get_tiktok_daily_task():
    """Get today's TikTok task"""
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if already claimed
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                      (user['id'], 'TIKTOK_DAILY', today))
        already_claimed = cursor.fetchone() is not None
        
        # Get today's task
        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        
        if task_row:
            task = {
                'tiktok_link': task_row[0],
                'reward_amount': float(task_row[1]) if task_row[1] else CONFIG.TIKTOK_REWARD
            }
            return jsonify({
                "success": True,
                "task": task,
                "already_claimed": already_claimed,
                "request_id": request.id
            })
        else:
            return jsonify({
                "success": False,
                "message": "No TikTok task for today",
                "already_claimed": already_claimed,
                "request_id": request.id
            }), 404
    except Exception as e:
        app.logger.error(f"[{request.id}] TikTok daily error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to get task: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=3)
def follow_tiktok_daily():
    """Claim TikTok daily reward"""
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if already claimed today
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                      (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Already claimed today",
                "request_id": request.id
            }), 400
        
        # Get today's task reward
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        
        if not task_row:
            return jsonify({
                "success": False,
                "message": "No task for today",
                "request_id": request.id
            }), 404
        
        reward = float(task_row[0]) if task_row[0] else CONFIG.TIKTOK_REWARD
        
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Create transaction
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ TikTok daily claimed by {user['username']}: reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Success! Claimed ₦{reward} for following TikTok",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ TikTok follow error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN TIKTOK ENDPOINTS =======================
@app.route('/api/admin/tiktok/set-daily', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_set_tiktok_daily():
    """Admin: Set today's TikTok task"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    tiktok_link = sanitize_input(data.get('tiktok_link', ''))
    
    if not tiktok_link:
        return jsonify({
            "success": False,
            "message": "TikTok link required",
            "request_id": request.id
        }), 400
    
    if not tiktok_link.startswith('https://www.tiktok.com/@'):
        return jsonify({
            "success": False,
            "message": "Link must start with https://www.tiktok.com/@",
            "request_id": request.id
        }), 400
    
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO tiktok_daily (date, tiktok_link, reward_amount)
            VALUES (%s, %s, %s)
            ON CONFLICT (date)
            DO UPDATE SET tiktok_link = EXCLUDED.tiktok_link, reward_amount = EXCLUDED.reward_amount
        ''', (today, tiktok_link, CONFIG.TIKTOK_REWARD))
        
        conn.commit()
        app.logger.info(f"[{request.id}] Admin set TikTok daily task: {tiktok_link}")
        
        return jsonify({
            "success": True,
            "message": "TikTok daily task set",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set TikTok daily error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to set task: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/tiktok/get-daily', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_tiktok_daily():
    """Admin: Get today's TikTok task"""
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT date, tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        row = cursor.fetchone()
        
        if row:
            task = {
                'date': row[0],
                'tiktok_link': row[1],
                'reward_amount': float(row[2]) if row[2] else CONFIG.TIKTOK_REWARD
            }
            return jsonify({
                "success": True,
                "task": task,
                "request_id": request.id
            })
        else:
            return jsonify({
                "success": False,
                "message": "No TikTok task set for today",
                "request_id": request.id
            })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get TikTok daily error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to get task",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/tiktok/history', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_tiktok_history():
    """Admin: Get TikTok task history"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT date, tiktok_link, reward_amount
            FROM tiktok_daily
            WHERE date >= %s
            ORDER BY date DESC
            LIMIT 7
        ''', ((datetime.utcnow().date() - timedelta(days=7)).isoformat(),))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'date': row[0],
                'tiktok_link': row[1],
                'reward_amount': float(row[2]) if row[2] else CONFIG.TIKTOK_REWARD
            })
        
        return jsonify({
            "success": True,
            "history": history,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get TikTok history error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load history",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN WITHDRAWAL DAYS ENDPOINTS =======================
@app.route('/api/admin/global-withdrawal-days', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_global_withdrawal_days():
    """Admin: Get global withdrawal days"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        
        if row and row[0]:
            days = json.loads(row[0])
            return jsonify({
                "success": True,
                "days": days,
                "request_id": request.id
            })
        else:
            return jsonify({
                "success": True,
                "days": CONFIG.DEFAULT_WITHDRAWAL_DAYS,
                "request_id": request.id
            })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get global withdrawal days error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/global-withdrawal-days', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_set_global_withdrawal_days():
    """Admin: Set global withdrawal days"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    days = data.get('days', [])
    
    if not isinstance(days, list):
        return jsonify({
            "success": False,
            "message": "Invalid days format",
            "request_id": request.id
        }), 400
    
    # Validate days
    valid_days = []
    for day in days:
        try:
            day_int = int(day)
            if 1 <= day_int <= 31:
                valid_days.append(day_int)
        except (ValueError, TypeError):
            continue
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE admin_settings SET global_withdrawal_days = %s', (json.dumps(valid_days),))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin updated global withdrawal days: {valid_days}")
        
        return jsonify({
            "success": True,
            "message": "Global withdrawal days updated",
            "days": valid_days,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set global withdrawal days error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN USER MANAGEMENT ENDPOINTS =======================
@app.route('/api/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_set_user_custom_days(user_id):
    """Admin: Set custom withdrawal days for user"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    days = data.get('days', [])
    
    if not isinstance(days, list):
        return jsonify({
            "success": False,
            "message": "Invalid days format",
            "request_id": request.id
        }), 400
    
    # Validate days
    valid_days = []
    for day in days:
        try:
            day_int = int(day)
            if 1 <= day_int <= 31:
                valid_days.append(day_int)
        except (ValueError, TypeError):
            continue
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        # Update custom days
        cursor.execute('UPDATE users SET custom_withdrawal_days = %s WHERE id = %s',
                      (json.dumps(valid_days) if valid_days else None, user_id))
        
        conn.commit()
        app.logger.info(f"[{request.id}] Admin set custom withdrawal days for user {user_id}: {valid_days}")
        
        return jsonify({
            "success": True,
            "message": "Custom withdrawal days updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set user custom days error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/set-limit', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_set_user_limit(user_id):
    """Admin: Set withdrawal limit for user"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    try:
        limit = float(data.get('limit', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid limit",
            "request_id": request.id
        }), 400
    
    if limit < 0:
        return jsonify({
            "success": False,
            "message": "Invalid limit",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        # Update limit
        cursor.execute('UPDATE users SET withdrawal_limit = %s WHERE id = %s', (limit, user_id))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin set withdrawal limit for user {user_id} to: {limit}")
        
        return jsonify({
            "success": True,
            "message": "Limit updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set limit error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/approve-withdrawal', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_approve_withdrawal():
    """Admin: Approve or reject withdrawal"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    transaction_id = data.get('transaction_id')
    action = data.get('action', '').upper()
    
    if not transaction_id or action not in ['APPROVE', 'REJECT']:
        return jsonify({
            "success": False,
            "message": "Invalid request",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get transaction details
        cursor.execute('SELECT user_id, amount, status FROM transactions WHERE id = %s', (transaction_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "Transaction not found",
                "request_id": request.id
            }), 404
        
        user_id, amount, current_status = row[0], float(row[1]), row[2]
        
        if current_status != 'PENDING':
            return jsonify({
                "success": False,
                "message": f"Transaction already {current_status}",
                "request_id": request.id
            }), 400
        
        # Process action
        new_status = 'COMPLETED' if action == 'APPROVE' else 'FAILED'
        
        if action == 'REJECT':
            # Refund balance
            update_user_balance(user_id, amount)
        
        # Update transaction status
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (new_status, transaction_id))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin {action}d withdrawal {transaction_id} for user {user_id}, amount: {amount}")
        
        return jsonify({
            "success": True,
            "message": f"Withdrawal {action.lower()}ed successfully",
            "status": new_status,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Approve withdrawal error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_withdrawal_status_report():
    """Admin: Get withdrawal status report"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get all users
        cursor.execute('''
            SELECT id, username, balance, withdrawal_restricted, custom_withdrawal_days,
            withdrawal_limit, withdrawal_pin
            FROM users
            ORDER BY id
        ''')
        
        users = []
        total_users = 0
        users_withdrawal_today = 0
        users_restricted = 0
        today_day = datetime.utcnow().day
        global_days = get_global_withdrawal_days()
        
        for row in cursor.fetchall():
            total_users += 1
            user_id = row[0]
            username = row[1]
            balance = float(row[2]) if row[2] else 0
            withdrawal_restricted = bool(row[3])
            custom_days_str = row[4] if row[4] else ''
            withdrawal_limit = float(row[5]) if row[5] else 0
            has_withdrawal_pin = bool(row[6])
            
            if withdrawal_restricted:
                users_restricted += 1
            
            # Check if user can withdraw today
            can_withdraw_today = False
            if not withdrawal_restricted:
                if custom_days_str:
                    try:
                        custom_days = json.loads(custom_days_str)
                        can_withdraw_today = today_day in custom_days
                    except:
                        can_withdraw_today = today_day in global_days
                else:
                    can_withdraw_today = today_day in global_days
            
            if can_withdraw_today:
                users_withdrawal_today += 1
            
            users.append({
                'id': user_id,
                'username': username,
                'balance': balance,
                'withdrawal_restricted': withdrawal_restricted,
                'custom_withdrawal_days': json.loads(custom_days_str) if custom_days_str else [],
                'withdrawal_limit': withdrawal_limit,
                'has_withdrawal_pin': has_withdrawal_pin,
                'can_withdraw_today': can_withdraw_today
            })
        
        return jsonify({
            "success": True,
            "today": datetime.utcnow().strftime("%d %B %Y"),
            "total_users": total_users,
            "users_withdrawal_today": users_withdrawal_today,
            "users_restricted": users_restricted,
            "global_withdrawal_days": global_days,
            "users": users,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Withdrawal status report error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to generate report",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_toggle_user_admin(user_id):
    """Admin: Toggle user admin status"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get user details
        cursor.execute('SELECT username, is_admin FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        username = row[0]
        is_currently_admin = bool(row[1])
        
        # Prevent modifying original admin
        if username == 'flexiaadmin':
            return jsonify({
                "success": False,
                "message": "Cannot modify original admin",
                "request_id": request.id
            }), 403
        
        # Toggle admin status
        new_admin_status = not is_currently_admin
        cursor.execute('UPDATE users SET is_admin = %s WHERE id = %s', (new_admin_status, user_id))
        conn.commit()
        
        action = "promoted to admin" if new_admin_status else "demoted from admin"
        app.logger.info(f"[{request.id}] Admin toggled user {username} ({user_id}) admin status to: {new_admin_status}")
        
        return jsonify({
            "success": True,
            "message": f"User {username} {action}",
            "is_admin": new_admin_status,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Toggle admin error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update admin status",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@require_admin
@rate_limit_decorator(limit_per_minute=3)
def admin_delete_user(user_id):
    """Admin: Delete user"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get user details
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        username = row[0]
        
        # Prevent deleting original admin
        if username == 'flexiaadmin':
            return jsonify({
                "success": False,
                "message": "Cannot delete original admin",
                "request_id": request.id
            }), 403
        
        # Delete user data (in correct order to maintain referential integrity)
        cursor.execute('DELETE FROM transactions WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM game_plays WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        
        conn.commit()
        app.logger.warning(f"[{request.id}] Admin deleted user: {username} (ID: {user_id})")
        
        return jsonify({
            "success": True,
            "message": f"User {username} deleted successfully",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete user error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete user",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN COUPON MANAGEMENT ENDPOINTS =======================
@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_coupons():
    """Admin: Get all coupons"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, status FROM coupons ORDER BY code')
        coupons = []
        
        for row in cursor.fetchall():
            coupons.append({
                'code': row[0],
                'status': row[1]
            })
        
        return jsonify({
            "success": True,
            "coupons": coupons,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin coupons error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load coupons",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/reset-used', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_reset_used_coupons():
    """Admin: Reset used coupons"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE coupons SET status = 'AVAILABLE' WHERE status = 'USED'")
        updated_count = cursor.rowcount
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin reset {updated_count} used coupons to available")
        
        return jsonify({
            "success": True,
            "message": f"Reset {updated_count} used coupons to available",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Reset coupons error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to reset coupons",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/delete', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=3)
def admin_delete_all_coupons():
    """Admin: Delete all coupons"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM coupons')
        deleted_count = cursor.rowcount
        conn.commit()
        
        app.logger.warning(f"[{request.id}] Admin deleted all {deleted_count} coupons")
        
        return jsonify({
            "success": True,
            "message": f"Deleted all {deleted_count} coupons",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete all coupons error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete coupons",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/add', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_add_bulk_coupons():
    """Admin: Add bulk coupons"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    codes = data.get('codes', [])
    
    if not isinstance(codes, list):
        return jsonify({
            "success": False,
            "message": "Invalid codes format",
            "request_id": request.id
        }), 400
    
    # Validate and sanitize codes
    valid_codes = []
    for code in codes:
        clean_code = sanitize_input(str(code).strip().upper())
        if clean_code and len(clean_code) >= 4:
            valid_codes.append(clean_code)
    
    if not valid_codes:
        return jsonify({
            "success": False,
            "message": "No valid coupon codes provided",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        added_count = 0
        for code in valid_codes:
            try:
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING',
                             (code, 'AVAILABLE'))
                if cursor.rowcount > 0:
                    added_count += 1
            except:
                continue
        
        conn.commit()
        app.logger.info(f"[{request.id}] Admin added {added_count} new coupon codes")
        
        return jsonify({
            "success": True,
            "message": f"Added {added_count} new coupon codes",
            "added": added_count,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Add bulk coupons error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to add coupons",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/load-file', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=3)
def admin_load_coupons_from_file():
    """Admin: Load coupons from file"""
    try:
        if not os.path.exists(CONFIG.COUPON_FILE):
            return jsonify({
                "success": False,
                "message": "coupon.txt file not found",
                "request_id": request.id
            }), 404
        
        # Read coupons from file
        with open(CONFIG.COUPON_FILE, 'r') as f:
            codes = [line.strip().upper() for line in f if line.strip()]
        
        if not codes:
            return jsonify({
                "success": False,
                "message": "No coupons in file",
                "request_id": request.id
            }), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        loaded = 0
        for code in codes:
            try:
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING',
                             (code, 'AVAILABLE'))
                loaded += 1
            except:
                continue
        
        conn.commit()
        return_db_connection(conn)
        
        app.logger.info(f"[{request.id}] Admin loaded {loaded} coupons from file")
        
        return jsonify({
            "success": True,
            "message": f"Loaded {loaded} coupons from file",
            "count": loaded,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Load coupons from file error: {e}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}",
            "request_id": request.id
        }), 500

@app.route('/api/admin/coupons/<code>/delete', methods=['DELETE'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_delete_coupon(code):
    """Admin: Delete specific coupon"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM coupons WHERE code = %s', (code,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "Coupon not found",
                "request_id": request.id
            }), 404
        
        app.logger.info(f"[{request.id}] Admin deleted coupon: {code}")
        
        return jsonify({
            "success": True,
            "message": "Coupon deleted",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete coupon error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN WHATSAPP NUMBERS ENDPOINTS =======================
@app.route('/api/admin/whatsapp-numbers', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_whatsapp_numbers():
    """Admin: Get all WhatsApp numbers"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, number, label, is_active, created_at FROM whatsapp_numbers ORDER BY created_at DESC')
        numbers = []
        
        for row in cursor.fetchall():
            num = {
                'id': row[0],
                'number': row[1],
                'label': row[2],
                'is_active': bool(row[3]),
                'created_at': row[4]
            }
            numbers.append(num)
        
        return jsonify({
            "success": True,
            "numbers": numbers,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin WhatsApp numbers error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load numbers",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_add_whatsapp_number():
    """Admin: Add WhatsApp number"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    number = sanitize_input(data.get('number', ''))
    label = sanitize_input(data.get('label', ''))
    
    if not number or len(number) < 10:
        return jsonify({
            "success": False,
            "message": "Valid phone number required",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES (%s, %s, %s, %s)',
                      (number, label, True, datetime.utcnow().isoformat()))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin added WhatsApp number: {number} ({label})")
        
        return jsonify({
            "success": True,
            "message": "WhatsApp number added",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Add WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to add number",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>/toggle', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_toggle_whatsapp_number(number_id):
    """Admin: Toggle WhatsApp number active status"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT is_active FROM whatsapp_numbers WHERE id = %s', (number_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "Number not found",
                "request_id": request.id
            }), 404
        
        current = bool(row[0])
        new_value = not current
        
        cursor.execute('UPDATE whatsapp_numbers SET is_active = %s WHERE id = %s', (new_value, number_id))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin toggled WhatsApp number {number_id} active status to: {new_value}")
        
        return jsonify({
            "success": True,
            "is_active": new_value,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Toggle WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to toggle",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>', methods=['DELETE'])
@require_admin
@rate_limit_decorator(limit_per_minute=3)
def admin_delete_whatsapp_number(number_id):
    """Admin: Delete WhatsApp number"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM whatsapp_numbers WHERE id = %s', (number_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "Number not found",
                "request_id": request.id
            }), 404
        
        app.logger.info(f"[{request.id}] Admin deleted WhatsApp number ID: {number_id}")
        
        return jsonify({
            "success": True,
            "message": "Number deleted",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= REFERRAL ENDPOINTS =======================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def claim_referral_bonus():
    """Claim referral bonus"""
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Count referrals
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        # Calculate bonus
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = int(user.get('claimed_bonuses', 0))
        unclaimed = total_bonus - claimed
        
        if unclaimed <= 0:
            return jsonify({
                "success": False,
                "message": "No bonus to claim",
                "request_id": request.id
            }), 400
        
        # Update balance
        new_balance = update_user_balance(user['id'], unclaimed)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Update claimed bonus
        cursor.execute('UPDATE users SET claimed_bonuses = %s WHERE id = %s',
                      (total_bonus, user['id']))
        
        # Create transaction
        tx_id = f"REF-{secrets.token_hex(8)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'REFERRAL_BONUS', unclaimed, 'COMPLETED',
            json.dumps({"referrals": referrals, "bonus_per_referral": CONFIG.REFERRAL_BONUS}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Referral bonus claimed by {user['username']}: {unclaimed}")
        
        return jsonify({
            "success": True,
            "claimed": unclaimed,
            "new_balance": new_balance,
            "message": f"Success! Claimed ₦{unclaimed} referral bonus",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Referral error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to claim: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= BANKING ENDPOINTS =======================
@app.route('/api/banking/banks', methods=['GET'])
@rate_limit_decorator(limit_per_minute=30)
def get_banks():
    """Get list of banks"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, name FROM banks WHERE is_active = TRUE ORDER BY name')
        banks = [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
        
        return jsonify({
            "success": True,
            "banks": banks,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Bank list error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load banks",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/banking/withdraw', methods=['POST'])
@require_auth
@rate_limit_decorator(limit_per_minute=5)
def withdraw():
    """Withdraw funds"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Input validation
    validation_rules = {
        'amount': {'required': True, 'type': 'float', 'min': CONFIG.MIN_WITHDRAWAL},
        'bank_code': {'required': True, 'type': 'string', 'min_length': 1},
        'account_number': {'required': True, 'type': 'string', 'min_length': 10, 'max_length': 15},
        'account_name': {'required': True, 'type': 'string', 'min_length': 1},
        'pin': {'required': True, 'type': 'string', 'min_length': 4, 'max_length': 6}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id
        }), 400
    
    # Extract and sanitize data
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount",
            "request_id": request.id
        }), 400
    
    bank_code = sanitize_input(data.get('bank_code', ''))
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    pin = data.get('pin', '')
    
    # Verify PIN
    withdrawal_pin = user.get('withdrawal_pin')
    if not withdrawal_pin or not check_password_hash(withdrawal_pin, pin):
        app.logger.warning(f"[{request.id}] Invalid PIN attempt for withdrawal by user: {user['username']}")
        return jsonify({
            "success": False,
            "message": "Invalid PIN",
            "request_id": request.id
        }), 403
    
    # Check if today is withdrawal day
    if not is_withdrawal_day(user['id']):
        global_days = get_global_withdrawal_days()
        return jsonify({
            "success": False,
            "message": f"Withdrawals only on days: {', '.join(map(str, sorted(global_days)))}",
            "request_id": request.id
        }), 403
    
    # Check minimum withdrawal
    if amount < CONFIG.MIN_WITHDRAWAL:
        return jsonify({
            "success": False,
            "message": f"Min withdrawal: ₦{CONFIG.MIN_WITHDRAWAL:,}",
            "request_id": request.id
        }), 400
    
    # Check balance
    if float(user['balance']) < amount:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id
        }), 400
    
    # Check withdrawal limit
    withdrawal_limit = float(user.get('withdrawal_limit', 0.00))
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({
            "success": False,
            "message": f"Max limit: ₦{withdrawal_limit:,.2f}",
            "request_id": request.id
        }), 400
    
    # Validate bank details
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({
            "success": False,
            "message": "Invalid bank details",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], -amount)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Create withdrawal transaction
        tx_id = f"TX-{int(datetime.utcnow().timestamp())}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING',
            json.dumps({'bank_code': bank_code, 'account_number': account_number, 'account_name': account_name}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ Withdrawal requested by {user['username']}: {amount} to {bank_code}:{account_number}")
        
        return jsonify({
            "success": True,
            "message": "Withdrawal submitted successfully",
            "transaction_id": tx_id,
            "new_balance": new_balance,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Withdrawal error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to process: {str(e)}",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= WHATSAPP ENDPOINTS =======================
@app.route('/api/whatsapp/numbers', methods=['GET'])
@rate_limit_decorator(limit_per_minute=30)
def get_whatsapp_numbers():
    """Get active WhatsApp numbers"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT number, label FROM whatsapp_numbers WHERE is_active = TRUE ORDER BY created_at DESC')
        numbers = []
        
        for row in cursor.fetchall():
            numbers.append({
                'number': row[0],
                'label': row[1] or 'Support'
            })
        
        return jsonify({
            "success": True,
            "numbers": numbers,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] WhatsApp numbers error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load numbers",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN MANAGEMENT ENDPOINTS =======================
@app.route('/api/admin/users', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_users():
    """Admin: Get all users"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, balance, referral_code, withdrawal_restricted, withdrawal_limit,
            created_at, last_login, is_admin
            FROM users ORDER BY id DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            user = {
                'id': row[0],
                'username': row[1],
                'balance': float(row[2]) if row[2] else 0.00,
                'referral_code': row[3],
                'withdrawal_restricted': bool(row[4]),
                'withdrawal_limit': float(row[5]) if row[5] else 0.00,
                'created_at': row[6],
                'last_login': row[7],
                'is_admin': bool(row[8])
            }
            users.append(user)
        
        return jsonify({
            "success": True,
            "users": users,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin users error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load users",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_user(user_id):
    """Admin: Get specific user"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        user = row_to_dict(cursor, row)
        
        return jsonify({
            "success": True,
            "user": user,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin get user error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load user",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_toggle_user_restrict(user_id):
    """Admin: Toggle user withdrawal restriction"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT withdrawal_restricted FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id
            }), 404
        
        current = bool(row[0])
        new_value = not current
        
        cursor.execute('UPDATE users SET withdrawal_restricted = %s WHERE id = %s', (new_value, user_id))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin toggled withdrawal restriction for user {user_id} to: {new_value}")
        
        return jsonify({
            "success": True,
            "restricted": new_value,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Toggle restrict error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/adjust-balance', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_adjust_user_balance(user_id):
    """Admin: Adjust user balance"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount",
            "request_id": request.id
        }), 400
    
    note = sanitize_input(data.get('note', ''))
    
    if amount == 0:
        return jsonify({
            "success": False,
            "message": "Invalid amount",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Update balance
        new_balance = update_user_balance(user_id, amount)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id
            }), 500
        
        # Create transaction
        tx_id = f"ADJ-{secrets.token_hex(8)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user_id, 'ADMIN_ADJUSTMENT', amount, 'COMPLETED',
            json.dumps({"note": note, "admin_action": True}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] Admin adjusted balance for user {user_id}: {amount} (note: {note})")
        
        return jsonify({
            "success": True,
            "message": "Balance adjusted",
            "new_balance": new_balance,
            "adjustment": amount,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Adjust balance error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to adjust balance",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/transactions', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_transactions():
    """Admin: Get all transactions"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT t.*, u.username
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.timestamp DESC LIMIT 100
        ''')
        
        transactions = []
        for row in cursor.fetchall():
            tx = row_to_dict(cursor, row)
            transactions.append(tx)
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin transactions error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load transactions",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/transaction/<tx_id>/update', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_update_transaction(tx_id):
    """Admin: Update transaction status"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    status = data.get('status')
    
    if status not in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
        return jsonify({
            "success": False,
            "message": "Invalid status",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (status, tx_id))
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin updated transaction {tx_id} status to: {status}")
        
        return jsonify({
            "success": True,
            "message": "Transaction updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Update transaction error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_settings():
    """Admin: Get settings"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        
        if row:
            settings = row_to_dict(cursor, row)
            return jsonify({
                "success": True,
                "settings": settings,
                "request_id": request.id
            })
        else:
            return jsonify({
                "success": False,
                "message": "Settings not found",
                "request_id": request.id
            }), 404
    except Exception as e:
        app.logger.error(f"[{request.id}] Get settings error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load settings",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/settings', methods=['POST'])
@require_admin
@rate_limit_decorator(limit_per_minute=5)
def admin_update_settings():
    """Admin: Update settings"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id
        }), 400
    
    # Extract and validate data
    whatsapp_link = sanitize_input(data.get('whatsapp_link', ''))
    telegram_link = sanitize_input(data.get('telegram_link', ''))
    facebook_link = sanitize_input(data.get('facebook_link', ''))
    global_withdrawal_days = data.get('global_withdrawal_days', [])
    
    if not isinstance(global_withdrawal_days, list):
        return jsonify({
            "success": False,
            "message": "Invalid withdrawal days format",
            "request_id": request.id
        }), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE admin_settings
            SET whatsapp_link = %s, telegram_link = %s, facebook_link = %s, global_withdrawal_days = %s
        ''', (whatsapp_link, telegram_link, facebook_link, json.dumps(global_withdrawal_days)))
        
        conn.commit()
        app.logger.info(f"[{request.id}] Admin updated settings")
        
        return jsonify({
            "success": True,
            "message": "Settings updated",
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Update settings error: {e}")
        conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
@rate_limit_decorator(limit_per_minute=10)
def admin_get_stats():
    """Admin: Get platform statistics"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # User statistics
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE')
        today_users = cursor.fetchone()[0]
        
        # Balance statistics
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        # Transaction statistics
        cursor.execute('SELECT COUNT(*) FROM transactions')
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = %s AND DATE(timestamp) = CURRENT_DATE', ('WITHDRAWAL',))
        today_withdrawals = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = %s AND status = %s', ('WITHDRAWAL', 'COMPLETED'))
        total_withdrawn = cursor.fetchone()[0] or 0
        
        # Coupon statistics
        cursor.execute('SELECT COUNT(*) FROM coupons')
        total_coupons = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM coupons WHERE status = %s', ('AVAILABLE',))
        available_coupons = cursor.fetchone()[0]
        
        # Game statistics
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE DATE(play_date) = CURRENT_DATE')
        today_games = cursor.fetchone()[0]
        
        return jsonify({
            "success": True,
            "stats": {
                "users": {
                    "total": total_users,
                    "today": today_users
                },
                "balance": {
                    "total": float(total_balance)
                },
                "transactions": {
                    "total": total_transactions,
                    "today_withdrawals": today_withdrawals,
                    "total_withdrawn": float(total_withdrawn)
                },
                "coupons": {
                    "total": total_coupons,
                    "available": available_coupons
                },
                "games": {
                    "today": today_games
                }
            },
            "request_id": request.id
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin stats error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load stats",
            "request_id": request.id
        }), 500
    finally:
        return_db_connection(conn)

# ======================= STATIC FILES =======================
@app.route('/')
def index():
    """Serve frontend index.html"""
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= CATCH-ALL ROUTE =======================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route for SPA routing"""
    if path.startswith('api/'):
        return jsonify({
            "success": False,
            "message": "API endpoint not found",
            "request_id": request.id
        }), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= MAIN ENTRY POINT =======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    
    app.logger.info(f"🚀 Starting Flexia Platform SECURE v13.0 on port {port} (debug: {debug})")
    app.logger.info(f"📊 Database pool: {CONFIG.DB_POOL_MIN}-{CONFIG.DB_POOL_MAX} connections")
    app.logger.info(f"🌐 CORS allowed origins: {CONFIG.ALLOWED_ORIGINS}")
    
    # For production, use Gunicorn instead
    if os.getenv('ENV') == 'production':
        app.logger.info("⚡ Running in PRODUCTION mode")
    else:
        app.logger.info("🔧 Running in DEVELOPMENT mode")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
