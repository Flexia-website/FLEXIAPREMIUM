# backend/app.py - FIXED PRODUCTION VERSION v11.1
# FLEXIA Platform - ALL FIXES APPLIED + COMPLETE ENDPOINTS

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, send_from_directory, redirect
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
    """Initialize database connection pool"""
    global db_pool
    
    if os.environ.get('DATABASE_URL'):
        try:
            db_pool = SimpleConnectionPool(
                1,  # min connections
                20, # max connections
                dsn=os.environ['DATABASE_URL']
            )
            app.logger.info('Database connection pool initialized')
        except Exception as e:
            app.logger.error(f'Failed to initialize connection pool: {str(e)}')
            db_pool = None

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

# ======================= INITIALIZATION =======================
def add_missing_columns():
    """Add missing columns if they don't exist"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            # Check and add last_game_timestamp for PostgreSQL
            cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' and column_name='last_game_timestamp'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN last_game_timestamp TEXT")
                app.logger.info("Added missing column: last_game_timestamp to users table")
        else:
            # SQLite - check pragma
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'last_game_timestamp' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN last_game_timestamp TEXT")
                app.logger.info("Added missing column: last_game_timestamp to users table")
        
        conn.commit()
        app.logger.info("Database column verification complete")
    except Exception as e:
        app.logger.error(f"Error adding missing columns: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None

    # Users table - FIXED WITH ALL COLUMNS
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
            last_game_timestamp TEXT
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
            last_game_timestamp TEXT
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
        )''',
        '''CREATE TABLE IF NOT EXISTS user_game_locks (
            user_id INTEGER PRIMARY KEY,
            lock_until TEXT,
            game_type TEXT
        )'''
    ]
    
    for sql in tables_sql:
        try:
            cursor.execute(sql)
        except Exception as e:
            app.logger.error(f"Error creating table: {e}")

    # Insert default banks - FIXED
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

    # Admin user
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s' if is_postgres else 'SELECT COUNT(*) as count FROM users WHERE username = ?', ("flexiaadmin",))
    admin_count = cursor.fetchone()[0]
    if admin_count == 0:
        admin_pass = generate_password_hash("Flexiaadmin")
        game_stats = json.dumps({
            "snake": {"high_score": 1200, "total_score": 5000},
            "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
            "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
        })
        pin_hash = generate_password_hash("4567")
        if is_postgres:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme, last_game_timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                "flexiaadmin", admin_pass, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, False, pin_hash, "", "", "light", datetime.utcnow().isoformat()
            ))
        else:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme, last_game_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "flexiaadmin", admin_pass, 500000.00, "ADM0001", 1,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, 0, pin_hash, "", "", "light", datetime.utcnow().isoformat()
            ))
        app.logger.warning("\n🚨 FLEXIA ADMIN ACCOUNT CREATED 🚨")
        app.logger.warning("Username: flexiaadmin")
        app.logger.warning("Initial Password: Flexiaadmin")
        app.logger.warning("Default Withdrawal PIN: 4567")
        app.logger.warning("🔐 Change both after first login!\n")

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

def check_game_cooldown(user_id, game_type):
    """Check if user is in cooldown for a specific game"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT last_game_timestamp FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            last_game = datetime.fromisoformat(row[0])
            now = datetime.utcnow()
            # 2 second cooldown between games
            if (now - last_game).total_seconds() < 2:
                return False
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

def can_play_today(user_id, game_type, max_plays=10):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f"SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}",
                       (user_id, game_type, today))
        count = cursor.fetchone()[0]
        return count < max_plays
    except Exception as e:
        app.logger.error(f"Play check error: {e}")
        return False
    finally:
        return_db_connection(conn)

def record_game_play(user_id, game_type):
    """Record a game play (idempotent)"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        # Check if already recorded today
        cursor.execute(f"SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}",
                       (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(f"INSERT INTO game_plays (user_id, game_type, play_date) VALUES ({ph}, {ph}, {ph})",
                           (user_id, game_type, today))
            conn.commit()
    except Exception as e:
        app.logger.error(f"Record game play error: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)

def is_withdrawal_day(user_id=None):
    today = datetime.utcnow().day
    if user_id is None:
        return today in get_global_withdrawal_days()
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'SELECT withdrawal_restricted, custom_withdrawal_days FROM users WHERE id = {ph}', (user_id,))
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
    finally:
        return_db_connection(conn)

def grant_achievement_rewards(user_id):
    """Calculate and grant achievement rewards - FIXED VERSION"""
    app.logger.info(f"Granting achievement rewards for user {user_id}")
    
    # Get a fresh connection for this function ONLY
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    
    try:
        # Get user data
        cursor.execute(f'SELECT balance, game_stats, referral_code, points FROM users WHERE id = {ph}', (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return None
        
        balance = float(row[0]) if row[0] else 0
        game_stats_str = row[1] if row[1] else '{}'
        referral_code = row[2] if row[2] else ''
        current_points = int(row[3]) if row[3] else 0
        
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

        # Define achievements
        achievements = [
            {"unlocked": total_games >= 1, "reward": 500, "points": 10},
            {"unlocked": total_games >= 50, "reward": 5000, "points": 50},
            {"unlocked": total_games >= 200, "reward": 15000, "points": 150},
            {"unlocked": snake_high >= 1000, "reward": 7500, "points": 75},
            {"unlocked": coin_streak >= 10, "reward": 10000, "points": 100},
            {"unlocked": coin_total >= 100, "reward": 6000, "points": 60},
            {"unlocked": plinko_wins >= 50, "reward": 8000, "points": 80},
            {"unlocked": balance >= 1000, "reward": 1000, "points": 15},
            {"unlocked": balance >= 50000, "reward": 10000, "points": 100},
            {"unlocked": balance >= 200000, "reward": 25000, "points": 200},
            {"unlocked": total_withdrawals >= 1, "reward": 5000, "points": 50},
            {"unlocked": games_today >= 5, "reward": 3000, "points": 30},
            {"unlocked": games_today >= 20, "reward": 8000, "points": 80},
            {"unlocked": referrals >= 5, "reward": 10000, "points": 100},
            {"unlocked": referrals >= 20, "reward": 30000, "points": 300},
            {"unlocked": total_tx >= 10, "reward": 4000, "points": 40}
        ]

        total_reward = sum(ach["reward"] for ach in achievements if ach["unlocked"])
        total_points = sum(ach["points"] for ach in achievements if ach["unlocked"])
        
        # Only update if there are new points
        if total_points <= current_points:
            cursor.close()
            conn.close()
            return balance

        new_balance = balance + total_reward
        
        # Update user balance and points
        cursor.execute(f'UPDATE users SET balance = {ph}, points = {ph} WHERE id = {ph}', 
                       (new_balance, total_points, user_id))
        
        # Record achievement transaction if reward > 0
        if total_reward > 0:
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute(f'''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', (
                tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
                json.dumps({"source": "auto_grant"}), datetime.utcnow().isoformat()
            ))
        
        conn.commit()
        app.logger.info(f"Granted achievement rewards to user {user_id}: ₦{total_reward}, {total_points} points")
        
        cursor.close()
        conn.close()
        return new_balance
        
    except Exception as e:
        app.logger.error(f"Achievement grant error for user {user_id}: {e}")
        app.logger.error(traceback.format_exc())
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return None

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
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()
    run_backup_scheduler()  # Start backup scheduler

# ======================= STATIC FILES =======================
@app.route('/')
def index():
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= DEBUG ENDPOINTS =======================
@app.route('/api/debug/db-status', methods=['GET'])
def db_status():
    try:
        conn = get_db()
        cursor = conn.cursor()
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
        available_coupons = cursor.fetchone()[0]
        return_db_connection(conn)
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite",
            "connection_pool": "active" if db_pool else "inactive"
        })
    except Exception as e:
        app.logger.error(f"DB status error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ======================= ENHANCED HEALTH CHECK =======================
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
            "version": "11.1",
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
            "version": "11.1"
        }), 503

# ======================= BACKUP ENDPOINTS =======================
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
            points, claimed_bonuses, last_game_timestamp
        ) VALUES (
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}
        )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, is_admin_value,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            admin_pw_changed, None, withdrawal_restricted, 0.00, 0, 0, datetime.utcnow().isoformat()
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
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
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

@app.route('/api/user/profile')
@require_auth
def get_user_profile():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
    # grant_achievement_rewards(user['id'])  # REMOVED
    
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
                "ui_theme": fresh_user.get('ui_theme', 'light')
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

# ================= USER SETTINGS =================
@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    user = get_current_user()
    data = request.get_json()
    picture_url = sanitize_input(data.get('picture_url', ''))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s', (picture_url, user['id']))
        conn.commit()
        app.logger.info(f"User {user['username']} updated profile picture")
        return jsonify({"success": True, "message": "Profile picture updated"})
    except Exception as e:
        app.logger.error(f"Profile picture error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_theme():
    user = get_current_user()
    data = request.get_json()
    theme = 'dark' if data.get('dark_mode') else 'light'
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s', (theme, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Theme updated"})
    except Exception as e:
        app.logger.error(f"Theme error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

# ================= PASSWORD & PIN =================
@app.route('/api/user/change-password', methods=['POST'])
@require_auth
def change_password():
    user = get_current_user()
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password or len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400
    
    if not check_password_hash(user['password'], old_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET password = %s WHERE id = %s",
                       (generate_password_hash(new_password), user['id']))
        conn.commit()
        app.logger.info(f"User {user['username']} changed password")
        return jsonify({"success": True, "message": "Password updated"})
    except Exception as e:
        app.logger.error(f"Password change error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def admin_change_password():
    """Admin: Change their own password"""
    admin_user = get_current_user()
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Both fields required"}), 400
    
    if len(new_password) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters"}), 400
    
    # Verify current password
    if not check_password_hash(admin_user['password'], current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET password = %s, admin_password_changed = %s WHERE id = %s',
                       (generate_password_hash(new_password), True, admin_user['id']))
        conn.commit()
        
        app.logger.info(f"Admin {admin_user['username']} changed their password")
        return jsonify({"success": True, "message": "Password changed successfully"})
        
    except Exception as e:
        app.logger.error(f"Admin password change error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to change password"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@require_auth
def set_withdrawal_pin():
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')
    
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        return jsonify({"success": False, "message": "PIN must be 4-6 digits"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s', (generate_password_hash(pin), user['id']))
        conn.commit()
        app.logger.info(f"User {user['username']} set withdrawal PIN")
        return jsonify({"success": True, "message": "PIN set successfully"})
    except Exception as e:
        app.logger.error(f"PIN error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
def verify_withdrawal_pin():
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')
    withdrawal_pin = _safe_get(user, 'withdrawal_pin')
    
    if not withdrawal_pin:
        return jsonify({"success": False, "message": "No PIN set"}), 400
    
    if not check_password_hash(withdrawal_pin, pin):
        app.logger.warning(f"Invalid PIN attempt for user: {user['username']}")
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    
    return jsonify({"success": True, "message": "PIN verified"})

# ================= GAME ENDPOINTS =================
@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=10):
        app.logger.warning(f"Rate limit exceeded for snake game from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    
    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "Invalid apple count"}), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'snake'):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    if not can_play_today(user['id'], 'snake', max_plays=20):
        return jsonify({"success": False, "message": "Max 20 plays per day"}), 403
    
    # 🔥 ADDED: Check for duplicate recent claims (within 3 seconds)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT COUNT(*) FROM transactions 
        WHERE user_id = %s AND type = 'SNAKE_REWARD' 
        AND timestamp > %s
        ''', (user['id'], (datetime.utcnow() - timedelta(seconds=3)).isoformat()))
        recent_claims = cursor.fetchone()[0]
        
        if recent_claims > 0:
            app.logger.warning(f"Duplicate snake claim attempt from user {user['id']}")
            return jsonify({"success": False, "message": "Please wait before claiming again"}), 429
    except Exception as e:
        app.logger.error(f"Duplicate check error: {e}")
    finally:
        return_db_connection(conn)
    
    reward = apples * CONFIG.SNAKE_REWARD
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        new_balance = float(user['balance']) + reward
        
        game_stats = json.loads(user.get('game_stats', '{}'))
        snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
        score = apples * 10
        
        if score > snake_stats['high_score']:
            snake_stats['high_score'] = score
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        game_stats['snake'] = snake_stats
        
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        
        # Update last game timestamp
        update_last_game_timestamp(user['id'])
        
        # Record game play
        record_game_play(user['id'], 'snake')
        
        # 🔥 ADDED: Record the transaction to prevent duplicates
        tx_id = f"SNK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "snake", "apples": apples}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} played snake: {apples} apples, reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "transaction_id": tx_id  # Send transaction ID back
        })
        
    except Exception as e:
        app.logger.error(f"Snake error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=15):
        app.logger.warning(f"Rate limit exceeded for coinflip game from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    won = data.get('won', False)
    
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'coinflip'):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    if not can_play_today(user['id'], 'coinflip', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    
    payout = bet * 2 if won else 0
    new_balance = float(user['balance']) + payout - bet
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        game_stats = json.loads(user.get('game_stats', '{}'))
        coinflip_stats = game_stats.get('coin_flip', {'wins': 0, 'losses': 0, 'current_streak': 0})
        
        if won:
            coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
            coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
        else:
            coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
            coinflip_stats['current_streak'] = 0
        
        game_stats['coin_flip'] = coinflip_stats
        
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        
        # Update last game timestamp
        update_last_game_timestamp(user['id'])
        
        # Record game play
        record_game_play(user['id'], 'coinflip')
        
        # Record transaction
        tx_id = f"COIN-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'COINFLIP_REWARD' if won else 'COINFLIP_LOSS', 
            payout if won else -bet, 'COMPLETED',
            json.dumps({"game": "coinflip", "bet": bet, "won": won}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} played coinflip: bet {bet}, won: {won}, payout: {payout}")
        
        return jsonify({
            "success": True,
            "payout": payout if won else 0,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Coinflip error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=10):
        app.logger.warning(f"Rate limit exceeded for plinko game from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    multiplier = float(data.get('multiplier', 0))
    
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    
    if multiplier not in [0.5, 3, 10]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'plinko'):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    if not can_play_today(user['id'], 'plinko', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    
    win = bet * multiplier
    new_balance = float(user['balance']) + win - bet
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        game_stats = json.loads(user.get('game_stats', '{}'))
        plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
        
        plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
        
        if win > bet:
            plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
            if win > plinko_stats.get('highest_win', 0):
                plinko_stats['highest_win'] = win
        
        game_stats['plinko'] = plinko_stats
        
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        
        # Update last game timestamp
        update_last_game_timestamp(user['id'])
        
        # Record game play
        record_game_play(user['id'], 'plinko')
        
        # Record transaction
        tx_id = f"PLK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'PLINKO_WIN' if win > bet else 'PLINKO_LOSS', 
            win - bet, 'COMPLETED',
            json.dumps({"game": "plinko", "bet": bet, "multiplier": multiplier, "win": win}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} played plinko: bet {bet}, multiplier: {multiplier}, win: {win}")
        
        return jsonify({
            "success": True,
            "win_amount": win,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Plinko error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
def report_spin():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=5):
        app.logger.warning(f"Rate limit exceeded for spin game from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    reward = data.get('reward', 0)
    
    if reward not in [0, 50, 100, 200, 500, 1000]:
        return jsonify({"success": False, "message": "Invalid spin reward"}), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'spin'):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    if not can_play_today(user['id'], 'spin', max_plays=1):
        return jsonify({"success": False, "message": "One spin per day"}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        new_balance = float(user['balance']) + reward
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        
        # Update last game timestamp
        update_last_game_timestamp(user['id'])
        
        # Record game play
        record_game_play(user['id'], 'spin')
        
        # Record transaction
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
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} played spin: reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Spin error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ================= ACHIEVEMENTS =================
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
        
        # Define achievements with FULL progress data
        achievements_data = [
            {"id": 1, "title": "First Game", "description": "Play any game once", "reward": 500, "points": 10, 
             "unlocked": total_games >= 1, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 1, "progress_percentage": min(100, (total_games / 1) * 100),
             "cash_reward": 500},
            {"id": 2, "title": "Gamer", "description": "Play 50 games", "reward": 5000, "points": 50, 
             "unlocked": total_games >= 50, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 50, "progress_percentage": min(100, (total_games / 50) * 100),
             "cash_reward": 5000},
            {"id": 3, "title": "Game Master", "description": "Play 200 games", "reward": 15000, "points": 150, 
             "unlocked": total_games >= 200, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": total_games, "target_value": 200, "progress_percentage": min(100, (total_games / 200) * 100),
             "cash_reward": 15000},
            {"id": 4, "title": "Snake Pro", "description": "Snake high score 1000+", "reward": 7500, "points": 75, 
             "unlocked": snake_high >= 1000, "category": "gaming", "icon": "fas fa-gamepad",
             "current_value": snake_high, "target_value": 1000, "progress_percentage": min(100, (snake_high / 1000) * 100),
             "cash_reward": 7500},
            {"id": 5, "title": "Lucky Streak", "description": "10+ coin flip win streak", "reward": 10000, "points": 100, 
             "unlocked": coin_streak >= 10, "category": "gaming", "icon": "fas fa-coins",
             "current_value": coin_streak, "target_value": 10, "progress_percentage": min(100, (coin_streak / 10) * 100),
             "cash_reward": 10000},
            {"id": 6, "title": "Coin Flipper", "description": "100+ coin flips", "reward": 6000, "points": 60, 
             "unlocked": coin_total >= 100, "category": "gaming", "icon": "fas fa-coins",
             "current_value": coin_total, "target_value": 100, "progress_percentage": min(100, (coin_total / 100) * 100),
             "cash_reward": 6000},
            {"id": 7, "title": "Plinko Champion", "description": "50+ Plinko wins", "reward": 8000, "points": 80, 
             "unlocked": plinko_wins >= 50, "category": "gaming", "icon": "fas fa-bullseye",
             "current_value": plinko_wins, "target_value": 50, "progress_percentage": min(100, (plinko_wins / 50) * 100),
             "cash_reward": 8000},
            {"id": 8, "title": "Thousandaire", "description": "Balance ₦1,000+", "reward": 1000, "points": 15, 
             "unlocked": balance >= 1000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 1000, "progress_percentage": min(100, (balance / 1000) * 100),
             "cash_reward": 1000},
            {"id": 9, "title": "Millionaire in Progress", "description": "Balance ₦50,000+", "reward": 10000, "points": 100, 
             "unlocked": balance >= 50000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 50000, "progress_percentage": min(100, (balance / 50000) * 100),
             "cash_reward": 10000},
            {"id": 10, "title": "High Roller", "description": "Balance ₦200,000+", "reward": 25000, "points": 200, 
             "unlocked": balance >= 200000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 200000, "progress_percentage": min(100, (balance / 200000) * 100),
             "cash_reward": 25000},
            {"id": 11, "title": "First Withdrawal", "description": "Make first withdrawal", "reward": 5000, "points": 50, 
             "unlocked": total_withdrawals >= 1, "category": "earnings", "icon": "fas fa-wallet",
             "current_value": total_withdrawals, "target_value": 1, "progress_percentage": min(100, (total_withdrawals / 1) * 100),
             "cash_reward": 5000},
            {"id": 12, "title": "Daily Grinder", "description": "Play 5 games in a day", "reward": 3000, "points": 30, 
             "unlocked": games_today >= 5, "category": "streaks", "icon": "fas fa-calendar-day",
             "current_value": games_today, "target_value": 5, "progress_percentage": min(100, (games_today / 5) * 100),
             "cash_reward": 3000},
            {"id": 13, "title": "Addicted", "description": "Play 20 games in a day", "reward": 8000, "points": 80, 
             "unlocked": games_today >= 20, "category": "streaks", "icon": "fas fa-calendar-day",
             "current_value": games_today, "target_value": 20, "progress_percentage": min(100, (games_today / 20) * 100),
             "cash_reward": 8000},
            {"id": 14, "title": "Referral Starter", "description": "Refer 5 users", "reward": 10000, "points": 100, 
             "unlocked": referrals >= 5, "category": "special", "icon": "fas fa-users",
             "current_value": referrals, "target_value": 5, "progress_percentage": min(100, (referrals / 5) * 100),
             "cash_reward": 10000},
            {"id": 15, "title": "Referral Master", "description": "Refer 20 users", "reward": 30000, "points": 300, 
             "unlocked": referrals >= 20, "category": "special", "icon": "fas fa-users",
             "current_value": referrals, "target_value": 20, "progress_percentage": min(100, (referrals / 20) * 100),
             "cash_reward": 30000},
            {"id": 16, "title": "Transaction Veteran", "description": "10+ transactions", "reward": 4000, "points": 40, 
             "unlocked": total_tx >= 10, "category": "special", "icon": "fas fa-exchange-alt",
             "current_value": total_tx, "target_value": 10, "progress_percentage": min(100, (total_tx / 10) * 100),
             "cash_reward": 4000}
        ]
        
        total_achievements = len(achievements_data)
        unlocked_achievements = sum(1 for a in achievements_data if a['unlocked'])
        total_points = sum(a['points'] for a in achievements_data if a['unlocked'])
        
        # ✅ FIXED: Grant achievement rewards when achievements are viewed
        if unlocked_achievements > 0:
            granted_balance = grant_achievement_rewards(user['id'])
            if granted_balance:
                # Update balance in response
                balance = granted_balance
        
        return jsonify({
            "success": True,
            "stats": {
                "total": total_achievements,
                "unlocked": unlocked_achievements,
                "points": total_points
            },
            "achievements": achievements_data,
            "current_balance": balance
        })
        
    except Exception as e:
        app.logger.error(f"Achievements error: {e}")
        return jsonify({"success": False, "message": f"Failed to load achievements: {str(e)}"}), 500
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
def follow_tiktok_daily():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        app.logger.warning(f"Rate limit exceeded for TikTok follow from {ip}")
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Already claimed today"}), 400
        
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        
        if not task_row:
            return jsonify({"success": False, "message": "No task for today"}), 404
        
        reward = float(task_row[0]) if task_row[0] else CONFIG.TIKTOK_REWARD
        new_balance = float(user['balance']) + reward
        
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        
        conn.commit()
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} claimed TikTok daily: reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"TikTok follow error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ======================= ADMIN TIKTOK ENDPOINTS =======================
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

# ======================= ADMIN GLOBAL WITHDRAWAL DAYS =======================
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

# ======================= ADMIN USER CUSTOM WITHDRAWAL DAYS =======================
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

# ======================= ADMIN USER SET LIMIT =======================
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

# ======================= ADMIN WITHDRAWAL APPROVAL =======================
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
            cursor.execute('SELECT balance FROM users WHERE id = %s', (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                current_balance = float(user_row[0]) if user_row[0] else 0
                new_balance = current_balance + amount
                cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user_id))
        
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

# ======================= ADMIN WITHDRAWAL STATUS REPORT =======================
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

# ======================= ADMIN TOGGLE USER ADMIN STATUS =======================
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
        
        if username == 'flexiaadmin':
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

# ======================= ADMIN DELETE USER =======================
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
        
        if username == 'flexiaadmin':
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

# ======================= ADMIN COUPON MANAGEMENT =======================
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

# ======================= ADMIN WHATSAPP NUMBERS =======================
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

# ================= REFERRAL ENDPOINTS =================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user.get('referral_code', ''),))
        referrals = cursor.fetchone()[0]
        
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = int(user.get('claimed_bonuses', 0))
        unclaimed = total_bonus - claimed
        
        if unclaimed <= 0:
            return jsonify({"success": False, "message": "No bonus to claim"}), 400
        
        new_balance = float(user['balance']) + unclaimed
        
        cursor.execute('UPDATE users SET balance = %s, claimed_bonuses = %s WHERE id = %s',
                       (new_balance, total_bonus, user['id']))
        
        conn.commit()
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} claimed referral bonus: {unclaimed}")
        
        return jsonify({
            "success": True,
            "claimed": unclaimed,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Referral error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to claim: {str(e)}"}), 500
    finally:
        return_db_connection(conn)

# ================= BANKING ENDPOINTS =================
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    """Get list of all active banks - FIXED"""
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
        new_balance = float(user['balance']) - amount
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        
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
        
        # ✅ FIXED: Remove grant_achievement_rewards call to prevent database conflicts
        # grant_achievement_rewards(user['id'])  # REMOVED
        
        app.logger.info(f"User {user['username']} requested withdrawal: {amount} to {bank_code}:{account_number}")
        
        return jsonify({
            "success": True,
            "message": "Withdrawal submitted",
            "transaction_id": tx_id,
            "new_balance": new_balance
        })
        
    except Exception as e:
        app.logger.error(f"Withdrawal error: {e}")
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
        cursor.execute('SELECT balance FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        current_balance = float(row[0]) if row[0] else 0
        new_balance = current_balance + amount
        
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user_id))
        
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
            "old_balance": current_balance,
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
    
    app.logger.info(f"🚀 Starting Flexia Platform v11.1 on port {port} (debug: {debug})")
    app.logger.info(f"📁 Frontend directory: {CONFIG.FRONTEND_DIR}")
    app.logger.info(f"🔐 Secret key set: {'Yes' if CONFIG.SECRET_KEY else 'No'}")
    app.logger.info(f"🗄️  Database: {'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'}")
    app.logger.info(f"🔧 Security headers: Enabled")
    app.logger.info(f"📊 Structured logging: Enabled")
    app.logger.info(f"💾 Database connection pool: {'Enabled' if db_pool else 'Disabled'}")
    app.logger.info(f"💾 Automatic backups: Enabled (daily at 2 AM UTC)")
    app.logger.info(f"✅ ALL FIXES APPLIED: Database connection issues, duplicate claims, achievements")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
