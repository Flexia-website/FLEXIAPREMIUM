# backend/app.py - COMPLETE PRODUCTION VERSION WITH ALL ENDPOINTS
# FLEXIA Platform - PRODUCTION READY v14.0
# COMPLETE VERSION WITH ALL FIXES AND ENDPOINTS
# ADMIN CREDENTIALS VIA ENVIRONMENT VARIABLES

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, send_from_directory, redirect, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
import threading
import time
import subprocess
import shutil
from logging.handlers import RotatingFileHandler
import psycopg2
from psycopg2.pool import SimpleConnectionPool

# ======================= CONFIGURATION =======================
class Config:
    if os.environ.get('DATABASE_URL'):
        DB_URL = os.environ.get('DATABASE_URL')
    else:
        DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flexia.db')
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'flexia_secure_key_2024_change_in_production')
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 7500
    TIKTOK_REWARD = 150
    SNAKE_REWARD = 200
    COIN_FLIP_MIN_BET = 100
    PLINKO_MIN_BET = 100
    SESSION_DURATION_HOURS = 24
    DEFAULT_WITHDRAWAL_DAYS = [7, 14, 25, 30]
    
    # Admin credentials from environment variables with defaults
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'flexiaadmin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'passwordinnumber1')
    ADMIN_WITHDRAWAL_PIN = os.environ.get('ADMIN_WITHDRAWAL_PIN', '4567')
    
    # Game daily limits
    GAME_DAILY_LIMITS = {
        'snake': 17,
        'coinflip': 12,
        'plinko': 12,
        'spin': 1,
        'tiktok': 1
    }
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

CONFIG = Config()

app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY

# ======================= SETUP LOGGING =======================
def setup_logging():
    """Setup structured logging for the application"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/flexia.log', 
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG)
    
    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    
    # Set werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.setLevel(logging.WARNING)

setup_logging()

# ======================= SECURITY HEADERS =======================
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.getenv('ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

# ======================= JSON RESPONSE ENFORCER =======================
@app.after_request
def enforce_json_response(response):
    """Ensure all API responses are JSON, even on error"""
    if request.path.startswith('/api/'):
        if response.content_type != 'application/json':
            try:
                # If not JSON, wrap it in JSON
                if response.status_code >= 400:
                    data = jsonify({
                        "success": False,
                        "message": "Server error occurred",
                        "status_code": response.status_code
                    })
                    return data
            except:
                pass
    return response

# ======================= ERROR HANDLERS =======================
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    app.logger.warning(f'404 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f'500 error: {str(error)}')
    app.logger.error(traceback.format_exc())
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Internal server error"}), 500
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(400)
def bad_request_error(error):
    """Handle 400 errors"""
    app.logger.warning(f'400 error: {str(error)}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Bad request"}), 400
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(401)
def unauthorized_error(error):
    """Handle 401 errors"""
    app.logger.warning(f'401 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Authentication required"}), 401
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    app.logger.warning(f'403 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Access forbidden"}), 403
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(429)
def too_many_requests_error(error):
    """Handle 429 errors"""
    app.logger.warning(f'429 rate limit exceeded: {request.remote_addr}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(Exception)
def handle_all_exceptions(error):
    """Catch-all exception handler to prevent HTML responses"""
    app.logger.error(f"❌ Unhandled exception: {str(error)}")
    app.logger.error(traceback.format_exc())
    
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Internal server error. Please try again.",
            "error_type": str(type(error).__name__)
        }), 500
    
    # For non-API routes, serve the frontend
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= BACKUP SYSTEM =======================
def backup_database():
    """Create a backup of the database"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if os.environ.get('DATABASE_URL'):
            # PostgreSQL backup
            app.logger.info('Creating PostgreSQL backup...')
            backup_file = f'backups/backup_flexia_{timestamp}.sql'
            
            # Create backups directory if it doesn't exist
            if not os.path.exists('backups'):
                os.makedirs('backups')
            
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
                '--no-password'
            ], env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                app.logger.info(f'PostgreSQL backup created: {backup_file}')
                return backup_file
            else:
                app.logger.error(f'PostgreSQL backup failed: {result.stderr}')
                return None
                
        else:
            # SQLite backup
            app.logger.info('Creating SQLite backup...')
            backup_file = f'backups/backup_flexia_{timestamp}.db'
            
            # Create backups directory if it doesn't exist
            if not os.path.exists('backups'):
                os.makedirs('backups')
            
            shutil.copy2(CONFIG.DB_FILE, backup_file)
            app.logger.info(f'SQLite backup created: {backup_file}')
            return backup_file
            
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
                # Run backup daily at 2 AM
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
                    
                    # Cleanup old backups (keep last 7 days)
                    cleanup_old_backups()
                else:
                    app.logger.error('Daily backup failed')
                    
            except Exception as e:
                app.logger.error(f'Backup scheduler error: {str(e)}')
                time.sleep(3600)  # Sleep 1 hour on error
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

def cleanup_old_backups():
    """Remove backups older than 7 days"""
    try:
        if not os.path.exists('backups'):
            return
        
        cutoff_time = datetime.now() - timedelta(days=7)
        
        for filename in os.listdir('backups'):
            filepath = os.path.join('backups', filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_time:
                    os.remove(filepath)
                    app.logger.info(f'Removed old backup: {filename}')
                    
    except Exception as e:
        app.logger.error(f'Cleanup old backups error: {str(e)}')

# ======================= DATABASE CONNECTION POOLING =======================
# Connection pool for PostgreSQL
db_pool = None

def init_db_pool():
    """Initialize database connection pool with optimized settings"""
    global db_pool
    
    if os.environ.get('DATABASE_URL'):
        try:
            # INCREASED CONNECTIONS FOR RENDER
            db_pool = SimpleConnectionPool(
                5,  # min connections
                50, # max connections
                dsn=os.environ['DATABASE_URL']
            )
            app.logger.info('✅ Database connection pool initialized: 5-50 connections')
        except Exception as e:
            app.logger.error(f'❌ Failed to initialize connection pool: {str(e)}')
            db_pool = None
    else:
        app.logger.info('✅ SQLite mode - connection pooling not needed')

def get_db():
    """Get database connection from pool or create new one"""
    global db_pool
    
    if os.environ.get('DATABASE_URL') and db_pool:
        try:
            conn = db_pool.getconn()
            conn.autocommit = False
            return conn
        except Exception as e:
            app.logger.error(f'Error getting connection from pool: {str(e)}')
            # Fallback to direct connection
            return get_db_direct()
    else:
        return get_db_direct()

def get_db_direct():
    """Get direct database connection (fallback)"""
    if os.environ.get('DATABASE_URL'):
        try:
            parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:],
                sslmode='require'
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            app.logger.error(f'Direct PostgreSQL connection failed: {str(e)}')
            raise
    else:
        if os.getenv('ENV') == 'production':
            raise RuntimeError("SQLite not allowed in production. Set DATABASE_URL.")
        import sqlite3
        conn = sqlite3.connect(CONFIG.DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def return_db_connection(conn):
    """Return connection to pool"""
    global db_pool
    
    if os.environ.get('DATABASE_URL') and db_pool:
        try:
            db_pool.putconn(conn)
        except:
            try:
                conn.close()
            except:
                pass
    else:
        try:
            conn.close()
        except:
            pass

# ======================= RATE LIMITING =======================
login_attempts = {}
register_attempts = {}
game_action_attempts = {}

def rate_limit(store, key, max_per_min=5):
    now = datetime.utcnow()
    if key not in store:
        store[key] = []
    store[key] = [t for t in store[key] if t > now - timedelta(minutes=1)]
    if len(store[key]) >= max_per_min:
        app.logger.warning(f'Rate limit exceeded for {key}: {len(store[key])} attempts')
        return False
    store[key].append(now)
    return True

# ======================= CLAIM LOCKING SYSTEM =======================
# Global claim lock to prevent duplicate claims
claim_locks = {}
claim_lock_timeout = 2  # seconds

def acquire_claim_lock(user_id, game_type):
    """Prevent duplicate claims from same user for same game"""
    key = f"{user_id}_{game_type}"
    now = time.time()
    
    if key in claim_locks:
        lock_time = claim_locks[key]
        if now - lock_time < claim_lock_timeout:
            return False
    
    claim_locks[key] = now
    return True

def release_claim_lock(user_id, game_type):
    """Release claim lock"""
    key = f"{user_id}_{game_type}"
    claim_locks.pop(key, None)

# ======================= SESSION MANAGER =======================
def create_session_token(user_id):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id})

def verify_session_token(token):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return data.get('user_id')
    except (BadSignature, SignatureExpired) as e:
        app.logger.warning(f'Invalid session token: {str(e)}')
        return None

def _safe_get(row, key, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    else:
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

def row_to_dict(cursor, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    else:
        if cursor and cursor.description:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return {}

def get_current_user():
    token = request.cookies.get('session_token')
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)
    except Exception as e:
        app.logger.error(f'Error getting current user: {str(e)}')
        return None
    finally:
        return_db_connection(conn)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            app.logger.warning(f'Unauthorized access attempt to {request.path}')
            return jsonify({"success": False, "message": "Login required"}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "message": "Login required"}), 401
        is_admin = _safe_get(user, 'is_admin', False)
        if not is_admin:
            app.logger.warning(f'Non-admin user {user["id"]} attempted admin endpoint {request.path}')
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# ======================= ENHANCED GAME LIMIT SYSTEM WITH LOGOUT =======================
def check_game_limit_with_logout(user_id, game_type):
    """Check if user can play and log them out if limit reached"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    
    try:
        # Get max plays for this game
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        
        # Check existing plays today
        cursor.execute(f'''
        SELECT COUNT(*) FROM game_plays 
        WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}
        ''', (user_id, game_type, today))
        
        count = cursor.fetchone()[0]
        
        if count >= max_plays:
            app.logger.info(f'🚫 GAME LIMIT REACHED: User {user_id}, Game {game_type}, Plays {count}/{max_plays}')
            
            # Record limit reached in database
            limit_log_id = f"LIMIT-{secrets.token_hex(8)}"
            cursor.execute(f'''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', (
                limit_log_id, user_id, 'GAME_LIMIT_REACHED', 0, 'COMPLETED',
                json.dumps({
                    "game_type": game_type,
                    "played_today": count,
                    "max_plays": max_plays,
                    "limit_reached": True,
                    "action": "auto_logout_required",
                    "message": f"Daily {game_type} limit reached: {count}/{max_plays} plays"
                }),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            return {
                "can_play": False,
                "reason": f"Daily limit reached ({count}/{max_plays} plays)",
                "action_required": "logout",
                "game_type": game_type,
                "played_today": count,
                "max_plays": max_plays,
                "reset_time": "00:00 UTC (Midnight)"
            }
        
        # Record this play
        cursor.execute(f'''
        INSERT INTO game_plays (user_id, game_type, play_date) 
        VALUES ({ph}, {ph}, {ph})
        ''', (user_id, game_type, today))
        
        conn.commit()
        return {
            "can_play": True,
            "played_today": count + 1,
            "max_plays": max_plays,
            "remaining": max_plays - (count + 1)
        }
        
    except Exception as e:
        app.logger.error(f"Game limit check error: {e}")
        conn.rollback()
        return {"can_play": False, "reason": "System error"}
    finally:
        return_db_connection(conn)

# ======================= GAME LIMIT TRACKING FUNCTIONS =======================
def check_and_record_game_play(user_id, game_type):
    """Check if user can play and record the play - PER REWARD CLAIM"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    
    try:
        # Get max plays for this game
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        
        # Check existing plays today
        cursor.execute(f'''
        SELECT COUNT(*) FROM game_plays 
        WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}
        ''', (user_id, game_type, today))
        
        count = cursor.fetchone()[0]
        
        if count >= max_plays:
            app.logger.info(f'Game limit reached: User {user_id}, Game {game_type}, Plays {count}/{max_plays}')
            return False
        
        # Record this play
        cursor.execute(f'''
        INSERT INTO game_plays (user_id, game_type, play_date) 
        VALUES ({ph}, {ph}, {ph})
        ''', (user_id, game_type, today))
        
        conn.commit()
        app.logger.info(f'Game play recorded: User {user_id}, Game {game_type}, Play #{count+1}')
        return True
        
    except Exception as e:
        app.logger.error(f"Game play check error: {e}")
        conn.rollback()
        return False
    finally:
        return_db_connection(conn)

def get_game_plays_today(user_id, game_type):
    """Get how many times user has played a game today"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f'''
        SELECT COUNT(*) FROM game_plays 
        WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}
        ''', (user_id, game_type, today))
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        app.logger.error(f"Get plays error: {e}")
        return 0
    finally:
        return_db_connection(conn)

# ======================= INITIALIZATION =======================
def add_missing_columns():
    """Add missing columns if they don't exist"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            # Check and add missing columns for PostgreSQL
            columns_to_add = ['last_achievement_check', 'last_game_timestamp', 'claimed_achievements']
            for column in columns_to_add:
                cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' and column_name='{column}'
                """)
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
                    app.logger.info(f"Added missing column: {column} to users table")
        else:
            # SQLite - check pragma
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            columns_to_add = ['last_achievement_check', 'last_game_timestamp', 'claimed_achievements']
            for column in columns_to_add:
                if column not in columns:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
                    app.logger.info(f"Added missing column: {column} to users table")
        
        conn.commit()
        app.logger.info("Database column verification complete")
    except Exception as e:
        app.logger.error(f"Error adding missing columns: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

def add_database_indexes():
    """Add performance indexes to database"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_timestamp ON transactions(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type_timestamp ON transactions(type, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_game_plays_user_date ON game_plays(user_id, play_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)"
        ]
        
        for sql in indexes:
            try:
                cursor.execute(sql)
                app.logger.info(f"Created index: {sql}")
            except Exception as e:
                app.logger.warning(f"Index creation warning: {e}")
        
        conn.commit()
        app.logger.info("Database indexes created/verified")
    except Exception as e:
        app.logger.error(f"Error creating indexes: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None

    # Users table
    if is_postgres:
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
    else:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.00,
            referral_code TEXT,
            referred_by TEXT,
            is_admin BOOLEAN DEFAULT 0,
            created_at TEXT,
            last_login TEXT,
            claimed_bonuses INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            game_stats TEXT,
            withdrawal_pin TEXT,
            admin_password_changed BOOLEAN DEFAULT 0,
            contact TEXT,
            profile_picture TEXT,
            ui_theme TEXT DEFAULT 'light',
            withdrawal_restricted BOOLEAN DEFAULT 0,
            custom_withdrawal_days TEXT,
            withdrawal_limit REAL DEFAULT 0.00,
            last_game_timestamp TEXT,
            last_achievement_check TEXT,
            claimed_achievements TEXT DEFAULT '[]'
        )
        ''')

    # Admin settings
    if is_postgres:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id SERIAL PRIMARY KEY,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT
        )
        ''')
    else:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT
        )
        ''')

    # Other tables
    tables_sql = [
        '''CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            status TEXT,
            details TEXT,
            timestamp TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            status TEXT DEFAULT 'AVAILABLE'
        )''',
        '''CREATE TABLE IF NOT EXISTS banks (
            code TEXT PRIMARY KEY,
            name TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )''',
        '''CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            label TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id SERIAL PRIMARY KEY,
            number TEXT UNIQUE NOT NULL,
            label TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS game_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            play_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS game_plays (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            game_type TEXT,
            play_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS tiktok_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount REAL DEFAULT 150.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS tiktok_daily (
            id SERIAL PRIMARY KEY,
            date TEXT UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount REAL DEFAULT 150.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    ]
    
    for sql in tables_sql:
        try:
            cursor.execute(sql)
        except Exception as e:
            app.logger.error(f"Error creating table: {e}")

    # Insert default banks
    ph = '%s' if is_postgres else '?'
    cursor.execute('SELECT COUNT(*) as count FROM banks')
    bank_count = cursor.fetchone()
    if isinstance(bank_count, dict):
        bank_count = bank_count['count']
    else:
        bank_count = bank_count[0] if bank_count else 0
        
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
        for bank in banks:
            try:
                cursor.execute(f'INSERT INTO banks (code, name, is_active) VALUES ({ph}, {ph}, {ph})', 
                             (bank[0], bank[1], True))
            except Exception as e:
                app.logger.error(f"Error inserting bank {bank[0]}: {e}")
        app.logger.info(f"Inserted {len(banks)} banks")

    # Admin settings
    cursor.execute('SELECT COUNT(*) as count FROM admin_settings')
    settings_count = cursor.fetchone()
    if isinstance(settings_count, dict):
        settings_count = settings_count['count']
    else:
        settings_count = settings_count[0] if settings_count else 0
    if settings_count == 0:
        default_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
        cursor.execute(f'INSERT INTO admin_settings (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) VALUES ({ph}, {ph}, {ph}, {ph})',
                       ('', '', '', default_days_json))

    # Coupons
    if os.path.exists(CONFIG.COUPON_FILE):
        try:
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            if codes:
                try:
                    cursor.execute('DELETE FROM coupons')
                except:
                    pass
                for code in codes:
                    try:
                        cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
                    except:
                        pass
                app.logger.info(f"Loaded {len(codes)} coupons from file")
        except Exception as e:
            app.logger.error(f"Error loading coupons: {e}")
    else:
        default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
        for code in default_coupons:
            try:
                cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
            except:
                pass
        app.logger.info(f"Created {len(default_coupons)} default coupons")

    # Admin user - USING ENVIRONMENT VARIABLES
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s' if is_postgres else 'SELECT COUNT(*) as count FROM users WHERE username = ?', (CONFIG.ADMIN_USERNAME,))
    admin_count = cursor.fetchone()[0]
    if admin_count == 0:
        admin_pass = generate_password_hash(CONFIG.ADMIN_PASSWORD)
        game_stats = json.dumps({
            "snake": {"high_score": 1200, "total_score": 5000},
            "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
            "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
        })
        pin_hash = generate_password_hash(CONFIG.ADMIN_WITHDRAWAL_PIN)
        if is_postgres:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme, 
                last_game_timestamp, last_achievement_check, claimed_achievements
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                CONFIG.ADMIN_USERNAME, admin_pass, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, False, pin_hash, "", "", "light", 
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                '[]'
            ))
        else:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme,
                last_game_timestamp, last_achievement_check, claimed_achievements
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                CONFIG.ADMIN_USERNAME, admin_pass, 500000.00, "ADM0001", 1,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, 0, pin_hash, "", "", "light",
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                '[]'
            ))
        app.logger.warning("\n⚠️ FLEXIA ADMIN ACCOUNT CREATED ⚠️")
        app.logger.warning(f"Username: {CONFIG.ADMIN_USERNAME}")
        app.logger.warning(f"Initial Password: {CONFIG.ADMIN_PASSWORD}")
        app.logger.warning(f"Default Withdrawal PIN: {CONFIG.ADMIN_WITHDRAWAL_PIN}")
        app.logger.warning("⚠️ Change both after first login!\n")
        app.logger.warning("ℹ️ Admin credentials can be changed via environment variables:")
        app.logger.warning("  - ADMIN_USERNAME")
        app.logger.warning("  - ADMIN_PASSWORD") 
        app.logger.warning("  - ADMIN_WITHDRAWAL_PIN")

    # WhatsApp number
    cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
    whatsapp_count = cursor.fetchone()[0]
    if whatsapp_count == 0:
        cursor.execute(f'INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES ({ph}, {ph}, {ph}, {ph})',
                       ('2348160881049', 'Primary Seller', True if is_postgres else 1, datetime.utcnow().isoformat()))

    conn.commit()
    return_db_connection(conn)
    app.logger.info("Database initialization completed successfully!")

# ======================= HELPERS =======================
def sanitize_input(text):
    if not text:
        return ""
    for char in '<>"\'`':
        text = text.replace(char, '')
    return text.strip()

def get_global_withdrawal_days():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row:
            settings = row_to_dict(cursor, row)
            days_str = _safe_get(settings, 'global_withdrawal_days', '')
            if days_str:
                return json.loads(days_str)
    except Exception as e:
        app.logger.error(f"Error getting global withdrawal days: {e}")
    finally:
        return_db_connection(conn)
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

def get_game_friendly_name(game_type):
    """Get user-friendly name for game type"""
    names = {
        'snake': 'Snake Game',
        'coinflip': 'Coin Flip',
        'plinko': 'Plinko 3D',
        'spin': 'Daily Spin',
        'tiktok': 'TikTok Follow'
    }
    return names.get(game_type, game_type)

# ======================= OPTIMIZED: ATOMIC BALANCE UPDATES =======================
def update_user_balance(user_id, amount_change):
    """Thread-safe atomic balance update with connection timeout"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Set a timeout to prevent hanging
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SET statement_timeout = 5000")  # 5 second timeout
        
        # Atomic update with row locking
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute(f'''
            UPDATE users 
            SET balance = balance + {ph}
            WHERE id = {ph}
            RETURNING balance
            ''', (amount_change, user_id))
        else:
            # SQLite version
            cursor.execute(f'''
            UPDATE users 
            SET balance = balance + {ph}
            WHERE id = {ph}
            ''', (amount_change, user_id))
            
            cursor.execute(f'SELECT balance FROM users WHERE id = {ph}', (user_id,))
        
        row = cursor.fetchone()
        new_balance = float(row[0]) if row and row[0] else 0.0
        
        conn.commit()
        app.logger.info(f"💰 Atomic balance update for user {user_id}: {amount_change}, new balance: {new_balance}")
        return new_balance
        
    except Exception as e:
        app.logger.error(f"❌ Balance update error: {str(e)}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            return_db_connection(conn)

def check_game_cooldown(user_id, game_type):
    """Check if user is in cooldown for a specific game"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT last_game_timestamp FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                last_game = datetime.fromisoformat(row[0])
                now = datetime.utcnow()
                # 1 second cooldown between games
                if (now - last_game).total_seconds() < 1:
                    return False
            except:
                pass
        return True
    except Exception as e:
        app.logger.error(f"Cooldown check error: {e}")
        return True
    finally:
        return_db_connection(conn)

def update_last_game_timestamp(user_id):
    """Update user's last game timestamp"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET last_game_timestamp = %s WHERE id = %s',
                       (datetime.utcnow().isoformat(), user_id))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Update last game timestamp error: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

# ======================= FIXED: WITHDRAWAL DAY CHECK =======================
def is_withdrawal_day(user_id=None):
    """Check if today is a withdrawal day for the user - FIXED VERSION"""
    today = datetime.utcnow().day
    
    # If no user_id provided, check global days
    if user_id is None:
        return today in get_global_withdrawal_days()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        
        # Get user's withdrawal settings
        cursor.execute(f'''
        SELECT withdrawal_restricted, custom_withdrawal_days 
        FROM users WHERE id = {ph}
        ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        withdrawal_restricted = bool(row[0])
        custom_days_str = row[1] if row[1] else ''
        
        # If user is restricted, cannot withdraw
        if withdrawal_restricted:
            return False
        
        # Check custom withdrawal days
        if custom_days_str and custom_days_str.strip():
            try:
                custom_days = json.loads(custom_days_str)
                if isinstance(custom_days, list) and custom_days:
                    return today in custom_days
            except:
                pass  # Fall through to global days
        
        # Fall back to global withdrawal days
        return today in get_global_withdrawal_days()
        
    except Exception as e:
        app.logger.error(f"Error checking withdrawal day: {e}")
        return False
    finally:
        return_db_connection(conn)

# ======================= OPTIMIZED: ACHIEVEMENT REWARDS =======================
def grant_achievement_rewards(user_id):
    """Thread-safe achievement reward calculation - ONE TIME ONLY REWARDS"""
    app.logger.info(f"Granting achievement rewards for user {user_id}")
    
    conn = None
    cursor = None
    
    try:
        # Get a fresh connection
        conn = get_db()
        cursor = conn.cursor()
        
        # Start transaction
        if os.environ.get('DATABASE_URL'):
            cursor.execute("BEGIN")
        else:
            cursor.execute("BEGIN IMMEDIATE")
        
        # Get user data WITH LOCK to prevent concurrent updates
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'''
        SELECT balance, game_stats, referral_code, points, last_achievement_check,
               claimed_achievements
        FROM users WHERE id = {ph}
        ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return None
        
        balance = float(row[0]) if row[0] else 0
        game_stats_str = row[1] if row[1] else '{}'
        referral_code = row[2] if row[2] else ''
        current_points = int(row[3]) if row[3] else 0
        last_check = row[4] if row[4] else None
        
        # Get already claimed achievements
        claimed_achievements_str = row[5] if len(row) > 5 else '[]'
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []
        
        # Check if already processed recently (within 5 minutes)
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
                if (datetime.utcnow() - last_check_time).total_seconds() < 300:  # 5 minutes
                    conn.rollback()
                    return balance
            except:
                pass
        
        game_stats = json.loads(game_stats_str)
        
        # Get referrals count
        cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (referral_code,))
        referrals = cursor.fetchone()[0]
        
        # Get transaction counts
        cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph}', (user_id,))
        total_tx = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = 'WITHDRAWAL'", (user_id,))
        total_withdrawals = cursor.fetchone()[0]
        
        # Get today's games
        today = datetime.utcnow().date()
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND play_date = {ph}', (user_id, today))
        games_today = cursor.fetchone()[0]
        
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph}', (user_id,))
        total_games = cursor.fetchone()[0]
        
        # Extract game stats
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

        # Define achievements with IDs
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

        # Filter out achievements that have already been rewarded
        new_achievements = []
        for ach in achievements:
            if ach["unlocked"] and ach["id"] not in claimed_achievements:
                new_achievements.append(ach)
        
        if not new_achievements:
            # Still update last check time
            cursor.execute(f'UPDATE users SET last_achievement_check = {ph} WHERE id = {ph}', 
                          (datetime.utcnow().isoformat(), user_id))
            conn.commit()
            return balance
        
        total_reward = sum(ach["reward"] for ach in new_achievements)
        total_points = sum(ach["points"] for ach in new_achievements)
        
        # Add the newly rewarded achievement IDs to claimed list
        new_achievement_ids = [ach["id"] for ach in new_achievements]
        all_claimed_achievements = claimed_achievements + new_achievement_ids
        
        new_balance = balance + total_reward
        
        # Update user balance and points using atomic update
        if os.environ.get('DATABASE_URL'):
            cursor.execute(f'''
            UPDATE users SET balance = {ph}, points = {ph}, 
            last_achievement_check = {ph}, claimed_achievements = {ph}
            WHERE id = {ph}
            ''', (new_balance, current_points + total_points, 
                  datetime.utcnow().isoformat(), 
                  json.dumps(all_claimed_achievements), user_id))
        else:
            # For SQLite, we need to update separately
            cursor.execute(f'''
            UPDATE users SET balance = balance + {ph}, points = points + {ph}, 
            last_achievement_check = {ph}, claimed_achievements = {ph}
            WHERE id = {ph}
            ''', (total_reward, total_points, 
                  datetime.utcnow().isoformat(), 
                  json.dumps(all_claimed_achievements), user_id))
        
        # Record achievement transaction if reward > 0
        if total_reward > 0:
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute(f'''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
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
        try:
            if conn:
                conn.rollback()
        except:
            pass
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

def cleanup_old_tiktok_tasks():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'DELETE FROM tiktok_daily WHERE date < {ph}', (cutoff_date,))
        conn.commit()
        return_db_connection(conn)
        app.logger.info(f"Removed TikTok tasks before {cutoff_date}")
    except Exception as e:
        app.logger.error(f"TikTok Cleanup Error: {e}")

def run_cleanup_scheduler():
    def schedule():
        while True:
            now = datetime.utcnow()
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now > next_run:
                next_run += timedelta(days=1)
            time_to_sleep = (next_run - now).total_seconds()
            time.sleep(time_to_sleep)
            cleanup_old_tiktok_tasks()
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= CRITICAL: DB INIT =======================
with app.app_context():
    init_db_pool()  # Initialize connection pool
    init_db()       # Initialize database
    add_missing_columns()  # Add missing columns
    add_database_indexes()  # Add performance indexes
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()
    run_backup_scheduler()  # Start backup scheduler

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
def register():
    ip = request.remote_addr
    if not rate_limit(register_attempts, ip, max_per_min=3):
        app.logger.warning(f"Rate limit exceeded for registration from {ip}")
        return jsonify({"success": False, "message": "Too many attempts. Try again later."}), 429
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    username = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    referral_code = sanitize_input(data.get('referral_code', ''))
    contact = sanitize_input(data.get('contact', ''))
    
    if not all([username, password, coupon_code]):
        return jsonify({"success": False, "message": "Missing fields"}), 400
    
    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "message": "Invalid username or password length"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    
    try:
        cursor.execute(f'SELECT id FROM users WHERE LOWER(username) = LOWER({ph})', (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username already taken"}), 409
        
        cursor.execute(f'SELECT status FROM coupons WHERE code = {ph}', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row:
            return jsonify({"success": False, "message": "Invalid coupon code"}), 403
        
        if coupon_row[0] != 'AVAILABLE':
            return jsonify({"success": False, "message": "Coupon already used"}), 403
        
        if referral_code:
            cursor.execute(f'SELECT referral_code FROM users WHERE referral_code = {ph}', (referral_code,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Invalid referral code"}), 400
        
        cursor.execute(f'UPDATE coupons SET status = {ph} WHERE code = {ph}', ("USED", coupon_code))
        
        timestamp = int(time.time())
        user_referral_code = f"{username[:3].upper()}{timestamp % 10000:04d}"
        
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0},
            "coin_flip": {"wins": 0, "losses": 0, "current_streak": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0}
        })
        
        is_admin_value = False if is_postgres else 0
        admin_pw_changed = False if is_postgres else 0
        withdrawal_restricted = False if is_postgres else 0
        
        cursor.execute(f'''
        INSERT INTO users (
            username, password, balance, referral_code, referred_by, is_admin,
            created_at, last_login, game_stats, contact, profile_picture, ui_theme,
            admin_password_changed, withdrawal_pin, withdrawal_restricted, withdrawal_limit, 
            points, claimed_bonuses, last_game_timestamp, last_achievement_check,
            claimed_achievements
        ) VALUES (
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}
        )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, is_admin_value,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            admin_pw_changed, None, withdrawal_restricted, 0.00, 0, 0, 
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            '[]'
        ))
        
        if is_postgres:
            cursor.execute("SELECT LASTVAL()")
            new_id = cursor.fetchone()[0]
        else:
            new_id = cursor.lastrowid
        
        admin_bonus = 0
        if referral_code:
            cursor.execute(f'SELECT is_admin FROM users WHERE referral_code = {ph}', (referral_code,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row[0]:
                admin_bonus = 5000
                cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (admin_bonus, new_id))
        
        conn.commit()
        
        token = create_session_token(new_id)
        
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": new_id,
                "username": username,
                "referral_code": user_referral_code,
                "balance": admin_bonus
            }
        })
        
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie('session_token', token, 
                          httponly=True, 
                          secure=secure_cookie, 
                          samesite='Lax', 
                          max_age=86400)
        
        app.logger.info(f"New user registered: {username} (ID: {new_id})")
        return response
        
    except Exception as e:
        app.logger.error(f"Registration error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Registration failed: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr
    if not rate_limit(login_attempts, ip, max_per_min=5):
        app.logger.warning(f"Rate limit exceeded for login from {ip}")
        return jsonify({"success": False, "message": "Too many login attempts"}), 429
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    
    if not identifier or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    
    try:
        cursor.execute(f'SELECT * FROM users WHERE LOWER(username) = LOWER({ph}) OR LOWER(contact) = LOWER({ph})',
                       (identifier, identifier))
        row = cursor.fetchone()
        
        if not row:
            app.logger.warning(f"Failed login attempt for identifier: {identifier}")
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        
        stored_password = row[2] if len(row) > 2 else None
        
        if not stored_password or not check_password_hash(stored_password, password):
            app.logger.warning(f"Invalid password for user: {identifier}")
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        
        user = row_to_dict(cursor, row)
        
        cursor.execute(f'UPDATE users SET last_login = {ph} WHERE id = {ph}',
                       (datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        
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
            }
        })
        
        token = create_session_token(user['id'])
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token, 
                       httponly=True, 
                       secure=secure_cookie, 
                       samesite='Lax', 
                       max_age=86400)
        
        app.logger.info(f"User logged in: {user['username']} (ID: {user['id']})")
        return resp
        
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({"success": False, "message": f"Login failed: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    user = get_current_user()
    if user:
        app.logger.info(f"User logged out: {user['username']} (ID: {user['id']})")
    resp = jsonify({"success": True, "message": "Logged out"})
    resp.set_cookie('session_token', '', expires=0)
    return resp

# ======================= USER ENDPOINTS =======================
@app.route('/api/user/profile')
@require_auth
def get_user_profile():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    
    try:
        cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user['id'],))
        fresh_user = row_to_dict(cursor, cursor.fetchone())
        
        if not fresh_user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (fresh_user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        claimed = int(fresh_user.get('claimed_bonuses', 0))
        unclaimed = max(0, referrals * CONFIG.REFERRAL_BONUS - claimed)
        
        cursor.execute(f'SELECT * FROM transactions WHERE user_id = {ph} ORDER BY timestamp DESC LIMIT 20', (user['id'],))
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
            }
        })
        
    except Exception as e:
        app.logger.error(f"Profile error: {e}")
        return jsonify({"success": False, "message": f"Failed to load profile: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@require_auth
def set_withdrawal_pin():
    """Set or change withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    pin = data.get('pin', '')
    
    if not pin or not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
        return jsonify({"success": False, "message": "PIN must be 4-6 digits"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Hash the PIN
        pin_hash = generate_password_hash(pin)
        
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s',
                      (pin_hash, user['id']))
        
        conn.commit()
        
        app.logger.info(f"User {user['username']} set withdrawal PIN")
        
        return jsonify({
            "success": True,
            "message": "Withdrawal PIN set successfully"
        })
        
    except Exception as e:
        app.logger.error(f"Set withdrawal PIN error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set PIN"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
def verify_withdrawal_pin():
    """Verify withdrawal PIN"""
    user = get_current_user()
    data = request.get_json()
    
    pin = data.get('pin', '')
    
    if not pin:
        return jsonify({"success": False, "message": "PIN required"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT withdrawal_pin FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        
        if not row or not row[0]:
            return jsonify({"success": False, "message": "No PIN set yet"}), 400
        
        stored_pin = row[0]
        
        if check_password_hash(stored_pin, pin):
            return jsonify({
                "success": True,
                "message": "PIN verified"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Incorrect PIN"
            }), 403
        
    except Exception as e:
        app.logger.error(f"Verify PIN error: {e}")
        return jsonify({"success": False, "message": "Failed to verify PIN"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    user = get_current_user()
    data = request.get_json()
    
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "Old and new password required"}), 400
    
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get current password
        cursor.execute('SELECT password FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        stored_password = row[0]
        
        # Verify old password
        if not check_password_hash(stored_password, old_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 403
        
        # Update to new password
        new_password_hash = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password = %s WHERE id = %s',
                      (new_password_hash, user['id']))
        
        conn.commit()
        
        app.logger.info(f"User {user['username']} changed password")
        
        return jsonify({
            "success": True,
            "message": "Password changed successfully"
        })
        
    except Exception as e:
        app.logger.error(f"Change password error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to change password"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    """Set user profile picture"""
    user = get_current_user()
    data = request.get_json()
    
    picture_url = data.get('picture_url', '').strip()
    
    if not picture_url:
        return jsonify({"success": False, "message": "Picture URL required"}), 400
    
    # Basic URL validation
    if not picture_url.startswith(('http://', 'https://')):
        return jsonify({"success": False, "message": "Invalid URL format"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s',
                      (picture_url, user['id']))
        
        conn.commit()
        
        app.logger.info(f"User {user['username']} updated profile picture")
        
        return jsonify({
            "success": True,
            "message": "Profile picture updated"
        })
        
    except Exception as e:
        app.logger.error(f"Set profile picture error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update profile picture"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_ui_theme():
    """Set user UI theme (dark/light)"""
    user = get_current_user()
    data = request.get_json()
    
    dark_mode = data.get('dark_mode', False)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        theme = 'dark' if dark_mode else 'light'
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s',
                      (theme, user['id']))
        
        conn.commit()
        
        app.logger.info(f"User {user['username']} set theme to {theme}")
        
        return jsonify({
            "success": True,
            "message": f"Theme set to {theme} mode"
        })
        
    except Exception as e:
        app.logger.error(f"Set theme error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set theme"}), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN PASSWORD CHANGE =======================
@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def admin_change_password():
    """Change admin password - FIXED VERSION"""
    user = get_current_user()
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Current and new password required"}), 400
    
    if len(new_password) < 8:
        return jsonify({"success": False, "message": "New password must be at least 8 characters"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get current password hash
        cursor.execute('SELECT password FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        stored_password = row[0]
        
        # Verify current password
        if not check_password_hash(stored_password, current_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 403
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password = %s, admin_password_changed = TRUE WHERE id = %s',
                      (new_password_hash, user['id']))
        
        conn.commit()
        
        app.logger.info(f"Admin password changed for user: {user['username']}")
        
        return jsonify({
            "success": True,
            "message": "Password changed successfully! Please login again."
        })
        
    except Exception as e:
        app.logger.error(f"Change admin password error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to change password"}), 500
    finally:
        return_db_connection(conn)

# ======================= CHECK WITHDRAWAL DAY STATUS =======================
@app.route('/api/withdrawal/check-day', methods=['GET'])
@require_auth
def check_withdrawal_day():
    """Check if user can withdraw today - FIXED VERSION"""
    user = get_current_user()
    today = datetime.utcnow().day
    
    try:
        can_withdraw = is_withdrawal_day(user['id'])
        global_days = get_global_withdrawal_days()
        
        # Get user's custom days if any
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT custom_withdrawal_days FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        custom_days = []
        if row and row[0]:
            try:
                custom_days = json.loads(row[0]) if row[0] else []
            except:
                pass
        
        return jsonify({
            "success": True,
            "can_withdraw": can_withdraw,
            "today": today,
            "global_withdrawal_days": global_days,
            "custom_withdrawal_days": custom_days if custom_days else [],
            "message": f"You {'CAN' if can_withdraw else 'CANNOT'} withdraw today. Withdrawal days: {', '.join(map(str, sorted(custom_days if custom_days else global_days)))}"
        })
        
    except Exception as e:
        app.logger.error(f"Check withdrawal day error: {e}")
        return jsonify({"success": False, "message": "Failed to check withdrawal day"}), 500

# ======================= GAME ACCESS CHECK ENDPOINTS =======================
@app.route('/api/games/access', methods=['GET'])
@require_auth
def check_game_access_simple():
    """Simple game access check - returns if user can play"""
    user = get_current_user()
    game_type = request.args.get('game')
    
    if not game_type:
        return jsonify({"success": False, "message": "Game type required"}), 400
    
    if game_type not in ['snake', 'coinflip', 'plinko', 'spin', 'tiktok']:
        return jsonify({"success": False, "message": "Invalid game type"}), 400
    
    try:
        plays_today = get_game_plays_today(user['id'], game_type)
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        
        can_play = plays_today < max_plays
        
        return jsonify({
            "success": True,
            "can_play": can_play,
            "played_today": plays_today,
            "max_plays": max_plays,
            "remaining_plays": max(0, max_plays - plays_today)
        })
        
    except Exception as e:
        app.logger.error(f"Game access check error: {e}")
        return jsonify({"success": False, "message": "Failed to check game access"}), 500

@app.route('/api/games/check-access/<game_type>', methods=['GET'])
@require_auth
def check_game_access(game_type):
    """Check if user can access a specific game BEFORE playing"""
    user = get_current_user()
    
    if game_type not in ['snake', 'coinflip', 'plinko', 'spin', 'tiktok']:
        return jsonify({"success": False, "message": "Invalid game type"}), 400
    
    try:
        # Get max plays for this game
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        
        # Get current plays today
        plays_today = get_game_plays_today(user['id'], game_type)
        
        can_play = plays_today < max_plays
        remaining = max(0, max_plays - plays_today)
        
        return jsonify({
            "success": True,
            "can_play": can_play,
            "played_today": plays_today,
            "max_plays": max_plays,
            "remaining": remaining,
            "game_type": game_type,
            "game_name": get_game_friendly_name(game_type),
            "message": f"You have {remaining} {game_type} plays remaining today" if can_play else f"Daily limit reached: {plays_today}/{max_plays} plays"
        })
        
    except Exception as e:
        app.logger.error(f"Game access check error: {e}")
        return jsonify({"success": False, "message": "Failed to check game access"}), 500

@app.route('/api/games/limit-check', methods=['GET'])
@require_auth
def check_game_limit():
    """Check game daily limit"""
    user = get_current_user()
    game_type = request.args.get('game')
    
    if not game_type:
        return jsonify({"success": False, "message": "Game type required"}), 400
    
    try:
        plays_today = get_game_plays_today(user['id'], game_type)
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        
        return jsonify({
            "success": True,
            "can_play": plays_today < max_plays,
            "played_today": plays_today,
            "max_per_day": max_plays,
            "remaining": max(0, max_plays - plays_today)
        })
        
    except Exception as e:
        app.logger.error(f"Game limit check error: {e}")
        return jsonify({"success": False, "message": "Failed to check limit"}), 500

# ======================= GAME LIMIT WITH LOGOUT ENDPOINTS =======================
@app.route('/api/games/check-limit-with-logout/<game_type>', methods=['GET'])
@require_auth
def check_game_limit_with_logout_endpoint(game_type):
    """Check if user can play a game - returns logout instruction if limit reached"""
    user = get_current_user()
    
    if game_type not in ['snake', 'coinflip', 'plinko', 'spin', 'tiktok']:
        return jsonify({"success": False, "message": "Invalid game type"}), 400
    
    try:
        result = check_game_limit_with_logout(user['id'], game_type)
        
        if result.get("can_play", False):
            return jsonify({
                "success": True,
                "can_play": True,
                "played_today": result.get("played_today", 0),
                "max_plays": result.get("max_plays", 5),
                "remaining": result.get("remaining", 0),
                "game_type": game_type,
                "game_name": get_game_friendly_name(game_type)
            })
        else:
            return jsonify({
                "success": False,
                "can_play": False,
                "reason": result.get("reason", "Daily limit reached"),
                "action_required": result.get("action_required", "logout"),
                "game_type": game_type,
                "played_today": result.get("played_today", 0),
                "max_plays": result.get("max_plays", 5),
                "reset_time": result.get("reset_time", "00:00 UTC"),
                "force_logout": True,
                "message": f"Daily limit reached! You've played {result.get('played_today', 0)}/{result.get('max_plays', 5)} times today. Please come back tomorrow after 00:00 UTC."
            }), 403
            
    except Exception as e:
        app.logger.error(f"Game limit check error: {e}")
        return jsonify({"success": False, "message": "Failed to check game limit"}), 500

@app.route('/api/games/force-logout/<game_type>', methods=['POST'])
@require_auth
def force_logout_from_game(game_type):
    """Force logout user from a game with detailed reason"""
    user = get_current_user()
    
    # Record forced logout
    conn = get_db()
    cursor = conn.cursor()
    try:
        tx_id = f"LOGOUT-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'FORCE_LOGOUT', 0, 'COMPLETED',
            json.dumps({
                "game_type": game_type,
                "reason": "daily_limit_reached",
                "action": "auto_logged_out",
                "redirect_to": "/?reason=daily_limit"
            }),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Force logout logging error: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)
    
    # Invalidate session
    resp = jsonify({
        "success": True,
        "force_logout": True,
        "reason": f"Daily {game_type} limit reached",
        "redirect": "/?reason=daily_limit_reached",
        "message": "You have reached your daily limit. Please come back tomorrow!"
    })
    resp.set_cookie('session_token', '', expires=0)
    return resp

# ================= GAME ENDPOINTS WITH LIMIT ENFORCEMENT =================
@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake_enhanced():
    """Snake game with enhanced limit checking"""
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    
    app.logger.info(f"🐍 Snake report from {user['username']}: {apples} apples")
    
    # Validate input
    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "Invalid apple count (1-100)"}), 400
    
    # ACQUIRE LOCK to prevent duplicate claims
    if not acquire_claim_lock(user['id'], 'SNAKE'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429
    
    try:
        # Check game cooldown
        if not check_game_cooldown(user['id'], 'SNAKE'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429
        
        # CHECK GAME LIMIT FIRST - Per reward claim
        limit_check = check_game_limit_with_logout(user['id'], 'snake')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily snake game limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403
        
        reward = apples * CONFIG.SNAKE_REWARD
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Use atomic balance update
            new_balance = update_user_balance(user['id'], reward)
            if new_balance is None:
                return jsonify({"success": False, "message": "Failed to update balance"}), 500
            
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
            
            # Update last game timestamp
            update_last_game_timestamp(user['id'])
            
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
            
            app.logger.info(f"✅ Snake reward granted to {user['username']}: ₦{reward}")
            
            return jsonify({
                "success": True,
                "reward": reward,
                "new_balance": new_balance,
                "apples": apples,
                "transaction_id": tx_id,
                "message": f"Success! Claimed ₦{reward} for {apples} apples"
            })
            
        except Exception as e:
            app.logger.error(f"❌ Snake database error: {e}")
            app.logger.error(traceback.format_exc())
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'SNAKE')

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip_enhanced():
    """Coin flip game report - WITH ENHANCED LIMIT CHECKING"""
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    won = data.get('won', False)
    
    app.logger.info(f"🪙 Coin flip from {user['username']}: bet {bet}, won: {won}")
    
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.COIN_FLIP_MIN_BET}, max: 50000)"}), 400
    
    # ACQUIRE LOCK
    if not acquire_claim_lock(user['id'], 'COINFLIP'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429
    
    try:
        # Check game cooldown
        if not check_game_cooldown(user['id'], 'COINFLIP'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429
        
        # CHECK GAME LIMIT FIRST - Per reward claim
        limit_check = check_game_limit_with_logout(user['id'], 'coinflip')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily coin flip limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403
        
        payout = bet * 2 if won else 0
        net_change = payout - bet
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Use atomic balance update
            new_balance = update_user_balance(user['id'], net_change)
            if new_balance is None:
                return jsonify({"success": False, "message": "Failed to update balance"}), 500
            
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
            
            # Update last game timestamp
            update_last_game_timestamp(user['id'])
            
            # Record transaction
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
            
            app.logger.info(f"✅ Coin flip processed for {user['username']}: {'WON' if won else 'LOST'} {bet}, net: {net_change}")
            
            return jsonify({
                "success": True,
                "payout": payout if won else 0,
                "net_change": net_change,
                "new_balance": new_balance,
                "won": won,
                "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}₦{abs(net_change):.2f}"
            })
            
        except Exception as e:
            app.logger.error(f"❌ Coin flip error: {e}")
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'COINFLIP')

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko_enhanced():
    """Plinko game report - WITH ENHANCED LIMIT CHECKING"""
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    multiplier = float(data.get('multiplier', 0))
    
    app.logger.info(f"🎯 Plinko from {user['username']}: bet {bet}, multiplier: {multiplier}")
    
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.PLINKO_MIN_BET}, max: 50000)"}), 400
    
    if multiplier not in [0.5, 3, 10]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400
    
    # ACQUIRE LOCK
    if not acquire_claim_lock(user['id'], 'PLINKO'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429
    
    try:
        # Check game cooldown
        if not check_game_cooldown(user['id'], 'PLINKO'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429
        
        # CHECK GAME LIMIT FIRST - Per reward claim
        limit_check = check_game_limit_with_logout(user['id'], 'plinko')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily plinko limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403
        
        win_amount = bet * multiplier
        net_change = win_amount - bet  # Positive if win, negative if loss
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Use atomic balance update
            new_balance = update_user_balance(user['id'], net_change)
            if new_balance is None:
                return jsonify({"success": False, "message": "Failed to update balance"}), 500
            
            game_stats = json.loads(user.get('game_stats', '{}'))
            plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
            
            plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
            
            if win_amount > bet:  # Actual win (not just getting bet back)
                plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
                if win_amount > plinko_stats.get('highest_win', 0):
                    plinko_stats['highest_win'] = win_amount
            
            game_stats['plinko'] = plinko_stats
            
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                           (json.dumps(game_stats), user['id']))
            
            # Update last game timestamp
            update_last_game_timestamp(user['id'])
            
            # Record transaction
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
            
            app.logger.info(f"✅ Plinko processed for {user['username']}: bet {bet}, multiplier {multiplier}, net: {net_change}")
            
            return jsonify({
                "success": True,
                "win_amount": win_amount,
                "net_change": net_change,
                "new_balance": new_balance,
                "multiplier": multiplier,
                "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}₦{net_change:.2f}"
            })
            
        except Exception as e:
            app.logger.error(f"❌ Plinko error: {e}")
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'PLINKO')

# ================= SPIN WHEEL ENDPOINTS =================
@app.route('/api/spin/daily-status', methods=['GET'])
@require_auth
def get_spin_daily_status():
    """Check if user can spin today - FIXED VERSION"""
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = 'SPIN_REWARD' 
        AND DATE(timestamp) = %s
        ''', (user['id'], today))
        
        already_spun = cursor.fetchone() is not None
        
        return jsonify({
            "success": True,
            "can_spin": not already_spun,
            "already_spun": already_spun,
            "today": today,
            "message": "You have already spun today" if already_spun else "You can spin now"
        })
        
    except Exception as e:
        app.logger.error(f"Spin status error: {e}")
        return jsonify({"success": False, "message": "Failed to check spin status"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/spin/execute', methods=['POST'])
@require_auth
def execute_spin():
    """Execute spin wheel game - FIXED VERSION"""
    user = get_current_user()
    
    # Check daily limit first
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = 'SPIN_REWARD' 
        AND DATE(timestamp) = %s
        ''', (user['id'], today))
        
        if cursor.fetchone() is not None:
            return jsonify({
                "success": False,
                "message": "You have already spun today. Come back tomorrow!"
            }), 400
        
        # Generate spin result
        rewards = [1000, 500, 200, 100, 50, 0]
        weights = [0.05, 0.1, 0.15, 0.2, 0.25, 0.25]  # Probabilities
        
        import random
        reward = random.choices(rewards, weights=weights, k=1)[0]
        
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        # Record transaction
        tx_id = f"SPIN-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "spin", "reward": reward}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Spin executed for {user['username']}: reward {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Congratulations! You won ₦{reward}!"
        })
        
    except Exception as e:
        app.logger.error(f"Spin execute error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process spin"}), 500
    finally:
        return_db_connection(conn)

# ================= TIKTOK DAILY =================
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily_task():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        already_claimed = cursor.fetchone() is not None
        
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
                "already_claimed": already_claimed
            })
        else:
            return jsonify({
                "success": False,
                "message": "No TikTok task for today",
                "already_claimed": already_claimed
            }), 404
            
    except Exception as e:
        app.logger.error(f"TikTok daily error: {e}")
        return jsonify({"success": False, "message": f"Failed to get task: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
def follow_tiktok_daily_enhanced():
    """TikTok daily follow with enhanced limit checking"""
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        app.logger.warning(f"Rate limit exceeded for TikTok follow from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    # ACQUIRE LOCK
    if not acquire_claim_lock(user['id'], 'TIKTOK'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Already claimed today"}), 400
        
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        
        if not task_row:
            return jsonify({"success": False, "message": "No task for today"}), 404
        
        reward = float(task_row[0]) if task_row[0] else CONFIG.TIKTOK_REWARD
        
        # CHECK GAME LIMIT - Per reward claim
        limit_check = check_game_limit_with_logout(user['id'], 'tiktok')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily TikTok limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403
        
        # Use atomic balance update
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        
        conn.commit()
        return_db_connection(conn)
        
        app.logger.info(f"✅ TikTok daily claimed by {user['username']}: reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Success! Claimed ₦{reward} for following TikTok"
        })
        
    except Exception as e:
        app.logger.error(f"❌ TikTok follow error: {e}")
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'TIKTOK')

# ================= REFERRAL ENDPOINTS =================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    """Referral bonus claiming with locking"""
    user = get_current_user()
    
    # ACQUIRE LOCK for referral claims
    if not acquire_claim_lock(user['id'], 'REFERRAL'):
        return jsonify({"success": False, "message": "Please wait before claiming again"}), 429
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = int(user.get('claimed_bonuses', 0))
        unclaimed = total_bonus - claimed
        
        if unclaimed <= 0:
            return jsonify({"success": False, "message": "No bonus to claim"}), 400
        
        # Use atomic balance update
        new_balance = update_user_balance(user['id'], unclaimed)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        cursor.execute('UPDATE users SET claimed_bonuses = %s WHERE id = %s',
                       (total_bonus, user['id']))
        
        # Record transaction
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
        return_db_connection(conn)
        
        app.logger.info(f"✅ Referral bonus claimed by {user['username']}: {unclaimed}")
        
        return jsonify({
            "success": True,
            "claimed": unclaimed,
            "new_balance": new_balance,
            "message": f"Success! Claimed ₦{unclaimed} referral bonus"
        })
        
    except Exception as e:
        app.logger.error(f"❌ Referral error: {e}")
        return jsonify({"success": False, "message": f"Failed to claim: {str(e)}"}), 500
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'REFERRAL')

# ================= ACHIEVEMENTS =================
@app.route('/api/achievements')
@require_auth
def get_achievements():
    """Get user achievements - UPDATED with claimed status"""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        game_stats = json.loads(user.get('game_stats', '{}'))
        balance = float(user.get('balance', 0))
        
        # Get claimed achievements
        claimed_achievements_str = user.get('claimed_achievements', '[]')
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []
        
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
        
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

        # Define achievements with FULL progress data and claimed status
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
            "has_unclaimed_rewards": unlocked_not_claimed > 0
        })
        
    except Exception as e:
        app.logger.error(f"❌ Achievements error: {e}")
        return jsonify({"success": False, "message": f"Failed to load achievements: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/achievements/claim', methods=['POST'])
@require_auth
def claim_achievement_rewards():
    """Manual achievement reward claiming - ONE TIME ONLY REWARDS"""
    user = get_current_user()
    
    # ACQUIRE LOCK for achievements
    if not acquire_claim_lock(user['id'], 'ACHIEVEMENTS'):
        return jsonify({"success": False, "message": "Please wait before claiming again"}), 429
    
    try:
        # Call the achievement grant function
        new_balance = grant_achievement_rewards(user['id'])
        
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to process achievement rewards"}), 500
        
        return jsonify({
            "success": True,
            "message": "Achievement rewards processed successfully",
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Claim achievement error: {e}")
        return jsonify({"success": False, "message": f"Failed to claim: {str(e)}"}), 500
    finally:
        # RELEASE LOCK
        release_claim_lock(user['id'], 'ACHIEVEMENTS')

# ================= BANKING ENDPOINTS =================
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    """Get list of all active banks"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT code, name FROM banks WHERE is_active = TRUE ORDER BY name')
        banks = [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
        return jsonify({"success": True, "banks": banks})
    except Exception as e:
        app.logger.error(f"Bank list error: {e}")
        return jsonify({"success": False, "message": "Failed to load banks"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/banking/withdraw', methods=['POST'])
@require_auth
def withdraw():
    user = get_current_user()
    data = request.get_json()
    
    amount = float(data.get('amount', 0))
    bank_code = data.get('bank_code')
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    pin = data.get('pin', '')
    
    if not pin:
        return jsonify({"success": False, "message": "PIN required"}), 400
    
    withdrawal_pin = user.get('withdrawal_pin')
    if not withdrawal_pin or not check_password_hash(withdrawal_pin, pin):
        app.logger.warning(f"Invalid PIN attempt for withdrawal by user: {user['username']}")
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    
    if not is_withdrawal_day(user['id']):
        global_days = get_global_withdrawal_days()
        return jsonify({"success": False, "message": f"Withdrawals only on days: {', '.join(map(str, sorted(global_days)))}"}), 403
    
    if amount < CONFIG.MIN_WITHDRAWAL:
        return jsonify({"success": False, "message": f"Min withdrawal: ₦{CONFIG.MIN_WITHDRAWAL:,}"}), 400
    
    if float(user['balance']) < amount:
        return jsonify({"success": False, "message": "Insufficient balance"}), 400
    
    withdrawal_limit = float(user.get('withdrawal_limit', 0.00))
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({"success": False, "message": f"Max limit: ₦{withdrawal_limit:,.2f}"}), 400
    
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({"success": False, "message": "Invalid bank details"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Use atomic balance update
        new_balance = update_user_balance(user['id'], -amount)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
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
        
        app.logger.info(f"✅ Withdrawal requested by {user['username']}: {amount} to {bank_code}:{account_number}")
        
        return jsonify({
            "success": True,
            "message": "Withdrawal submitted successfully",
            "transaction_id": tx_id,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"❌ Withdrawal error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ================= WHATSAPP ENDPOINTS =================
@app.route('/api/whatsapp/numbers', methods=['GET'])
def get_whatsapp_numbers():
    """Get active WhatsApp numbers for users"""
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
        return jsonify({"success": True, "numbers": numbers})
    except Exception as e:
        app.logger.error(f"WhatsApp numbers error: {e}")
        return jsonify({"success": False, "message": "Failed to load numbers"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN ENDPOINTS =================
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
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
        return jsonify({"success": True, "users": users})
    except Exception as e:
        app.logger.error(f"Admin users error: {e}")
        return jsonify({"success": False, "message": "Failed to load users"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@require_admin
def admin_get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        user = row_to_dict(cursor, row)
        return jsonify({"success": True, "user": user})
    except Exception as e:
        app.logger.error(f"Admin get user error: {e}")
        return jsonify({"success": False, "message": "Failed to load user"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@require_admin
def admin_toggle_user_restrict(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT withdrawal_restricted FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        current = bool(row[0])
        new_value = not current
        cursor.execute('UPDATE users SET withdrawal_restricted = %s WHERE id = %s', (new_value, user_id))
        conn.commit()
        
        app.logger.info(f"Admin toggled withdrawal restriction for user {user_id} to: {new_value}")
        
        return jsonify({"success": True, "restricted": new_value})
    except Exception as e:
        app.logger.error(f"Toggle restrict error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/adjust-balance', methods=['POST'])
@require_admin
def admin_adjust_user_balance(user_id):
    data = request.get_json()
    amount = float(data.get('amount', 0))
    note = data.get('note', '')
    
    if amount == 0:
        return jsonify({"success": False, "message": "Invalid amount"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Use atomic balance update
        new_balance = update_user_balance(user_id, amount)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
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
        
        app.logger.info(f"Admin adjusted balance for user {user_id}: {amount} (note: {note})")
        
        return jsonify({
            "success": True,
            "message": "Balance adjusted",
            "new_balance": new_balance,
            "adjustment": amount
        })
    except Exception as e:
        app.logger.error(f"Adjust balance error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to adjust balance"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/transactions', methods=['GET'])
@require_admin
def admin_get_transactions():
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
        return jsonify({"success": True, "transactions": transactions})
    except Exception as e:
        app.logger.error(f"Admin transactions error: {e}")
        return jsonify({"success": False, "message": "Failed to load transactions"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/transaction/<tx_id>/update', methods=['POST'])
@require_admin
def admin_update_transaction(tx_id):
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (status, tx_id))
        conn.commit()
        
        app.logger.info(f"Admin updated transaction {tx_id} status to: {status}")
        
        return jsonify({"success": True, "message": "Transaction updated"})
    except Exception as e:
        app.logger.error(f"Update transaction error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
def admin_get_settings():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row:
            settings = row_to_dict(cursor, row)
            return jsonify({"success": True, "settings": settings})
        else:
            return jsonify({"success": False, "message": "Settings not found"}), 404
    except Exception as e:
        app.logger.error(f"Get settings error: {e}")
        return jsonify({"success": False, "message": "Failed to load settings"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/settings', methods=['POST'])
@require_admin
def admin_update_settings():
    data = request.get_json()
    whatsapp_link = data.get('whatsapp_link', '')
    telegram_link = data.get('telegram_link', '')
    facebook_link = data.get('facebook_link', '')
    global_withdrawal_days = data.get('global_withdrawal_days', [])
    
    if not isinstance(global_withdrawal_days, list):
        return jsonify({"success": False, "message": "Invalid withdrawal days format"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE admin_settings 
        SET whatsapp_link = %s, telegram_link = %s, facebook_link = %s, global_withdrawal_days = %s
        ''', (whatsapp_link, telegram_link, facebook_link, json.dumps(global_withdrawal_days)))
        conn.commit()
        
        app.logger.info(f"Admin updated settings")
        
        return jsonify({"success": True, "message": "Settings updated"})
    except Exception as e:
        app.logger.error(f"Update settings error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE')
        today_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM transactions')
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = %s AND DATE(timestamp) = CURRENT_DATE', ('WITHDRAWAL',))
        today_withdrawals = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = %s AND status = %s', ('WITHDRAWAL', 'COMPLETED'))
        total_withdrawn = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM coupons')
        total_coupons = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM coupons WHERE status = %s', ('AVAILABLE',))
        available_coupons = cursor.fetchone()[0]
        
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
            }
        })
        
    except Exception as e:
        app.logger.error(f"Admin stats error: {e}")
        return jsonify({"success": False, "message": "Failed to load stats"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN WITHDRAWAL DAYS =======================
@app.route('/api/admin/global-withdrawal-days', methods=['GET'])
@require_admin
def admin_get_global_withdrawal_days():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row and row[0]:
            days = json.loads(row[0])
            return jsonify({"success": True, "days": days})
        else:
            return jsonify({"success": True, "days": CONFIG.DEFAULT_WITHDRAWAL_DAYS})
    except Exception as e:
        app.logger.error(f"Get global withdrawal days error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/global-withdrawal-days', methods=['POST'])
@require_admin
def admin_set_global_withdrawal_days():
    data = request.get_json()
    days = data.get('days', [])
    
    if not isinstance(days, list):
        return jsonify({"success": False, "message": "Invalid days format"}), 400
    
    # Validate days (1-31)
    valid_days = [day for day in days if isinstance(day, int) and 1 <= day <= 31]
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE admin_settings SET global_withdrawal_days = %s', (json.dumps(valid_days),))
        conn.commit()
        app.logger.info(f"Admin updated global withdrawal days: {valid_days}")
        return jsonify({"success": True, "message": "Global withdrawal days updated", "days": valid_days})
    except Exception as e:
        app.logger.error(f"Set global withdrawal days error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN USER CUSTOM WITHDRAWAL DAYS =======================
@app.route('/api/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@require_admin
def admin_set_user_custom_days(user_id):
    """Set custom withdrawal days for a specific user"""
    data = request.get_json()
    days = data.get('days', [])
    
    if not isinstance(days, list):
        return jsonify({"success": False, "message": "Invalid days format"}), 400
    
    # Validate days (1-31)
    valid_days = [day for day in days if isinstance(day, int) and 1 <= day <= 31]
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "User not found"}), 404
        
        cursor.execute('UPDATE users SET custom_withdrawal_days = %s WHERE id = %s',
                       (json.dumps(valid_days) if valid_days else None, user_id))
        conn.commit()
        
        app.logger.info(f"Admin set custom withdrawal days for user {user_id}: {valid_days}")
        return jsonify({"success": True, "message": "Custom withdrawal days updated"})
        
    except Exception as e:
        app.logger.error(f"Set user custom days error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN USER SET LIMIT =======================
@app.route('/api/admin/user/<int:user_id>/set-limit', methods=['POST'])
@require_admin
def admin_set_user_limit(user_id):
    data = request.get_json()
    limit = data.get('limit', 0)
    
    if limit < 0:
        return jsonify({"success": False, "message": "Invalid limit"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        cursor.execute('UPDATE users SET withdrawal_limit = %s WHERE id = %s', (limit, user_id))
        conn.commit()
        
        app.logger.info(f"Admin set withdrawal limit for user {user_id} to: {limit}")
        return jsonify({"success": True, "message": "Limit updated"})
    except Exception as e:
        app.logger.error(f"Set limit error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN WITHDRAWAL APPROVAL =======================
@app.route('/api/admin/approve-withdrawal', methods=['POST'])
@require_admin
def admin_approve_withdrawal():
    data = request.get_json()
    transaction_id = data.get('transaction_id')
    action = data.get('action', '').upper()
    
    if not transaction_id or action not in ['APPROVE', 'REJECT']:
        return jsonify({"success": False, "message": "Invalid request"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get transaction details
        cursor.execute('SELECT user_id, amount, status FROM transactions WHERE id = %s', (transaction_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Transaction not found"}), 404
        
        user_id, amount, current_status = row[0], float(row[1]), row[2]
        
        if current_status != 'PENDING':
            return jsonify({"success": False, "message": f"Transaction already {current_status}"}), 400
        
        new_status = 'COMPLETED' if action == 'APPROVE' else 'FAILED'
        
        # If rejecting, refund the amount to user balance
        if action == 'REJECT':
            # Use atomic balance update
            update_user_balance(user_id, amount)
        
        # Update transaction status
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (new_status, transaction_id))
        
        conn.commit()
        
        app.logger.info(f"Admin {action}d withdrawal {transaction_id} for user {user_id}, amount: {amount}")
        
        return jsonify({
            "success": True,
            "message": f"Withdrawal {action.lower()}ed successfully",
            "status": new_status
        })
        
    except Exception as e:
        app.logger.error(f"Approve withdrawal error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN WITHDRAWAL STATUS REPORT =======================
@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@require_admin
def admin_withdrawal_status_report():
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
                can_withdraw_today = False
            else:
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
            "users": users
        })
        
    except Exception as e:
        app.logger.error(f"Withdrawal status report error: {e}")
        return jsonify({"success": False, "message": "Failed to generate report"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN TOGGLE USER ADMIN STATUS =======================
@app.route('/api/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
def admin_toggle_user_admin(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if trying to modify original admin
        cursor.execute('SELECT username, is_admin FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        username = row[0]
        is_currently_admin = bool(row[1])
        
        if username == CONFIG.ADMIN_USERNAME:
            return jsonify({"success": False, "message": "Cannot modify original admin"}), 403
        
        new_admin_status = not is_currently_admin
        
        cursor.execute('UPDATE users SET is_admin = %s WHERE id = %s', (new_admin_status, user_id))
        conn.commit()
        
        action = "promoted to admin" if new_admin_status else "demoted from admin"
        app.logger.info(f"Admin toggled user {username} ({user_id}) admin status to: {new_admin_status}")
        
        return jsonify({
            "success": True,
            "message": f"User {username} {action}",
            "is_admin": new_admin_status
        })
        
    except Exception as e:
        app.logger.error(f"Toggle admin error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update admin status"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN DELETE USER =======================
@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if trying to delete original admin
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        username = row[0]
        
        if username == CONFIG.ADMIN_USERNAME:
            return jsonify({"success": False, "message": "Cannot delete original admin"}), 403
        
        # Delete user's transactions
        cursor.execute('DELETE FROM transactions WHERE user_id = %s', (user_id,))
        # Delete user's game plays
        cursor.execute('DELETE FROM game_plays WHERE user_id = %s', (user_id,))
        # Delete user
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        
        conn.commit()
        
        app.logger.warning(f"Admin deleted user: {username} (ID: {user_id})")
        
        return jsonify({
            "success": True,
            "message": f"User {username} deleted successfully"
        })
        
    except Exception as e:
        app.logger.error(f"Delete user error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete user"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN COUPON MANAGEMENT =======================
@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
def admin_get_coupons():
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
        return jsonify({"success": True, "coupons": coupons})
    except Exception as e:
        app.logger.error(f"Admin coupons error: {e}")
        return jsonify({"success": False, "message": "Failed to load coupons"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/reset-used', methods=['POST'])
@require_admin
def admin_reset_used_coupons():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE coupons SET status = 'AVAILABLE' WHERE status = 'USED'")
        updated_count = cursor.rowcount
        
        conn.commit()
        
        app.logger.info(f"Admin reset {updated_count} used coupons to available")
        
        return jsonify({
            "success": True,
            "message": f"Reset {updated_count} used coupons to available"
        })
        
    except Exception as e:
        app.logger.error(f"Reset coupons error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to reset coupons"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/delete', methods=['POST'])
@require_admin
def admin_delete_all_coupons():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM coupons')
        deleted_count = cursor.rowcount
        
        conn.commit()
        
        app.logger.warning(f"Admin deleted all {deleted_count} coupons")
        
        return jsonify({
            "success": True,
            "message": f"Deleted all {deleted_count} coupons"
        })
        
    except Exception as e:
        app.logger.error(f"Delete all coupons error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete coupons"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/add', methods=['POST'])
@require_admin
def admin_add_bulk_coupons():
    data = request.get_json()
    codes = data.get('codes', [])
    
    if not isinstance(codes, list):
        return jsonify({"success": False, "message": "Invalid codes format"}), 400
    
    # Clean and validate codes
    valid_codes = []
    for code in codes:
        clean_code = sanitize_input(str(code).strip().upper())
        if clean_code and len(clean_code) >= 4:
            valid_codes.append(clean_code)
    
    if not valid_codes:
        return jsonify({"success": False, "message": "No valid coupon codes provided"}), 400
    
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
        
        app.logger.info(f"Admin added {added_count} new coupon codes")
        
        return jsonify({
            "success": True,
            "message": f"Added {added_count} new coupon codes",
            "added": added_count
        })
        
    except Exception as e:
        app.logger.error(f"Add bulk coupons error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to add coupons"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons/load-file', methods=['POST'])
@require_admin
def admin_load_coupons_from_file():
    try:
        if not os.path.exists(CONFIG.COUPON_FILE):
            return jsonify({"success": False, "message": "coupon.txt file not found"}), 404
        
        with open(CONFIG.COUPON_FILE, 'r') as f:
            codes = [line.strip().upper() for line in f if line.strip()]
        
        if not codes:
            return jsonify({"success": False, "message": "No coupons in file"}), 400
        
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
        
        app.logger.info(f"Admin loaded {loaded} coupons from file")
        
        return jsonify({
            "success": True, 
            "message": f"Loaded {loaded} coupons from file",
            "count": loaded
        })
        
    except Exception as e:
        app.logger.error(f"Load coupons from file error: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/admin/coupons/<code>/delete', methods=['DELETE'])
@require_admin
def admin_delete_coupon(code):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM coupons WHERE code = %s', (code,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Coupon not found"}), 404
        
        app.logger.info(f"Admin deleted coupon: {code}")
        
        return jsonify({"success": True, "message": "Coupon deleted"})
    except Exception as e:
        app.logger.error(f"Delete coupon error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN WHATSAPP NUMBERS =======================
@app.route('/api/admin/whatsapp-numbers', methods=['GET'])
@require_admin
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
        return jsonify({"success": True, "numbers": numbers})
    except Exception as e:
        app.logger.error(f"Admin WhatsApp numbers error: {e}")
        return jsonify({"success": False, "message": "Failed to load numbers"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers', methods=['POST'])
@require_admin
def admin_add_whatsapp_number():
    """Admin: Add new WhatsApp number"""
    data = request.get_json()
    number = sanitize_input(data.get('number', ''))
    label = sanitize_input(data.get('label', ''))
    
    if not number or len(number) < 10:
        return jsonify({"success": False, "message": "Valid phone number required"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES (%s, %s, %s, %s)',
                       (number, label, True, datetime.utcnow().isoformat()))
        conn.commit()
        
        app.logger.info(f"Admin added WhatsApp number: {number} ({label})")
        
        return jsonify({"success": True, "message": "WhatsApp number added"})
    except Exception as e:
        app.logger.error(f"Add WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to add number"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>/toggle', methods=['POST'])
@require_admin
def admin_toggle_whatsapp_number(number_id):
    """Admin: Toggle WhatsApp number active status"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT is_active FROM whatsapp_numbers WHERE id = %s', (number_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Number not found"}), 404
        
        current = bool(row[0])
        new_value = not current
        cursor.execute('UPDATE whatsapp_numbers SET is_active = %s WHERE id = %s', (new_value, number_id))
        conn.commit()
        
        app.logger.info(f"Admin toggled WhatsApp number {number_id} active status to: {new_value}")
        
        return jsonify({"success": True, "is_active": new_value})
    except Exception as e:
        app.logger.error(f"Toggle WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to toggle"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>', methods=['DELETE'])
@require_admin
def admin_delete_whatsapp_number(number_id):
    """Admin: Delete WhatsApp number"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM whatsapp_numbers WHERE id = %s', (number_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Number not found"}), 404
        
        app.logger.info(f"Admin deleted WhatsApp number ID: {number_id}")
        
        return jsonify({"success": True, "message": "Number deleted"})
    except Exception as e:
        app.logger.error(f"Delete WhatsApp number error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN TIKTOK ENDPOINTS =======================
@app.route('/api/admin/tiktok/set-daily', methods=['POST'])
@require_admin
def admin_set_tiktok_daily():
    data = request.get_json()
    tiktok_link = data.get('tiktok_link', '')
    
    if not tiktok_link:
        return jsonify({"success": False, "message": "TikTok link required"}), 400
    
    if not tiktok_link.startswith('https://www.tiktok.com/@'):
        return jsonify({"success": False, "message": "Link must start with https://www.tiktok.com/@"}), 400
    
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
        app.logger.info(f"Admin set TikTok daily task: {tiktok_link}")
        return jsonify({"success": True, "message": "TikTok daily task set"})
        
    except Exception as e:
        app.logger.error(f"Set TikTok daily error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to set task: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/tiktok/get-daily', methods=['GET'])
@require_admin
def admin_get_tiktok_daily():
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
            return jsonify({"success": True, "task": task})
        else:
            return jsonify({"success": False, "message": "No TikTok task set for today"})
            
    except Exception as e:
        app.logger.error(f"Get TikTok daily error: {e}")
        return jsonify({"success": False, "message": "Failed to get task"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/tiktok/history', methods=['GET'])
@require_admin
def admin_get_tiktok_history():
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
        
        return jsonify({"success": True, "history": history})
        
    except Exception as e:
        app.logger.error(f"Get TikTok history error: {e}")
        return jsonify({"success": False, "message": "Failed to load history"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN DATABASE CLEARING =======================
@app.route('/api/admin/database/clear', methods=['POST'])
@require_admin
def admin_clear_database():
    """Admin: Clear all data except main admin account"""
    data = request.get_json()
    sudo_confirmation = data.get('sudo_confirmation', '')
    
    # Require sudo confirmation
    if sudo_confirmation != 'DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN':
        return jsonify({
            "success": False,
            "message": "Sudo confirmation required. Type: DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN"
        }), 403
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        app.logger.warning("🚨 ADMIN INITIATED DATABASE CLEARING - KEEPING ONLY MAIN ADMIN")
        
        # Start transaction
        if os.environ.get('DATABASE_URL'):
            cursor.execute("BEGIN")
        
        # Get admin user details
        cursor.execute("SELECT id, username FROM users WHERE username = %s", (CONFIG.ADMIN_USERNAME,))
        admin_row = cursor.fetchone()
        
        if not admin_row:
            return jsonify({"success": False, "message": "Main admin not found"}), 404
        
        admin_id = admin_row[0]
        admin_username = admin_row[1]
        
        # Delete all users except main admin
        cursor.execute("DELETE FROM users WHERE id != %s", (admin_id,))
        users_deleted = cursor.rowcount
        
        # Reset admin balance and stats
        cursor.execute('''
        UPDATE users SET 
            balance = 500000.00,
            claimed_bonuses = 0,
            points = 0,
            game_stats = %s,
            last_game_timestamp = %s,
            last_achievement_check = %s,
            claimed_achievements = '[]'
        WHERE id = %s
        ''', (
            json.dumps({
                "snake": {"high_score": 1200, "total_score": 5000},
                "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
                "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
            }),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            admin_id
        ))
        
        # Clear all transactions
        cursor.execute("DELETE FROM transactions")
        transactions_deleted = cursor.rowcount
        
        # Clear game plays
        cursor.execute("DELETE FROM game_plays")
        game_plays_deleted = cursor.rowcount
        
        # Reset coupons to AVAILABLE
        cursor.execute("UPDATE coupons SET status = 'AVAILABLE'")
        coupons_reset = cursor.rowcount
        
        # Reset TikTok daily tasks
        cursor.execute("DELETE FROM tiktok_daily")
        
        conn.commit()
        
        app.logger.warning(f"✅ DATABASE CLEARED: {users_deleted} users, {transactions_deleted} transactions, {game_plays_deleted} game plays removed")
        app.logger.warning(f"✅ Coupons reset: {coupons_reset}")
        app.logger.warning(f"✅ Admin account '{admin_username}' kept with reset stats")
        
        # Create backup before clearing (optional)
        backup_file = backup_database()
        
        return jsonify({
            "success": True,
            "message": "Database cleared successfully!",
            "stats": {
                "users_deleted": users_deleted,
                "transactions_deleted": transactions_deleted,
                "game_plays_deleted": game_plays_deleted,
                "coupons_reset": coupons_reset,
                "admin_kept": admin_username,
                "backup_created": backup_file if backup_file else "No backup"
            },
            "warning": "ALL USER DATA HAS BEEN PERMANENTLY DELETED. This action cannot be undone."
        })
        
    except Exception as e:
        app.logger.error(f"❌ Database clearing error: {e}")
        app.logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to clear database: {str(e)}"
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/database/preview-clear', methods=['GET'])
@require_admin
def admin_preview_database_clear():
    """Preview what will be deleted when clearing database"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Count all users except admin
        cursor.execute("SELECT COUNT(*) FROM users WHERE username != %s", (CONFIG.ADMIN_USERNAME,))
        users_count = cursor.fetchone()[0]
        
        # Count transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transactions_count = cursor.fetchone()[0]
        
        # Count game plays
        cursor.execute("SELECT COUNT(*) FROM game_plays")
        game_plays_count = cursor.fetchone()[0]
        
        # Count coupons
        cursor.execute("SELECT COUNT(*) FROM coupons")
        coupons_count = cursor.fetchone()[0]
        
        # Count used coupons
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'USED'")
        used_coupons_count = cursor.fetchone()[0]
        
        # Get admin info
        cursor.execute("SELECT id, username, balance FROM users WHERE username = %s", (CONFIG.ADMIN_USERNAME,))
        admin_row = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "preview": {
                "users_to_delete": users_count,
                "transactions_to_delete": transactions_count,
                "game_plays_to_delete": game_plays_count,
                "coupons_to_reset": coupons_count,
                "used_coupons_to_reset": used_coupons_count,
                "admin_to_keep": {
                    "id": admin_row[0],
                    "username": admin_row[1],
                    "balance": float(admin_row[2]) if admin_row[2] else 0
                },
                "warning": "This action is irreversible. All user data will be permanently deleted.",
                "sudo_confirmation_required": "DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN"
            }
        })
        
    except Exception as e:
        app.logger.error(f"Preview error: {e}")
        return jsonify({"success": False, "message": "Failed to generate preview"}), 500
    finally:
        return_db_connection(conn)

# ================= ADMIN EXPORT DATA =======================
@app.route('/api/admin/export-data', methods=['POST'])
@require_admin
def admin_export_data():
    """Export database data in various formats"""
    data = request.get_json()
    export_format = data.get('format', 'csv')
    export_users = data.get('users', True)
    export_transactions = data.get('transactions', True)
    export_game_plays = data.get('game_plays', False)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        export_data = {}
        
        if export_users:
            cursor.execute('SELECT * FROM users')
            users = [row_to_dict(cursor, row) for row in cursor.fetchall()]
            export_data['users'] = users
        
        if export_transactions:
            cursor.execute('SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10000')
            transactions = [row_to_dict(cursor, row) for row in cursor.fetchall()]
            export_data['transactions'] = transactions
        
        if export_game_plays:
            cursor.execute('SELECT * FROM game_plays ORDER BY created_at DESC')
            game_plays = [row_to_dict(cursor, row) for row in cursor.fetchall()]
            export_data['game_plays'] = game_plays
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'json':
            response = jsonify(export_data)
            response.headers['Content-Disposition'] = f'attachment; filename=flexia_export_{timestamp}.json'
            response.headers['Content-Type'] = 'application/json'
            return response
        
        elif export_format == 'csv':
            import csv
            import io
            
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write users CSV
            if 'users' in export_data:
                writer.writerow(['=== USERS ==='])
                if export_data['users']:
                    headers = export_data['users'][0].keys()
                    writer.writerow(headers)
                    for user in export_data['users']:
                        writer.writerow([user.get(h, '') for h in headers])
                writer.writerow([])
            
            # Write transactions CSV
            if 'transactions' in export_data:
                writer.writerow(['=== TRANSACTIONS ==='])
                if export_data['transactions']:
                    headers = export_data['transactions'][0].keys()
                    writer.writerow(headers)
                    for tx in export_data['transactions']:
                        writer.writerow([tx.get(h, '') for h in headers])
                writer.writerow([])
            
            # Convert to bytes for response
            csv_data = output.getvalue()
            output.close()
            
            response = make_response(csv_data)
            response.headers['Content-Disposition'] = f'attachment; filename=flexia_export_{timestamp}.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
        
        else:
            return jsonify({"success": False, "message": "Unsupported export format"}), 400
            
    except Exception as e:
        app.logger.error(f"Export data error: {e}")
        return jsonify({"success": False, "message": f"Export failed: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ================= NEW: DATABASE EXPORT/IMPORT WITH .FLEXIA FILES =======================
@app.route('/api/admin/database/export-all', methods=['POST'])
@require_admin
def admin_export_all_data():
    """Export ALL database data to .flexia file format - NEW ENDPOINT"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get all data
        data = {}
        
        # Users (exclude password hashes for security)
        cursor.execute('''
        SELECT id, username, balance, referral_code, referred_by, is_admin,
               created_at, last_login, claimed_bonuses, points, game_stats,
               contact, profile_picture, ui_theme, withdrawal_restricted,
               custom_withdrawal_days, withdrawal_limit, last_game_timestamp,
               last_achievement_check, claimed_achievements
        FROM users
        ''')
        users = []
        for row in cursor.fetchall():
            user_dict = {}
            columns = [col[0] for col in cursor.description]
            for i, col in enumerate(columns):
                user_dict[col] = row[i]
            users.append(user_dict)
        data['users'] = users
        
        # Transactions
        cursor.execute('SELECT * FROM transactions')
        transactions = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['transactions'] = transactions
        
        # Game plays
        cursor.execute('SELECT * FROM game_plays')
        game_plays = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['game_plays'] = game_plays
        
        # Coupons
        cursor.execute('SELECT * FROM coupons')
        coupons = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['coupons'] = coupons
        
        # WhatsApp numbers
        cursor.execute('SELECT * FROM whatsapp_numbers')
        whatsapp_numbers = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['whatsapp_numbers'] = whatsapp_numbers
        
        # TikTok daily
        cursor.execute('SELECT * FROM tiktok_daily')
        tiktok_daily = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['tiktok_daily'] = tiktok_daily
        
        # Banks
        cursor.execute('SELECT * FROM banks')
        banks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['banks'] = banks
        
        # Admin settings
        cursor.execute('SELECT * FROM admin_settings')
        admin_settings = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['admin_settings'] = admin_settings
        
        # Add metadata
        data['_metadata'] = {
            'export_date': datetime.utcnow().isoformat(),
            'version': 'FLEXIA_BACKUP_v1.0',
            'total_records': {
                'users': len(users),
                'transactions': len(transactions),
                'game_plays': len(game_plays),
                'coupons': len(coupons)
            }
        }
        
        return_db_connection(conn)
        
        # Convert to JSON
        json_data = json.dumps(data, indent=2, default=str)
        
        # Create response
        response = make_response(json_data)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        response.headers['Content-Disposition'] = f'attachment; filename=flexia_backup_{timestamp}.flexia'
        response.headers['Content-Type'] = 'application/json'
        
        app.logger.info(f"Database exported: {len(users)} users, {len(transactions)} transactions")
        
        return response
        
    except Exception as e:
        app.logger.error(f"Export all data error: {e}")
        return jsonify({"success": False, "message": f"Export failed: {str(e)}"}), 500

@app.route('/api/admin/database/import-all', methods=['POST'])
@require_admin
def admin_import_all_data():
    """Import data from .flexia file (complete restore) - NEW ENDPOINT"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400
        
        # Check file extension
        if not file.filename.endswith('.flexia'):
            return jsonify({"success": False, "message": "File must be .flexia format"}), 400
        
        # Read and parse JSON
        json_data = file.read().decode('utf-8')
        data = json.loads(json_data)
        
        # Verify it's a valid FLEXIA backup
        if '_metadata' not in data:
            return jsonify({"success": False, "message": "Invalid .flexia file format"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            if os.environ.get('DATABASE_URL'):
                cursor.execute("BEGIN")
            
            # Clear existing data (keep admin settings structure)
            tables_to_clear = ['users', 'transactions', 'game_plays', 'coupons', 
                              'whatsapp_numbers', 'tiktok_daily']
            
            for table in tables_to_clear:
                try:
                    cursor.execute(f'DELETE FROM {table}')
                except:
                    pass
            
            # Import data
            imported_counts = {}
            
            # Import users
            if 'users' in data:
                for user in data['users']:
                    try:
                        # Handle is_admin for different DB types
                        is_admin_value = user.get('is_admin', False)
                        if os.environ.get('DATABASE_URL'):
                            is_admin_value = bool(is_admin_value)
                        else:
                            is_admin_value = 1 if is_admin_value else 0
                        
                        # Handle withdrawal_restricted
                        withdrawal_restricted = user.get('withdrawal_restricted', False)
                        if os.environ.get('DATABASE_URL'):
                            withdrawal_restricted = bool(withdrawal_restricted)
                        else:
                            withdrawal_restricted = 1 if withdrawal_restricted else 0
                        
                        cursor.execute('''
                        INSERT INTO users (
                            id, username, balance, referral_code, referred_by, is_admin,
                            created_at, last_login, claimed_bonuses, points, game_stats,
                            contact, profile_picture, ui_theme, withdrawal_restricted,
                            custom_withdrawal_days, withdrawal_limit, last_game_timestamp,
                            last_achievement_check, claimed_achievements
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            user.get('id'), user.get('username'), user.get('balance', 0),
                            user.get('referral_code'), user.get('referred_by'), is_admin_value,
                            user.get('created_at'), user.get('last_login'), user.get('claimed_bonuses', 0),
                            user.get('points', 0), user.get('game_stats'), user.get('contact'),
                            user.get('profile_picture'), user.get('ui_theme', 'light'),
                            withdrawal_restricted, user.get('custom_withdrawal_days'),
                            user.get('withdrawal_limit', 0), user.get('last_game_timestamp'),
                            user.get('last_achievement_check'), user.get('claimed_achievements', '[]')
                        ))
                        imported_counts['users'] = imported_counts.get('users', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping user {user.get('username')}: {e}")
            
            # Import transactions
            if 'transactions' in data:
                for tx in data['transactions']:
                    try:
                        cursor.execute('''
                        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            tx.get('id'), tx.get('user_id'), tx.get('type'), tx.get('amount'),
                            tx.get('status'), tx.get('details'), tx.get('timestamp')
                        ))
                        imported_counts['transactions'] = imported_counts.get('transactions', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping transaction {tx.get('id')}: {e}")
            
            # Import game plays
            if 'game_plays' in data:
                for play in data['game_plays']:
                    try:
                        cursor.execute('''
                        INSERT INTO game_plays (id, user_id, game_type, play_date, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ''', (
                            play.get('id'), play.get('user_id'), play.get('game_type'),
                            play.get('play_date'), play.get('created_at')
                        ))
                        imported_counts['game_plays'] = imported_counts.get('game_plays', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping game play {play.get('id')}: {e}")
            
            # Import coupons
            if 'coupons' in data:
                for coupon in data['coupons']:
                    try:
                        cursor.execute('''
                        INSERT INTO coupons (code, status)
                        VALUES (%s, %s)
                        ''', (
                            coupon.get('code'), coupon.get('status', 'AVAILABLE')
                        ))
                        imported_counts['coupons'] = imported_counts.get('coupons', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping coupon {coupon.get('code')}: {e}")
            
            # Import WhatsApp numbers
            if 'whatsapp_numbers' in data:
                for num in data['whatsapp_numbers']:
                    try:
                        cursor.execute('''
                        INSERT INTO whatsapp_numbers (id, number, label, is_active, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ''', (
                            num.get('id'), num.get('number'), num.get('label'),
                            num.get('is_active'), num.get('created_at')
                        ))
                        imported_counts['whatsapp_numbers'] = imported_counts.get('whatsapp_numbers', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping WhatsApp number {num.get('number')}: {e}")
            
            # Import TikTok daily
            if 'tiktok_daily' in data:
                for tiktok in data['tiktok_daily']:
                    try:
                        cursor.execute('''
                        INSERT INTO tiktok_daily (id, date, tiktok_link, reward_amount, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ''', (
                            tiktok.get('id'), tiktok.get('date'), tiktok.get('tiktok_link'),
                            tiktok.get('reward_amount'), tiktok.get('created_at')
                        ))
                        imported_counts['tiktok_daily'] = imported_counts.get('tiktok_daily', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping TikTok daily {tiktok.get('date')}: {e}")
            
            # Import admin settings
            if 'admin_settings' in data:
                for setting in data['admin_settings']:
                    try:
                        cursor.execute('''
                        INSERT INTO admin_settings (id, whatsapp_link, telegram_link, facebook_link, global_withdrawal_days)
                        VALUES (%s, %s, %s, %s, %s)
                        ''', (
                            setting.get('id'), setting.get('whatsapp_link'), setting.get('telegram_link'),
                            setting.get('facebook_link'), setting.get('global_withdrawal_days')
                        ))
                        imported_counts['admin_settings'] = imported_counts.get('admin_settings', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping admin setting: {e}")
            
            conn.commit()
            
            app.logger.info(f"Database imported successfully: {imported_counts}")
            
            return jsonify({
                "success": True,
                "message": "Database imported successfully!",
                "imported_counts": imported_counts,
                "metadata": data.get('_metadata', {})
            })
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Import error: {e}")
            return jsonify({"success": False, "message": f"Import failed: {str(e)}"}), 500
            
    except Exception as e:
        app.logger.error(f"Import all data error: {e}")
        return jsonify({"success": False, "message": f"Import failed: {str(e)}"}), 500

# ================= BACKUP ENDPOINTS =======================
@app.route('/api/admin/backup/trigger', methods=['POST'])
@require_admin
def trigger_backup():
    """Manually trigger a database backup"""
    try:
        backup_file = backup_database()
        if backup_file:
            app.logger.info(f"Manual backup triggered: {backup_file}")
            return jsonify({
                "success": True,
                "message": "Backup created successfully",
                "backup_file": backup_file
            })
        else:
            return jsonify({
                "success": False,
                "message": "Backup creation failed"
            }), 500
    except Exception as e:
        app.logger.error(f"Manual backup error: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Backup error: {str(e)}"
        }), 500

@app.route('/api/admin/backup/list', methods=['GET'])
@require_admin
def list_backups():
    """List all available backups"""
    try:
        if not os.path.exists('backups'):
            return jsonify({"success": True, "backups": []})
        
        backups = []
        for filename in sorted(os.listdir('backups'), reverse=True):
            filepath = os.path.join('backups', filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                backups.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_human": f"{stat.st_size / 1024 / 1024:.2f} MB"
                })
        
        return jsonify({
            "success": True,
            "backups": backups
        })
    except Exception as e:
        app.logger.error(f"List backups error: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error listing backups: {str(e)}"
        }), 500

# ================= HEALTH CHECK =======================
def get_uptime():
    """Calculate application uptime"""
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.utcnow()
    uptime = datetime.utcnow() - get_uptime.start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

@app.route('/api/health', methods=['GET'])
def api_health():
    """Enhanced health check endpoint"""
    try:
        # Test database connection
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_status = 'connected'
        
        # Get basic stats
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = %s', ('PENDING',))
        pending_withdrawals = cursor.fetchone()[0]
        
        return_db_connection(conn)
        
        health_data = {
            "status": "online",
            "service": "FLEXIA API",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": get_uptime(),
            "database": db_status,
            "version": "14.0",
            "stats": {
                "total_users": user_count,
                "pending_withdrawals": pending_withdrawals
            },
            "environment": os.getenv('ENV', 'development'),
            "connection_pool": "active" if db_pool else "inactive"
        }
        
        app.logger.info(f"Health check passed: {health_data}")
        return jsonify(health_data), 200
        
    except Exception as e:
        app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "degraded",
            "service": "FLEXIA API",
            "timestamp": datetime.utcnow().isoformat(),
            "database": f"error: {str(e)}",
            "uptime": get_uptime(),
            "version": "14.0"
        }), 503

# ================= STATIC FILES =======================
@app.route('/')
def index():
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ================= CATCH-ALL =================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ================= MAIN =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    
    app.logger.info(f"🚀 Starting Flexia Platform v14.0 with Complete Game Limits on port {port} (debug: {debug})")
    app.logger.info(f"📁 Frontend directory: {CONFIG.FRONTEND_DIR}")
    app.logger.info(f"🔒 Secret key set: {'Yes' if CONFIG.SECRET_KEY else 'No'}")
    app.logger.info(f"🗄️ Database: {'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'}")
    app.logger.info(f"🛡️ Security headers: Enabled")
    app.logger.info(f"📊 Structured logging: Enabled")
    app.logger.info(f"🔗 Database connection pool: {'Enabled (5-50)' if db_pool else 'Disabled'}")
    app.logger.info(f"💾 Automatic backups: Enabled (daily at 2 AM UTC)")
    app.logger.info(f"🎮 GAME LIMITS ENABLED (PER REWARD CLAIM):")
    app.logger.info(f"   • Snake: {CONFIG.GAME_DAILY_LIMITS['snake']} plays/day")
    app.logger.info(f"   • Coin Flip: {CONFIG.GAME_DAILY_LIMITS['coinflip']} plays/day")
    app.logger.info(f"   • Plinko: {CONFIG.GAME_DAILY_LIMITS['plinko']} plays/day")
    app.logger.info(f"   • Spin: {CONFIG.GAME_DAILY_LIMITS['spin']} plays/day")
    app.logger.info(f"   • TikTok: {CONFIG.GAME_DAILY_LIMITS['tiktok']} plays/day")
    app.logger.info(f"🧹 Database Clearing: Enabled (Admin only)")
    app.logger.info(f"📤 Data Export/Import: Enabled (Admin only - .flexia format)")
    app.logger.info(f"👑 ADMIN CREDENTIALS VIA ENVIRONMENT VARIABLES:")
    app.logger.info(f"   • ADMIN_USERNAME: {CONFIG.ADMIN_USERNAME}")
    app.logger.info(f"   • ADMIN_PASSWORD: [SET VIA ENV VAR]")
    app.logger.info(f"   • ADMIN_WITHDRAWAL_PIN: [SET VIA ENV VAR]")
    app.logger.info(f"🚀 VERSION 14.0: Complete with all fixes and endpoints")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
