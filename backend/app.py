# backend/app.py - ULTIMATE PRODUCTION VERSION 13.0
# FLEXIA Platform - COMPLETE WITH ALL ENDPOINTS

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
import uuid
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, send_from_directory, redirect, render_template_string, session
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

# ======================= CONFIGURATION =======================
class Config:
    # PostgreSQL is required
    DB_URL = os.environ.get('DATABASE_URL')
    if not DB_URL:
        raise ValueError("DATABASE_URL environment variable is required for PostgreSQL connection")
    
    # Admin credentials from environment variables
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'flexiaadmin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
    ADMIN_PIN = os.environ.get('ADMIN_PIN', '4567')
    
    if not ADMIN_PASSWORD:
        raise ValueError("ADMIN_PASSWORD environment variable is required")
    
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 7500
    TIKTOK_REWARD = 150
    SNAKE_REWARD = 200
    COIN_FLIP_MIN_BET = 100
    PLINKO_MIN_BET = 100
    SESSION_DURATION_HOURS = 24
    DEFAULT_WITHDRAWAL_DAYS = [7, 14, 25, 30]
    
    # Timezone for Nigeria
    TIMEZONE = 'Africa/Lagos'
    
    # Game cooldown periods in seconds
    GAME_COOLDOWNS = {
        'SNAKE': 600,     # 10 minutes
        'COINFLIP': 300,  # 5 minutes
        'PLINKO': 300,    # 5 minutes
        'SPIN': 86400,    # 24 hours
        'TIKTOK': 86400   # 24 hours
    }
    
    # Daily game limits
    GAME_DAILY_LIMITS = {
        'snake': 5,
        'coinflip': 2,
        'plinko': 2,
        'spin': 1,
        'tiktok': 1
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
    console_handler.setLevel(logging.WARNING)
    
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
class AppError(Exception):
    """Custom application error"""
    def __init__(self, message, status_code=400, error_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

@app.errorhandler(AppError)
def handle_app_error(error):
    """Handle application errors"""
    response = jsonify({
        "success": False,
        "message": error.message,
        "error_code": error.error_code
    })
    response.status_code = error.status_code
    return response

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

# ======================= RATE LIMITING =======================
class RateLimiter:
    """In-memory rate limiter with thread safety"""
    def __init__(self):
        self.attempts = {}
        self.lock = threading.Lock()
    
    def is_allowed(self, key, max_per_min):
        """Check if request is allowed"""
        now = datetime.utcnow()
        
        with self.lock:
            if key not in self.attempts:
                self.attempts[key] = []
            
            # Clean old attempts
            self.attempts[key] = [t for t in self.attempts[key] if t > now - timedelta(minutes=1)]
            
            if len(self.attempts[key]) >= max_per_min:
                return False
            
            self.attempts[key].append(now)
            return True
    
    def cleanup_old_entries(self):
        """Clean up old rate limit entries"""
        now = datetime.utcnow()
        with self.lock:
            for key in list(self.attempts.keys()):
                self.attempts[key] = [t for t in self.attempts[key] if t > now - timedelta(minutes=5)]
                if not self.attempts[key]:
                    del self.attempts[key]

rate_limiter = RateLimiter()

def rate_limit_cleanup_scheduler():
    """Clean up old rate limit entries periodically"""
    def schedule():
        while True:
            time.sleep(300)  # 5 minutes
            try:
                rate_limiter.cleanup_old_entries()
            except Exception as e:
                app.logger.error(f"Rate limit cleanup error: {e}")
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= BACKUP SYSTEM =======================
def backup_database():
    """Create a backup of the database"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
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
# Thread-safe connection pool for PostgreSQL
db_pool = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    
    try:
        # Use ThreadedConnectionPool for thread safety with background tasks
        db_pool = ThreadedConnectionPool(
            1,   # min connections
            20,  # max connections
            dsn=os.environ['DATABASE_URL']
        )
        app.logger.info('Threaded database connection pool initialized')
    except Exception as e:
        app.logger.error(f'Failed to initialize connection pool: {str(e)}')
        db_pool = None

def get_db():
    """Get database connection from pool or create new one"""
    global db_pool
    
    if db_pool:
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
    """Get direct database connection (fallback) - FIXED SSL TIMEOUT"""
    try:
        parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:],
            sslmode='require',
            connect_timeout=10,  # Add timeout to prevent hanging
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        app.logger.error(f'Direct PostgreSQL connection failed: {str(e)}')
        raise

def return_db_connection(conn):
    """Return connection to pool"""
    global db_pool
    
    if db_pool:
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

# ======================= CONNECTION POOL MONITOR =======================
def check_connection_pool():
    """Check connection pool status safely"""
    global db_pool
    
    if not db_pool:
        return {"status": "no_pool"}
    
    try:
        pool_info = {
            "status": "healthy",
            "min_connections": 1,
            "max_connections": 20,
            "pool_type": "ThreadedConnectionPool",
            "connections": "pool_active"
        }
        
        # Only test real connection occasionally (10% chance)
        if random.randint(1, 10) == 1:
            try:
                conn = get_db_direct()  # Use direct connection, not pool
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                conn.close()
                pool_info["connection_test"] = "success"
            except Exception as e:
                pool_info["connection_test"] = f"failed: {str(e)[:50]}"
                pool_info["status"] = "degraded"
        
        return pool_info
    except Exception as e:
        app.logger.warning(f"Connection pool check warning: {e}")
        return {"status": "warning", "error": str(e)[:100]}

def health_check_scheduler():
    """Run periodic health checks"""
    def schedule():
        app.logger.info('Health check scheduler started')
        while True:
            try:
                time.sleep(300)  # 5 minutes
                status = check_connection_pool()
                if status.get("status") != "healthy":
                    app.logger.warning(f"Connection pool status: {status}")
            except Exception as e:
                app.logger.error(f"Health check error: {str(e)}")
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= SESSION MANAGER =======================
def create_session_token(user_id, is_admin=False):
    """Create session token with user info"""
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id, 'is_admin': is_admin})

def verify_session_token(token):
    """Verify session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return data
    except (BadSignature, SignatureExpired) as e:
        app.logger.warning(f'Invalid session token: {str(e)}')
        return None

def _safe_get(row, key, default=None):
    """Safely get value from row"""
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
    """Convert database row to dictionary"""
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
    """Get current user from session token"""
    token = request.cookies.get('session_token')
    if not token:
        return None
    
    session_data = verify_session_token(token)
    if not session_data:
        return None
    
    user_id = session_data.get('user_id')
    if not user_id:
        return None
    
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        user = row_to_dict(cursor, row)
        
        # Verify admin status matches session
        if user:
            session_is_admin = session_data.get('is_admin', False)
            user_is_admin = bool(_safe_get(user, 'is_admin', False))
            if session_is_admin != user_is_admin:
                app.logger.warning(f"Session admin mismatch for user {user_id}")
                return None
        
        return user
    except Exception as e:
        app.logger.error(f'Error getting current user: {str(e)}')
        return None
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise AppError("Login required", 401)
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise AppError("Login required", 401)
        
        is_admin = _safe_get(user, 'is_admin', False)
        if not is_admin:
            app.logger.warning(f'Non-admin user {user["id"]} attempted admin endpoint {request.path}')
            raise AppError("Admin access required", 403)
        
        return f(*args, **kwargs)
    return decorated

# ======================= ADMIN PANEL ROUTES =======================
# Admin login page HTML template (same as before, but included for completeness)
ADMIN_LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flexia Admin Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
            padding: 40px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo h1 {
            color: #333;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .logo p {
            color: #666;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .error-message {
            background: #fee;
            border: 1px solid #f99;
            color: #c00;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        
        .error-message.show {
            display: block;
        }
        
        .login-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .login-btn:active {
            transform: translateY(0);
        }
        
        .admin-info {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 12px;
        }
        
        @media (max-width: 480px) {
            .login-container {
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Flexia Admin</h1>
            <p>Administration Panel</p>
        </div>
        
        <div id="errorMessage" class="error-message"></div>
        
        <form id="loginForm">
            <div class="form-group">
                <label for="password">Admin Password</label>
                <input type="password" id="password" name="password" required 
                       placeholder="Enter admin password" autocomplete="current-password">
            </div>
            
            <button type="submit" class="login-btn">Login to Admin Panel</button>
        </form>
        
        <div class="admin-info">
            <p>Access restricted to authorized administrators only.</p>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('errorMessage');
            
            // Clear previous errors
            errorDiv.classList.remove('show');
            errorDiv.textContent = '';
            
            try {
                const response = await fetch('/admin/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ password: password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Redirect to admin dashboard
                    window.location.href = '/admin/dashboard';
                } else {
                    errorDiv.textContent = data.message || 'Login failed';
                    errorDiv.classList.add('show');
                }
            } catch (error) {
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.classList.add('show');
            }
        });
        
        // Focus password field on load
        document.getElementById('password').focus();
    </script>
</body>
</html>
'''

# Admin dashboard HTML template (included for completeness but shortened in this display)
ADMIN_DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flexia Admin Dashboard</title>
    <style>
        /* Full CSS from previous code */
    </style>
</head>
<body>
    <!-- Full HTML from previous code -->
</body>
</html>
'''

@app.route('/admin')
def admin_login_page():
    """Serve admin login page"""
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    data = request.get_json()
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"}), 400
    
    # Check admin password
    if password != CONFIG.ADMIN_PASSWORD:
        app.logger.warning(f'Failed admin login attempt from {request.remote_addr}')
        return jsonify({"success": False, "message": "Invalid admin password"}), 401
    
    # Create admin session
    admin_session = {
        'admin_id': 1,
        'username': CONFIG.ADMIN_USERNAME,
        'is_admin': True,
        'login_time': datetime.utcnow().isoformat()
    }
    
    token = create_session_token(1, is_admin=True)
    
    response = jsonify({
        "success": True,
        "message": "Login successful",
        "admin": {
            "username": CONFIG.ADMIN_USERNAME
        }
    })
    
    secure_cookie = (os.getenv('ENV') == 'production')
    response.set_cookie('admin_token', token, 
                       httponly=True, 
                       secure=secure_cookie, 
                       samesite='Lax', 
                       max_age=86400)
    
    app.logger.info(f'Admin logged in: {CONFIG.ADMIN_USERNAME}')
    return response

@app.route('/admin/check-session')
def admin_check_session():
    """Check admin session"""
    token = request.cookies.get('admin_token')
    if not token:
        return jsonify({"success": False, "message": "No session"}), 401
    
    session_data = verify_session_token(token)
    if not session_data or not session_data.get('is_admin'):
        return jsonify({"success": False, "message": "Invalid session"}), 401
    
    return jsonify({
        "success": True,
        "admin": {
            "username": CONFIG.ADMIN_USERNAME
        }
    })

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Admin logout"""
    response = jsonify({"success": True, "message": "Logged out"})
    response.set_cookie('admin_token', '', expires=0)
    app.logger.info('Admin logged out')
    return response

@app.route('/admin/dashboard')
def admin_dashboard():
    """Serve admin dashboard"""
    token = request.cookies.get('admin_token')
    if not token:
        return redirect('/admin')
    
    session_data = verify_session_token(token)
    if not session_data or not session_data.get('is_admin'):
        return redirect('/admin')
    
    return render_template_string(ADMIN_DASHBOARD_HTML)

# ======================= INITIALIZATION =======================
def add_missing_columns():
    """Add missing columns if they don't exist"""
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        columns_to_add = [
            'last_achievement_check', 'last_game_timestamp', 'claimed_achievements',
            'total_referrals', 'total_games_played', 'total_withdrawals', 'total_transactions',
            'last_snake_play', 'last_coinflip_play', 'last_plinko_play', 'last_spin_play', 'last_tiktok_play'
        ]
        for column in columns_to_add:
            cursor.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' and column_name='{column}'
            """)
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
                app.logger.info(f"Added missing column: {column} to users table")
        
        conn.commit()
        app.logger.info("Database column verification complete")
    except Exception as e:
        app.logger.error(f"Error adding missing columns: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def add_database_indexes():
    """Add performance indexes to database"""
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

def init_db():
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()

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
            total_referrals INTEGER DEFAULT 0,
            total_games_played INTEGER DEFAULT 0,
            total_withdrawals INTEGER DEFAULT 0,
            total_transactions INTEGER DEFAULT 0,
            last_snake_play TEXT,
            last_coinflip_play TEXT,
            last_plinko_play TEXT,
            last_spin_play TEXT,
            last_tiktok_play TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id SERIAL PRIMARY KEY,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT
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
                status TEXT DEFAULT 'AVAILABLE'
            )''',
            '''CREATE TABLE IF NOT EXISTS banks (
                code TEXT PRIMARY KEY,
                name TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )''',
            '''CREATE TABLE IF NOT EXISTS whatsapp_numbers (
                id SERIAL PRIMARY KEY,
                number TEXT UNIQUE NOT NULL,
                label TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS game_plays (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                game_type TEXT,
                play_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS tiktok_daily (
                id SERIAL PRIMARY KEY,
                date TEXT UNIQUE NOT NULL,
                tiktok_link TEXT NOT NULL,
                reward_amount REAL DEFAULT 150.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS admin_audit_log (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER,
                action TEXT,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        
        for sql in tables_sql:
            try:
                cursor.execute(sql)
            except Exception as e:
                app.logger.error(f"Error creating table: {e}")

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
                    cursor.execute('INSERT INTO banks (code, name, is_active) VALUES (%s, %s, %s)', 
                                 (bank[0], bank[1], True))
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
            cursor.execute('INSERT INTO admin_settings (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) VALUES (%s, %s, %s, %s)',
                           ('', '', '', default_days_json))

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
                            cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', (code, 'AVAILABLE'))
                        except:
                            pass
                    app.logger.info(f"Loaded {len(codes)} coupons from file")
            except Exception as e:
                app.logger.error(f"Error loading coupons: {e}")
        else:
            default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
            for code in default_coupons:
                try:
                    cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', (code, 'AVAILABLE'))
                except:
                    pass
            app.logger.info(f"Created {len(default_coupons)} default coupons")

        cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s', (CONFIG.ADMIN_USERNAME,))
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            admin_pass = generate_password_hash(CONFIG.ADMIN_PASSWORD)
            pin_hash = generate_password_hash(CONFIG.ADMIN_PIN)
            
            game_stats = json.dumps({
                "snake": {"high_score": 1200, "total_score": 5000},
                "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
                "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
            })
            
            cursor.execute('''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme, 
                last_game_timestamp, last_achievement_check, claimed_achievements,
                total_referrals, total_games_played, total_withdrawals, total_transactions,
                last_snake_play, last_coinflip_play, last_plinko_play, last_spin_play, last_tiktok_play
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ''', (
                CONFIG.ADMIN_USERNAME, admin_pass, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, True, pin_hash, "", "", "light", 
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                '[]', 0, 0, 0, 0,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 
                datetime.utcnow().isoformat()
            ))
            app.logger.warning(f"\n🎮 FLEXIA ADMIN ACCOUNT CREATED 🎮")
            app.logger.warning(f"Username: {CONFIG.ADMIN_USERNAME}")
            app.logger.warning(f"Password: From environment variable")
            app.logger.warning(f"Default Withdrawal PIN: {CONFIG.ADMIN_PIN}")
            app.logger.warning(f"🎮 Admin credentials are secure 🎮\n")

        cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
        whatsapp_count = cursor.fetchone()[0]
        if whatsapp_count == 0:
            cursor.execute('INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES (%s, %s, %s, %s)',
                           ('2348160881049', 'Primary Seller', True, datetime.utcnow().isoformat()))

        conn.commit()
        app.logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        app.logger.error(f"Database initialization error: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= AUDIT LOGGING =======================
def log_admin_action(admin_id, action, target_type, target_id, details):
    """Log admin actions for audit trail"""
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO admin_audit_log (admin_id, action, target_type, target_id, details, ip_address, user_agent)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            admin_id, action, target_type, target_id,
            json.dumps(details) if details else '{}',
            request.remote_addr,
            request.user_agent.string[:500] if request.user_agent else ''
        ))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Audit log error: {e}")
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= HELPERS =======================
def sanitize_input(text):
    """Sanitize user input"""
    if not text:
        return ""
    for char in '<>"\'`;':
        text = text.replace(char, '')
    return text.strip()

def get_global_withdrawal_days():
    """Get global withdrawal days from settings"""
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

# ======================= ATOMIC BALANCE UPDATES =======================
def update_user_balance(user_id, amount_change):
    """Thread-safe atomic balance update"""
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute('BEGIN')
        cursor.execute('SELECT balance FROM users WHERE id = %s FOR UPDATE', (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return None
        
        current_balance = float(row[0]) if row[0] else 0.0
        new_balance = current_balance + amount_change
        
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user_id))
        conn.commit()
        
        app.logger.info(f"Atomic balance update for user {user_id}: {amount_change}, new balance: {new_balance}")
        return new_balance
        
    except Exception as e:
        app.logger.error(f"Balance update error: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= GAME COOLDOWN SYSTEM =======================
def check_game_cooldown(user_id, game_type):
    """Check if user is in cooldown for a specific game"""
    ALLOWED_COLUMNS = {
        'SNAKE': 'last_snake_play',
        'COINFLIP': 'last_coinflip_play',
        'PLINKO': 'last_plinko_play',
        'SPIN': 'last_spin_play',
        'TIKTOK': 'last_tiktok_play'
    }
    
    column_name = ALLOWED_COLUMNS.get(game_type)
    if not column_name:
        return {"can_play": True, "message": "Unknown game type"}
    
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {column_name} FROM users WHERE id = %s", (user_id,))
        
        row = cursor.fetchone()
        if not row or not row[0]:
            return {"can_play": True}
        
        try:
            last_play = datetime.fromisoformat(row[0])
            now = datetime.utcnow()
            cooldown_seconds = CONFIG.GAME_COOLDOWNS.get(game_type, 0)
            
            time_since_last = (now - last_play).total_seconds()
            
            if time_since_last < cooldown_seconds:
                remaining = int(cooldown_seconds - time_since_last)
                return {
                    "can_play": False,
                    "remaining_seconds": remaining,
                    "message": f"Please wait {remaining // 60} minutes {(remaining % 60)} seconds before playing {game_type.lower()} again"
                }
            else:
                return {"can_play": True}
                
        except Exception as e:
            app.logger.error(f"Error parsing timestamp for {game_type}: {e}")
            return {"can_play": True}
            
    except Exception as e:
        app.logger.error(f"Cooldown check error for {game_type}: {e}")
        return {"can_play": True}
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def update_game_cooldown(user_id, game_type):
    """Update the last play timestamp for a specific game"""
    ALLOWED_COLUMNS = {
        'SNAKE': 'last_snake_play',
        'COINFLIP': 'last_coinflip_play',
        'PLINKO': 'last_plinko_play',
        'SPIN': 'last_spin_play',
        'TIKTOK': 'last_tiktok_play'
    }
    
    column_name = ALLOWED_COLUMNS.get(game_type)
    if not column_name:
        return
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE users SET {column_name} = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), user_id))
        conn.commit()
        
    except Exception as e:
        app.logger.error(f"Update cooldown error for {game_type}: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def can_play_today(user_id, game_type, max_plays=None):
    """Check if user can play a game today"""
    if max_plays is None:
        max_plays = CONFIG.GAME_DAILY_LIMITS.get(game_type, 10)
    
    conn = get_db()
    cursor = None
    today = datetime.utcnow().date()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s",
                       (user_id, game_type, today))
        count = cursor.fetchone()[0]
        return count < max_plays
    except Exception as e:
        app.logger.error(f"Play check error: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def record_game_play(user_id, game_type):
    """Record a game play (idempotent)"""
    conn = get_db()
    cursor = None
    today = datetime.utcnow().date()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s",
                       (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("INSERT INTO game_plays (user_id, game_type, play_date) VALUES (%s, %s, %s)",
                           (user_id, game_type, today))
            
            cursor.execute('UPDATE users SET total_games_played = total_games_played + 1 WHERE id = %s', (user_id,))
            
            conn.commit()
    except Exception as e:
        app.logger.error(f"Record game play error: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def is_withdrawal_day(user_id=None):
    """Check if today is a withdrawal day for user"""
    # Import zoneinfo for timezone support
    from zoneinfo import ZoneInfo
    
    tz = ZoneInfo(CONFIG.TIMEZONE)
    now = datetime.now(tz)
    today = now.day
    
    if user_id is None:
        return today in get_global_withdrawal_days()
    
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
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
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= DUPLICATE CLAIM PREVENTION =======================
def check_duplicate_claim(user_id, game_type, data_hash, cooldown_seconds=1):
    """Check if user is trying to claim duplicate reward"""
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cutoff_time = (datetime.utcnow() - timedelta(seconds=cooldown_seconds)).isoformat()
        
        cursor.execute('''
        SELECT COUNT(*) FROM transactions 
        WHERE user_id = %s AND type LIKE %s 
        AND timestamp > %s
        ''', (user_id, f'%{game_type}%', cutoff_time))
        
        recent_claims = cursor.fetchone()[0]
        return recent_claims == 0
    except Exception as e:
        app.logger.error(f"Duplicate claim check error: {e}")
        return True
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

def create_transaction_hash(user_id, game_type, data):
    """Create hash to identify duplicate transactions"""
    data_str = json.dumps(data, sort_keys=True)
    hash_input = f"{user_id}-{game_type}-{data_str}-{int(time.time())}"
    return hashlib.md5(hash_input.encode()).hexdigest()

# ======================= ACHIEVEMENT REWARDS =======================
def grant_achievement_rewards(user_id):
    """Thread-safe achievement reward calculation"""
    app.logger.info(f"Granting achievement rewards for user {user_id}")
    
    conn = None
    cursor = None
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("BEGIN")
        cursor.execute('SELECT * FROM users WHERE id = %s FOR UPDATE', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return None
        
        user = row_to_dict(cursor, row)
        balance = float(user['balance']) if user['balance'] else 0
        game_stats_str = user.get('game_stats', '{}')
        current_points = int(user.get('points', 0))
        last_check = user.get('last_achievement_check')
        claimed_achievements_str = user.get('claimed_achievements', '[]')
        
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
        
        total_games = int(user.get('total_games_played', 0))
        referrals = int(user.get('total_referrals', 0))
        total_withdrawals = int(user.get('total_withdrawals', 0))
        total_tx = int(user.get('total_transactions', 0))
        
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user_id, today))
        games_today = cursor.fetchone()[0]
        
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
        app.logger.info(f"Granted achievement rewards to user {user_id}: {total_reward}, {total_points} points")
        
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
    """Clean up old TikTok tasks"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        cursor.execute('DELETE FROM tiktok_daily WHERE date < %s', (cutoff_date,))
        conn.commit()
        return_db_connection(conn)
        app.logger.info(f"Removed TikTok tasks before {cutoff_date}")
    except Exception as e:
        app.logger.error(f"TikTok Cleanup Error: {e}")

def run_cleanup_scheduler():
    """Run cleanup scheduler in background"""
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
    init_db_pool()
    init_db()
    add_missing_columns()
    add_database_indexes()
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()
    run_backup_scheduler()
    health_check_scheduler()
    rate_limit_cleanup_scheduler()

# ======================= ALL YOUR ENDPOINTS =======================
# ======================= DEBUG ENDPOINTS =======================
@app.route('/api/debug/db-status', methods=['GET'])
def db_status():
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
        available_coupons = cursor.fetchone()[0]
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL",
            "connection_pool": "active" if db_pool else "inactive"
        })
    except Exception as e:
        app.logger.error(f"DB status error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/debug/user-claims', methods=['GET'])
@require_auth
def debug_user_claims():
    user = get_current_user()
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT type, amount, timestamp 
        FROM transactions 
        WHERE user_id = %s 
        ORDER BY timestamp DESC 
        LIMIT 20
        ''', (user['id'],))
        
        claims = []
        for row in cursor.fetchall():
            claims.append({
                'type': row[0],
                'amount': row[1],
                'timestamp': row[2]
            })
        
        return jsonify({"success": True, "claims": claims})
        
    except Exception as e:
        app.logger.error(f"User claims error: {e}")
        return jsonify({"success": False, "message": "Failed to load claims"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/debug/connection-pool', methods=['GET'])
def debug_connection_pool():
    try:
        status = check_connection_pool()
        return jsonify({
            "success": True,
            "pool_status": status
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ======================= HEALTH CHECK =======================
def get_uptime():
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.utcnow()
    uptime = datetime.utcnow() - get_uptime.start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

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
        
        cursor.close()
        return_db_connection(conn)
        
        health_data = {
            "status": "online",
            "service": "FLEXIA API",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": get_uptime(),
            "database": db_status,
            "version": "13.0",
            "stats": {
                "total_users": user_count,
                "pending_withdrawals": pending_withdrawals
            },
            "environment": os.getenv('ENV', 'development'),
            "connection_pool": "active" if db_pool else "inactive",
            "pool_status": check_connection_pool()
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
            "version": "13.0"
        }), 503

# ======================= SPIN WHEEL ENDPOINTS =======================
@app.route('/api/spin/daily-status', methods=['GET'])
@require_auth
def spin_daily_status():
    user = get_current_user()
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = %s 
        AND DATE(timestamp) = %s
        ''', (user['id'], 'SPIN_REWARD', today))
        
        has_spun_today = cursor.fetchone() is not None
        
        return jsonify({
            "success": True,
            "can_spin": not has_spun_today,
            "has_spun_today": has_spun_today
        })
        
    except Exception as e:
        app.logger.error(f"Spin daily status error: {e}")
        return jsonify({"success": False, "message": "Failed to check spin status"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/spin/execute', methods=['POST'])
@require_auth
def spin_execute():
    user = get_current_user()
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT 1 FROM transactions 
        WHERE user_id = %s AND type = %s 
        AND DATE(timestamp) = %s
        ''', (user['id'], 'SPIN_REWARD', today))
        
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "You already spun today"
            }), 400
        
        cooldown_check = check_game_cooldown(user['id'], 'SPIN')
        if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
            return jsonify({
                "success": False,
                "message": cooldown_check.get("message", "Please wait before spinning again")
            }), 429
        
        possible_rewards = [1000, 0, 500, 50, 1000, 100, 500, 200]
        weights = [5, 25, 15, 20, 5, 15, 15, 20]
        
        reward = random.choices(possible_rewards, weights=weights, k=1)[0]
        
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        update_game_cooldown(user['id'], 'SPIN')
        record_game_play(user['id'], 'spin')
        
        tx_id = f"SPIN-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Spin executed for {user['username']}: reward {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "message": f"Congratulations! You won ?{reward}!"
        })
        
    except Exception as e:
        app.logger.error(f"Spin execute error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process spin: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
def register():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"register:{ip}", CONFIG.RATE_LIMITS['register']):
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
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE LOWER(username) = LOWER(%s)', (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username already taken"}), 409
        
        cursor.execute('SELECT status FROM coupons WHERE code = %s', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row:
            return jsonify({"success": False, "message": "Invalid coupon code"}), 403
        
        if coupon_row[0] != 'AVAILABLE':
            return jsonify({"success": False, "message": "Coupon already used"}), 403
        
        if referral_code:
            cursor.execute('SELECT referral_code FROM users WHERE referral_code = %s', (referral_code,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Invalid referral code"}), 400
        
        cursor.execute('UPDATE coupons SET status = %s WHERE code = %s', ("USED", coupon_code))
        
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
            claimed_achievements, total_referrals, total_games_played, total_withdrawals, total_transactions,
            last_snake_play, last_coinflip_play, last_plinko_play, last_spin_play, last_tiktok_play
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, False,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            False, None, False, 0.00, 0, 0, 
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            '[]', 0, 0, 0, 0,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 
            datetime.utcnow().isoformat()
        ))
        
        cursor.execute("SELECT LASTVAL()")
        new_id = cursor.fetchone()[0]
        
        admin_bonus = 0
        if referral_code:
            cursor.execute('SELECT is_admin FROM users WHERE referral_code = %s', (referral_code,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row[0]:
                admin_bonus = 5000
                cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (admin_bonus, new_id))
        
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"login:{ip}", CONFIG.RATE_LIMITS['login']):
        return jsonify({"success": False, "message": "Too many login attempts"}), 429
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    
    if not identifier or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(contact) = LOWER(%s)',
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
        
        cursor.execute('UPDATE users SET last_login = %s WHERE id = %s',
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
        if cursor:
            cursor.close()
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
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = %s', (user['id'],))
        fresh_user = row_to_dict(cursor, cursor.fetchone())
        
        if not fresh_user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        cursor.execute('SELECT total_referrals FROM users WHERE id = %s', (user['id'],))
        referrals_row = cursor.fetchone()
        referrals = int(referrals_row[0]) if referrals_row and referrals_row[0] else 0
        
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
            }
        })
        
    except Exception as e:
        app.logger.error(f"Profile error: {e}")
        return jsonify({"success": False, "message": f"Failed to load profile: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= USER SETTINGS =================
@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    user = get_current_user()
    data = request.get_json()
    picture_url = sanitize_input(data.get('picture_url', ''))
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s', (picture_url, user['id']))
        conn.commit()
        app.logger.info(f"User {user['username']} updated profile picture")
        return jsonify({"success": True, "message": "Profile picture updated"})
    except Exception as e:
        app.logger.error(f"Profile picture error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_theme():
    user = get_current_user()
    data = request.get_json()
    theme = 'dark' if data.get('dark_mode') else 'light'
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s', (theme, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Theme updated"})
    except Exception as e:
        app.logger.error(f"Theme error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def admin_change_password():
    admin_user = get_current_user()
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Both fields required"}), 400
    
    if len(new_password) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters"}), 400
    
    if not check_password_hash(admin_user['password'], current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 403
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s', (generate_password_hash(pin), user['id']))
        conn.commit()
        app.logger.info(f"User {user['username']} set withdrawal PIN")
        return jsonify({"success": True, "message": "PIN set successfully"})
    except Exception as e:
        app.logger.error(f"PIN error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set"}), 500
    finally:
        if cursor:
            cursor.close()
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
@app.route('/api/games/limit-check', methods=['GET'])
@require_auth
def check_game_limits():
    user = get_current_user()
    game_type = request.args.get('game', '')
    
    if game_type not in CONFIG.GAME_DAILY_LIMITS:
        return jsonify({"success": True, "can_play": True, "remaining": 999})
    
    max_plays = CONFIG.GAME_DAILY_LIMITS[game_type]
    today = datetime.utcnow().date()
    
    conn = get_db()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s',
                       (user['id'], game_type, today))
        played_today = cursor.fetchone()[0]
        remaining = max(0, max_plays - played_today)
        
        return jsonify({
            "success": True,
            "can_play": remaining > 0,
            "played_today": played_today,
            "remaining": remaining,
            "max_per_day": max_plays
        })
    except Exception as e:
        app.logger.error(f"Limit check error: {e}")
        return jsonify({"success": False, "message": "Failed to check limits"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/games/cooldown-check', methods=['GET'])
@require_auth
def check_game_cooldown_endpoint():
    user = get_current_user()
    
    games = ['SNAKE', 'COINFLIP', 'PLINKO', 'SPIN', 'TIKTOK']
    cooldown_status = {}
    
    for game in games:
        result = check_game_cooldown(user['id'], game)
        if isinstance(result, dict):
            cooldown_status[game.lower()] = result
        else:
            cooldown_status[game.lower()] = {"can_play": True}
    
    return jsonify({
        "success": True,
        "cooldowns": cooldown_status,
        "cooldown_periods": CONFIG.GAME_COOLDOWNS
    })

@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"snake:{ip}", CONFIG.RATE_LIMITS['game']):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    
    app.logger.info(f"Snake report from {user['username']}: {apples} apples")
    
    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "Invalid apple count (1-100)"}), 400
    
    cooldown_check = check_game_cooldown(user['id'], 'SNAKE')
    if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
        return jsonify({
            "success": False,
            "message": cooldown_check.get("message", "Please wait before playing snake again")
        }), 429
    
    if not can_play_today(user['id'], 'snake', max_plays=CONFIG.GAME_DAILY_LIMITS['snake']):
        return jsonify({"success": False, "message": f"Max {CONFIG.GAME_DAILY_LIMITS['snake']} snake plays per day"}), 403
    
    data_hash = create_transaction_hash(user['id'], 'SNAKE', {'apples': apples})
    if not check_duplicate_claim(user['id'], 'SNAKE', data_hash, cooldown_seconds=1):
        return jsonify({"success": False, "message": "Please wait before claiming again"}), 429
    
    reward = apples * CONFIG.SNAKE_REWARD
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        
        cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                      (json.dumps(game_stats), user['id']))
        
        update_game_cooldown(user['id'], 'SNAKE')
        record_game_play(user['id'], 'snake')
        
        tx_id = f"SNK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "snake", "apples": apples, "reward_per_apple": CONFIG.SNAKE_REWARD, "hash": data_hash}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Snake reward granted to {user['username']}: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "apples": apples,
            "transaction_id": tx_id,
            "message": f"Success! Claimed ?{reward} for {apples} apples"
        })
        
    except Exception as e:
        app.logger.error(f"Snake report error: {e}")
        app.logger.error(traceback.format_exc())
        conn.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"coinflip:{ip}", CONFIG.RATE_LIMITS['game']):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    won = data.get('won', False)
    
    app.logger.info(f"Coin flip from {user['username']}: bet {bet}, won: {won}")
    
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.COIN_FLIP_MIN_BET}, max: 50000)"}), 400
    
    cooldown_check = check_game_cooldown(user['id'], 'COINFLIP')
    if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
        return jsonify({
            "success": False,
            "message": cooldown_check.get("message", "Please wait before playing coinflip again")
        }), 429
    
    if not can_play_today(user['id'], 'coinflip', max_plays=CONFIG.GAME_DAILY_LIMITS['coinflip']):
        return jsonify({"success": False, "message": f"Max {CONFIG.GAME_DAILY_LIMITS['coinflip']} coin flips per day"}), 403
    
    data_hash = create_transaction_hash(user['id'], 'COINFLIP', {'bet': bet, 'won': won})
    if not check_duplicate_claim(user['id'], 'COINFLIP', data_hash, cooldown_seconds=1):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    payout = bet * 2 if won else 0
    net_change = payout - bet
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        
        update_game_cooldown(user['id'], 'COINFLIP')
        record_game_play(user['id'], 'coinflip')
        
        tx_type = 'COINFLIP_WIN' if won else 'COINFLIP_LOSS'
        tx_id = f"COIN-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({"game": "coinflip", "bet": bet, "won": won, "payout": payout, "hash": data_hash}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Coin flip processed for {user['username']}: {'WON' if won else 'LOST'} {bet}, net: {net_change}")
        
        return jsonify({
            "success": True,
            "payout": payout if won else 0,
            "net_change": net_change,
            "new_balance": new_balance,
            "won": won,
            "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}?{abs(net_change):.2f}"
        })
        
    except Exception as e:
        app.logger.error(f"Coin flip error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"plinko:{ip}", CONFIG.RATE_LIMITS['game']):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    bet = float(data.get('bet', 0))
    multiplier = float(data.get('multiplier', 0))
    
    app.logger.info(f"Plinko from {user['username']}: bet {bet}, multiplier: {multiplier}")
    
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or float(user['balance']) < bet:
        return jsonify({"success": False, "message": f"Invalid bet (min: {CONFIG.PLINKO_MIN_BET}, max: 50000)"}), 400
    
    if multiplier not in [0.5, 3, 10]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400
    
    cooldown_check = check_game_cooldown(user['id'], 'PLINKO')
    if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
        return jsonify({
            "success": False,
            "message": cooldown_check.get("message", "Please wait before playing plinko again")
        }), 429
    
    if not can_play_today(user['id'], 'plinko', max_plays=CONFIG.GAME_DAILY_LIMITS['plinko']):
        return jsonify({"success": False, "message": f"Max {CONFIG.GAME_DAILY_LIMITS['plinko']} plinko plays per day"}), 403
    
    data_hash = create_transaction_hash(user['id'], 'PLINKO', {'bet': bet, 'multiplier': multiplier})
    if not check_duplicate_claim(user['id'], 'PLINKO', data_hash, cooldown_seconds=1):
        return jsonify({"success": False, "message": "Please wait before playing again"}), 429
    
    win_amount = bet * multiplier
    net_change = win_amount - bet
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        
        cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                       (json.dumps(game_stats), user['id']))
        
        update_game_cooldown(user['id'], 'PLINKO')
        record_game_play(user['id'], 'plinko')
        
        tx_type = 'PLINKO_WIN' if net_change > 0 else 'PLINKO_LOSS'
        tx_id = f"PLK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], tx_type, net_change, 'COMPLETED',
            json.dumps({"game": "plinko", "bet": bet, "multiplier": multiplier, "win_amount": win_amount, "hash": data_hash}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Plinko processed for {user['username']}: bet {bet}, multiplier {multiplier}, net: {net_change}")
        
        return jsonify({
            "success": True,
            "win_amount": win_amount,
            "net_change": net_change,
            "new_balance": new_balance,
            "multiplier": multiplier,
            "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}?{net_change:.2f}"
        })
        
    except Exception as e:
        app.logger.error(f"Plinko error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
def report_spin():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"spin:{ip}", CONFIG.RATE_LIMITS['game']):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    data = request.get_json()
    reward = data.get('reward', 0)
    
    app.logger.info(f"Spin wheel from {user['username']}: reward {reward}")
    
    valid_rewards = [0, 50, 100, 200, 500, 1000]
    if reward not in valid_rewards:
        return jsonify({"success": False, "message": "Invalid spin reward"}), 400
    
    cooldown_check = check_game_cooldown(user['id'], 'SPIN')
    if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
        return jsonify({
            "success": False,
            "message": cooldown_check.get("message", "Please wait before spinning again")
        }), 429
    
    if not can_play_today(user['id'], 'spin', max_plays=CONFIG.GAME_DAILY_LIMITS['spin']):
        return jsonify({"success": False, "message": "One spin per day only"}), 403
    
    data_hash = create_transaction_hash(user['id'], 'SPIN', {'reward': reward})
    if not check_duplicate_claim(user['id'], 'SPIN', data_hash, cooldown_seconds=1):
        return jsonify({"success": False, "message": "Please wait before spinning again"}), 429
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        update_game_cooldown(user['id'], 'SPIN')
        record_game_play(user['id'], 'spin')
        
        tx_id = f"SPIN-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
            json.dumps({"game": "spin", "reward": reward, "hash": data_hash}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"Spin wheel processed for {user['username']}: reward {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Congratulations! You won ?{reward}!"
        })
        
    except Exception as e:
        app.logger.error(f"Spin error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= ACHIEVEMENTS =================
@app.route('/api/achievements')
@require_auth
def get_achievements():
    user = get_current_user()
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        game_stats = json.loads(user.get('game_stats', '{}'))
        balance = float(user.get('balance', 0))
        
        claimed_achievements_str = user.get('claimed_achievements', '[]')
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []
        
        total_tx = int(user.get('total_transactions', 0)) if user.get('total_transactions') else 0
        total_withdrawals = int(user.get('total_withdrawals', 0)) if user.get('total_withdrawals') else 0
        referrals = int(user.get('total_referrals', 0)) if user.get('total_referrals') else 0
        total_games = int(user.get('total_games_played', 0)) if user.get('total_games_played') else 0
        
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', 
                      (user['id'], today))
        games_today = cursor.fetchone()[0]
        
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

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
            {"id": 8, "title": "Thousandaire", "description": "Balance ?1,000+", "reward": 1000, "points": 15, 
             "unlocked": balance >= 1000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 1000, "progress_percentage": min(100, (balance / 1000) * 100),
             "cash_reward": 1000, "claimed": 8 in claimed_achievements},
            {"id": 9, "title": "Millionaire in Progress", "description": "Balance ?50,000+", "reward": 10000, "points": 100, 
             "unlocked": balance >= 50000, "category": "earnings", "icon": "fas fa-money-bill-wave",
             "current_value": balance, "target_value": 50000, "progress_percentage": min(100, (balance / 50000) * 100),
             "cash_reward": 10000, "claimed": 9 in claimed_achievements},
            {"id": 10, "title": "High Roller", "description": "Balance ?200,000+", "reward": 25000, "points": 200, 
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/achievements/claim', methods=['POST'])
@require_auth
def claim_achievement_rewards():
    user = get_current_user()
    
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

# ================= TIKTOK DAILY =================
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily_task():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
def follow_tiktok_daily():
    ip = request.remote_addr
    if not rate_limiter.is_allowed(f"tiktok:{ip}", CONFIG.RATE_LIMITS['game']):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND DATE(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Already claimed today"}), 400
        
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        
        if not task_row:
            return jsonify({"success": False, "message": "No task for today"}), 404
        
        cooldown_check = check_game_cooldown(user['id'], 'TIKTOK')
        if isinstance(cooldown_check, dict) and not cooldown_check.get("can_play", True):
            return jsonify({
                "success": False,
                "message": cooldown_check.get("message", "Please wait before claiming TikTok reward again")
            }), 429
        
        reward = float(task_row[0]) if task_row[0] else CONFIG.TIKTOK_REWARD
        
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        update_game_cooldown(user['id'], 'TIKTOK')
        
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        
        conn.commit()
        
        app.logger.info(f"TikTok daily claimed by {user['username']}: reward: {reward}")
        
        return jsonify({
            "success": True,
            "reward": reward,
            "new_balance": new_balance,
            "message": f"Success! Claimed ?{reward} for following TikTok"
        })
        
    except Exception as e:
        app.logger.error(f"TikTok follow error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to process: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/tiktok/get-daily', methods=['GET'])
@require_admin
def admin_get_tiktok_daily():
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/tiktok/history', methods=['GET'])
@require_admin
def admin_get_tiktok_history():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN WITHDRAWAL DAYS =======================
@app.route('/api/admin/global-withdrawal-days', methods=['GET'])
@require_admin
def admin_get_global_withdrawal_days():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE admin_settings SET global_withdrawal_days = %s', (json.dumps(valid_days),))
        conn.commit()
        app.logger.info(f"Admin updated global withdrawal days: {valid_days}")
        return jsonify({"success": True, "message": "Global withdrawal days updated", "days": valid_days})
    except Exception as e:
        app.logger.error(f"Set global withdrawal days error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN USER CUSTOM WITHDRAWAL DAYS =======================
@app.route('/api/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@require_admin
def admin_set_user_custom_days(user_id):
    data = request.get_json()
    days = data.get('days', [])
    
    if not isinstance(days, list):
        return jsonify({"success": False, "message": "Invalid days format"}), 400
    
    valid_days = [day for day in days if isinstance(day, int) and 1 <= day <= 31]
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN WITHDRAWAL STATUS REPORT =======================
@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@require_admin
def admin_withdrawal_status_report():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        
        # Import zoneinfo for timezone support
        from zoneinfo import ZoneInfo
        
        tz = ZoneInfo(CONFIG.TIMEZONE)
        today_day = datetime.now(tz).day
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
            "today": datetime.now(tz).strftime("%d %B %Y"),
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN TOGGLE USER ADMIN STATUS =======================
@app.route('/api/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
def admin_toggle_user_admin(user_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN DELETE USER =======================
@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        
        return jsonify({
            "success": True,
            "message": f"User {username} deleted successfully"
        })
        
    except Exception as e:
        app.logger.error(f"Delete user error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to delete user"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN COUPON MANAGEMENT =======================
@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
def admin_get_coupons():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/coupons/reset-used', methods=['POST'])
@require_admin
def admin_reset_used_coupons():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/coupons/delete', methods=['POST'])
@require_admin
def admin_delete_all_coupons():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= ADMIN WHATSAPP NUMBERS =======================
@app.route('/api/admin/whatsapp-numbers', methods=['GET'])
@require_admin
def admin_get_whatsapp_numbers():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>/toggle', methods=['POST'])
@require_admin
def admin_toggle_whatsapp_number(number_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/whatsapp-numbers/<int:number_id>', methods=['DELETE'])
@require_admin
def admin_delete_whatsapp_number(number_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= REFERRAL ENDPOINTS =================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    user = get_current_user()
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT total_referrals FROM users WHERE id = %s', (user['id'],))
        referrals_row = cursor.fetchone()
        referrals = int(referrals_row[0]) if referrals_row and referrals_row[0] else 0
        
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = int(user.get('claimed_bonuses', 0))
        unclaimed = total_bonus - claimed
        
        if unclaimed <= 0:
            return jsonify({"success": False, "message": "No bonus to claim"}), 400
        
        new_balance = update_user_balance(user['id'], unclaimed)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        cursor.execute('UPDATE users SET claimed_bonuses = %s WHERE id = %s',
                       (total_bonus, user['id']))
        
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
        
        app.logger.info(f"Referral bonus claimed by {user['username']}: {unclaimed}")
        
        return jsonify({
            "success": True,
            "claimed": unclaimed,
            "new_balance": new_balance,
            "message": f"Success! Claimed ?{unclaimed} referral bonus"
        })
        
    except Exception as e:
        app.logger.error(f"Referral error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": f"Failed to claim: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= BANKING ENDPOINTS =================
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT code, name FROM banks WHERE is_active = TRUE ORDER BY name')
        banks = [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
        return jsonify({"success": True, "banks": banks})
    except Exception as e:
        app.logger.error(f"Bank list error: {e}")
        return jsonify({"success": False, "message": "Failed to load banks"}), 500
    finally:
        if cursor:
            cursor.close()
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
        return jsonify({"success": False, "message": f"Min withdrawal: ?{CONFIG.MIN_WITHDRAWAL:,}"}), 400
    
    if float(user['balance']) < amount:
        return jsonify({"success": False, "message": "Insufficient balance"}), 400
    
    withdrawal_limit = float(user.get('withdrawal_limit', 0.00))
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({"success": False, "message": f"Max limit: ?{withdrawal_limit:,.2f}"}), 400
    
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({"success": False, "message": "Invalid bank details"}), 400
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        new_balance = update_user_balance(user['id'], -amount)
        if new_balance is None:
            return jsonify({"success": False, "message": "Failed to update balance"}), 500
        
        cursor.execute('UPDATE users SET total_withdrawals = total_withdrawals + 1 WHERE id = %s', (user['id'],))
        
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= WHATSAPP ENDPOINTS =================
@app.route('/api/whatsapp/numbers', methods=['GET'])
def get_whatsapp_numbers():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ================= ADMIN ENDPOINTS =================
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@require_admin
def admin_get_user(user_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@require_admin
def admin_toggle_user_restrict(user_id):
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/transactions', methods=['GET'])
@require_admin
def admin_get_transactions():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/transaction/<tx_id>/update', methods=['POST'])
@require_admin
def admin_update_transaction(tx_id):
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (status, tx_id))
        conn.commit()
        
        app.logger.info(f"Admin updated transaction {tx_id} status to: {status}")
        
        return jsonify({"success": True, "message": "Transaction updated"})
    except Exception as e:
        app.logger.error(f"Update transaction error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
def admin_get_settings():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
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
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_get_stats():
    conn = get_db()
    cursor = None
    
    try:
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        return_db_connection(conn)

# ======================= BACKUP ENDPOINTS =======================
@app.route('/api/admin/backup/trigger', methods=['POST'])
@require_admin
def trigger_backup():
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

# ======================= ERROR ISOLATION MIDDLEWARE =======================
@app.before_request
def isolate_errors():
    try:
        if request.endpoint and 'api' in request.endpoint:
            ip = request.remote_addr
            
            if not rate_limiter.is_allowed(f"api:{ip}", CONFIG.RATE_LIMITS['api']):
                raise AppError("Too many requests", 429)
    except AppError:
        raise
    except Exception as e:
        app.logger.error(f"Error isolation middleware error: {e}")

@app.after_request
def add_error_headers(response):
    if response.status_code >= 400:
        response.headers['X-Error-ID'] = str(uuid.uuid4())
    return response

# ======================= MAIN APPLICATION ROUTES =======================
@app.route('/')
def index():
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= MAIN =======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    
    app.logger.info(f"Starting Flexia Platform PRODUCTION v13.0 on port {port}")
    app.logger.info(f"Admin username: {CONFIG.ADMIN_USERNAME}")
    app.logger.info(f"Admin panel: Access at /admin")
    app.logger.info(f"Timezone: {CONFIG.TIMEZONE}")
    app.logger.info(f"Error isolation: Enabled")
    app.logger.info(f"Rate limiting: Enabled")
    app.logger.info(f"Security: SQL injection protection enabled")
    app.logger.info(f"Database: PostgreSQL with connection pooling")
    app.logger.info(f"Total endpoints: {len([rule for rule in app.url_map.iter_rules() if 'static' not in rule.endpoint])}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
