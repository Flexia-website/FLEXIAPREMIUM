# backend/app.py
# Flexia Platform v10.9 — Updated Jan 5, 2026 — RENDER-READY
# CHANGES:
# - Fixed Gunicorn startup: DB init + scheduler now run correctly ✅
# - All endpoints preserved from your original app.txt
# - SQLite blocked in production
# - HTTPS enforced
# - PWA frontend served

import os
import json
import random
import secrets
import urllib.parse
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
import threading
import time

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

CONFIG = Config()

app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY

# Rate limiting (in-memory)
login_attempts = {}
register_attempts = {}
game_action_attempts = {}

def rate_limit(store, key, max_per_min=5):
    now = datetime.utcnow()
    if key not in store:
        store[key] = []
    store[key] = [t for t in store[key] if t > now - timedelta(minutes=1)]
    if len(store[key]) >= max_per_min:
        return False
    store[key].append(now)
    return True

# ======================= HTTPS ENFORCEMENT =======================
@app.before_request
def force_https():
    if not request.is_secure and os.getenv('ENV') == 'production':
        return redirect(request.url.replace("http://", "https://"))

# ======================= SESSION MANAGER =======================
def create_session_token(user_id):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id})

def verify_session_token(token):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return data.get('user_id')
    except (BadSignature, SignatureExpired):
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
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_dict(cursor, row)
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
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
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# ======================= DATABASE =======================
def get_db():
    if os.environ.get('DATABASE_URL'):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        parsed = urllib.parse.urlparse(CONFIG.DB_URL)
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
    else:
        if os.getenv('ENV') == 'production':
            raise RuntimeError("SQLite not allowed in production. Set DATABASE_URL.")
        import sqlite3
        conn = sqlite3.connect(CONFIG.DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

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
            withdrawal_limit REAL DEFAULT 0.00
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
            withdrawal_limit REAL DEFAULT 0.00
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
            name TEXT
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
        cursor.execute(sql)

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
        cursor.executemany(f'INSERT INTO banks (code, name) VALUES ({ph}, {ph})', banks)

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

    # Coupons initialization
    if os.path.exists(CONFIG.COUPON_FILE):
        try:
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            if codes:
                cursor.execute('DELETE FROM coupons')
                for code in codes:
                    try:
                        cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
                    except:
                        pass
                print(f"[INIT] Loaded {len(codes)} coupons from file")
        except Exception as e:
            print(f"[INIT] Error loading coupons: {e}")
    else:
        print(f"[INIT] Warning: Coupon file not found at {CONFIG.COUPON_FILE}")
        default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
        for code in default_coupons:
            try:
                cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
            except:
                pass
        print(f"[INIT] Created {len(default_coupons)} default coupons")

    # Admin user
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_admin = ' + ('TRUE' if is_postgres else '1'))
    admin_count = cursor.fetchone()
    if isinstance(admin_count, dict):
        admin_count = admin_count['count']
    else:
        admin_count = admin_count[0] if admin_count else 0
    if admin_count == 0:
        admin_pass_raw = "Flexiaadmin"
        admin_pass = generate_password_hash(admin_pass_raw)
        game_stats = json.dumps({
            "snake": {"high_score": 1200, "total_score": 5000},
            "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
            "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
        })
        if is_postgres:
            cursor.execute(f'''
            INSERT INTO users (username, password, balance, referral_code, is_admin, created_at, last_login, game_stats, admin_password_changed, withdrawal_pin, contact, profile_picture, ui_theme)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', ("flexiaadmin", admin_pass, 500000.00, "ADM0001", True, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, False, generate_password_hash("4567"), "", "", "light"))
        else:
            cursor.execute(f'''
            INSERT INTO users (username, password, balance, referral_code, is_admin, created_at, last_login, game_stats, admin_password_changed, withdrawal_pin, contact, profile_picture, ui_theme)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', ("flexiaadmin", admin_pass, 500000.00, "ADM0001", 1, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, 0, generate_password_hash("4567"), "", "", "light"))
        print("\n🚨 FLEXIA ADMIN ACCOUNT CREATED 🚨")
        print("Username: flexiaadmin")
        print("Initial Password: Flexiaadmin")
        print("Default Withdrawal PIN: 4567")
        print("🔐 Change both after first login!\n")

    # WhatsApp number
    cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
    whatsapp_count = cursor.fetchone()
    if isinstance(whatsapp_count, dict):
        whatsapp_count = whatsapp_count['count']
    else:
        whatsapp_count = whatsapp_count[0] if whatsapp_count else 0
    if whatsapp_count == 0:
        cursor.execute(f'INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES ({ph}, {ph}, {ph}, {ph})',
                       ('2348100000000', 'Primary Seller', True if is_postgres else 1, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

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
        print(f"Error getting global withdrawal days: {e}")
    finally:
        conn.close()
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

def can_play_today(user_id, game_type, max_plays=10, record_play=True):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f"SELECT COUNT(*) as count FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}",
                       (user_id, game_type, today))
        count_row = cursor.fetchone()
        count = count_row['count'] if isinstance(count_row, dict) else count_row[0]
        if count < max_plays:
            if record_play:
                cursor.execute(f"INSERT INTO game_plays (user_id, game_type, play_date) VALUES ({ph}, {ph}, {ph})",
                               (user_id, game_type, today))
                conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Play check error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def is_withdrawal_day(user_id=None):
    today = datetime.utcnow().day
    if user_id is None:
        global_days = get_global_withdrawal_days()
        return today in global_days
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'''
    SELECT withdrawal_restricted, custom_withdrawal_days
    FROM users WHERE id = {ph}
    ''', (user_id,))
    user_row = cursor.fetchone()
    conn.close()
    if user_row:
        user = row_to_dict(cursor, user_row)
        if _safe_get(user, 'withdrawal_restricted', False):
            return False
        custom_days_str = _safe_get(user, 'custom_withdrawal_days', '')
        if custom_days_str:
            try:
                return today in json.loads(custom_days_str)
            except:
                pass
        global_days = get_global_withdrawal_days()
        return today in global_days

# ✅ AUTO-CLAIM ACHIEVEMENT REWARDS
def grant_achievement_rewards(user_id):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'SELECT balance, game_stats, referral_code, points FROM users WHERE id = {ph}', (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return None
    user = row_to_dict(cursor, user_row)
    game_stats = json.loads(user.get('game_stats', '{}'))
    balance = float(user['balance'])
    referral_code = user['referral_code']
    current_points = user['points']
    cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (referral_code,))
    referrals = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph}', (user_id,))
    total_tx = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = "WITHDRAWAL"', (user_id,))
    total_withdrawals = cursor.fetchone()[0]
    today = datetime.utcnow().date()
    cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND play_date = {ph}', (user_id, today))
    games_today = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph}', (user_id,))
    total_games = cursor.fetchone()[0]
    conn.close()

    snake_high = game_stats.get('snake', {}).get('high_score', 0)
    coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
    coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
    plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

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
    if total_points <= current_points:
        return balance

    new_balance = balance + total_reward
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET balance = {ph}, points = {ph} WHERE id = {ph}', (new_balance, total_points, user_id))
    if total_reward > 0:
        tx_id = f"ACH-{secrets.token_hex(8)}"
        cursor.execute(f'''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        ''', (
            tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
            json.dumps({"source": "auto_grant"}),
            datetime.utcnow().isoformat()
        ))
    conn.commit()
    conn.close()
    return new_balance

# ✅ TIKTOK DAILY CLEANUP (older than 2 days)
def cleanup_old_tiktok_tasks():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        cursor.execute('DELETE FROM tiktok_daily WHERE date < ?', (cutoff_date,))
        conn.commit()
        conn.close()
        print(f"[TikTok Cleanup] Removed tasks before {cutoff_date}")
    except Exception as e:
        print(f"[TikTok Cleanup Error] {e}")

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

# >>>>>>>>>>> CRITICAL: Initialize DB and start scheduler on import (for Gunicorn) <<<<<<<<<<<
with app.app_context():
    init_db()
    cleanup_old_tiktok_tasks()  # Run once at startup
    run_cleanup_scheduler()     # Start background thread

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
    """Check database status"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        if os.environ.get('DATABASE_URL'):
            cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons WHERE status = "AVAILABLE"')
        available_coupons = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/debug/registration-test', methods=['POST'])
def registration_test():
    data = request.get_json()
    coupon_code = data.get('coupon_code', '').upper() if data else ''
    conn = get_db()
    cursor = conn.cursor()
    results = {
        "database_connection": "OK",
        "coupons_table_exists": False,
        "coupon_valid": False,
        "coupon_details": None,
        "total_coupons": 0,
        "available_coupons": 0
    }
    try:
        if os.environ.get('DATABASE_URL'):
            cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'coupons'
            )
            """)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'")
        results["coupons_table_exists"] = bool(cursor.fetchone())
        if results["coupons_table_exists"]:
            cursor.execute("SELECT COUNT(*) FROM coupons")
            results["total_coupons"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
            results["available_coupons"] = cursor.fetchone()[0]
            if coupon_code:
                cursor.execute("SELECT code, status FROM coupons WHERE code = ?", (coupon_code,))
                coupon = cursor.fetchone()
                if coupon:
                    results["coupon_valid"] = True
                    results["coupon_details"] = {"code": coupon[0], "status": coupon[1]}
    except Exception as e:
        results["error"] = str(e)
    finally:
        conn.close()
    return jsonify(results)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
def register():
    ip = request.remote_addr
    if not rate_limit(register_attempts, ip, max_per_min=3):
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
        if is_postgres:
            cursor.execute(f'SELECT id FROM users WHERE LOWER(username) = LOWER({ph})', (username,))
        else:
            cursor.execute(f'SELECT id FROM users WHERE LOWER(username) = LOWER({ph})', (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Username already taken"}), 409
    except Exception as e:
        print(f"Error checking username: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Database error"}), 500
    try:
        cursor.execute(f'SELECT status FROM coupons WHERE code = {ph}', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row:
            conn.close()
            return jsonify({"success": False, "message": "Invalid coupon code"}), 403
        if isinstance(coupon_row, dict):
            coupon_status = coupon_row.get('status')
        else:
            coupon_status = coupon_row[0] if coupon_row else None
        if coupon_status != 'AVAILABLE':
            conn.close()
            return jsonify({"success": False, "message": "Coupon already used or invalid"}), 403
    except Exception as e:
        print(f"Error checking coupon: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Database error"}), 500
    if referral_code:
        try:
            cursor.execute(f'SELECT referral_code FROM users WHERE referral_code = {ph}', (referral_code,))
            if not cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "Invalid referral code"}), 400
        except Exception as e:
            print(f"Error checking referral: {e}")
            conn.close()
            return jsonify({"success": False, "message": "Database error"}), 500
    try:
        cursor.execute(f'UPDATE coupons SET status = {ph} WHERE code = {ph}', ("USED", coupon_code))
        import time
        timestamp = int(time.time())
        user_referral_code = f"{username[:3].upper()}{timestamp % 10000:04d}"
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0},
            "coin_flip": {"wins": 0, "losses": 0, "current_streak": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0}
        })
        if is_postgres:
            is_admin_value = False
            admin_password_changed_value = False
            withdrawal_restricted_value = False
        else:
            is_admin_value = 0
            admin_password_changed_value = 0
            withdrawal_restricted_value = 0
        cursor.execute(f'''
        INSERT INTO users (
            username, password, balance, referral_code,
            referred_by, is_admin, created_at, last_login,
            game_stats, contact, profile_picture, ui_theme,
            admin_password_changed, withdrawal_pin, withdrawal_restricted,
            withdrawal_limit, points, claimed_bonuses
        ) VALUES (
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}
        )
        ''', (
            username, generate_password_hash(password), 0.00,
            user_referral_code,
            referral_code if referral_code else None,
            is_admin_value,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            game_stats,
            contact if contact else "",
            "", "light",
            admin_password_changed_value,
            None,
            withdrawal_restricted_value,
            0.00,
            0,
            0
        ))
        if is_postgres:
            cursor.execute("SELECT LASTVAL()")
            new_id = cursor.fetchone()[0]
        else:
            new_id = cursor.lastrowid
        admin_bonus = 0
        if referral_code:
            try:
                cursor.execute(f'SELECT is_admin FROM users WHERE referral_code = {ph}', (referral_code,))
                referrer_row = cursor.fetchone()
                if referrer_row:
                    if is_postgres:
                        is_referrer_admin = referrer_row[0] if isinstance(referrer_row, (list, tuple)) else referrer_row.get('is_admin')
                    else:
                        is_referrer_admin = referrer_row[0] if referrer_row else False
                    if is_referrer_admin:
                        admin_bonus = 5000
                        cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (admin_bonus, new_id))
            except Exception as e:
                print(f"Error applying admin bonus: {e}")
        conn.commit()
        token = create_session_token(new_id)
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": new_id,
                "username": username,
                "referral_code": user_referral_code
            }
        })
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie(
            'session_token',
            token,
            httponly=True,
            secure=secure_cookie,
            samesite='Lax',
            max_age=86400
        )
        return response
    except Exception as e:
        print(f"Registration error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return jsonify({"success": False, "message": f"Registration failed: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr
    if not rate_limit(login_attempts, ip, max_per_min=5):
        return jsonify({"success": False, "message": "Too many login attempts. Try again later."}), 429
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    if not identifier or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        if is_postgres:
            cursor.execute(f'SELECT * FROM users WHERE LOWER(username) = LOWER({ph}) OR LOWER(contact) = LOWER({ph})',
                           (identifier, identifier))
        else:
            cursor.execute(f'SELECT * FROM users WHERE (LOWER(username) = LOWER({ph}) OR LOWER(contact) = LOWER({ph}))',
                           (identifier, identifier))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        user = row_to_dict(cursor, row)
        if not user or not check_password_hash(user['password'], password):
            conn.close()
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        cursor.execute(f'UPDATE users SET last_login = {ph} WHERE id = {ph}',
                       (datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        admin_pw_changed = _safe_get(user, 'admin_password_changed', False)
        profile_picture = _safe_get(user, 'profile_picture', '')
        ui_theme = _safe_get(user, 'ui_theme', 'light')
        grant_achievement_rewards(user['id'])
        resp = jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "balance": float(user['balance']),
                "referral_code": user['referral_code'],
                "is_admin": bool(user['is_admin']),
                "admin_password_changed": bool(admin_pw_changed),
                "profile_picture": profile_picture,
                "ui_theme": ui_theme
            }
        })
        token = create_session_token(user['id'])
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token, httponly=True, secure=secure_cookie, samesite='Lax', max_age=86400)
        return resp
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "message": "Login failed"}), 500
    finally:
        conn.close()

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({"success": True, "message": "Logged out"})
    resp.set_cookie('session_token', '', expires=0, httponly=True, secure=(os.getenv('ENV') == 'production'), samesite='Lax')
    return resp

@app.route('/api/user/profile')
@require_auth
def get_user_profile():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    grant_achievement_rewards(user['id'])
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user['id'],))
        fresh_user_row = cursor.fetchone()
        if not fresh_user_row:
            conn.close()
            return jsonify({"success": False, "message": "User not found"}), 404
        fresh_user = row_to_dict(cursor, fresh_user_row)
        cursor.execute(f'SELECT COUNT(*) as count FROM users WHERE referred_by = {ph}', (fresh_user['referral_code'],))
        ref_row = cursor.fetchone()
        referrals = ref_row['count'] if isinstance(ref_row, dict) else ref_row[0]
        claimed = _safe_get(fresh_user, 'claimed_bonuses', 0)
        unclaimed = max(0, referrals * CONFIG.REFERRAL_BONUS - claimed)
        cursor.execute(f'SELECT * FROM transactions WHERE user_id = {ph} ORDER BY timestamp DESC LIMIT 20', (fresh_user['id'],))
        transactions = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({
            "success": True,
            "user": {
                "id": fresh_user['id'],
                "username": fresh_user['username'],
                "balance": float(fresh_user['balance']),
                "referral_code": fresh_user['referral_code'],
                "is_admin": bool(fresh_user['is_admin']),
                "created_at": fresh_user['created_at'],
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
        print(f"Profile error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load profile"}), 500

# ================= USER SETTINGS ENDPOINTS =================
@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    user = get_current_user()
    data = request.get_json()
    picture_url = sanitize_input(data.get('picture_url', ''))
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET profile_picture = {ph} WHERE id = {ph}', (picture_url, user['id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Profile picture updated"})
    except Exception as e:
        print(f"Profile picture error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to update profile picture"}), 500

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_theme():
    user = get_current_user()
    data = request.get_json()
    theme = 'dark' if data.get('dark_mode') else 'light'
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET ui_theme = {ph} WHERE id = {ph}', (theme, user['id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Theme updated"})
    except Exception as e:
        print(f"Theme update error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to update theme"}), 500

# ================= PASSWORD & PIN ENDPOINTS =================
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
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f"UPDATE users SET password = {ph} WHERE id = {ph}",
                       (generate_password_hash(new_password), user['id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Password updated successfully"})
    except Exception as e:
        print(f"Password change error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to update password"}), 500

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
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET withdrawal_pin = {ph} WHERE id = {ph}', (generate_password_hash(pin), user['id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "PIN set successfully"})
    except Exception as e:
        print(f"PIN set error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to set PIN"}), 500

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
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    return jsonify({"success": True, "message": "PIN verified"})

# ================= GAME REPORTING ENDPOINTS =================
@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests. Try again later."}), 429
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "You must eat at least 1 apple"}), 400
    if not can_play_today(user['id'], 'snake', max_plays=20):
        return jsonify({"success": False, "message": "You can only play Snake 20 times per day"}), 403
    reward = apples * CONFIG.SNAKE_REWARD
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        new_balance = user['balance'] + reward
        game_stats = json.loads(user.get('game_stats', '{}'))
        snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
        score = apples * 10
        if score > snake_stats['high_score']:
            snake_stats['high_score'] = score
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        game_stats['snake'] = snake_stats
        cursor.execute(f'UPDATE users SET balance = {ph}, game_stats = {ph} WHERE id = {ph}',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"Snake report error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process game result"}), 500

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=10):
        return jsonify({"success": False, "message": "Too many requests. Try again later."}), 429
    user = get_current_user()
    data = request.get_json()
    bet = data.get('bet', 0)
    won = data.get('won', False)
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or user['balance'] < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    if not can_play_today(user['id'], 'coinflip', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    payout = bet * 2 if won else 0
    new_balance = user['balance'] + payout - bet
    game_stats = json.loads(user.get('game_stats', '{}'))
    coinflip_stats = game_stats.get('coin_flip', {'wins': 0, 'losses': 0, 'current_streak': 0})
    if won:
        coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
        coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
    else:
        coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
        coinflip_stats['current_streak'] = 0
    game_stats['coin_flip'] = coinflip_stats
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET balance = {ph}, game_stats = {ph} WHERE id = {ph}',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "payout": payout if won else 0, "new_balance": new_balance})
    except Exception as e:
        print(f"Coinflip report error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process game result"}), 500

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=5):
        return jsonify({"success": False, "message": "Too many requests. Try again later."}), 429
    user = get_current_user()
    data = request.get_json()
    bet = data.get('bet', 0)
    multiplier = data.get('multiplier', 0)
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or user['balance'] < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    if multiplier not in [0.5, 3, 10]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400
    if not can_play_today(user['id'], 'plinko', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    win = bet * multiplier
    new_balance = user['balance'] + win - bet
    game_stats = json.loads(user.get('game_stats', '{}'))
    plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
    plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
    if win > bet:
        plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
        if win > plinko_stats.get('highest_win', 0):
            plinko_stats['highest_win'] = win
    game_stats['plinko'] = plinko_stats
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'UPDATE users SET balance = {ph}, game_stats = {ph} WHERE id = {ph}',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "win_amount": win, "new_balance": new_balance})
    except Exception as e:
        print(f"Plinko report error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process game result"}), 500

# ✅ TIKTOK DAILY ENDPOINTS
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily_task():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'''
        SELECT 1 FROM transactions
        WHERE user_id = {ph} AND type = 'TIKTOK_DAILY' AND date(timestamp) = ?
        ''', (user['id'], today))
        already_claimed = cursor.fetchone() is not None
        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = ?', (today,))
        task_row = cursor.fetchone()
        conn.close()
        if task_row:
            task = row_to_dict(cursor, task_row)
            return jsonify({
                "success": True,
                "task": {
                    "tiktok_link": task['tiktok_link'],
                    "reward_amount": task['reward_amount']
                },
                "already_claimed": already_claimed
            })
        else:
            return jsonify({
                "success": False,
                "message": "No TikTok task available for today",
                "already_claimed": already_claimed
            }), 404
    except Exception as e:
        print(f"TikTok daily error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to get TikTok task"}), 500

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
def follow_tiktok_daily():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests. Try again later."}), 429
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'''
        SELECT 1 FROM transactions
        WHERE user_id = {ph} AND type = 'TIKTOK_DAILY' AND date(timestamp) = ?
        ''', (user['id'], today))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "You already claimed today's TikTok reward"}), 400
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = ?', (today,))
        task_row = cursor.fetchone()
        if not task_row:
            conn.close()
            return jsonify({"success": False, "message": "No TikTok task available for today"}), 404
        reward = task_row['reward_amount'] or CONFIG.TIKTOK_REWARD
        new_balance = user['balance'] + reward
        cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (new_balance, user['id']))
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute(f'''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"TikTok follow error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process TikTok reward"}), 500

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
def report_spin():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests. Try again later."}), 429
    user = get_current_user()
    data = request.get_json()
    reward = data.get('reward', 0)
    if reward not in [0, 50, 100, 200, 500, 1000]:
        return jsonify({"success": False, "message": "Invalid spin reward"}), 400
    if not can_play_today(user['id'], 'spin', max_plays=1):
        return jsonify({"success": False, "message": "You can spin once per day"}), 403
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        new_balance = user['balance'] + reward
        cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (new_balance, user['id']))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"Spin report error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process spin result"}), 500

@app.route('/api/achievements')
@require_auth
def get_achievements():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        game_stats = json.loads(_safe_get(user, 'game_stats', '{}'))
        balance = float(_safe_get(user, 'balance', 0))
        cursor.execute(f'SELECT COUNT(*) as count FROM transactions WHERE user_id = {ph}', (user['id'],))
        tx_row = cursor.fetchone()
        total_transactions = tx_row['count'] if isinstance(tx_row, dict) else tx_row[0]
        cursor.execute(f'SELECT COUNT(*) as count FROM transactions WHERE user_id = {ph} AND type = {ph}', (user['id'], 'WITHDRAWAL'))
        wd_row = cursor.fetchone()
        total_withdrawals = wd_row['count'] if isinstance(wd_row, dict) else wd_row[0]
        cursor.execute(f'SELECT COUNT(*) as count FROM users WHERE referred_by = {ph}', (user['referral_code'],))
        ref_row = cursor.fetchone()
        referrals = ref_row['count'] if isinstance(ref_row, dict) else ref_row[0]
        today = datetime.utcnow().date()
        cursor.execute(f'SELECT COUNT(*) as count FROM game_plays WHERE user_id = {ph} AND play_date = {ph}', (user['id'], today))
        games_today_row = cursor.fetchone()
        games_today = games_today_row['count'] if isinstance(games_today_row, dict) else games_today_row[0]
        cursor.execute(f'SELECT COUNT(*) as count FROM game_plays WHERE user_id = {ph}', (user['id'],))
        total_games_row = cursor.fetchone()
        total_games = total_games_row['count'] if isinstance(total_games_row, dict) else total_games_row[0]
        conn.close()
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coinflip_wins = game_stats.get('coin_flip', {}).get('wins', 0)
        coinflip_losses = game_stats.get('coin_flip', {}).get('losses', 0)
        coinflip_total = coinflip_wins + coinflip_losses
        coinflip_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)
        achievements = [
            {"title": "First Steps", "description": "Play your first game", "category": "gaming", "icon": "fas fa-gamepad", "unlocked": total_games >= 1, "progress_percentage": min(100, (total_games / 1) * 100), "current_value": min(total_games, 1), "target_value": 1, "points": 10, "cash_reward": 500},
            {"title": "Gaming Enthusiast", "description": "Play 50 games", "category": "gaming", "icon": "fas fa-trophy", "unlocked": total_games >= 50, "progress_percentage": min(100, (total_games / 50) * 100), "current_value": min(total_games, 50), "target_value": 50, "points": 50, "cash_reward": 5000},
            {"title": "Gaming Legend", "description": "Play 200 games", "category": "gaming", "icon": "fas fa-crown", "unlocked": total_games >= 200, "progress_percentage": min(100, (total_games / 200) * 100), "current_value": min(total_games, 200), "target_value": 200, "points": 150, "cash_reward": 15000},
            {"title": "Snake Master", "description": "Score 1000+ in Snake game", "category": "gaming", "icon": "fas fa-dragon", "unlocked": snake_high >= 1000, "progress_percentage": min(100, (snake_high / 1000) * 100), "current_value": min(snake_high, 1000), "target_value": 1000, "points": 75, "cash_reward": 7500},
            {"title": "Lucky Flipper", "description": "Win 10 coin flips in a row", "category": "streaks", "icon": "fas fa-coins", "unlocked": coinflip_streak >= 10, "progress_percentage": min(100, (coinflip_streak / 10) * 100), "current_value": min(coinflip_streak, 10), "target_value": 10, "points": 100, "cash_reward": 10000},
            {"title": "Coin Flip Pro", "description": "Play 100 coin flip games", "category": "gaming", "icon": "fas fa-exchange-alt", "unlocked": coinflip_total >= 100, "progress_percentage": min(100, (coinflip_total / 100) * 100), "current_value": min(coinflip_total, 100), "target_value": 100, "points": 60, "cash_reward": 6000},
            {"title": "Plinko Champion", "description": "Win 50 Plinko games", "category": "gaming", "icon": "fas fa-bullseye", "unlocked": plinko_wins >= 50, "progress_percentage": min(100, (plinko_wins / 50) * 100), "current_value": min(plinko_wins, 50), "target_value": 50, "points": 80, "cash_reward": 8000},
            {"title": "First Earnings", "description": "Earn your first ₦1,000", "category": "earnings", "icon": "fas fa-money-bill-wave", "unlocked": balance >= 1000, "progress_percentage": min(100, (balance / 1000) * 100), "current_value": min(int(balance), 1000), "target_value": 1000, "points": 15, "cash_reward": 1000},
            {"title": "High Roller", "description": "Accumulate ₦50,000", "category": "earnings", "icon": "fas fa-gem", "unlocked": balance >= 50000, "progress_percentage": min(100, (balance / 50000) * 100), "current_value": min(int(balance), 50000), "target_value": 50000, "points": 100, "cash_reward": 10000},
            {"title": "Wealthy Player", "description": "Accumulate ₦200,000", "category": "earnings", "icon": "fas fa-sack-dollar", "unlocked": balance >= 200000, "progress_percentage": min(100, (balance / 200000) * 100), "current_value": min(int(balance), 200000), "target_value": 200000, "points": 200, "cash_reward": 25000},
            {"title": "First Cashout", "description": "Make your first withdrawal", "category": "earnings", "icon": "fas fa-hand-holding-usd", "unlocked": total_withdrawals >= 1, "progress_percentage": min(100, (total_withdrawals / 1) * 100), "current_value": min(total_withdrawals, 1), "target_value": 1, "points": 50, "cash_reward": 5000},
            {"title": "Daily Grinder", "description": "Play 5 games in one day", "category": "streaks", "icon": "fas fa-fire", "unlocked": games_today >= 5, "progress_percentage": min(100, (games_today / 5) * 100), "current_value": min(games_today, 5), "target_value": 5, "points": 30, "cash_reward": 3000},
            {"title": "Dedication", "description": "Play 20 games in one day", "category": "streaks", "icon": "fas fa-medal", "unlocked": games_today >= 20, "progress_percentage": min(100, (games_today / 20) * 100), "current_value": min(games_today, 20), "target_value": 20, "points": 80, "cash_reward": 8000},
            {"title": "Social Butterfly", "description": "Refer 5 friends", "category": "special", "icon": "fas fa-users", "unlocked": referrals >= 5, "progress_percentage": min(100, (referrals / 5) * 100), "current_value": min(referrals, 5), "target_value": 5, "points": 100, "cash_reward": 10000},
            {"title": "Influencer", "description": "Refer 20 friends", "category": "special", "icon": "fas fa-star", "unlocked": referrals >= 20, "progress_percentage": min(100, (referrals / 20) * 100), "current_value": min(referrals, 20), "target_value": 20, "points": 300, "cash_reward": 30000},
            {"title": "Transaction Master", "description": "Complete 10 transactions", "category": "special", "icon": "fas fa-receipt", "unlocked": total_transactions >= 10, "progress_percentage": min(100, (total_transactions / 10) * 100), "current_value": min(total_transactions, 10), "target_value": 10, "points": 40, "cash_reward": 4000}
        ]
        total_achievements = len(achievements)
        unlocked_achievements = sum(1 for a in achievements if a['unlocked'])
        total_points = sum(a['points'] for a in achievements if a['unlocked'])
        return jsonify({
            "success": True,
            "stats": {"total": total_achievements, "unlocked": unlocked_achievements, "points": total_points},
            "achievements": achievements
        })
    except Exception as e:
        print(f"Achievements error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load achievements"}), 500

# ================= REFERRAL BONUS =================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f'SELECT COUNT(*) as count FROM users WHERE referred_by = {ph}', (user['referral_code'],))
        ref_row = cursor.fetchone()
        referrals = ref_row['count'] if isinstance(ref_row, dict) else ref_row[0]
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = _safe_get(user, 'claimed_bonuses', 0)
        unclaimed = total_bonus - claimed
        if unclaimed <= 0:
            conn.close()
            return jsonify({"success": False, "message": "No referral bonus to claim"}), 400
        new_balance = user['balance'] + unclaimed
        new_claimed = claimed + unclaimed
        cursor.execute(f'UPDATE users SET balance = {ph}, claimed_bonuses = {ph} WHERE id = {ph}',
                       (new_balance, new_claimed, user['id']))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "claimed": unclaimed, "new_balance": new_balance})
    except Exception as e:
        print(f"Referral claim error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to claim referral bonus"}), 500

# ================= WITHDRAWAL =================
@app.route('/api/banking/withdraw', methods=['POST'])
@require_auth
def withdraw():
    user = get_current_user()
    data = request.get_json()
    amount = data.get('amount', 0)
    bank_code = data.get('bank_code')
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    pin = data.get('pin', '')
    if not pin:
        return jsonify({"success": False, "message": "Withdrawal PIN required"}), 400
    withdrawal_pin = _safe_get(user, 'withdrawal_pin')
    if not withdrawal_pin or not check_password_hash(withdrawal_pin, pin):
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    if not is_withdrawal_day(user['id']):
        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'''
        SELECT withdrawal_restricted, custom_withdrawal_days
        FROM users WHERE id = {ph}
        ''', (user['id'],))
        user_row = cursor.fetchone()
        conn.close()
        if user_row:
            user_settings = row_to_dict(cursor, user_row)
            if _safe_get(user_settings, 'withdrawal_restricted', False):
                message = "Withdrawals are disabled for your account"
            else:
                custom_days_str = _safe_get(user_settings, 'custom_withdrawal_days', '')
                if custom_days_str:
                    try:
                        custom_days = json.loads(custom_days_str)
                        message = f"Withdrawals allowed on days: {', '.join(map(str, sorted(custom_days)))}"
                    except:
                        global_days = get_global_withdrawal_days()
                        message = f"Withdrawals are only allowed on days: {', '.join(map(str, sorted(global_days)))}"
                else:
                    global_days = get_global_withdrawal_days()
                    message = f"Withdrawals are only allowed on days: {', '.join(map(str, sorted(global_days)))}"
        else:
            global_days = get_global_withdrawal_days()
            message = f"Withdrawals are only allowed on days: {', '.join(map(str, sorted(global_days)))}"
        return jsonify({"success": False, "message": message}), 403
    if amount < CONFIG.MIN_WITHDRAWAL:
        return jsonify({"success": False, "message": f"Min withdrawal: ₦{CONFIG.MIN_WITHDRAWAL}"}), 400
    if user['balance'] < amount:
        return jsonify({"success": False, "message": "Insufficient balance"}), 400
    withdrawal_limit = _safe_get(user, 'withdrawal_limit', 0.00)
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({"success": False, "message": f"Maximum withdrawal limit: ₦{withdrawal_limit:,.2f}"}), 400
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({"success": False, "message": "Invalid bank details"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        new_balance = user['balance'] - amount
        cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (new_balance, user['id']))
        tx_id = f"TX-{int(datetime.utcnow().timestamp())}"
        cursor.execute(f'''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        ''', (
            tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING',
            json.dumps({
                'bank_code': bank_code,
                'account_number': account_number,
                'account_name': account_name
            }),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
        grant_achievement_rewards(user['id'])
        return jsonify({
            "success": True,
            "message": "Withdrawal submitted for manual review",
            "transaction_id": tx_id,
            "new_balance": new_balance
        })
    except Exception as e:
        print(f"Withdrawal error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process withdrawal"}), 500

# ================= ADMIN ENDPOINTS =================
@app.route('/api/admin/users')
@require_admin
def admin_get_users():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT id, username, balance, referral_code, withdrawal_restricted, withdrawal_limit
        FROM users ORDER BY id DESC
        ''')
        users = []
        for row in cursor.fetchall():
            user = row_to_dict(cursor, row)
            user['withdrawal_restricted'] = bool(_safe_get(user, 'withdrawal_restricted', False))
            user['withdrawal_limit'] = float(_safe_get(user, 'withdrawal_limit', 0.00))
            users.append(user)
        conn.close()
        return jsonify({"success": True, "users": users, "totalPages": 1})
    except Exception as e:
        print(f"Admin get users error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load users"}), 500

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    admin = get_current_user()
    if user_id == admin['id']:
        return jsonify({"success": False, "message": "Cannot delete yourself"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'DELETE FROM users WHERE id = {ph}', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "User deleted"})
    except Exception as e:
        print(f"Delete user error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to delete user"}), 500

@app.route('/api/admin/transactions')
@require_admin
def admin_get_transactions():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM transactions ORDER BY timestamp DESC')
        txs = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        for tx in txs:
            tx['details'] = json.loads(tx['details']) if tx.get('details') else {}
        conn.close()
        return jsonify({"success": True, "transactions": txs})
    except Exception as e:
        print(f"Admin transactions error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load transactions"}), 500

@app.route('/api/admin/approve-withdrawal', methods=['POST'])
@require_admin
def admin_approve_withdrawal():
    data = request.get_json()
    tx_id = data.get('transaction_id')
    action = data.get('action')
    if not tx_id or action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Invalid request"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'SELECT * FROM transactions WHERE id = {ph}', (tx_id,))
        tx_row = cursor.fetchone()
        tx = row_to_dict(cursor, tx_row) if tx_row else None
        if not tx or tx['status'] != 'PENDING':
            conn.close()
            return jsonify({"success": False, "message": "Transaction not found or not pending"}), 404
        new_status = 'COMPLETED' if action == 'approve' else 'REJECTED'
        if action == 'reject':
            user_id = tx['user_id']
            refund_amount = tx['amount']
            cursor.execute(f'SELECT balance FROM users WHERE id = {ph}', (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                user_data = row_to_dict(cursor, user_row)
                current_balance = float(_safe_get(user_data, 'balance', 0.00))
                new_balance = current_balance + refund_amount
                cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (new_balance, user_id))
        cursor.execute(f'UPDATE transactions SET status = {ph} WHERE id = {ph}', (new_status, tx_id))
        conn.commit()
        conn.close()
        if action == 'reject':
            return jsonify({
                "success": True,
                "message": f"Withdrawal rejected and ₦{tx['amount']:,.2f} refunded to user"
            })
        else:
            return jsonify({"success": True, "message": "Withdrawal approved"})
    except Exception as e:
        print(f"Approve withdrawal error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to process withdrawal"}), 500

@app.route('/api/admin/global-withdrawal-days', methods=['GET', 'POST'])
@require_admin
def manage_global_withdrawal_days():
    if request.method == 'GET':
        days = get_global_withdrawal_days()
        return jsonify({"success": True, "days": days})
    else:
        data = request.get_json()
        days = data.get('days', [])
        if not isinstance(days, list):
            return jsonify({"success": False, "message": "Days must be an array"}), 400
        if len(days) == 0:
            days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
        for day in days:
            if not isinstance(day, int) or day < 1 or day > 31:
                return jsonify({"success": False, "message": f"Invalid day: {day}. Must be 1-31"}), 400
        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        try:
            days_json = json.dumps(days)
            cursor.execute(f'UPDATE admin_settings SET global_withdrawal_days = {ph} WHERE id = 1', (days_json,))
            if cursor.rowcount == 0:
                cursor.execute(f'INSERT INTO admin_settings (id, global_withdrawal_days) VALUES (1, {ph})', (days_json,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": f"Global withdrawal days updated to: {sorted(days)}", "days": days})
        except Exception as e:
            print(f"Global withdrawal days error: {e}")
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "Failed to update withdrawal days"}), 500

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@require_admin
def admin_settings():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'GET':
        try:
            cursor.execute('SELECT * FROM admin_settings LIMIT 1')
            row = cursor.fetchone()
            data = row_to_dict(cursor, row) if row else {}
            conn.close()
            return jsonify({"success": True, "settings": data})
        except Exception as e:
            print(f"Get admin settings error: {e}")
            conn.close()
            return jsonify({"success": False, "message": "Failed to load settings"}), 500
    else:
        data = request.get_json()
        whatsapp = sanitize_input(data.get('whatsapp_link', ''))
        telegram = sanitize_input(data.get('telegram_link', ''))
        facebook = sanitize_input(data.get('facebook_link', ''))
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        try:
            cursor.execute(f'UPDATE admin_settings SET whatsapp_link = {ph}, telegram_link = {ph}, facebook_link = {ph} WHERE id = 1',
                           (whatsapp, telegram, facebook))
            if cursor.rowcount == 0:
                cursor.execute(f'INSERT INTO admin_settings (id, whatsapp_link, telegram_link, facebook_link) VALUES (1, {ph}, {ph}, {ph})',
                               (whatsapp, telegram, facebook))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "Admin settings updated"})
        except Exception as e:
            print(f"Update admin settings error: {e}")
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "Failed to update settings"}), 500

@app.route('/api/admin/user/<int:user_id>/withdrawal-settings', methods=['GET', 'PUT'])
@require_admin
def manage_user_withdrawal_settings(user_id):
    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        try:
            cursor.execute(f'''
            SELECT id, username, withdrawal_restricted, custom_withdrawal_days, withdrawal_limit
            FROM users WHERE id = {ph}
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return jsonify({"success": False, "message": "User not found"}), 404
            user_data = row_to_dict(cursor, row)
            custom_days = []
            custom_days_str = _safe_get(user_data, 'custom_withdrawal_days', '')
            if custom_days_str:
                try:
                    custom_days = json.loads(custom_days_str)
                except:
                    custom_days = []
            return jsonify({
                "success": True,
                "user": {
                    "id": user_data['id'],
                    "username": user_data['username'],
                    "withdrawal_restricted": bool(_safe_get(user_data, 'withdrawal_restricted', False)),
                    "custom_withdrawal_days": custom_days,
                    "withdrawal_limit": float(_safe_get(user_data, 'withdrawal_limit', 0.00))
                }
            })
        except Exception as e:
            print(f"Get user withdrawal settings error: {e}")
            conn.close()
            return jsonify({"success": False, "message": "Failed to load settings"}), 500
    else:
        data = request.get_json()
        withdrawal_restricted = data.get('withdrawal_restricted', False)
        custom_days = data.get('custom_withdrawal_days', [])
        withdrawal_limit = data.get('withdrawal_limit', 0.00)
        if custom_days:
            if not isinstance(custom_days, list):
                return jsonify({"success": False, "message": "custom_withdrawal_days must be an array"}), 400
            for day in custom_days:
                if not isinstance(day, int) or day < 1 or day > 31:
                    return jsonify({"success": False, "message": f"Invalid withdrawal day: {day}. Must be 1-31"}), 400
        try:
            withdrawal_limit = float(withdrawal_limit)
            if withdrawal_limit < 0:
                return jsonify({"success": False, "message": "Withdrawal limit cannot be negative"}), 400
        except:
            return jsonify({"success": False, "message": "Invalid withdrawal limit"}), 400
        conn = get_db()
        cursor = conn.cursor()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        is_postgres = os.environ.get('DATABASE_URL') is not None
        try:
            cursor.execute(f'SELECT id FROM users WHERE id = {ph}', (user_id,))
            if not cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "User not found"}), 404
            custom_days_json = json.dumps(custom_days)
            cursor.execute(f'''
            UPDATE users
            SET withdrawal_restricted = {ph},
            custom_withdrawal_days = {ph},
            withdrawal_limit = {ph}
            WHERE id = {ph}
            ''', (
                withdrawal_restricted if is_postgres else (1 if withdrawal_restricted else 0),
                custom_days_json,
                withdrawal_limit,
                user_id
            ))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "User withdrawal settings updated successfully"})
        except Exception as e:
            print(f"Update user withdrawal settings error: {e}")
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "Failed to update settings"}), 500

@app.route('/api/admin/user/<int:user_id>/enable-anytime-withdrawal', methods=['POST'])
@require_admin
def enable_anytime_withdrawal(user_id):
    data = request.get_json()
    enable = data.get('enable', True)
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        if enable:
            all_days = list(range(1, 32))
            custom_days_json = json.dumps(all_days)
            cursor.execute(f'''
            UPDATE users
            SET withdrawal_restricted = {ph},
            custom_withdrawal_days = {ph}
            WHERE id = {ph}
            ''', (
                False if is_postgres else 0,
                custom_days_json,
                user_id
            ))
            message = "User can now withdraw any day"
        else:
            cursor.execute(f'''
            UPDATE users
            SET withdrawal_restricted = {ph},
            custom_withdrawal_days = NULL
            WHERE id = {ph}
            ''', (
                False if is_postgres else 0,
                user_id
            ))
            message = "User withdrawal reset to default schedule"
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": message})
    except Exception as e:
        print(f"Enable anytime withdrawal error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to update withdrawal settings"}), 500

@app.route('/api/admin/user/<int:user_id>/disable-withdrawal', methods=['POST'])
@require_admin
def disable_user_withdrawal(user_id):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        cursor.execute(f'''
        UPDATE users
        SET withdrawal_restricted = {ph}
        WHERE id = {ph}
        ''', (
            True if is_postgres else 1,
            user_id
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Withdrawal disabled for this user"})
    except Exception as e:
        print(f"Disable withdrawal error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to disable withdrawal"}), 500

@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@require_admin
def withdrawal_status_report():
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        if is_postgres:
            cursor.execute('''
            SELECT id, username, withdrawal_restricted,
            custom_withdrawal_days, withdrawal_limit,
            balance, withdrawal_pin
            FROM users
            WHERE is_admin = FALSE
            ORDER BY username
            ''')
        else:
            cursor.execute('''
            SELECT id, username, withdrawal_restricted,
            custom_withdrawal_days, withdrawal_limit,
            balance, withdrawal_pin
            FROM users
            WHERE is_admin = 0
            ORDER BY username
            ''')
        users = []
        today = datetime.utcnow().day
        global_days = get_global_withdrawal_days()
        for row in cursor.fetchall():
            user = row_to_dict(cursor, row)
            custom_days = []
            custom_days_str = _safe_get(user, 'custom_withdrawal_days', '')
            if custom_days_str:
                try:
                    custom_days = json.loads(custom_days_str)
                except:
                    custom_days = []
            can_withdraw_today = False
            if not _safe_get(user, 'withdrawal_restricted', False):
                if custom_days:
                    can_withdraw_today = today in custom_days
                else:
                    can_withdraw_today = today in global_days
            users.append({
                "id": user['id'],
                "username": user['username'],
                "balance": float(_safe_get(user, 'balance', 0.00)),
                "withdrawal_restricted": bool(_safe_get(user, 'withdrawal_restricted', False)),
                "custom_withdrawal_days": custom_days,
                "withdrawal_limit": float(_safe_get(user, 'withdrawal_limit', 0.00)),
                "can_withdraw_today": can_withdraw_today,
                "has_withdrawal_pin": bool(_safe_get(user, 'withdrawal_pin', ''))
            })
        conn.close()
        return jsonify({
            "success": True,
            "report_date": datetime.utcnow().isoformat(),
            "today": today,
            "total_users": len(users),
            "users_withdrawal_today": sum(1 for u in users if u['can_withdraw_today']),
            "users_restricted": sum(1 for u in users if u['withdrawal_restricted']),
            "users": users
        })
    except Exception as e:
        print(f"Withdrawal status report error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to generate report"}), 500

@app.route('/api/admin/whatsapp-numbers', methods=['GET', 'POST'])
@require_admin
def manage_whatsapp():
    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM whatsapp_numbers ORDER BY created_at DESC')
            numbers = [row_to_dict(cursor, row) for row in cursor.fetchall()]
            conn.close()
            return jsonify({"success": True, "numbers": numbers})
        except Exception as e:
            print(f"Get WhatsApp numbers error: {e}")
            conn.close()
            return jsonify({"success": False, "message": "Failed to load numbers"}), 500
    data = request.get_json()
    number = sanitize_input(data.get('number', '').strip())
    label = sanitize_input(data.get('label', f"Agent {random.randint(100,999)}"))
    if not number or not number.isdigit():
        return jsonify({"success": False, "message": "Valid WhatsApp number required"}), 400
    if not number.startswith('234'):
        return jsonify({"success": False, "message": "Number must start with 234 (Nigeria)"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        cursor.execute(f'INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES ({ph}, {ph}, {ph}, {ph})',
                       (number, label, True if is_postgres else 1, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Number added"})
    except Exception as e:
        print(f"Add WhatsApp number error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Number already exists"}), 409

@app.route('/api/admin/whatsapp-numbers/<int:number_id>', methods=['DELETE'])
@require_admin
def delete_whatsapp_number(number_id):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'DELETE FROM whatsapp_numbers WHERE id = {ph}', (number_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Number removed"})
    except Exception as e:
        print(f"Delete WhatsApp number error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to remove number"}), 500

@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
def admin_get_coupons():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, status FROM coupons ORDER BY code ASC')
        coupons = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        conn.close()
        total = len(coupons)
        available = sum(1 for c in coupons if c['status'] == 'AVAILABLE')
        used = sum(1 for c in coupons if c['status'] == 'USED')
        return jsonify({
            "success": True,
            "coupons": coupons,
            "stats": {"total": total, "available": available, "used": used}
        })
    except Exception as e:
        print(f"Get coupons error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load coupons"}), 500

@app.route('/api/admin/coupons/add', methods=['POST'])
@require_admin
def admin_add_coupons():
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes or not isinstance(codes, list):
        return jsonify({"success": False, "message": "Provide an array of coupon codes"}), 400
    cleaned_codes = []
    for code in codes:
        code = sanitize_input(str(code).strip().upper())
        if code and len(code) >= 4:
            cleaned_codes.append(code)
    if not cleaned_codes:
        return jsonify({"success": False, "message": "No valid codes provided"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    added = 0
    duplicates = 0
    try:
        for code in cleaned_codes:
            try:
                cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
                added += 1
            except:
                duplicates += 1
                continue
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Added {added} coupons ({duplicates} duplicates skipped)",
            "added": added,
            "duplicates": duplicates
        })
    except Exception as e:
        print(f"Add coupons error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to add coupons"}), 500

@app.route('/api/admin/coupons/delete', methods=['POST'])
@require_admin
def admin_delete_coupons():
    data = request.get_json()
    codes = data.get('codes', [])
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        if not codes or len(codes) == 0:
            cursor.execute('DELETE FROM coupons')
            deleted = cursor.rowcount
        else:
            deleted = 0
            for code in codes:
                code = sanitize_input(str(code).strip().upper())
                cursor.execute(f'DELETE FROM coupons WHERE code = {ph}', (code,))
                if cursor.rowcount > 0:
                    deleted += 1
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Deleted {deleted} coupons",
            "deleted": deleted
        })
    except Exception as e:
        print(f"Delete coupons error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to delete coupons"}), 500

@app.route('/api/admin/coupons/reset-used', methods=['POST'])
@require_admin
def admin_reset_used_coupons():
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f"UPDATE coupons SET status = {ph} WHERE status = {ph}", ('AVAILABLE', 'USED'))
        reset_count = cursor.rowcount
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Reset {reset_count} used coupons to available",
            "reset_count": reset_count
        })
    except Exception as e:
        print(f"Reset coupons error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to reset coupons"}), 500

# ✅ NEW TIKTOK ADMIN ENDPOINTS
@app.route('/api/admin/tiktok/set-daily', methods=['POST'])
@require_admin
def admin_set_tiktok_daily():
    data = request.get_json()
    link = (data.get('tiktok_link') or '').strip()
    if not link:
        return jsonify({'success': False, 'message': 'TikTok link is required.'}), 400
    if not link.startswith('https://www.tiktok.com/@'):
        return jsonify({'success': False, 'message': 'Invalid TikTok profile link. Must start with https://www.tiktok.com/@'}), 400
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO tiktok_daily (date, tiktok_link, reward_amount)
        VALUES (?, ?, ?)
        ''', (today, link, CONFIG.TIKTOK_REWARD))
        conn.commit()
        cleanup_old_tiktok_tasks()  # Immediate cleanup
        conn.close()
        return jsonify({'success': True, 'message': 'TikTok daily task set.'})
    except Exception as e:
        print(f"Admin set TikTok error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'message': 'Failed to set task.'}), 500

@app.route('/api/admin/tiktok/get-daily', methods=['GET'])
@require_admin
def admin_get_tiktok_daily():
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT date, tiktok_link, reward_amount FROM tiktok_daily WHERE date = ?', (today,))
        task_row = cursor.fetchone()
        conn.close()
        if task_row:
            task = row_to_dict(cursor, task_row)
            return jsonify({
                'success': True,
                'task': {
                    'date': task['date'],
                    'tiktok_link': task['tiktok_link'],
                    'reward_amount': task['reward_amount']
                }
            })
        else:
            return jsonify({'success': True, 'task': None})
    except Exception as e:
        print(f"Admin get TikTok error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Failed to fetch task.'}), 500

@app.route('/api/admin/tiktok/history', methods=['GET'])
@require_admin
def admin_tiktok_history():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT date, tiktok_link, reward_amount
        FROM tiktok_daily
        WHERE date >= date('now', '-7 days')
        ORDER BY date DESC
        LIMIT 7
        ''')
        history = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        print(f"Admin TikTok history error: {e}")
        conn.close()
        return jsonify({'success': False, 'message': 'Failed to load history.'}), 500

@app.route('/api/coupon/whatsapp-numbers', methods=['GET'])
def get_active_whatsapp_numbers():
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        if is_postgres:
            cursor.execute('SELECT number FROM whatsapp_numbers WHERE is_active = TRUE ORDER BY created_at DESC LIMIT 1')
        else:
            cursor.execute('SELECT number FROM whatsapp_numbers WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        if row:
            number_dict = row_to_dict(cursor, row)
            return jsonify({"success": True, "number": number_dict['number']})
        return jsonify({"success": False, "message": "No WhatsApp seller available"})
    except Exception as e:
        print(f"Get WhatsApp numbers error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load WhatsApp numbers"}), 500

@app.route('/api/admin/banks', methods=['GET'])
def get_banks():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, name FROM banks')
        banks = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "banks": banks})
    except Exception as e:
        print(f"Get banks error: {e}")
        conn.close()
        return jsonify({"success": False, "message": "Failed to load banks"}), 500

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def admin_change_password():
    admin = get_current_user()
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password or len(new_password) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters"}), 400
    if not check_password_hash(admin['password'], current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    is_postgres = os.environ.get('DATABASE_URL') is not None
    try:
        cursor.execute(f"UPDATE users SET password = {ph}, admin_password_changed = {ph} WHERE id = {ph}",
                       (generate_password_hash(new_password), True if is_postgres else 1, admin['id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Password updated successfully"})
    except Exception as e:
        print(f"Admin password change error: {e}")
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Failed to update password"}), 500

# ================= HEALTH CHECK =================
@app.route('/api/health')
def api_health():
    return jsonify({"status": "online", "service": "FLEXIA API"}), 200

# ================= MAIN (for local dev only) =================
if __name__ == '__main__':
    # Already initialized above, but safe for local dev
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=(os.getenv('ENV') != 'production'))
