# backend/app.py - COMPLETE PRODUCTION VERSION v17.2
# FLEXIA Platform - FULL INTEGRATION WITH PAYSTACK, BREVO API, SESSION MANAGEMENT
# GEVENT ASYNC - HANDLES UNLIMITED SIMULTANEOUS USERS

from gevent import monkey
monkey.patch_all()

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

class Config:
    if os.environ.get('DATABASE_URL'):
        DB_URL = os.environ.get('DATABASE_URL')
    else:
        DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flexia.db')
    COUPON_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'flexia_secure_key_2024_change_in_production')
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 7500
    TIKTOK_REWARD = 150
    SNAKE_REWARD = 20
    COIN_FLIP_MIN_BET = 100
    PLINKO_MIN_BET = 100
    SESSION_DURATION_HOURS = 24
    DEFAULT_WITHDRAWAL_DAYS = [7, 14, 25, 30]
    MIN_COUPON_AMOUNT = int(os.environ.get('MIN_COUPON_AMOUNT', 8000))

    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'flexiaadmin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'passwordinnumber1')
    ADMIN_WITHDRAWAL_PIN = os.environ.get('ADMIN_WITHDRAWAL_PIN', '4567')

    GAME_DAILY_LIMITS = {
        'snake': 17,
        'coinflip': 12,
        'plinko': 12,
        'spin': 1,
        'tiktok': 3
    }

    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

CONFIG = Config()

app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', 'noreply@flexia.com')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'FLEXIA Platform')
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

# LIVE KEYS - For real coupon payments (users pay real money)
PAYSTACK_LIVE_SECRET_KEY = os.environ.get('PAYSTACK_LIVE_SECRET_KEY', '')
PAYSTACK_LIVE_PUBLIC_KEY = os.environ.get('PAYSTACK_LIVE_PUBLIC_KEY', '')

# TEST KEYS - For account verification (FREE, no cost)
PAYSTACK_TEST_SECRET_KEY = os.environ.get('PAYSTACK_TEST_SECRET_KEY', 'sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
PAYSTACK_TEST_PUBLIC_KEY = os.environ.get('PAYSTACK_TEST_PUBLIC_KEY', 'pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')

# DEFAULT KEYS - Fallback if specific keys not set (uses live for payments)
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', PAYSTACK_LIVE_SECRET_KEY or PAYSTACK_TEST_SECRET_KEY)
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', PAYSTACK_LIVE_PUBLIC_KEY or PAYSTACK_TEST_PUBLIC_KEY)

PAYSTACK_CALLBACK_URL = os.environ.get('PAYSTACK_CALLBACK_URL', 'https://yourdomain.com/api/paystack/callback')

def setup_logging():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    console_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(console_handler)
    werkzeug_logger.setLevel(logging.WARNING)
    if os.getenv('ENV') != 'production':
        try:
            if not os.path.exists('logs'):
                os.makedirs('logs')
            file_handler = RotatingFileHandler('logs/flexia.log', maxBytes=10485760, backupCount=10)
            file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            werkzeug_logger.addHandler(file_handler)
        except Exception:
            pass

try:
    setup_logging()
except Exception:
    pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.getenv('ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

@app.after_request
def enforce_json_response(response):
    if request.path.startswith('/api/'):
        if response.content_type != 'application/json':
            try:
                if response.status_code >= 400:
                    data = jsonify({"success": False, "message": "Server error occurred", "status_code": response.status_code})
                    return data
            except:
                pass
    return response

@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'404 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'500 error: {str(error)}')
    app.logger.error(traceback.format_exc())
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Internal server error"}), 500
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(400)
def bad_request_error(error):
    app.logger.warning(f'400 error: {str(error)}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Bad request"}), 400
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(401)
def unauthorized_error(error):
    app.logger.warning(f'401 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Authentication required"}), 401
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(403)
def forbidden_error(error):
    app.logger.warning(f'403 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Access forbidden"}), 403
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(429)
def too_many_requests_error(error):
    app.logger.warning(f'429 rate limit exceeded: {request.remote_addr}')
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(Exception)
def handle_all_exceptions(error):
    app.logger.error(f"Unhandled exception: {str(error)}")
    app.logger.error(traceback.format_exc())
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "Internal server error. Please try again.", "error_type": str(type(error).__name__)}), 500
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

def backup_database():
    if os.getenv('ENV') == 'production':
        app.logger.info('Production environment - skipping local file backup')
        return None
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if os.environ.get('DATABASE_URL'):
            app.logger.info('Creating PostgreSQL backup...')
            backup_file = f'backups/backup_flexia_{timestamp}.sql'
            if not os.path.exists('backups'):
                os.makedirs('backups')
            parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
            env = os.environ.copy()
            env['PGPASSWORD'] = parsed.password
            result = subprocess.run(['pg_dump', '-h', parsed.hostname, '-p', str(parsed.port), '-U', parsed.username, '-d', parsed.path[1:], '-f', backup_file, '--no-password'], env=env, capture_output=True, text=True)
            if result.returncode == 0:
                app.logger.info(f'PostgreSQL backup created: {backup_file}')
                return backup_file
            else:
                app.logger.error(f'PostgreSQL backup failed: {result.stderr}')
                return None
        else:
            app.logger.info('Creating SQLite backup...')
            backup_file = f'backups/backup_flexia_{timestamp}.db'
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

db_pool = None
db_pool_lock = threading.Lock()

def init_db_pool():
    global db_pool
    if os.environ.get('DATABASE_URL'):
        try:
            db_pool = ThreadedConnectionPool(4, 30, dsn=os.environ['DATABASE_URL'], connect_timeout=10)
            app.logger.info('Database connection pool initialized: 4-30 connections (thread-safe)')
        except Exception as e:
            app.logger.error(f'Failed to initialize connection pool: {str(e)}')
            db_pool = None
    else:
        app.logger.info('SQLite mode - connection pooling not needed')

def get_db():
    global db_pool
    if os.environ.get('DATABASE_URL') and db_pool:
        try:
            with db_pool_lock:
                conn = db_pool.getconn()
            if conn.closed:
                with db_pool_lock:
                    db_pool.putconn(conn)
                return get_db_direct()
            try:
                conn.cursor().execute('SELECT 1')
            except Exception:
                try:
                    with db_pool_lock:
                        db_pool.putconn(conn)
                except Exception:
                    pass
                return get_db_direct()
            try:
                conn.rollback()
            except Exception:
                pass
            conn.autocommit = False
            return conn
        except Exception as e:
            app.logger.error(f'Pool connection error: {str(e)} — falling back to direct')
            return get_db_direct()
    else:
        return get_db_direct()

def get_db_direct():
    if os.environ.get('DATABASE_URL'):
        try:
            parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
            conn = psycopg2.connect(host=parsed.hostname, port=parsed.port, user=parsed.username, password=parsed.password, database=parsed.path[1:], sslmode='require')
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
    global db_pool
    if os.environ.get('DATABASE_URL') and db_pool:
        try:
            try:
                conn.rollback()
            except Exception:
                pass
            with db_pool_lock:
                db_pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    else:
        try:
            conn.close()
        except Exception:
            pass

login_attempts = {}
register_attempts = {}
game_action_attempts = {}
_rate_limit_lock = threading.Lock()

def rate_limit(store, key, max_per_min=5):
    now = datetime.utcnow()
    with _rate_limit_lock:
        stale = [k for k, v in list(store.items()) if not v or v[-1] < now - timedelta(minutes=2)]
        for k in stale:
            del store[k]
        if key not in store:
            store[key] = []
        store[key] = [t for t in store[key] if t > now - timedelta(minutes=1)]
        if len(store[key]) >= max_per_min:
            app.logger.warning(f'Rate limit exceeded for {key}: {len(store[key])} attempts')
            return False
        store[key].append(now)
        return True

claim_locks = {}
claim_locks_mutex = threading.Lock()
claim_lock_timeout = 5

def acquire_claim_lock(user_id, game_type):
    key = f"{user_id}_{game_type}"
    now = time.time()
    with claim_locks_mutex:
        expired = [k for k, v in claim_locks.items() if now - v > claim_lock_timeout * 2]
        for k in expired:
            claim_locks.pop(k, None)
        if key in claim_locks:
            lock_time = claim_locks[key]
            if now - lock_time < claim_lock_timeout:
                return False
        claim_locks[key] = now
        return True

def release_claim_lock(user_id, game_type):
    key = f"{user_id}_{game_type}"
    with claim_locks_mutex:
        claim_locks.pop(key, None)

def create_session_token(user_id):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id, 'created_at': datetime.utcnow().isoformat()})

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

@app.route('/api/session/refresh', methods=['POST'])
@require_auth
def refresh_session():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    token = create_session_token(user['id'])
    resp = jsonify({"success": True, "message": "Session refreshed", "user": {"id": user['id'], "username": user['username'], "balance": float(user['balance']) if user['balance'] else 0.00}})
    secure_cookie = (os.getenv('ENV') == 'production')
    resp.set_cookie('session_token', token, httponly=True, secure=secure_cookie, samesite='Lax', max_age=86400)
    app.logger.info(f"Session refreshed for user: {user['username']}")
    return resp

@app.route('/api/session/status', methods=['GET'])
def session_status():
    user = get_current_user()
    if user:
        return jsonify({"success": True, "authenticated": True, "user": {"id": user['id'], "username": user['username']}})
    else:
        return jsonify({"success": True, "authenticated": False})

def check_game_limit_with_logout(user_id, game_type):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}', (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count >= max_plays:
            app.logger.info(f'GAME LIMIT REACHED: User {user_id}, Game {game_type}, Plays {count}/{max_plays}')
            limit_log_id = f"LIMIT-{secrets.token_hex(8)}"
            cursor.execute(f'INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})', (limit_log_id, user_id, 'GAME_LIMIT_REACHED', 0, 'COMPLETED', json.dumps({"t": game_type, "p": count, "m": max_plays}), datetime.utcnow().isoformat()))
            conn.commit()
            return {"can_play": False, "reason": f"Daily limit reached ({count}/{max_plays} plays)", "action_required": "logout", "game_type": game_type, "played_today": count, "max_plays": max_plays, "reset_time": "00:00 UTC (Midnight)"}
        cursor.execute(f'INSERT INTO game_plays (user_id, game_type, play_date) VALUES ({ph}, {ph}, {ph})', (user_id, game_type, today))
        conn.commit()
        return {"can_play": True, "played_today": count + 1, "max_plays": max_plays, "remaining": max_plays - (count + 1)}
    except Exception as e:
        app.logger.error(f"Game limit check error: {e}")
        conn.rollback()
        return {"can_play": False, "reason": "System error"}
    finally:
        return_db_connection(conn)

def check_and_record_game_play(user_id, game_type):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}', (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count >= max_plays:
            app.logger.info(f'Game limit reached: User {user_id}, Game {game_type}, Plays {count}/{max_plays}')
            return False
        cursor.execute(f'INSERT INTO game_plays (user_id, game_type, play_date) VALUES ({ph}, {ph}, {ph})', (user_id, game_type, today))
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
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}', (user_id, game_type, today))
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        app.logger.error(f"Get plays error: {e}")
        return 0
    finally:
        return_db_connection(conn)

def add_missing_columns():
    conn = get_db()
    cursor = conn.cursor()
    try:
        is_postgres = os.environ.get('DATABASE_URL') is not None
        if is_postgres:
            columns_to_add = ['last_achievement_check', 'last_game_timestamp', 'claimed_achievements', 'login_streak', 'last_login_date']
            for column in columns_to_add:
                cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='users' and column_name='{column}'")
                if not cursor.fetchone():
                    default = 'DEFAULT 0' if column == 'login_streak' else ''
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT {default}")
                    app.logger.info(f"Added missing column: {column} to users table")
        else:
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            columns_to_add = ['last_achievement_check', 'last_game_timestamp', 'claimed_achievements', 'login_streak', 'last_login_date']
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
    conn = get_db()
    cursor = conn.cursor()
    try:
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
    if conn is None:
        raise RuntimeError("Cannot initialize DB - no connection available")
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    _init_db_conn_ref = conn

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
            claimed_achievements TEXT DEFAULT '[]',
            login_streak INTEGER DEFAULT 0,
            last_login_date TEXT
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
            claimed_achievements TEXT DEFAULT '[]',
            login_streak INTEGER DEFAULT 0,
            last_login_date TEXT
        )
        ''')

    if is_postgres:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id SERIAL PRIMARY KEY,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT,
            min_withdrawal REAL DEFAULT 100000
        )
        ''')
    else:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT,
            min_withdrawal REAL DEFAULT 100000
        )
        ''')

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
            status TEXT DEFAULT 'AVAILABLE',
            metadata TEXT
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

    ph = '%s' if is_postgres else '?'
    cursor.execute('SELECT COUNT(*) as count FROM banks')
    bank_count = cursor.fetchone()
    if isinstance(bank_count, dict):
        bank_count = bank_count['count']
    else:
        bank_count = bank_count[0] if bank_count else 0

    if bank_count == 0:
        banks = [("057", "Zenith Bank Plc"), ("058", "GTBank"), ("044", "Access Bank"), ("033", "UBA"), ("011", "First Bank"), ("070", "Fidelity Bank"), ("050", "Ecobank"), ("039", "Stanbic IBTC"), ("214", "FCMB"), ("232", "Sterling Bank"), ("032", "Union Bank"), ("035", "Wema Bank"), ("082", "Keystone Bank"), ("215", "Unity Bank"), ("076", "Polaris Bank"), ("565", "OPay"), ("100", "PalmPay"), ("50211", "Kuda Bank"), ("566", "VBank"), ("035A", "ALAT by Wema")]
        for bank in banks:
            try:
                cursor.execute(f'INSERT INTO banks (code, name, is_active) VALUES ({ph}, {ph}, {ph})', (bank[0], bank[1], True))
            except Exception as e:
                app.logger.error(f"Error inserting bank {bank[0]}: {e}")
        app.logger.info(f"Inserted {len(banks)} banks")

    cursor.execute('SELECT COUNT(*) as count FROM admin_settings')
    settings_count = cursor.fetchone()
    if isinstance(settings_count, dict):
        settings_count = settings_count['count']
    else:
        settings_count = settings_count[0] if settings_count else 0
    if settings_count == 0:
        default_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
        cursor.execute(f'INSERT INTO admin_settings (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) VALUES ({ph}, {ph}, {ph}, {ph})', ('', '', '', default_days_json))

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

    cursor.execute(f'SELECT COUNT(*) FROM users WHERE username = {ph}', (CONFIG.ADMIN_USERNAME,))
    admin_count = cursor.fetchone()[0]

    admin_pass = generate_password_hash(CONFIG.ADMIN_PASSWORD)
    pin_hash = generate_password_hash(CONFIG.ADMIN_WITHDRAWAL_PIN)
    game_stats = json.dumps({"snake": {"high_score": 1200, "total_score": 5000}, "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3}, "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}})

    if admin_count == 0:
        if is_postgres:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme,
                last_game_timestamp, last_achievement_check, claimed_achievements,
                login_streak, last_login_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (CONFIG.ADMIN_USERNAME, admin_pass, 500000.00, "ADM0001", True, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, False, pin_hash, "", "", "light", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), '[]', 0, datetime.utcnow().isoformat()))
        else:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme,
                last_game_timestamp, last_achievement_check, claimed_achievements,
                login_streak, last_login_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (CONFIG.ADMIN_USERNAME, admin_pass, 500000.00, "ADM0001", 1, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, 0, pin_hash, "", "", "light", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), '[]', 0, datetime.utcnow().isoformat()))
        app.logger.warning(f"Admin account CREATED: {CONFIG.ADMIN_USERNAME}")
    else:
        cursor.execute(f'UPDATE users SET password = {ph}, withdrawal_pin = {ph}, is_admin = {ph} WHERE username = {ph}', (admin_pass, pin_hash, True if is_postgres else 1, CONFIG.ADMIN_USERNAME))
        app.logger.warning(f"Admin credentials SYNCED from environment variables for: {CONFIG.ADMIN_USERNAME}")

    cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
    whatsapp_count = cursor.fetchone()[0]
    if whatsapp_count == 0:
        cursor.execute(f'INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES ({ph}, {ph}, {ph}, {ph})', ('2348160881049', 'Primary Seller', True if is_postgres else 1, datetime.utcnow().isoformat()))

    conn.commit()
    app.logger.info("Database initialization completed successfully!")
    return_db_connection(_init_db_conn_ref)

def send_email_brevo_api(to_email, subject, html_content, text_content=None):
    if not BREVO_API_KEY:
        app.logger.error("BREVO_API_KEY not configured")
        return False
    try:
        headers = {"accept": "application/json", "content-type": "application/json", "api-key": BREVO_API_KEY}
        payload = {"sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL}, "to": [{"email": to_email, "name": to_email.split('@')[0] if '@' in to_email else to_email}], "subject": subject, "htmlContent": html_content}
        if text_content:
            payload["textContent"] = text_content
        payload["trackingEnabled"] = True
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            app.logger.info(f"Brevo API email sent to {to_email}")
            return True
        else:
            app.logger.error(f"Brevo API error: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.Timeout:
        app.logger.error("Brevo API timeout")
        return False
    except Exception as e:
        app.logger.error(f"Brevo API error: {str(e)}")
        return False

def send_coupon_email(email, coupon_code, amount):
    subject = "Your FLEXIA Coupon Code"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0A0A1F; color: #F0F0F0; padding: 20px; }}
            .container {{ max-width: 550px; margin: 0 auto; background: #151535; padding: 35px; border-radius: 16px; border: 1px solid #8000FF; }}
            .header {{ text-align: center; margin-bottom: 25px; }}
            .header h1 {{ background: linear-gradient(45deg, #8000FF, #00CCFF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2rem; font-family: 'Orbitron', sans-serif; }}
            .code-box {{ background: #1E1E45; padding: 25px; border-radius: 12px; text-align: center; border: 2px solid #8000FF; margin: 20px 0; }}
            .code-box span {{ font-size: 2.2rem; font-family: 'Courier New', monospace; letter-spacing: 6px; color: #00FF55; font-weight: bold; }}
            .details {{ background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px; margin: 15px 0; }}
            .details p {{ margin: 8px 0; color: #A0A0B5; }}
            .details strong {{ color: #F0F0F0; }}
            .footer {{ text-align: center; color: #A0A0B5; font-size: 0.8rem; margin-top: 25px; border-top: 1px solid #252540; padding-top: 20px; }}
            .highlight {{ color: #00FF55; font-weight: bold; }}
            .btn {{ display: inline-block; padding: 12px 30px; background: linear-gradient(45deg, #8000FF, #00CCFF); color: white; text-decoration: none; border-radius: 50px; font-weight: bold; margin: 15px 0; }}
            .steps {{ text-align: left; padding-left: 20px; }}
            .steps li {{ margin: 8px 0; color: #A0A0B5; }}
            .steps li strong {{ color: #F0F0F0; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>FLEXIA</h1>
                <p style="color: #A0A0B5; font-size: 1.1rem;">Your Coupon Code is Ready</p>
            </div>
            <div style="text-align:center;color:#00FF55;font-size:1.2rem;margin-bottom:10px;">Payment Successful</div>
            <p style="color: #F0F0F0;">Thank you for your payment of <strong style="color: #00FF55;">₦{amount:,.2f}</strong>.</p>
            <p style="color: #A0A0B5;">Here is your unique coupon code for FLEXIA registration:</p>
            <div class="code-box"><span>{coupon_code}</span></div>
            <div class="details">
                <p><strong>Payment Method:</strong> Bank Transfer</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Amount:</strong> ₦{amount:,.2f}</p>
                <p><strong>Date:</strong> {datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')}</p>
            </div>
            <p style="color: #F0F0F0; font-weight: bold; margin-top: 20px;">How to Use Your Coupon</p>
            <ol class="steps">
                <li>Go to <a href="https://flexia.com" style="color: #00CCFF; text-decoration: none; font-weight: bold;">FLEXIA</a></li>
                <li>Click <strong>REGISTER</strong></li>
                <li>Enter your coupon code in the <strong>Coupon Code</strong> field</li>
                <li>Complete your registration and start earning</li>
            </ol>
            <div style="text-align:center;"><a href="https://flexia.com" class="btn">Go to FLEXIA</a></div>
            <div class="footer">
                <p>This coupon code is valid for <strong>one-time use</strong> only.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <p style="margin-top:10px;">For support: <a href="mailto:support@flexia.com" style="color: #00CCFF;">support@flexia.com</a></p>
                <p style="margin-top:10px; font-size: 0.7rem; opacity: 0.6;">Sent via Brevo API</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    FLEXIA Coupon Code
    Thank you for your payment of ₦{amount:,.2f}.
    Your coupon code: {coupon_code}
    How to use:
    1. Go to FLEXIA
    2. Click REGISTER
    3. Enter your coupon code during registration
    This coupon is valid for one-time use only.
    Support: support@flexia.com
    """
    return send_email_brevo_api(email, subject, html_content, text_content)

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

def get_min_withdrawal():
    conn = get_db()
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('ALTER TABLE admin_settings ADD COLUMN min_withdrawal REAL DEFAULT 100000')
            conn.commit()
        except Exception:
            pass
        cursor.execute('SELECT min_withdrawal FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row and row[0] is not None:
            return float(row[0])
    except Exception as e:
        app.logger.error(f"Error getting min_withdrawal: {e}")
    finally:
        return_db_connection(conn)
    return CONFIG.MIN_WITHDRAWAL

def get_game_friendly_name(game_type):
    names = {'snake': 'Snake Game', 'coinflip': 'Coin Flip', 'plinko': 'Plinko 3D', 'spin': 'Daily Spin', 'tiktok': 'TikTok Follow'}
    return names.get(game_type, game_type)

def update_user_balance(user_id, amount_change):
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        if os.environ.get('DATABASE_URL'):
            cursor.execute(f'UPDATE users SET balance = balance + {ph} WHERE id = {ph} RETURNING balance', (amount_change, user_id))
        else:
            cursor.execute(f'UPDATE users SET balance = balance + {ph} WHERE id = {ph}', (amount_change, user_id))
            cursor.execute(f'SELECT balance FROM users WHERE id = {ph}', (user_id,))
        row = cursor.fetchone()
        new_balance = float(row[0]) if row and row[0] else 0.0
        conn.commit()
        app.logger.info(f"Atomic balance update for user {user_id}: {amount_change}, new balance: {new_balance}")
        return new_balance
    except Exception as e:
        app.logger.error(f"Balance update error: {str(e)}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            return_db_connection(conn)

def check_game_cooldown(user_id, game_type):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'SELECT last_game_timestamp FROM users WHERE id = {ph}', (user_id,))
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
        app.logger.error(f"Cooldown check error: {e}")
        return True
    finally:
        return_db_connection(conn)

def update_last_game_timestamp(user_id):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET last_game_timestamp = {ph} WHERE id = {ph}', (datetime.utcnow().isoformat(), user_id))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Update last game timestamp error: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

def is_withdrawal_day(user_id=None):
    today = datetime.utcnow().day
    if user_id is None:
        return today in get_global_withdrawal_days()
    conn = get_db()
    cursor = conn.cursor()
    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT withdrawal_restricted, custom_withdrawal_days FROM users WHERE id = {ph}', (user_id,))
        row = cursor.fetchone()
        if not row:
            return False
        withdrawal_restricted = bool(row[0])
        custom_days_str = row[1] if row[1] else ''
        if withdrawal_restricted:
            return False
        if custom_days_str and custom_days_str.strip():
            try:
                custom_days = json.loads(custom_days_str)
                if isinstance(custom_days, list) and custom_days:
                    return today in custom_days
            except:
                pass
        return today in get_global_withdrawal_days()
    except Exception as e:
        app.logger.error(f"Error checking withdrawal day: {e}")
        return False
    finally:
        return_db_connection(conn)

def grant_achievement_rewards(user_id):
    app.logger.info(f"Granting achievement rewards for user {user_id}")
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        if os.environ.get('DATABASE_URL'):
            cursor.execute("BEGIN")
        else:
            cursor.execute("BEGIN IMMEDIATE")
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT balance, game_stats, referral_code, points, last_achievement_check, claimed_achievements FROM users WHERE id = {ph}', (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return None
        balance = float(row[0]) if row[0] else 0
        game_stats_str = row[1] if row[1] else '{}'
        referral_code = row[2] if row[2] else ''
        current_points = int(row[3]) if row[3] else 0
        last_check = row[4] if row[4] else None
        claimed_achievements_str = row[5] if len(row) > 5 else '[]'
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
                if (datetime.utcnow() - last_check_time).total_seconds() < 300:
                    conn.rollback()
                    return balance
            except:
                pass
        game_stats = json.loads(game_stats_str)
        cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (referral_code,))
        referrals = cursor.fetchone()[0]
        cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph}', (user_id,))
        total_tx = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = 'WITHDRAWAL'", (user_id,))
        total_withdrawals = cursor.fetchone()[0]
        today = datetime.utcnow().date()
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND play_date = {ph}', (user_id, today))
        games_today = cursor.fetchone()[0]
        cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph}', (user_id,))
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

        new_achievements = []
        for ach in achievements:
            if ach["unlocked"] and ach["id"] not in claimed_achievements:
                new_achievements.append(ach)

        if not new_achievements:
            cursor.execute(f'UPDATE users SET last_achievement_check = {ph} WHERE id = {ph}', (datetime.utcnow().isoformat(), user_id))
            conn.commit()
            return balance

        total_reward = sum(ach["reward"] for ach in new_achievements)
        total_points = sum(ach["points"] for ach in new_achievements)
        new_achievement_ids = [ach["id"] for ach in new_achievements]
        all_claimed_achievements = claimed_achievements + new_achievement_ids
        new_balance = balance + total_reward

        if os.environ.get('DATABASE_URL'):
            cursor.execute(f'UPDATE users SET balance = {ph}, points = {ph}, last_achievement_check = {ph}, claimed_achievements = {ph} WHERE id = {ph}', (new_balance, current_points + total_points, datetime.utcnow().isoformat(), json.dumps(all_claimed_achievements), user_id))
        else:
            cursor.execute(f'UPDATE users SET balance = balance + {ph}, points = points + {ph}, last_achievement_check = {ph}, claimed_achievements = {ph} WHERE id = {ph}', (total_reward, total_points, datetime.utcnow().isoformat(), json.dumps(all_claimed_achievements), user_id))

        if total_reward > 0:
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute(f'INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})', (tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED', json.dumps({"pts": total_points, "ids": new_achievement_ids}), datetime.utcnow().isoformat()))

        conn.commit()
        app.logger.info(f"Granted achievement rewards to user {user_id}: ₦{total_reward}, {total_points} points, achievements: {new_achievement_ids}")
        return new_balance
    except Exception as e:
        app.logger.error(f"Achievement grant error for user {user_id}: {e}")
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

def cleanup_old_transactions():
    conn = get_db()
    cursor = conn.cursor()
    try:
        if os.environ.get('DATABASE_URL'):
            cursor.execute("""
                DELETE FROM transactions
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY user_id ORDER BY timestamp DESC
                        ) as rn
                        FROM transactions
                    ) ranked
                    WHERE rn <= 50
                )
            """)
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            app.logger.info(f"Cleaned up {deleted} old transactions")
    except Exception as e:
        app.logger.error(f"Transaction cleanup error: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        return_db_connection(conn)

def start_cleanup_scheduler():
    def run():
        time.sleep(300)
        while True:
            try:
                cleanup_old_transactions()
            except Exception as e:
                app.logger.error(f"Cleanup scheduler error: {e}")
            time.sleep(3600)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    app.logger.info("Transaction cleanup scheduler started")

def generate_coupon_code():
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return f"FLEX-{parts[0]}-{parts[1]}-{parts[2]}"

def generate_and_save_coupon(amount, email, transaction_ref):
    conn = get_db()
    cursor = conn.cursor()
    try:
        coupon_code = generate_coupon_code()
        cursor.execute("SELECT code FROM coupons WHERE code = %s", (coupon_code,))
        while cursor.fetchone():
            coupon_code = generate_coupon_code()
            cursor.execute("SELECT code FROM coupons WHERE code = %s", (coupon_code,))
        cursor.execute('INSERT INTO coupons (code, status, metadata) VALUES (%s, %s, %s)', (coupon_code, 'AVAILABLE', json.dumps({'generated_by': 'paystack', 'amount_paid': amount, 'email': email, 'transaction_ref': transaction_ref, 'payment_method': 'bank_transfer', 'generated_at': datetime.utcnow().isoformat()})))
        conn.commit()
        app.logger.info(f"Coupon generated: {coupon_code} for {email}")
        return coupon_code
    except Exception as e:
        app.logger.error(f"Coupon generation error: {e}")
        conn.rollback()
        return None
    finally:
        return_db_connection(conn)

def initialize_app():
    try:
        init_db_pool()
        app.logger.info("DB pool initialized")
    except Exception as e:
        app.logger.error(f"DB pool failed: {e}")
    try:
        init_db()
        app.logger.info("DB tables ready")
    except Exception as e:
        app.logger.error(f"DB init failed: {e}")
    try:
        add_missing_columns()
        app.logger.info("DB columns verified")
    except Exception as e:
        app.logger.error(f"Column migration failed: {e}")
    try:
        add_database_indexes()
    except Exception as e:
        app.logger.error(f"Index creation failed: {e}")
    try:
        cleanup_old_tiktok_tasks()
    except Exception as e:
        app.logger.error(f"TikTok cleanup failed: {e}")
    try:
        run_cleanup_scheduler()
        run_backup_scheduler()
        start_cleanup_scheduler()
        app.logger.info("Background schedulers started")
    except Exception as e:
        app.logger.error(f"Scheduler start failed: {e}")
    try:
        if BREVO_API_KEY:
            app.logger.info("Brevo API configured")
        else:
            app.logger.warning("BREVO_API_KEY not set - email sending will fail")
    except Exception as e:
        app.logger.error(f"Brevo check failed: {e}")

with app.app_context():
    initialize_app()

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

        cursor.execute(f'SELECT status, metadata FROM coupons WHERE code = {ph}', (coupon_code,))
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
            claimed_achievements, login_streak, last_login_date
        ) VALUES (
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}
        )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, is_admin_value,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            admin_pw_changed, None, withdrawal_restricted, 0.00, 0, 0,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            '[]', 0, datetime.utcnow().isoformat()
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
        cursor.execute(f'SELECT * FROM users WHERE LOWER(username) = LOWER({ph}) OR LOWER(contact) = LOWER({ph})', (identifier, identifier))
        row = cursor.fetchone()

        if not row:
            app.logger.warning(f"Failed login attempt for identifier: {identifier}")
            return jsonify({"success": False, "message": "Invalid credentials"}), 401

        stored_password = row[2] if len(row) > 2 else None
        if not stored_password or not check_password_hash(stored_password, password):
            app.logger.warning(f"Invalid password for user: {identifier}")
            return jsonify({"success": False, "message": "Invalid credentials"}), 401

        user = row_to_dict(cursor, row)

        cursor.execute(f'UPDATE users SET last_login = {ph} WHERE id = {ph}', (datetime.utcnow().isoformat(), user['id']))
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
                "ui_theme": user.get('ui_theme', 'light'),
                "transactions": []
            }
        })

        token = create_session_token(user['id'])
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token, httponly=True, secure=secure_cookie, samesite='Lax', max_age=86400)

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

@app.route('/api/auth/validate-coupon', methods=['POST'])
def validate_coupon():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    coupon_code = sanitize_input(data.get('coupon_code', '').upper())

    if not coupon_code:
        return jsonify({"success": False, "message": "Coupon code required"}), 400

    if len(coupon_code) < 4:
        return jsonify({"success": False, "message": "Invalid coupon code format"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT status, metadata FROM coupons WHERE code = {ph}', (coupon_code,))
        row = cursor.fetchone()

        if not row:
            return jsonify({
                "success": False,
                "message": "Invalid coupon code. Please check and try again."
            }), 404

        status = row[0]
        metadata = json.loads(row[1]) if row[1] else {}

        if status != 'AVAILABLE':
            if status == 'USED':
                return jsonify({
                    "success": False,
                    "message": "This coupon code has already been used."
                }), 403
            else:
                return jsonify({
                    "success": False,
                    "message": f"This coupon code is {status}. Please contact support."
                }), 403

        if metadata.get('expires_at'):
            try:
                expiry = datetime.fromisoformat(metadata['expires_at'])
                if datetime.utcnow() > expiry:
                    return jsonify({
                        "success": False,
                        "message": "This coupon code has expired."
                    }), 403
            except:
                pass

        return jsonify({
            "success": True,
            "message": "Coupon code is valid",
            "coupon_code": coupon_code,
            "generated_by": metadata.get('generated_by', 'unknown'),
            "amount_paid": metadata.get('amount_paid', 0)
        })

    except Exception as e:
        app.logger.error(f"Coupon validation error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to validate coupon. Please try again."
        }), 500
    finally:
        return_db_connection(conn)

@app.route('/api/config')
def get_public_config():
    return jsonify({"success": True, "min_withdrawal": get_min_withdrawal()})

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
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')

    if not pin or not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
        return jsonify({"success": False, "message": "PIN must be 4-6 digits"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        pin_hash = generate_password_hash(pin)
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'UPDATE users SET withdrawal_pin = {ph} WHERE id = {ph}', (pin_hash, user['id']))
        conn.commit()

        app.logger.info(f"User {user['username']} set withdrawal PIN")
        return jsonify({"success": True, "message": "Withdrawal PIN set successfully"})

    except Exception as e:
        app.logger.error(f"Set withdrawal PIN error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set PIN"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
def verify_withdrawal_pin():
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')

    if not pin:
        return jsonify({"success": False, "message": "PIN required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT withdrawal_pin FROM users WHERE id = {ph}', (user['id'],))
        row = cursor.fetchone()

        if not row or not row[0]:
            return jsonify({"success": False, "message": "No PIN set yet"}), 400

        stored_pin = row[0]
        if check_password_hash(stored_pin, pin):
            return jsonify({"success": True, "message": "PIN verified"})
        else:
            return jsonify({"success": False, "message": "Incorrect PIN"}), 403

    except Exception as e:
        app.logger.error(f"Verify PIN error: {e}")
        return jsonify({"success": False, "message": "Failed to verify PIN"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/change-password', methods=['POST'])
@require_auth
def change_password():
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
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT password FROM users WHERE id = {ph}', (user['id'],))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404

        stored_password = row[0]
        if not check_password_hash(stored_password, old_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 403

        new_password_hash = generate_password_hash(new_password)
        cursor.execute(f'UPDATE users SET password = {ph} WHERE id = {ph}', (new_password_hash, user['id']))
        conn.commit()

        app.logger.info(f"User {user['username']} changed password")
        return jsonify({"success": True, "message": "Password changed successfully"})

    except Exception as e:
        app.logger.error(f"Change password error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to change password"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    user = get_current_user()
    data = request.get_json()
    picture_url = data.get('picture_url', '').strip()

    if not picture_url:
        return jsonify({"success": False, "message": "Picture URL required"}), 400

    if not picture_url.startswith(('http://', 'https://')):
        return jsonify({"success": False, "message": "Invalid URL format"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'UPDATE users SET profile_picture = {ph} WHERE id = {ph}', (picture_url, user['id']))
        conn.commit()

        app.logger.info(f"User {user['username']} updated profile picture")
        return jsonify({"success": True, "message": "Profile picture updated"})

    except Exception as e:
        app.logger.error(f"Set profile picture error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update profile picture"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_ui_theme():
    user = get_current_user()
    data = request.get_json()
    dark_mode = data.get('dark_mode', False)

    conn = get_db()
    cursor = conn.cursor()

    try:
        theme = 'dark' if dark_mode else 'light'
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'UPDATE users SET ui_theme = {ph} WHERE id = {ph}', (theme, user['id']))
        conn.commit()

        app.logger.info(f"User {user['username']} set theme to {theme}")
        return jsonify({"success": True, "message": f"Theme set to {theme} mode"})

    except Exception as e:
        app.logger.error(f"Set theme error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set theme"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def admin_change_password():
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
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT password FROM users WHERE id = {ph}', (user['id'],))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404

        stored_password = row[0]
        if not check_password_hash(stored_password, current_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 403

        new_password_hash = generate_password_hash(new_password)

        if os.environ.get('DATABASE_URL'):
            cursor.execute(f'UPDATE users SET password = {ph}, admin_password_changed = TRUE WHERE id = {ph}', (new_password_hash, user['id']))
        else:
            cursor.execute(f'UPDATE users SET password = {ph}, admin_password_changed = 1 WHERE id = {ph}', (new_password_hash, user['id']))

        conn.commit()

        app.logger.info(f"Admin password changed for user: {user['username']}")
        return jsonify({"success": True, "message": "Password changed successfully! Please login again."})

    except Exception as e:
        app.logger.error(f"Change admin password error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to change password"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/withdrawal/check-day', methods=['GET'])
@require_auth
def check_withdrawal_day():
    user = get_current_user()
    today = datetime.utcnow().day
    conn = None

    try:
        can_withdraw = is_withdrawal_day(user['id'])
        global_days = get_global_withdrawal_days()

        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT custom_withdrawal_days FROM users WHERE id = {ph}', (user['id'],))
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
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/games/access', methods=['GET'])
@require_auth
def check_game_access_simple():
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
    user = get_current_user()

    if game_type not in ['snake', 'coinflip', 'plinko', 'spin', 'tiktok']:
        return jsonify({"success": False, "message": "Invalid game type"}), 400

    try:
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 5)
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

@app.route('/api/games/check-limit-with-logout/<game_type>', methods=['GET'])
@require_auth
def check_game_limit_with_logout_endpoint(game_type):
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
    user = get_current_user()

    conn = get_db()
    cursor = conn.cursor()

    try:
        tx_id = f"LOGOUT-{secrets.token_hex(8)}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                      (tx_id, user['id'], 'FORCE_LOGOUT', 0, 'COMPLETED', json.dumps({"gt":game_type,"r":"limit"}), datetime.utcnow().isoformat()))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Force logout logging error: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

    resp = jsonify({
        "success": True,
        "force_logout": True,
        "reason": f"Daily {game_type} limit reached",
        "redirect": "/?reason=daily_limit_reached",
        "message": "You have reached your daily limit. Please come back tomorrow!"
    })
    resp.set_cookie('session_token', '', expires=0)
    return resp

@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake_enhanced():
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)

    app.logger.info(f"Snake report from {user['username']}: {apples} apples")

    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "Invalid apple count (1-100)"}), 400

    if not acquire_claim_lock(user['id'], 'SNAKE'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429

    try:
        if not check_game_cooldown(user['id'], 'SNAKE'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429

        limit_check = check_game_limit_with_logout(user['id'], 'snake')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily snake game limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403

        golden_apples = data.get('golden_apples', 0)
        normal_apples = apples - golden_apples
        reward = (normal_apples * CONFIG.SNAKE_REWARD) + (golden_apples * CONFIG.SNAKE_REWARD * 2)
        reward = max(0, reward)

        conn = get_db()
        cursor = conn.cursor()

        try:
            today = datetime.utcnow().date().isoformat()
            ph = '%s' if os.environ.get('DATABASE_URL') else '?'

            cursor.execute(f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = {ph} AND type = 'SNAKE_REWARD' AND DATE(timestamp) = {ph}", (user['id'], today))
            earned_today = float(cursor.fetchone()[0] or 0)

            SNAKE_DAILY_CAP = 5000

            if earned_today >= SNAKE_DAILY_CAP:
                return_db_connection(conn)
                return jsonify({
                    "success": False,
                    "message": f"Daily snake earnings cap reached (₦{SNAKE_DAILY_CAP}). Come back tomorrow!",
                    "daily_earned": earned_today,
                    "daily_cap": SNAKE_DAILY_CAP
                }), 400

            if earned_today + reward > SNAKE_DAILY_CAP:
                reward = SNAKE_DAILY_CAP - earned_today

            new_balance = update_user_balance(user['id'], reward)

            if new_balance is None:
                return jsonify({"success": False, "message": "Failed to update balance"}), 500

            game_stats = json.loads(user.get('game_stats', '{}'))
            snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
            score = apples * 10

            if score > snake_stats.get('high_score', 0):
                snake_stats['high_score'] = score

            snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
            game_stats['snake'] = snake_stats

            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s', (json.dumps(game_stats), user['id']))
            update_last_game_timestamp(user['id'])

            tx_id = f"SNK-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                          (tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED', json.dumps({"g":"snake","a":apples,"ga":golden_apples}), datetime.utcnow().isoformat()))
            conn.commit()

            app.logger.info(f"Snake reward granted to {user['username']}: ₦{reward}")
            remaining_cap = max(0, SNAKE_DAILY_CAP - (earned_today + reward))

            return jsonify({
                "success": True,
                "reward": reward,
                "new_balance": new_balance,
                "apples": apples,
                "transaction_id": tx_id,
                "daily_earned": earned_today + reward,
                "daily_cap": SNAKE_DAILY_CAP,
                "remaining_today": remaining_cap,
                "message": f"Success! Claimed ₦{reward} for {apples} apples. Daily cap: ₦{int(earned_today+reward)}/₦{SNAKE_DAILY_CAP}"
            })

        except Exception as e:
            app.logger.error(f"Snake database error: {e}")
            app.logger.error(traceback.format_exc())
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)
    finally:
        release_claim_lock(user['id'], 'SNAKE')

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip_enhanced():
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    won = data.get('won', False)

    app.logger.info(f"Coin flip from {user['username']}: bet {bet}, won: {won}")

    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.COIN_FLIP_MIN_BET}, max: 50000)"}), 400

    if not acquire_claim_lock(user['id'], 'COINFLIP'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429

    try:
        if not check_game_cooldown(user['id'], 'COINFLIP'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429

        limit_check = check_game_limit_with_logout(user['id'], 'coinflip')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily coin flip limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403

        payout = round(bet * 1.8, 2) if won else 0
        net_change = round(payout - bet, 2)

        conn = get_db()
        cursor = conn.cursor()

        try:
            today = datetime.utcnow().date().isoformat()
            ph = '%s' if os.environ.get('DATABASE_URL') else '?'

            if won:
                cursor.execute(f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = {ph} AND type = 'COINFLIP_WIN' AND DATE(timestamp) = {ph}", (user['id'], today))
                won_today = float(cursor.fetchone()[0] or 0)
                COINFLIP_WIN_CAP = 5000

                if won_today >= COINFLIP_WIN_CAP:
                    return_db_connection(conn)
                    return jsonify({
                        "success": False,
                        "message": f"Daily coinflip win cap reached (₦{COINFLIP_WIN_CAP}). Come back tomorrow!",
                        "daily_won": won_today,
                        "daily_cap": COINFLIP_WIN_CAP
                    }), 400

                if won_today + net_change > COINFLIP_WIN_CAP:
                    net_change = COINFLIP_WIN_CAP - won_today
                    payout = net_change + bet
            else:
                won_today = 0
                COINFLIP_WIN_CAP = 5000

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
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s', (json.dumps(game_stats), user['id']))
            update_last_game_timestamp(user['id'])

            tx_type = 'COINFLIP_WIN' if won else 'COINFLIP_LOSS'
            tx_id = f"COIN-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                          (tx_id, user['id'], tx_type, net_change, 'COMPLETED', json.dumps({"g": "coin", "b": bet, "w": int(won)}), datetime.utcnow().isoformat()))
            conn.commit()

            app.logger.info(f"Coin flip processed for {user['username']}: {'WON' if won else 'LOST'} {bet}, net: {net_change}")
            daily_won_after = won_today + net_change if won else won_today

            return jsonify({
                "success": True,
                "payout": payout if won else 0,
                "net_change": net_change,
                "new_balance": new_balance,
                "won": won,
                "daily_won": daily_won_after,
                "daily_cap": COINFLIP_WIN_CAP,
                "house_edge_note": "Wins pay 1.8x your bet",
                "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}₦{abs(net_change):.2f}"
            })

        except Exception as e:
            app.logger.error(f"Coin flip error: {e}")
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)
    finally:
        release_claim_lock(user['id'], 'COINFLIP')

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko_enhanced():
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    multiplier = float(data.get('multiplier', 0))

    app.logger.info(f"Plinko from {user['username']}: bet {bet}, multiplier: {multiplier}")

    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.PLINKO_MIN_BET}, max: 50000)"}), 400

    if multiplier not in [0.5, 1.0, 3.0, 10.0]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400

    if not acquire_claim_lock(user['id'], 'PLINKO'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429

    try:
        if not check_game_cooldown(user['id'], 'PLINKO'):
            return jsonify({"success": False, "message": "Please wait 1 second between games"}), 429

        limit_check = check_game_limit_with_logout(user['id'], 'plinko')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily plinko limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403

        win_amount = round(bet * multiplier, 2)
        net_change = round(win_amount - bet, 2)

        conn = get_db()
        cursor = conn.cursor()

        try:
            today = datetime.utcnow().date().isoformat()
            ph = '%s' if os.environ.get('DATABASE_URL') else '?'

            PLINKO_WIN_CAP = 3000

            if net_change > 0:
                cursor.execute(f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = {ph} AND type = 'PLINKO_WIN' AND DATE(timestamp) = {ph}", (user['id'], today))
                plinko_won_today = float(cursor.fetchone()[0] or 0)

                if plinko_won_today >= PLINKO_WIN_CAP:
                    return_db_connection(conn)
                    return jsonify({
                        "success": False,
                        "message": f"Daily plinko win cap reached (₦{PLINKO_WIN_CAP}). Come back tomorrow!",
                        "daily_won": plinko_won_today,
                        "daily_cap": PLINKO_WIN_CAP
                    }), 400

                if plinko_won_today + net_change > PLINKO_WIN_CAP:
                    net_change = PLINKO_WIN_CAP - plinko_won_today
                    win_amount = bet + net_change
            else:
                plinko_won_today = 0

            new_balance = update_user_balance(user['id'], net_change)

            if new_balance is None:
                return jsonify({"success": False, "message": "Failed to update balance"}), 500

            game_stats = json.loads(user.get('game_stats', '{}'))
            plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})

            plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet

            if win_amount > bet:
                plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
                if win_amount > plinko_stats.get('highest_win', 0):
                    plinko_stats['highest_win'] = win_amount

            game_stats['plinko'] = plinko_stats
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s', (json.dumps(game_stats), user['id']))
            update_last_game_timestamp(user['id'])

            tx_type = 'PLINKO_WIN' if net_change > 0 else 'PLINKO_LOSS'
            tx_id = f"PLK-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                          (tx_id, user['id'], tx_type, net_change, 'COMPLETED', json.dumps({"g": "plinko", "b": bet, "x": multiplier}), datetime.utcnow().isoformat()))
            conn.commit()

            app.logger.info(f"Plinko processed for {user['username']}: bet {bet}, multiplier {multiplier}, net: {net_change}")
            daily_plinko_after = plinko_won_today + net_change if net_change > 0 else plinko_won_today

            return jsonify({
                "success": True,
                "win_amount": win_amount,
                "net_change": net_change,
                "new_balance": new_balance,
                "multiplier": multiplier,
                "daily_won": daily_plinko_after,
                "daily_cap": PLINKO_WIN_CAP,
                "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}₦{net_change:.2f}"
            })

        except Exception as e:
            app.logger.error(f"Plinko error: {e}")
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        release_claim_lock(user['id'], 'PLINKO')

@app.route('/api/spin/execute', methods=['POST'])
@require_auth
def execute_spin():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    try:
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'

        cursor.execute(f'SELECT 1 FROM transactions WHERE user_id = {ph} AND type = \'SPIN_REWARD\' AND DATE(timestamp) = {ph}', (user['id'], today))
        if cursor.fetchone() is not None:
            return jsonify({"success": False, "message": "You have already spun today. Come back tomorrow!"}), 400

        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = 'SPIN_REWARD' AND timestamp >= NOW() - INTERVAL '7 days'" if os.environ.get('DATABASE_URL') else "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND type = 'SPIN_REWARD' AND timestamp >= datetime('now', '-7 days')", (user['id'],))
        spins_last_7_days = cursor.fetchone()[0]

        is_bonus_spin = spins_last_7_days >= 6

        rewards = [1000, 500, 200, 100, 50, 0]

        if is_bonus_spin:
            weights = [0.03, 0.07, 0.15, 0.25, 0.30, 0.20]
        else:
            weights = [0.01, 0.04, 0.10, 0.20, 0.30, 0.35]

        import random
        reward = random.choices(rewards, weights=weights, k=1)[0]

        new_balance = update_user_balance(user['id'], reward)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        tx_id = f"SPIN-{secrets.token_hex(8)}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                      (tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED', json.dumps({"g": "spin"}), datetime.utcnow().isoformat()))
        conn.commit()

        app.logger.info(f"Spin executed for {user['username']}: reward {reward}")

        prizes = [1000, 500, 200, 100, 50, 0]
        prize_index = prizes.index(reward) if reward in prizes else 5

        msg = f"Congratulations! You won ₦{reward}!" if reward > 0 else "Better luck tomorrow! Keep spinning daily for a bonus spin!"
        if is_bonus_spin:
            msg = f"BONUS SPIN! 7-day streak reward: ₦{reward}!"

        return jsonify({
            "success": True,
            "reward": reward,
            "prize_index": prize_index,
            "new_balance": new_balance,
            "is_bonus_spin": is_bonus_spin,
            "message": msg
        })

    except Exception as e:
        app.logger.error(f"Spin execute error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process spin"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily_task():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s', (user['id'], 'TIKTOK_DAILY', today))
        already_claimed = cursor.fetchone() is not None

        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()

        if task_row:
            task = {
                'tiktok_link': task_row[0],
                'reward_amount': float(task_row[1]) if task_row[1] else CONFIG.TIKTOK_REWARD
            }
            return jsonify({"success": True, "task": task, "already_claimed": already_claimed})
        else:
            return jsonify({"success": False, "message": "No TikTok task for today", "already_claimed": already_claimed}), 404

    except Exception as e:
        app.logger.error(f"TikTok daily error: {e}")
        return jsonify({"success": False, "message": f"Failed to get task: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
def follow_tiktok_daily_enhanced():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        app.logger.warning(f"Rate limit exceeded for TikTok follow from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429

    user = get_current_user()
    today = datetime.utcnow().date().isoformat()

    if not acquire_claim_lock(user['id'], 'TIKTOK'):
        return jsonify({"success": False, "message": "Please wait 2 seconds between claims"}), 429

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s', (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Already claimed today"}), 400

        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()

        if not task_row:
            return jsonify({"success": False, "message": "No task for today"}), 404

        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = %s AND DATE(timestamp) = %s', (user['id'], 'TIKTOK_DAILY', today))
        tasks_done_today = cursor.fetchone()[0]

        tiered_rewards = {0: 50, 1: 75, 2: 100}
        reward = tiered_rewards.get(tasks_done_today, 50)

        limit_check = check_game_limit_with_logout(user['id'], 'tiktok')
        if not limit_check.get("can_play", False):
            return jsonify({
                "success": False,
                "message": f"Daily TikTok limit reached! {limit_check.get('reason', '')}",
                "force_logout": True,
                "redirect": True,
                "details": limit_check
            }), 403

        new_balance = update_user_balance(user['id'], reward)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, timestamp) VALUES (%s, %s, %s, %s, %s, %s)',
                      (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        conn.commit()
        return_db_connection(conn)

        app.logger.info(f"TikTok daily claimed by {user['username']}: reward: {reward}")

        task_number = tasks_done_today + 1
        next_reward = tiered_rewards.get(tasks_done_today + 1, None)

        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "task_number": task_number,
            "next_reward": next_reward,
            "message": f"Task {task_number}/3 complete! Earned ₦{reward}" + (f" | Next task: ₦{next_reward}" if next_reward else " | All tasks done today!")
        })

    except Exception as e:
        app.logger.error(f"TikTok follow error: {e}")
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        release_claim_lock(user['id'], 'TIKTOK')

@app.route('/api/daily-login-bonus', methods=['POST'])
@require_auth
def claim_daily_login_bonus():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()

    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT login_streak, last_login_date FROM users WHERE id = {ph}', (user['id'],))
        row = cursor.fetchone()

        current_streak = int(row[0] or 0) if row else 0
        last_login_date = row[1] if row else None

        if last_login_date == today:
            return jsonify({
                "success": False,
                "message": "Already claimed today's login bonus. Come back tomorrow!",
                "streak": current_streak
            }), 400

        yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

        if last_login_date == yesterday:
            new_streak = current_streak + 1
        else:
            new_streak = 1

        if new_streak >= 30:
            reward = 500
            milestone = "30-Day Streak Bonus!"
        elif new_streak >= 7 and new_streak % 7 == 0:
            reward = 100
            milestone = f"{new_streak}-Day Streak Bonus!"
        else:
            reward = 20
            milestone = None

        new_balance = update_user_balance(user['id'], reward)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        cursor.execute(f'UPDATE users SET login_streak = {ph}, last_login_date = {ph} WHERE id = {ph}', (new_streak, today, user['id']))

        tx_id = f"LOGIN-{secrets.token_hex(6)}"
        cursor.execute(f"INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                      (tx_id, user['id'], 'LOGIN_BONUS', reward, 'COMPLETED', json.dumps({"streak": new_streak}), datetime.utcnow().isoformat()))
        conn.commit()

        next_milestone = None
        if new_streak < 7:
            next_milestone = f"₦100 bonus in {7 - new_streak} days!"
        elif new_streak < 30:
            days_to_30 = 30 - new_streak
            next_7 = 7 - (new_streak % 7)
            next_milestone = f"₦100 bonus in {next_7} days, ₦500 in {days_to_30} days!"

        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "streak": new_streak,
            "milestone": milestone,
            "next_milestone": next_milestone,
            "message": f"{'🎉 ' + milestone + ' ' if milestone else ''}Daily bonus: ₦{reward} | Streak: {new_streak} days"
        })

    except Exception as e:
        app.logger.error(f"Login bonus error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process login bonus"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/daily-login-bonus/status', methods=['GET'])
@require_auth
def get_login_bonus_status():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()

    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT login_streak, last_login_date FROM users WHERE id = {ph}', (user['id'],))
        row = cursor.fetchone()

        streak = int(row[0] or 0) if row else 0
        last_date = row[1] if row else None
        already_claimed = last_date == today

        next_reward = 20
        if (streak + 1) >= 30:
            next_reward = 500
        elif (streak + 1) % 7 == 0:
            next_reward = 100

        return jsonify({
            "success": True,
            "streak": streak,
            "already_claimed": already_claimed,
            "next_reward": next_reward,
            "last_claimed": last_date
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    user = get_current_user()

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

        new_balance = update_user_balance(user['id'], unclaimed)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        cursor.execute('UPDATE users SET claimed_bonuses = %s WHERE id = %s', (total_bonus, user['id']))

        tx_id = f"REF-{secrets.token_hex(8)}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                      (tx_id, user['id'], 'REFERRAL_BONUS', unclaimed, 'COMPLETED', json.dumps({"refs": referrals}), datetime.utcnow().isoformat()))
        conn.commit()
        return_db_connection(conn)

        app.logger.info(f"Referral bonus claimed by {user['username']}: {unclaimed}")

        return jsonify({
            "success": True,
            "claimed": unclaimed,
            "new_balance": new_balance,
            "message": f"Success! Claimed ₦{unclaimed} referral bonus"
        })

    except Exception as e:
        app.logger.error(f"Referral error: {e}")
        return jsonify({"success": False, "message": f"Failed to claim: {str(e)}"}), 500
    finally:
        release_claim_lock(user['id'], 'REFERRAL')

@app.route('/api/achievements')
@require_auth
def get_achievements():
    user = get_current_user()

    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    conn = get_db()
    cursor = conn.cursor()

    try:
        game_stats = json.loads(user.get('game_stats', '{}'))
        balance = float(user.get('balance', 0))
        claimed_achievements_str = user.get('claimed_achievements', '[]')

        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []

        ph = '%s' if os.environ.get('DATABASE_URL') else '?'

        cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph}', (user['id'],))
        total_tx = cursor.fetchone()[0]

        cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = {ph}', (user['id'], 'WITHDRAWAL'))
        total_withdrawals = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]

        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user['id'], today))
        games_today = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user['id'],))
        total_games = cursor.fetchone()[0]

        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

        achievements_data = [
            {"id": 1, "title": "First Game", "description": "Play any game once", "reward": 500, "points": 10, "unlocked": total_games >= 1, "category": "gaming", "icon": "fas fa-gamepad", "current_value": total_games, "target_value": 1, "progress_percentage": min(100, (total_games / 1) * 100), "cash_reward": 500, "claimed": 1 in claimed_achievements},
            {"id": 2, "title": "Gamer", "description": "Play 50 games", "reward": 5000, "points": 50, "unlocked": total_games >= 50, "category": "gaming", "icon": "fas fa-gamepad", "current_value": total_games, "target_value": 50, "progress_percentage": min(100, (total_games / 50) * 100), "cash_reward": 5000, "claimed": 2 in claimed_achievements},
            {"id": 3, "title": "Game Master", "description": "Play 200 games", "reward": 15000, "points": 150, "unlocked": total_games >= 200, "category": "gaming", "icon": "fas fa-gamepad", "current_value": total_games, "target_value": 200, "progress_percentage": min(100, (total_games / 200) * 100), "cash_reward": 15000, "claimed": 3 in claimed_achievements},
            {"id": 4, "title": "Snake Pro", "description": "Snake high score 1000+", "reward": 7500, "points": 75, "unlocked": snake_high >= 1000, "category": "gaming", "icon": "fas fa-gamepad", "current_value": snake_high, "target_value": 1000, "progress_percentage": min(100, (snake_high / 1000) * 100), "cash_reward": 7500, "claimed": 4 in claimed_achievements},
            {"id": 5, "title": "Lucky Streak", "description": "10+ coin flip win streak", "reward": 10000, "points": 100, "unlocked": coin_streak >= 10, "category": "gaming", "icon": "fas fa-coins", "current_value": coin_streak, "target_value": 10, "progress_percentage": min(100, (coin_streak / 10) * 100), "cash_reward": 10000, "claimed": 5 in claimed_achievements},
            {"id": 6, "title": "Coin Flipper", "description": "100+ coin flips", "reward": 6000, "points": 60, "unlocked": coin_total >= 100, "category": "gaming", "icon": "fas fa-coins", "current_value": coin_total, "target_value": 100, "progress_percentage": min(100, (coin_total / 100) * 100), "cash_reward": 6000, "claimed": 6 in claimed_achievements},
            {"id": 7, "title": "Plinko Champion", "description": "50+ Plinko wins", "reward": 8000, "points": 80, "unlocked": plinko_wins >= 50, "category": "gaming", "icon": "fas fa-bullseye", "current_value": plinko_wins, "target_value": 50, "progress_percentage": min(100, (plinko_wins / 50) * 100), "cash_reward": 8000, "claimed": 7 in claimed_achievements},
            {"id": 8, "title": "Thousandaire", "description": "Balance ₦1,000+", "reward": 1000, "points": 15, "unlocked": balance >= 1000, "category": "earnings", "icon": "fas fa-money-bill-wave", "current_value": balance, "target_value": 1000, "progress_percentage": min(100, (balance / 1000) * 100), "cash_reward": 1000, "claimed": 8 in claimed_achievements},
            {"id": 9, "title": "Millionaire in Progress", "description": "Balance ₦50,000+", "reward": 10000, "points": 100, "unlocked": balance >= 50000, "category": "earnings", "icon": "fas fa-money-bill-wave", "current_value": balance, "target_value": 50000, "progress_percentage": min(100, (balance / 50000) * 100), "cash_reward": 10000, "claimed": 9 in claimed_achievements},
            {"id": 10, "title": "High Roller", "description": "Balance ₦200,000+", "reward": 25000, "points": 200, "unlocked": balance >= 200000, "category": "earnings", "icon": "fas fa-money-bill-wave", "current_value": balance, "target_value": 200000, "progress_percentage": min(100, (balance / 200000) * 100), "cash_reward": 25000, "claimed": 10 in claimed_achievements},
            {"id": 11, "title": "First Withdrawal", "description": "Make first withdrawal", "reward": 5000, "points": 50, "unlocked": total_withdrawals >= 1, "category": "earnings", "icon": "fas fa-wallet", "current_value": total_withdrawals, "target_value": 1, "progress_percentage": min(100, (total_withdrawals / 1) * 100), "cash_reward": 5000, "claimed": 11 in claimed_achievements},
            {"id": 12, "title": "Daily Grinder", "description": "Play 5 games in a day", "reward": 3000, "points": 30, "unlocked": games_today >= 5, "category": "streaks", "icon": "fas fa-calendar-day", "current_value": games_today, "target_value": 5, "progress_percentage": min(100, (games_today / 5) * 100), "cash_reward": 3000, "claimed": 12 in claimed_achievements},
            {"id": 13, "title": "Addicted", "description": "Play 20 games in a day", "reward": 8000, "points": 80, "unlocked": games_today >= 20, "category": "streaks", "icon": "fas fa-calendar-day", "current_value": games_today, "target_value": 20, "progress_percentage": min(100, (games_today / 20) * 100), "cash_reward": 8000, "claimed": 13 in claimed_achievements},
            {"id": 14, "title": "Referral Starter", "description": "Refer 5 users", "reward": 10000, "points": 100, "unlocked": referrals >= 5, "category": "special", "icon": "fas fa-users", "current_value": referrals, "target_value": 5, "progress_percentage": min(100, (referrals / 5) * 100), "cash_reward": 10000, "claimed": 14 in claimed_achievements},
            {"id": 15, "title": "Referral Master", "description": "Refer 20 users", "reward": 30000, "points": 300, "unlocked": referrals >= 20, "category": "special", "icon": "fas fa-users", "current_value": referrals, "target_value": 20, "progress_percentage": min(100, (referrals / 20) * 100), "cash_reward": 30000, "claimed": 15 in claimed_achievements},
            {"id": 16, "title": "Transaction Veteran", "description": "10+ transactions", "reward": 4000, "points": 40, "unlocked": total_tx >= 10, "category": "special", "icon": "fas fa-exchange-alt", "current_value": total_tx, "target_value": 10, "progress_percentage": min(100, (total_tx / 10) * 100), "cash_reward": 4000, "claimed": 16 in claimed_achievements}
        ]

        total_achievements = len(achievements_data)
        unlocked_achievements = sum(1 for a in achievements_data if a['unlocked'])
        unlocked_not_claimed = sum(1 for a in achievements_data if a['unlocked'] and not a['claimed'])
        total_points = sum(a['points'] for a in achievements_data if a['unlocked'])

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
        app.logger.error(f"Achievements error: {e}")
        return jsonify({"success": False, "message": f"Failed to load achievements: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/achievements/claim', methods=['POST'])
@require_auth
def claim_achievement_rewards():
    user = get_current_user()

    if not acquire_claim_lock(user['id'], 'ACHIEVEMENTS'):
        return jsonify({"success": False, "message": "Please wait before claiming again"}), 429

    try:
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
        release_claim_lock(user['id'], 'ACHIEVEMENTS')

@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
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

@app.route('/api/banking/verify-account', methods=['POST'])
@require_auth
def verify_bank_account():
    data = request.get_json()
    bank_code = data.get('bank_code')
    account_number = data.get('account_number')
    
    if not bank_code or not account_number:
        return jsonify({"success": False, "message": "Bank code and account number required"}), 400
    
    if not account_number.isdigit() or len(account_number) < 10:
        return jsonify({"success": False, "message": "Invalid account number"}), 400
    
    try:
        # USE TEST KEYS FOR VERIFICATION (FREE)
        verification_key = PAYSTACK_TEST_SECRET_KEY or PAYSTACK_SECRET_KEY

        headers = {
            'Authorization': f'Bearer {verification_key}',
            'Content-Type': 'application/json'
        }
        
        url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('status'):
            account_name = data['data']['account_name']
            return jsonify({
                "success": True,
                "account_name": account_name,
                "account_number": account_number,
                "bank_code": bank_code
            })
        else:
            error_msg = data.get('message', 'Unable to verify account')
            if 'invalid' in error_msg.lower():
                error_msg = "Invalid account number. Please check and try again."
            elif 'bank' in error_msg.lower():
                error_msg = "Invalid bank selected. Please choose a valid bank."
            
            return jsonify({
                "success": False,
                "message": error_msg
            }), 400
            
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "Verification timed out. Please try again."}), 408
    except Exception as e:
        app.logger.error(f"Bank verification error: {e}")
        return jsonify({"success": False, "message": "Failed to verify account. Please try again."}), 500

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

    if amount < get_min_withdrawal():
        return jsonify({"success": False, "message": f"Min withdrawal: ₦{get_min_withdrawal():,.0f}"}), 400

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
        new_balance = update_user_balance(user['id'], -amount)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        tx_id = f"TX-{int(datetime.utcnow().timestamp())}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                      (tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING', json.dumps({'bc':bank_code,'an':account_number,'nm':account_name}), datetime.utcnow().isoformat()))
        conn.commit()

        app.logger.info(f"Withdrawal requested by {user['username']}: {amount} to {bank_code}:{account_number}")

        return jsonify({
            "success": True,
            "message": "Withdrawal submitted successfully",
            "transaction_id": tx_id,
            "new_balance": new_balance
        })

    except Exception as e:
        app.logger.error(f"Withdrawal error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/whatsapp/numbers', methods=['GET'])
def get_whatsapp_numbers():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT number, label FROM whatsapp_numbers WHERE is_active = TRUE ORDER BY created_at DESC')
        numbers = []

        for row in cursor.fetchall():
            numbers.append({'number': row[0], 'label': row[1] or 'Support'})

        return jsonify({"success": True, "numbers": numbers})

    except Exception as e:
        app.logger.error(f"WhatsApp numbers error: {e}")
        return jsonify({"success": False, "message": "Failed to load numbers"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/paystack/initialize', methods=['POST'])
@require_auth
def initialize_paystack_payment():
    user = get_current_user()
    data = request.get_json()

    email = data.get('email')
    amount = data.get('amount')

    if not email:
        return jsonify({"success": False, "message": "Email address required"}), 400

    if not amount or amount < 500:
        return jsonify({"success": False, "message": "Minimum amount is ₦500"}), 400

    try:
        amount_kobo = int(amount * 100)
        reference = f"FLEX-{secrets.token_hex(8)}"

        # USE LIVE KEYS FOR REAL PAYMENTS
        payment_key = PAYSTACK_LIVE_SECRET_KEY or PAYSTACK_SECRET_KEY

        headers = {
            'Authorization': f'Bearer {payment_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'email': email,
            'amount': amount_kobo,
            'reference': reference,
            'callback_url': PAYSTACK_CALLBACK_URL,
            'metadata': json.dumps({
                'user_id': user['id'],
                'username': user['username'],
                'coupon_amount': amount,
                'type': 'coupon_purchase',
                'email': email
            })
        }

        response = requests.post('https://api.paystack.co/transaction/initialize', headers=headers, json=payload)
        data = response.json()

        if data.get('status'):
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                          (f"PAY-{secrets.token_hex(8)}", user['id'], 'PAYSTACK_INIT', amount, 'PENDING',
                           json.dumps({
                               'reference': reference,
                               'email': email,
                               'amount': amount,
                               'authorization_url': data['data']['authorization_url'],
                               'bank_transfer': data['data'].get('bank_transfer'),
                               'expires_at': (datetime.utcnow() + timedelta(minutes=60)).isoformat()
                           }),
                           datetime.utcnow().isoformat()))
            conn.commit()
            return_db_connection(conn)

            return jsonify({
                "success": True,
                "authorization_url": data['data']['authorization_url'],
                "reference": reference,
                "bank_transfer_details": data['data'].get('bank_transfer'),
                "expires_at": (datetime.utcnow() + timedelta(minutes=60)).isoformat(),
                "message": "Payment initialized successfully"
            })
        else:
            app.logger.error(f"Paystack init error: {data}")
            return jsonify({"success": False, "message": data.get('message', 'Payment initialization failed')}), 400

    except Exception as e:
        app.logger.error(f"Paystack initialize error: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"Payment initialization failed: {str(e)}"}), 500

@app.route('/api/paystack/callback', methods=['GET', 'POST'])
def paystack_callback():
    try:
        reference = request.args.get('reference')

        if not reference:
            return redirect(f"{CONFIG.FRONTEND_DIR}/payment-failed.html?error=No+reference+provided")

        # USE LIVE KEYS TO VERIFY PAYMENTS
        verification_key = PAYSTACK_LIVE_SECRET_KEY or PAYSTACK_SECRET_KEY

        headers = {
            'Authorization': f'Bearer {verification_key}',
            'Content-Type': 'application/json'
        }

        response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers, timeout=15)
        data = response.json()

        if not data.get('status'):
            app.logger.error(f"Paystack verification failed: {data}")
            return redirect(f"{CONFIG.FRONTEND_DIR}/payment-failed.html?ref={reference}&error=Verification+failed")

        transaction = data['data']

        if transaction['status'] != 'success':
            app.logger.warning(f"Transaction not successful: {transaction['status']}")
            return redirect(f"{CONFIG.FRONTEND_DIR}/payment-failed.html?ref={reference}&error=Transaction+not+successful")

        email = transaction['customer']['email']
        amount = transaction['amount'] / 100
        payment_method = transaction.get('channel', 'bank_transfer')
        metadata = json.loads(transaction.get('metadata', '{}'))
        user_id = metadata.get('user_id')

        MIN_COUPON_AMOUNT = CONFIG.MIN_COUPON_AMOUNT
        coupon_code = None
        email_sent = False

        if amount >= MIN_COUPON_AMOUNT:
            app.logger.info(f"Amount ₦{amount} qualifies for coupon (>= ₦{MIN_COUPON_AMOUNT})")
            coupon_code = generate_and_save_coupon(amount, email, reference)

            if coupon_code:
                email_sent = send_coupon_email(email, coupon_code, amount)
                app.logger.info(f"Coupon {coupon_code} sent to {email}")
            else:
                app.logger.error(f"Failed to generate coupon for {email}")
        else:
            app.logger.info(f"Amount ₦{amount} does NOT qualify for coupon (< ₦{MIN_COUPON_AMOUNT})")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('UPDATE transactions SET status = %s, details = %s WHERE type = \'PAYSTACK_INIT\' AND details LIKE %s',
                      ('COMPLETED', json.dumps({
                          'reference': reference,
                          'coupon_code': coupon_code if coupon_code else None,
                          'email': email,
                          'amount': amount,
                          'payment_method': payment_method,
                          'coupon_sent': email_sent,
                          'coupon_generated': coupon_code is not None,
                          'minimum_amount_required': MIN_COUPON_AMOUNT,
                          'payment_accepted': True,
                          'paystack_data': transaction
                      }), f'%{reference}%'))
        conn.commit()
        return_db_connection(conn)

        app.logger.info(f"Payment processed: {reference}, amount: ₦{amount}, coupon: {coupon_code if coupon_code else 'NOT GENERATED'}")

        if coupon_code:
            return redirect(f"{CONFIG.FRONTEND_DIR}/payment-success.html?ref={reference}")
        else:
            return redirect(f"{CONFIG.FRONTEND_DIR}/payment-success.html?ref={reference}&nocoupon=true")

    except requests.exceptions.Timeout:
        app.logger.error("Paystack verification timeout")
        return redirect(f"{CONFIG.FRONTEND_DIR}/payment-failed.html?error=Timeout+verifying+payment")
    except Exception as e:
        app.logger.error(f"Paystack callback error: {e}")
        app.logger.error(traceback.format_exc())
        return redirect(f"{CONFIG.FRONTEND_DIR}/payment-failed.html?error={str(e)}")

@app.route('/api/paystack/status/<reference>', methods=['GET'])
def get_paystack_status(reference):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT status, details FROM transactions WHERE type = \'PAYSTACK_INIT\' AND details LIKE %s ORDER BY timestamp DESC LIMIT 1', (f'%{reference}%',))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Transaction not found"}), 404

        status = row[0]
        details = json.loads(row[1]) if row[1] else {}

        return jsonify({
            "success": True,
            "status": status,
            "coupon_code": details.get('coupon_code'),
            "email": details.get('email'),
            "amount": details.get('amount'),
            "payment_method": details.get('payment_method', 'bank_transfer'),
            "coupon_generated": details.get('coupon_generated', False),
            "coupon_sent": details.get('coupon_sent', False),
            "payment_accepted": details.get('payment_accepted', True),
            "minimum_amount_required": details.get('minimum_amount_required', 8000),
            "message": "Coupon generated and sent!" if details.get('coupon_generated') else f"Payment accepted. Minimum ₦{details.get('minimum_amount_required', 8000)} required for coupon."
        })

    except Exception as e:
        app.logger.error(f"Payment status error: {e}")
        return jsonify({"success": False, "message": "Failed to get status"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id, username, balance, referral_code, withdrawal_restricted, withdrawal_limit, created_at, last_login, is_admin FROM users ORDER BY id DESC')
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
        new_balance = update_user_balance(user_id, amount)

        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500

        tx_id = f"ADJ-{secrets.token_hex(8)}"
        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                      (tx_id, user_id, 'ADMIN_ADJUSTMENT', amount, 'COMPLETED', json.dumps({"note": note[:80] if note else ""}), datetime.utcnow().isoformat()))
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
        cursor.execute('SELECT t.*, u.username FROM transactions t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.timestamp DESC LIMIT 100')
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
    min_withdrawal = data.get('min_withdrawal', None)

    if not isinstance(global_withdrawal_days, list):
        return jsonify({"success": False, "message": "Invalid withdrawal days format"}), 400

    if min_withdrawal is not None:
        try:
            min_withdrawal = float(min_withdrawal)
            if min_withdrawal < 0:
                return jsonify({"success": False, "message": "Minimum withdrawal cannot be negative"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid minimum withdrawal amount"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        try:
            cursor.execute('ALTER TABLE admin_settings ADD COLUMN min_withdrawal REAL DEFAULT 100000')
            conn.commit()
        except Exception:
            pass

        ph = '%s' if os.environ.get('DATABASE_URL') else '?'

        if min_withdrawal is not None:
            cursor.execute(f'UPDATE admin_settings SET whatsapp_link = {ph}, telegram_link = {ph}, facebook_link = {ph}, global_withdrawal_days = {ph}, min_withdrawal = {ph}',
                          (whatsapp_link, telegram_link, facebook_link, json.dumps(global_withdrawal_days), min_withdrawal))
        else:
            cursor.execute(f'UPDATE admin_settings SET whatsapp_link = {ph}, telegram_link = {ph}, facebook_link = {ph}, global_withdrawal_days = {ph}',
                          (whatsapp_link, telegram_link, facebook_link, json.dumps(global_withdrawal_days)))

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

@app.route('/api/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@require_admin
def admin_set_user_custom_days(user_id):
    data = request.get_json()
    days = data.get('days', [])

    if not isinstance(days, list):
        return jsonify({"success": False, "message": "Invalid days format"}), 400

    valid_days = [day for day in days if isinstance(day, int) and 1 <= day <= 31]

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "User not found"}), 404

        cursor.execute('UPDATE users SET custom_withdrawal_days = %s WHERE id = %s', (json.dumps(valid_days) if valid_days else None, user_id))
        conn.commit()

        app.logger.info(f"Admin set custom withdrawal days for user {user_id}: {valid_days}")

        return jsonify({"success": True, "message": "Custom withdrawal days updated"})

    except Exception as e:
        app.logger.error(f"Set user custom days error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

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
        cursor.execute('SELECT user_id, amount, status FROM transactions WHERE id = %s', (transaction_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Transaction not found"}), 404

        user_id, amount, current_status = row[0], float(row[1]), row[2]

        if current_status != 'PENDING':
            return jsonify({"success": False, "message": f"Transaction already {current_status}"}), 400

        new_status = 'COMPLETED' if action == 'APPROVE' else 'FAILED'

        if action == 'REJECT':
            update_user_balance(user_id, amount)

        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (new_status, transaction_id))
        conn.commit()

        app.logger.info(f"Admin {action}d withdrawal {transaction_id} for user {user_id}, amount: {amount}")

        return jsonify({"success": True, "message": f"Withdrawal {action.lower()}ed successfully", "status": new_status})

    except Exception as e:
        app.logger.error(f"Approve withdrawal error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@require_admin
def admin_withdrawal_status_report():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id, username, balance, withdrawal_restricted, custom_withdrawal_days, withdrawal_limit, withdrawal_pin FROM users ORDER BY id')

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

@app.route('/api/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
def admin_toggle_user_admin(user_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
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

        return jsonify({"success": True, "message": f"User {username} {action}", "is_admin": new_admin_status})

    except Exception as e:
        app.logger.error(f"Toggle admin error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update admin status"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404

        username = row[0]

        if username == CONFIG.ADMIN_USERNAME:
            return jsonify({"success": False, "message": "Cannot delete original admin"}), 403

        cursor.execute('DELETE FROM transactions WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM game_plays WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()

        app.logger.warning(f"Admin deleted user: {username} (ID: {user_id})")

        return jsonify({"success": True, "message": f"User {username} deleted successfully"})

    except Exception as e:
        app.logger.error(f"Delete user error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete user"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
def admin_get_coupons():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT code, status FROM coupons ORDER BY code')
        coupons = []

        for row in cursor.fetchall():
            coupons.append({'code': row[0], 'status': row[1]})

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

        return jsonify({"success": True, "message": f"Reset {updated_count} used coupons to available"})

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

        return jsonify({"success": True, "message": f"Deleted all {deleted_count} coupons"})

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
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING', (code, 'AVAILABLE'))
                if cursor.rowcount > 0:
                    added_count += 1
            except:
                continue

        conn.commit()

        app.logger.info(f"Admin added {added_count} new coupon codes")

        return jsonify({"success": True, "message": f"Added {added_count} new coupon codes", "added": added_count})

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
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING', (code, 'AVAILABLE'))
                loaded += 1
            except:
                continue

        conn.commit()
        return_db_connection(conn)

        app.logger.info(f"Admin loaded {loaded} coupons from file")

        return jsonify({"success": True, "message": f"Loaded {loaded} coupons from file", "count": loaded})

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

@app.route('/api/admin/whatsapp-numbers', methods=['GET'])
@require_admin
def admin_get_whatsapp_numbers():
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
        cursor.execute('INSERT INTO tiktok_daily (date, tiktok_link, reward_amount) VALUES (%s, %s, %s) ON CONFLICT (date) DO UPDATE SET tiktok_link = EXCLUDED.tiktok_link, reward_amount = EXCLUDED.reward_amount',
                      (today, tiktok_link, CONFIG.TIKTOK_REWARD))
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
        cursor.execute('SELECT date, tiktok_link, reward_amount FROM tiktok_daily WHERE date >= %s ORDER BY date DESC LIMIT 7',
                      ((datetime.utcnow().date() - timedelta(days=7)).isoformat(),))
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

@app.route('/api/admin/database/clear', methods=['POST'])
@require_admin
def admin_clear_database():
    data = request.get_json()
    sudo_confirmation = data.get('sudo_confirmation', '')

    if sudo_confirmation != 'DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN':
        return jsonify({"success": False, "message": "Sudo confirmation required. Type: DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN"}), 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        app.logger.warning("Admin initiated database clearing - keeping only main admin")

        if os.environ.get('DATABASE_URL'):
            cursor.execute("BEGIN")

        cursor.execute("SELECT id, username FROM users WHERE username = %s", (CONFIG.ADMIN_USERNAME,))
        admin_row = cursor.fetchone()

        if not admin_row:
            return jsonify({"success": False, "message": "Main admin not found"}), 404

        admin_id = admin_row[0]
        admin_username = admin_row[1]

        cursor.execute("DELETE FROM users WHERE id != %s", (admin_id,))
        users_deleted = cursor.rowcount

        cursor.execute('UPDATE users SET balance = 500000.00, claimed_bonuses = 0, points = 0, game_stats = %s, last_game_timestamp = %s, last_achievement_check = %s, claimed_achievements = \'[]\' WHERE id = %s',
                      (json.dumps({"snake": {"high_score": 1200, "total_score": 5000}, "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3}, "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}}), datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), admin_id))

        cursor.execute("DELETE FROM transactions")
        transactions_deleted = cursor.rowcount

        cursor.execute("DELETE FROM game_plays")
        game_plays_deleted = cursor.rowcount

        cursor.execute("UPDATE coupons SET status = 'AVAILABLE'")
        coupons_reset = cursor.rowcount

        cursor.execute("DELETE FROM tiktok_daily")

        conn.commit()

        app.logger.warning(f"Database cleared: {users_deleted} users, {transactions_deleted} transactions, {game_plays_deleted} game plays removed")
        app.logger.warning(f"Coupons reset: {coupons_reset}")
        app.logger.warning(f"Admin account '{admin_username}' kept with reset stats")

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
        app.logger.error(f"Database clearing error: {e}")
        app.logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Failed to clear database: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/database/preview-clear', methods=['GET'])
@require_admin
def admin_preview_database_clear():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username != %s", (CONFIG.ADMIN_USERNAME,))
        users_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transactions")
        transactions_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM game_plays")
        game_plays_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM coupons")
        coupons_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'USED'")
        used_coupons_count = cursor.fetchone()[0]

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

@app.route('/api/admin/export-data', methods=['POST'])
@require_admin
def admin_export_data():
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
            output = io.StringIO()
            writer = csv.writer(output)

            if 'users' in export_data:
                writer.writerow(['=== USERS ==='])
                if export_data['users']:
                    headers = export_data['users'][0].keys()
                    writer.writerow(headers)
                    for user in export_data['users']:
                        writer.writerow([user.get(h, '') for h in headers])
                writer.writerow([])

            if 'transactions' in export_data:
                writer.writerow(['=== TRANSACTIONS ==='])
                if export_data['transactions']:
                    headers = export_data['transactions'][0].keys()
                    writer.writerow(headers)
                    for tx in export_data['transactions']:
                        writer.writerow([tx.get(h, '') for h in headers])
                writer.writerow([])

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

@app.route('/api/admin/database/export-all', methods=['POST'])
@require_admin
def admin_export_all_data():
    try:
        conn = get_db()
        cursor = conn.cursor()

        data = {}

        cursor.execute('SELECT id, username, balance, referral_code, referred_by, is_admin, created_at, last_login, claimed_bonuses, points, game_stats, contact, profile_picture, ui_theme, withdrawal_restricted, custom_withdrawal_days, withdrawal_limit, last_game_timestamp, last_achievement_check, claimed_achievements FROM users')
        users = []
        for row in cursor.fetchall():
            user_dict = {}
            columns = [col[0] for col in cursor.description]
            for i, col in enumerate(columns):
                user_dict[col] = row[i]
            users.append(user_dict)
        data['users'] = users

        cursor.execute('SELECT * FROM transactions')
        transactions = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['transactions'] = transactions

        cursor.execute('SELECT * FROM game_plays')
        game_plays = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['game_plays'] = game_plays

        cursor.execute('SELECT * FROM coupons')
        coupons = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['coupons'] = coupons

        cursor.execute('SELECT * FROM whatsapp_numbers')
        whatsapp_numbers = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['whatsapp_numbers'] = whatsapp_numbers

        cursor.execute('SELECT * FROM tiktok_daily')
        tiktok_daily = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['tiktok_daily'] = tiktok_daily

        cursor.execute('SELECT * FROM banks')
        banks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['banks'] = banks

        cursor.execute('SELECT * FROM admin_settings')
        admin_settings = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        data['admin_settings'] = admin_settings

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

        json_data = json.dumps(data, indent=2, default=str)
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
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400

        if not file.filename.endswith('.flexia'):
            return jsonify({"success": False, "message": "File must be .flexia format"}), 400

        json_data = file.read().decode('utf-8')
        data = json.loads(json_data)

        if '_metadata' not in data:
            return jsonify({"success": False, "message": "Invalid .flexia file format"}), 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            if os.environ.get('DATABASE_URL'):
                cursor.execute("BEGIN")

            tables_to_clear = ['users', 'transactions', 'game_plays', 'coupons', 'whatsapp_numbers', 'tiktok_daily']

            for table in tables_to_clear:
                try:
                    cursor.execute(f'DELETE FROM {table}')
                except:
                    pass

            imported_counts = {}

            if 'users' in data:
                for user in data['users']:
                    try:
                        is_admin_value = user.get('is_admin', False)
                        if os.environ.get('DATABASE_URL'):
                            is_admin_value = bool(is_admin_value)
                        else:
                            is_admin_value = 1 if is_admin_value else 0

                        withdrawal_restricted = user.get('withdrawal_restricted', False)
                        if os.environ.get('DATABASE_URL'):
                            withdrawal_restricted = bool(withdrawal_restricted)
                        else:
                            withdrawal_restricted = 1 if withdrawal_restricted else 0

                        cursor.execute('INSERT INTO users (id, username, balance, referral_code, referred_by, is_admin, created_at, last_login, claimed_bonuses, points, game_stats, contact, profile_picture, ui_theme, withdrawal_restricted, custom_withdrawal_days, withdrawal_limit, last_game_timestamp, last_achievement_check, claimed_achievements) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                                      (user.get('id'), user.get('username'), user.get('balance', 0), user.get('referral_code'), user.get('referred_by'), is_admin_value, user.get('created_at'), user.get('last_login'), user.get('claimed_bonuses', 0), user.get('points', 0), user.get('game_stats'), user.get('contact'), user.get('profile_picture'), user.get('ui_theme', 'light'), withdrawal_restricted, user.get('custom_withdrawal_days'), user.get('withdrawal_limit', 0), user.get('last_game_timestamp'), user.get('last_achievement_check'), user.get('claimed_achievements', '[]')))
                        imported_counts['users'] = imported_counts.get('users', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping user {user.get('username')}: {e}")

            if 'transactions' in data:
                for tx in data['transactions']:
                    try:
                        cursor.execute('INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                      (tx.get('id'), tx.get('user_id'), tx.get('type'), tx.get('amount'), tx.get('status'), tx.get('details'), tx.get('timestamp')))
                        imported_counts['transactions'] = imported_counts.get('transactions', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping transaction {tx.get('id')}: {e}")

            if 'game_plays' in data:
                for play in data['game_plays']:
                    try:
                        cursor.execute('INSERT INTO game_plays (id, user_id, game_type, play_date, created_at) VALUES (%s, %s, %s, %s, %s)',
                                      (play.get('id'), play.get('user_id'), play.get('game_type'), play.get('play_date'), play.get('created_at')))
                        imported_counts['game_plays'] = imported_counts.get('game_plays', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping game play {play.get('id')}: {e}")

            if 'coupons' in data:
                for coupon in data['coupons']:
                    try:
                        cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)',
                                      (coupon.get('code'), coupon.get('status', 'AVAILABLE')))
                        imported_counts['coupons'] = imported_counts.get('coupons', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping coupon {coupon.get('code')}: {e}")

            if 'whatsapp_numbers' in data:
                for num in data['whatsapp_numbers']:
                    try:
                        cursor.execute('INSERT INTO whatsapp_numbers (id, number, label, is_active, created_at) VALUES (%s, %s, %s, %s, %s)',
                                      (num.get('id'), num.get('number'), num.get('label'), num.get('is_active'), num.get('created_at')))
                        imported_counts['whatsapp_numbers'] = imported_counts.get('whatsapp_numbers', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping WhatsApp number {num.get('number')}: {e}")

            if 'tiktok_daily' in data:
                for tiktok in data['tiktok_daily']:
                    try:
                        cursor.execute('INSERT INTO tiktok_daily (id, date, tiktok_link, reward_amount, created_at) VALUES (%s, %s, %s, %s, %s)',
                                      (tiktok.get('id'), tiktok.get('date'), tiktok.get('tiktok_link'), tiktok.get('reward_amount'), tiktok.get('created_at')))
                        imported_counts['tiktok_daily'] = imported_counts.get('tiktok_daily', 0) + 1
                    except Exception as e:
                        app.logger.warning(f"Skipping TikTok daily {tiktok.get('date')}: {e}")

            if 'admin_settings' in data:
                for setting in data['admin_settings']:
                    try:
                        cursor.execute('INSERT INTO admin_settings (id, whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) VALUES (%s, %s, %s, %s, %s)',
                                      (setting.get('id'), setting.get('whatsapp_link'), setting.get('telegram_link'), setting.get('facebook_link'), setting.get('global_withdrawal_days')))
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

@app.route('/api/admin/backup/trigger', methods=['POST'])
@require_admin
def trigger_backup():
    try:
        backup_file = backup_database()

        if backup_file:
            app.logger.info(f"Manual backup triggered: {backup_file}")
            return jsonify({"success": True, "message": "Backup created successfully", "backup_file": backup_file})
        else:
            return jsonify({"success": False, "message": "Backup creation failed"}), 500

    except Exception as e:
        app.logger.error(f"Manual backup error: {str(e)}")
        return jsonify({"success": False, "message": f"Backup error: {str(e)}"}), 500

@app.route('/api/admin/backup/list', methods=['GET'])
@require_admin
def list_backups():
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

        return jsonify({"success": True, "backups": backups})

    except Exception as e:
        app.logger.error(f"List backups error: {str(e)}")
        return jsonify({"success": False, "message": f"Error listing backups: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def api_health():
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

        health_data = {
            "status": "online",
            "service": "FLEXIA API",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": get_uptime(),
            "database": db_status,
            "version": "17.2",
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
            "version": "17.2"
        }), 503

def get_uptime():
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.utcnow()

    uptime = datetime.utcnow() - get_uptime.start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{days}d {hours}h {minutes}m {seconds}s"

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404

    if path == '' or path is None:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, path)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'

    app.logger.info(f"Starting Flexia Platform v17.2 on port {port} (debug: {debug})")
    app.logger.info(f"Frontend directory: {CONFIG.FRONTEND_DIR}")
    app.logger.info(f"Database: {'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'}")
    app.logger.info(f"Paystack Integration: Enabled")
    app.logger.info(f"Brevo API: {'Configured' if BREVO_API_KEY else 'Not configured'}")
    app.logger.info(f"Session Management: Enabled")
    app.logger.info(f"Game Limits: Enabled")
    app.logger.info(f"Admin: {CONFIG.ADMIN_USERNAME}")
    app.logger.info(f"Success Page: {CONFIG.FRONTEND_DIR}/payment-success.html")
    app.logger.info(f"Failed Page: {CONFIG.FRONTEND_DIR}/payment-failed.html")
    app.logger.info(f"Bank Verification: Enabled via Paystack")

    app.run(host='0.0.0.0', port=port, debug=debug)
