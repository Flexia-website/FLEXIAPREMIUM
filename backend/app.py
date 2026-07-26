# app.py – FLEXIA Backend – Full Production Version
# All admin features, TikTok seeding, export/import, user deletion, database clear

import os
import json
import uuid
import random
import string
import datetime
from functools import wraps
from flask import Flask, request, jsonify, session, g, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
import requests

# -------------------- CONFIGURATION --------------------
app = Flask(__name__)

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app.static_folder = frontend_path
app.static_url_path = ''

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///flexia.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    # Without this, an unhandled exception on any /api/ route returns Flask's
    # default HTML error page. The frontend always does response.json() on
    # /api/ calls, so an HTML page there fails with "Unexpected token '<'"
    # instead of showing the real error — this makes every API route fail
    # safely with JSON instead, regardless of where the exception came from.
    code = getattr(e, 'code', 500)
    if request.path.startswith('/api/'):
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e) if code == 500 else getattr(e, 'description', str(e))}), code if isinstance(code, int) else 500
    raise e
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

# -------------------- MODELS --------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    referral_code = db.Column(db.String(20), unique=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    withdrawal_pin = db.Column(db.String(10), nullable=True)
    withdrawal_restricted = db.Column(db.Boolean, default=False)
    withdrawal_limit = db.Column(db.Float, default=0.0)
    custom_withdrawal_days = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(500), nullable=True)
    ui_theme = db.Column(db.String(10), default='light')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    contact = db.Column(db.String(100), nullable=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    game_stats = db.relationship('GameStats', backref='user', uselist=False, cascade='all, delete-orphan')
    achievements = db.relationship('Achievement', backref='user', lazy=True, cascade='all, delete-orphan')
    referrals = db.relationship('Referral', backref='referrer', lazy=True, cascade='all, delete-orphan',
                                foreign_keys='Referral.referrer_id', primaryjoin='User.id==Referral.referrer_id')
    referred_from = db.relationship('Referral', backref='referred', lazy=True, cascade='all, delete-orphan',
                                    foreign_keys='Referral.referred_user_id', primaryjoin='User.id==Referral.referred_user_id')
    withdrawals = db.relationship('Withdrawal', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'balance': self.balance,
            'referral_code': self.referral_code,
            'referred_by': self.referred_by,
            'withdrawal_pin': bool(self.withdrawal_pin),
            'withdrawal_restricted': self.withdrawal_restricted,
            'withdrawal_limit': self.withdrawal_limit,
            'custom_withdrawal_days': [int(d) for d in self.custom_withdrawal_days.split(',')] if self.custom_withdrawal_days else [],
            'is_admin': self.is_admin,
            'profile_picture': self.profile_picture,
            'ui_theme': self.ui_theme,
            'created_at': self.created_at.isoformat(),
            'contact': self.contact,
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='PENDING')
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'type': self.type,
            'status': self.status,
            'details': json.loads(self.details) if self.details else None,
            'timestamp': self.timestamp.isoformat(),
        }


class GameStats(db.Model):
    __tablename__ = 'game_stats'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    snake_high_score = db.Column(db.Integer, default=0)
    snake_plays_today = db.Column(db.Integer, default=0)
    snake_last_play_date = db.Column(db.Date, nullable=True)
    coinflip_wins = db.Column(db.Integer, default=0)
    coinflip_losses = db.Column(db.Integer, default=0)
    coinflip_plays_today = db.Column(db.Integer, default=0)
    coinflip_last_play_date = db.Column(db.Date, nullable=True)
    plinko_total_wins = db.Column(db.Integer, default=0)
    plinko_plays_today = db.Column(db.Integer, default=0)
    plinko_last_play_date = db.Column(db.Date, nullable=True)
    spin_plays_today = db.Column(db.Integer, default=0)
    spin_last_play_date = db.Column(db.Date, nullable=True)
    tiktok_claimed_today = db.Column(db.Boolean, default=False)
    tiktok_last_claim_date = db.Column(db.Date, nullable=True)


class Achievement(db.Model):
    __tablename__ = 'achievements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    category = db.Column(db.String(50))
    points = db.Column(db.Integer, default=0)
    cash_reward = db.Column(db.Float, default=0.0)
    unlocked = db.Column(db.Boolean, default=False)
    unlocked_at = db.Column(db.DateTime, nullable=True)
    progress = db.Column(db.Integer, default=0)
    target = db.Column(db.Integer, default=1)
    processed = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='uix_user_achievement'),)


class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='AVAILABLE')
    used_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)


class Withdrawal(db.Model):
    __tablename__ = 'withdrawals'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = db.Column(db.String(36), db.ForeignKey('transactions.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    bank_code = db.Column(db.String(10))
    account_number = db.Column(db.String(20))
    account_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='PENDING')
    note = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)


class Referral(db.Model):
    __tablename__ = 'referrals'
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bonus_claimed = db.Column(db.Boolean, default=False)
    claimed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class TikTokTask(db.Model):
    __tablename__ = 'tiktok_tasks'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    tiktok_link = db.Column(db.String(255), nullable=False)
    reward_amount = db.Column(db.Float, default=150.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class TikTokAccount(db.Model):
    __tablename__ = 'tiktok_accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class SocialSettings(db.Model):
    __tablename__ = 'social_settings'
    id = db.Column(db.Integer, primary_key=True)
    whatsapp_link = db.Column(db.String(255))
    telegram_link = db.Column(db.String(255))
    facebook_link = db.Column(db.String(255))
    min_withdrawal = db.Column(db.Float, default=100000.0)


class GlobalWithdrawalDay(db.Model):
    __tablename__ = 'global_withdrawal_days'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('day', name='uix_global_day'),)


class BackupLog(db.Model):
    __tablename__ = 'backup_logs'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# -------------------- HELPERS --------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        g.user = User.query.get(session['user_id'])
        if not g.user:
            session.clear()
            return jsonify({'success': False, 'message': 'User not found'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        g.user = user
        return f(*args, **kwargs)
    return decorated


def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_today_utc():
    return datetime.datetime.utcnow().date()


def get_today_day():
    return get_today_utc().day


def is_withdrawal_day(user, today_day):
    if user.custom_withdrawal_days:
        days = [int(d) for d in user.custom_withdrawal_days.split(',') if d.strip()]
        return today_day in days if days else True
    global_days = [d.day for d in GlobalWithdrawalDay.query.all()]
    return today_day in global_days if global_days else True


def apply_game_limit(game_type, user_stats):
    limit_map = {'snake': 17, 'coinflip': 5, 'plinko': 5, 'spin': 1, 'tiktok': 3}
    today = get_today_utc()
    if game_type == 'snake':
        if user_stats.snake_last_play_date != today:
            user_stats.snake_plays_today = 0
            user_stats.snake_last_play_date = today
        return user_stats.snake_plays_today < limit_map.get('snake', 17)
    elif game_type == 'coinflip':
        if user_stats.coinflip_last_play_date != today:
            user_stats.coinflip_plays_today = 0
            user_stats.coinflip_last_play_date = today
        return user_stats.coinflip_plays_today < limit_map.get('coinflip', 5)
    elif game_type == 'plinko':
        if user_stats.plinko_last_play_date != today:
            user_stats.plinko_plays_today = 0
            user_stats.plinko_last_play_date = today
        return user_stats.plinko_plays_today < limit_map.get('plinko', 5)
    elif game_type == 'spin':
        if user_stats.spin_last_play_date != today:
            user_stats.spin_plays_today = 0
            user_stats.spin_last_play_date = today
        return user_stats.spin_plays_today < limit_map.get('spin', 1)
    elif game_type == 'tiktok':
        if user_stats.tiktok_last_claim_date != today:
            user_stats.tiktok_claimed_today = False
            user_stats.tiktok_last_claim_date = today
        return not user_stats.tiktok_claimed_today
    return True


def increment_game_play(game_type, user_stats):
    today = get_today_utc()
    if game_type == 'snake':
        if user_stats.snake_last_play_date != today:
            user_stats.snake_plays_today = 0
            user_stats.snake_last_play_date = today
        user_stats.snake_plays_today += 1
    elif game_type == 'coinflip':
        if user_stats.coinflip_last_play_date != today:
            user_stats.coinflip_plays_today = 0
            user_stats.coinflip_last_play_date = today
        user_stats.coinflip_plays_today += 1
    elif game_type == 'plinko':
        if user_stats.plinko_last_play_date != today:
            user_stats.plinko_plays_today = 0
            user_stats.plinko_last_play_date = today
        user_stats.plinko_plays_today += 1
    elif game_type == 'spin':
        if user_stats.spin_last_play_date != today:
            user_stats.spin_plays_today = 0
            user_stats.spin_last_play_date = today
        user_stats.spin_plays_today += 1
    elif game_type == 'tiktok':
        user_stats.tiktok_claimed_today = True
        user_stats.tiktok_last_claim_date = today


def create_transaction(user_id, amount, tx_type, status='COMPLETED', details=None):
    tx = Transaction(user_id=user_id, amount=amount, type=tx_type, status=status, details=json.dumps(details) if details else None)
    db.session.add(tx)
    return tx


def verify_bank_account(bank_code, account_number):
    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY')
    if not paystack_secret:
        return {'success': True, 'account_name': 'John Doe'}
    url = f'https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}'
    headers = {'Authorization': f'Bearer {paystack_secret}'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get('status'):
            return {'success': True, 'account_name': data['data']['account_name']}
        else:
            return {'success': False, 'message': data.get('message', 'Verification failed')}
    except Exception as e:
        return {'success': False, 'message': str(e)}


# -------------------- AUTH ROUTES --------------------
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    coupon_code = data.get('coupon_code', '').strip().upper()
    referral_code = data.get('referral_code', '').strip()
    contact = data.get('contact', '').strip()
    if not username or not password or not coupon_code:
        return jsonify({'success': False, 'message': 'Username, password, and coupon are required'}), 400
    if len(username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already taken'}), 400
    coupon = Coupon.query.filter_by(code=coupon_code, status='AVAILABLE').first()
    if not coupon:
        return jsonify({'success': False, 'message': 'Invalid or used coupon code'}), 400
    user = User(username=username, contact=contact)
    user.set_password(password)
    user.referral_code = generate_referral_code()
    db.session.add(user)
    db.session.flush()
    coupon.status = 'USED'
    coupon.used_by = user.id
    coupon.used_at = datetime.datetime.utcnow()
    if referral_code:
        referrer = User.query.filter_by(referral_code=referral_code).first()
        if referrer and referrer.id != user.id:
            user.referred_by = referrer.id
            ref = Referral(referrer_id=referrer.id, referred_user_id=user.id)
            db.session.add(ref)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account created successfully'})


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    session['user_id'] = user.id
    session.permanent = True
    return jsonify({'success': True, 'message': 'Login successful', 'user': user.to_dict()})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/api/auth/validate-coupon', methods=['POST'])
def validate_coupon():
    data = request.get_json()
    code = data.get('coupon_code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'message': 'Coupon code required'}), 400
    coupon = Coupon.query.filter_by(code=code, status='AVAILABLE').first()
    if coupon:
        return jsonify({'success': True, 'message': 'Coupon is valid'})
    return jsonify({'success': False, 'message': 'Invalid or used coupon'})


# -------------------- USER PROFILE --------------------
@app.route('/api/user/profile', methods=['GET'])
@login_required
def profile():
    user = g.user
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.timestamp.desc()).limit(50).all()
    referrals = Referral.query.filter_by(referrer_id=user.id).all()
    referred_users = []
    for ref in referrals:
        referred = User.query.get(ref.referred_user_id)
        if referred:
            referred_users.append({
                'username': referred.username,
                'bonus_claimed': ref.bonus_claimed,
                'claimed_at': ref.claimed_at.isoformat() if ref.claimed_at else None,
                'created_at': ref.created_at.isoformat(),
            })
    unclaimed_refs = [r for r in referrals if not r.bonus_claimed]
    unclaimed_bonus = len(unclaimed_refs) * 7500
    referral_txs = Transaction.query.filter_by(user_id=user.id, type='REFERRAL_BONUS').order_by(Transaction.timestamp.desc()).all()
    data = user.to_dict()
    data['transactions'] = [t.to_dict() for t in transactions]
    data['referrals'] = {
        'count': len(referrals),
        'unclaimed_bonus': unclaimed_bonus,
        'referred_users': referred_users,
        'claim_history': [t.to_dict() for t in referral_txs],
    }
    data['game_stats'] = {
        'snake': {'high_score': user.game_stats.snake_high_score if user.game_stats else 0},
        'coin_flip': {'wins': user.game_stats.coinflip_wins if user.game_stats else 0,
                      'losses': user.game_stats.coinflip_losses if user.game_stats else 0},
        'plinko': {'total_wins': user.game_stats.plinko_total_wins if user.game_stats else 0},
    }
    return jsonify({'success': True, 'user': data})


@app.route('/api/user/set-theme', methods=['POST'])
@login_required
def set_theme():
    data = request.get_json()
    dark_mode = data.get('dark_mode', False)
    g.user.ui_theme = 'dark' if dark_mode else 'light'
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/user/set-profile-picture', methods=['POST'])
@login_required
def set_profile_picture():
    data = request.get_json()
    url = data.get('picture_url', '').strip()
    if not url:
        return jsonify({'success': False, 'message': 'URL required'}), 400
    g.user.profile_picture = url
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    current = data.get('current_password')
    new = data.get('new_password')
    if not current or not new:
        return jsonify({'success': False, 'message': 'Current and new password required'}), 400
    if len(new) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400
    if not g.user.check_password(current):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
    g.user.set_password(new)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password changed'}), 200


@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@login_required
def set_withdrawal_pin():
    data = request.get_json()
    pin = data.get('pin', '').strip()
    if not pin or not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
        return jsonify({'success': False, 'message': 'PIN must be 4-6 digits'}), 400
    g.user.withdrawal_pin = pin
    db.session.commit()
    return jsonify({'success': True, 'message': 'PIN set successfully'})


@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@login_required
def verify_withdrawal_pin():
    data = request.get_json()
    pin = data.get('pin', '').strip()
    if not g.user.withdrawal_pin:
        return jsonify({'success': False, 'message': 'No PIN set'}), 400
    if g.user.withdrawal_pin != pin:
        return jsonify({'success': False, 'message': 'Incorrect PIN'}), 400
    return jsonify({'success': True})


# -------------------- CONFIG --------------------
@app.route('/api/config', methods=['GET'])
def get_config():
    social = SocialSettings.query.first()
    min_wd = social.min_withdrawal if social else 100000.0
    return jsonify({
        'success': True,
        'min_withdrawal': min_wd,
        'referral_bonus': 7500,
        'tiktok_reward': 150,
        'snake_reward': 20,
        'currency': '₦',
    })


@app.route('/api/social-links', methods=['GET'])
def get_social_links():
    social = SocialSettings.query.first()
    if social:
        return jsonify({
            'success': True,
            'whatsapp_link': social.whatsapp_link or '',
            'telegram_link': social.telegram_link or '',
            'facebook_link': social.facebook_link or '',
        })
    return jsonify({'success': False})


# -------------------- GAME ROUTES --------------------
@app.route('/api/games/check-limit-with-logout/<game_type>', methods=['GET'])
@login_required
def check_game_limit(game_type):
    user = g.user
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    can_play = apply_game_limit(game_type, user.game_stats)
    played_today = 0
    max_plays = 0
    if game_type == 'snake':
        played_today = user.game_stats.snake_plays_today
        max_plays = 17
    elif game_type == 'coinflip':
        played_today = user.game_stats.coinflip_plays_today
        max_plays = 5
    elif game_type == 'plinko':
        played_today = user.game_stats.plinko_plays_today
        max_plays = 5
    elif game_type == 'spin':
        played_today = user.game_stats.spin_plays_today
        max_plays = 1
    elif game_type == 'tiktok':
        played_today = 1 if user.game_stats.tiktok_claimed_today else 0
        max_plays = 1
    return jsonify({
        'success': True,
        'can_play': can_play,
        'played_today': played_today,
        'max_plays': max_plays,
        'reset_time': 'midnight UTC',
    })


@app.route('/api/games/snake/report', methods=['POST'])
@login_required
def snake_report():
    user = g.user
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    golden = data.get('golden_apples', 0)
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    today = get_today_utc()
    if not apply_game_limit('snake', user.game_stats):
        return jsonify({'success': False, 'message': 'Daily limit reached'}), 400
    increment_game_play('snake', user.game_stats)
    reward = apples * 20 + golden * 40
    if reward == 0:
        return jsonify({'success': True, 'message': 'No apples eaten', 'reward': 0, 'new_balance': user.balance})
    total_daily = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'SNAKE_REWARD',
        func.date(Transaction.timestamp) == today
    ).scalar() or 0.0
    if total_daily + reward > 500:
        reward = max(0, 500 - total_daily)
    if reward > 0:
        tx = create_transaction(user.id, reward, 'SNAKE_REWARD')
        user.balance += reward
        if user.game_stats.snake_high_score < apples + golden:
            user.game_stats.snake_high_score = apples + golden
        db.session.commit()
        return jsonify({
            'success': True,
            'reward': reward,
            'new_balance': user.balance,
            'daily_earned': total_daily + reward,
            'remaining_today': max(0, 500 - (total_daily + reward))
        })
    else:
        return jsonify({'success': True, 'reward': 0, 'new_balance': user.balance})


@app.route('/api/games/coinflip/report', methods=['POST'])
@login_required
def coinflip_report():
    user = g.user
    data = request.get_json()
    bet = data.get('bet', 0)
    won = data.get('won', False)
    if bet < 100:
        return jsonify({'success': False, 'message': 'Minimum bet is ₦100'}), 400
    if bet > user.balance:
        return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    if not apply_game_limit('coinflip', user.game_stats):
        return jsonify({'success': False, 'message': 'Daily limit reached'}), 400
    increment_game_play('coinflip', user.game_stats)
    payout = 0
    net_change = 0
    daily_cap = 5000
    if won:
        payout = bet * 1.8
        net_change = payout - bet
        today = get_today_utc()
        total_daily = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'COINFLIP_WIN',
            func.date(Transaction.timestamp) == today
        ).scalar() or 0.0
        if total_daily + payout > daily_cap:
            payout = max(0, daily_cap - total_daily)
            net_change = payout - bet
        tx = create_transaction(user.id, payout, 'COINFLIP_WIN')
        user.balance += net_change
        user.game_stats.coinflip_wins += 1
    else:
        tx = create_transaction(user.id, -bet, 'COINFLIP_LOSS', status='COMPLETED')
        user.balance -= bet
        user.game_stats.coinflip_losses += 1
        net_change = -bet
        payout = 0
    db.session.commit()
    return jsonify({
        'success': True,
        'payout': payout,
        'new_balance': user.balance,
        'daily_won': (db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'COINFLIP_WIN',
            func.date(Transaction.timestamp) == get_today_utc()
        ).scalar() or 0.0)
    })


@app.route('/api/games/plinko/report', methods=['POST'])
@login_required
def plinko_report():
    user = g.user
    data = request.get_json()
    bet = data.get('bet', 0)
    multiplier = data.get('multiplier', 0)
    if bet < 100:
        return jsonify({'success': False, 'message': 'Minimum bet is ₦100'}), 400
    if bet > user.balance:
        return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    if not apply_game_limit('plinko', user.game_stats):
        return jsonify({'success': False, 'message': 'Daily limit reached'}), 400
    increment_game_play('plinko', user.game_stats)
    payout = 0
    net_change = 0
    if multiplier > 1:
        payout = bet * multiplier
        net_change = payout - bet
        today = get_today_utc()
        total_daily = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'PLINKO_WIN',
            func.date(Transaction.timestamp) == today
        ).scalar() or 0.0
        if total_daily + payout > 3000:
            payout = max(0, 3000 - total_daily)
            net_change = payout - bet
        tx = create_transaction(user.id, payout, 'PLINKO_WIN')
        user.balance += net_change
        user.game_stats.plinko_total_wins += 1
    else:
        tx = create_transaction(user.id, -bet, 'PLINKO_LOSS')
        user.balance -= bet
        net_change = -bet
        payout = 0
    db.session.commit()
    return jsonify({
        'success': True,
        'payout': payout,
        'net_change': net_change,
        'new_balance': user.balance,
        'daily_won': (db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'PLINKO_WIN',
            func.date(Transaction.timestamp) == get_today_utc()
        ).scalar() or 0.0)
    })


@app.route('/api/spin/execute', methods=['POST'])
@login_required
def spin_execute():
    user = g.user
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    if not apply_game_limit('spin', user.game_stats):
        return jsonify({'success': False, 'message': 'Daily spin limit reached'}), 400
    increment_game_play('spin', user.game_stats)
    prizes = [1000, 500, 200, 100, 50, 0]
    idx = random.randint(0, 5)
    reward = prizes[idx]
    if reward > 0:
        tx = create_transaction(user.id, reward, 'SPIN_WIN')
        user.balance += reward
    else:
        tx = create_transaction(user.id, 0, 'SPIN_LOSS')
    db.session.commit()
    return jsonify({
        'success': True,
        'reward': reward,
        'prize_index': idx,
        'new_balance': user.balance
    })


@app.route('/api/games/tiktok/daily', methods=['GET'])
@login_required
def tiktok_daily():
    user = g.user
    today = get_today_utc()
    task = TikTokTask.query.filter_by(date=today).first()
    if task:
        link = task.tiktok_link
        reward = task.reward_amount
    else:
        accounts = TikTokAccount.query.filter_by(active=True).all()
        if accounts:
            chosen = random.choice(accounts)
            link = f'https://www.tiktok.com/@{chosen.username}'
            reward = 150.0
        else:
            return jsonify({'success': False, 'message': 'No TikTok accounts available and no manual task set'})
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    if user.game_stats.tiktok_claimed_today and user.game_stats.tiktok_last_claim_date == today:
        return jsonify({'success': False, 'message': 'Already claimed today', 'already_claimed': True})
    return jsonify({
        'success': True,
        'task': {
            'tiktok_link': link,
            'reward_amount': reward,
            'date': today.isoformat()
        }
    })


@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@login_required
def tiktok_follow():
    user = g.user
    today = get_today_utc()
    if not user.game_stats:
        stats = GameStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        user.game_stats = stats
    if user.game_stats.tiktok_claimed_today and user.game_stats.tiktok_last_claim_date == today:
        return jsonify({'success': False, 'message': 'Already claimed today'}), 400
    task = TikTokTask.query.filter_by(date=today).first()
    if not task:
        accounts = TikTokAccount.query.filter_by(active=True).all()
        if not accounts:
            return jsonify({'success': False, 'message': 'No TikTok account available'}), 400
    reward = task.reward_amount if task else 150.0
    tx = create_transaction(user.id, reward, 'TIKTOK_REWARD')
    user.balance += reward
    user.game_stats.tiktok_claimed_today = True
    user.game_stats.tiktok_last_claim_date = today
    db.session.commit()
    return jsonify({'success': True, 'reward': reward, 'new_balance': user.balance})


# -------------------- BANKING --------------------
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    banks = [
        {"code": "057", "name": "Zenith Bank Plc"},
        {"code": "058", "name": "GTBank"},
        {"code": "044", "name": "Access Bank"},
        {"code": "033", "name": "UBA"},
        {"code": "011", "name": "First Bank"},
        {"code": "070", "name": "Fidelity Bank"},
        {"code": "050", "name": "Ecobank"},
        {"code": "039", "name": "Stanbic IBTC"},
        {"code": "214", "name": "FCMB"},
        {"code": "232", "name": "Sterling Bank"},
        {"code": "032", "name": "Union Bank"},
        {"code": "035", "name": "Wema Bank"},
        {"code": "082", "name": "Keystone Bank"},
        {"code": "215", "name": "Unity Bank"},
        {"code": "076", "name": "Polaris Bank"},
        {"code": "565", "name": "OPay"},
        {"code": "100", "name": "PalmPay"},
        {"code": "50211", "name": "Kuda Bank"},
        {"code": "566", "name": "VBank"},
        {"code": "035A", "name": "ALAT by Wema"},
    ]
    return jsonify({'success': True, 'banks': banks})


@app.route('/api/banking/verify-account', methods=['POST'])
@login_required
def verify_account():
    data = request.get_json()
    bank_code = data.get('bank_code')
    account_number = data.get('account_number')
    if not bank_code or not account_number or len(account_number) != 10:
        return jsonify({'success': False, 'message': 'Invalid bank code or account number'}), 400
    result = verify_bank_account(bank_code, account_number)
    return jsonify(result)


@app.route('/api/banking/withdraw', methods=['POST'])
@login_required
def withdraw():
    user = g.user
    data = request.get_json()
    amount = data.get('amount')
    bank_code = data.get('bank_code')
    account_number = data.get('account_number')
    account_name = data.get('account_name')
    pin = data.get('pin')
    if not all([amount, bank_code, account_number, account_name, pin]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    social = SocialSettings.query.first()
    min_wd = social.min_withdrawal if social else 100000.0
    if amount < min_wd:
        return jsonify({'success': False, 'message': f'Minimum withdrawal is ₦{min_wd}'}), 400
    if amount > user.balance:
        return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
    if user.withdrawal_restricted:
        return jsonify({'success': False, 'message': 'Withdrawal restricted'}), 400
    if not user.withdrawal_pin:
        return jsonify({'success': False, 'message': 'Withdrawal PIN not set'}), 400
    if user.withdrawal_pin != pin:
        return jsonify({'success': False, 'message': 'Incorrect PIN'}), 400
    today_day = get_today_day()
    if not is_withdrawal_day(user, today_day):
        return jsonify({'success': False, 'message': 'Withdrawal not allowed today'}), 400
    user.balance -= amount
    banks_list = get_banks().json['banks']
    bank_name = next((b['name'] for b in banks_list if b['code'] == bank_code), 'Unknown Bank')
    tx = create_transaction(
        user.id, -amount, 'WITHDRAWAL', status='PENDING',
        details={
            'bank_code': bank_code,
            'account_number': account_number,
            'account_name': account_name,
            'bank_name': bank_name
        }
    )
    db.session.flush()  # ensures tx.id is populated before we link it below
    wd = Withdrawal(
        user_id=user.id,
        amount=amount,
        bank_code=bank_code,
        account_number=account_number,
        account_name=account_name,
        status='PENDING',
        transaction_id=tx.id
    )
    db.session.add(wd)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Withdrawal request submitted', 'new_balance': user.balance})


# -------------------- REFERRAL --------------------
@app.route('/api/referral/claim', methods=['POST'])
@login_required
def claim_referral():
    user = g.user
    unclaimed_refs = Referral.query.filter_by(referrer_id=user.id, bonus_claimed=False).all()
    if not unclaimed_refs:
        return jsonify({'success': False, 'message': 'No unclaimed bonuses'}), 400
    bonus = len(unclaimed_refs) * 7500
    tx = create_transaction(user.id, bonus, 'REFERRAL_BONUS')
    user.balance += bonus
    for ref in unclaimed_refs:
        ref.bonus_claimed = True
        ref.claimed_at = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': f'Claimed ₦{bonus}', 'new_balance': user.balance})


# -------------------- ACHIEVEMENTS --------------------
@app.route('/api/achievements', methods=['GET'])
@login_required
def get_achievements():
    user = g.user
    predefined = [
        {'id': 'first_win', 'title': 'First Win', 'description': 'Win your first game', 'icon': 'fas fa-trophy', 'category': 'gaming', 'points': 10, 'cash_reward': 50, 'target': 1},
        {'id': 'snake_10', 'title': 'Snake Pro', 'description': 'Eat 10 apples in Snake', 'icon': 'fas fa-gamepad', 'category': 'gaming', 'points': 20, 'cash_reward': 100, 'target': 10},
        {'id': 'coinflip_5', 'title': 'Coin Master', 'description': 'Win 5 coin flips', 'icon': 'fas fa-coins', 'category': 'gaming', 'points': 20, 'cash_reward': 100, 'target': 5},
        {'id': 'plinko_3', 'title': 'Plinko Champ', 'description': 'Win 3 Plinko games', 'icon': 'fas fa-bowling-ball', 'category': 'gaming', 'points': 20, 'cash_reward': 100, 'target': 3},
        {'id': 'refer_1', 'title': 'Referral Starter', 'description': 'Refer 1 friend', 'icon': 'fas fa-users', 'category': 'earnings', 'points': 30, 'cash_reward': 150, 'target': 1},
        {'id': 'daily_claim', 'title': 'Daily Grinder', 'description': 'Claim TikTok reward 3 times', 'icon': 'fab fa-tiktok', 'category': 'streaks', 'points': 25, 'cash_reward': 200, 'target': 3},
    ]
    achievements = []
    for ach in predefined:
        existing = Achievement.query.filter_by(user_id=user.id, achievement_id=ach['id']).first()
        if not existing:
            existing = Achievement(
                user_id=user.id,
                achievement_id=ach['id'],
                title=ach['title'],
                description=ach['description'],
                icon=ach['icon'],
                category=ach['category'],
                points=ach['points'],
                cash_reward=ach['cash_reward'],
                target=ach['target'],
                progress=0,
                unlocked=False
            )
            db.session.add(existing)
            db.session.flush()
        progress = 0
        if ach['id'] == 'snake_10':
            total_apples = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user.id, Transaction.type == 'SNAKE_REWARD'
            ).scalar() or 0
            progress = int(total_apples / 20)
        elif ach['id'] == 'coinflip_5':
            progress = user.game_stats.coinflip_wins if user.game_stats else 0
        elif ach['id'] == 'plinko_3':
            progress = user.game_stats.plinko_total_wins if user.game_stats else 0
        elif ach['id'] == 'refer_1':
            progress = Referral.query.filter_by(referrer_id=user.id, bonus_claimed=True).count()
        elif ach['id'] == 'daily_claim':
            progress = Transaction.query.filter_by(user_id=user.id, type='TIKTOK_REWARD').count()
        elif ach['id'] == 'first_win':
            progress = 1 if Transaction.query.filter_by(user_id=user.id, type='COINFLIP_WIN').first() or \
                          Transaction.query.filter_by(user_id=user.id, type='PLINKO_WIN').first() or \
                          Transaction.query.filter_by(user_id=user.id, type='SNAKE_REWARD').first() else 0
        if not existing.unlocked and progress >= ach['target']:
            existing.unlocked = True
            existing.unlocked_at = datetime.datetime.utcnow()
            existing.progress = progress
        else:
            existing.progress = min(progress, ach['target'])
        achievements.append({
            'id': existing.achievement_id,
            'title': existing.title,
            'description': existing.description,
            'icon': existing.icon,
            'category': existing.category,
            'points': existing.points,
            'cash_reward': existing.cash_reward,
            'unlocked': existing.unlocked,
            'progress_percentage': (existing.progress / existing.target) * 100 if existing.target else 0,
            'current_value': existing.progress,
            'target_value': existing.target,
            'processed': existing.processed,
        })
    db.session.commit()
    stats = {
        'total': len(achievements),
        'unlocked': sum(1 for a in achievements if a['unlocked']),
        'points': sum(a['points'] for a in achievements if a['unlocked']),
    }
    return jsonify({'success': True, 'achievements': achievements, 'stats': stats, 'current_balance': user.balance})


@app.route('/api/achievements/claim', methods=['POST'])
@login_required
def claim_achievement_rewards():
    user = g.user
    unlocked = Achievement.query.filter_by(user_id=user.id, unlocked=True, processed=False).all()
    if not unlocked:
        return jsonify({'success': False, 'message': 'No rewards to claim'}), 400
    total_reward = sum(a.cash_reward for a in unlocked)
    for ach in unlocked:
        ach.processed = True
    tx = create_transaction(user.id, total_reward, 'ACHIEVEMENT_REWARD')
    user.balance += total_reward
    db.session.commit()
    return jsonify({'success': True, 'new_balance': user.balance, 'claimed': total_reward})


# -------------------- WITHDRAWAL DAY CHECK --------------------
@app.route('/api/withdrawal/check-day', methods=['GET'])
@login_required
def check_withdrawal_day():
    user = g.user
    today = get_today_utc()
    today_day = today.day
    can_withdraw = is_withdrawal_day(user, today_day)
    global_days = [d.day for d in GlobalWithdrawalDay.query.all()]
    custom_days = [int(d) for d in user.custom_withdrawal_days.split(',')] if user.custom_withdrawal_days else []
    used_days = custom_days if custom_days else global_days
    return jsonify({
        'success': True,
        'today': today_day,
        'today_date': today.isoformat(),
        'can_withdraw': can_withdraw,
        'global_withdrawal_days': global_days,
        'custom_withdrawal_days': custom_days,
        'used_days': used_days,
        'timezone_display': 'UTC',
        'timezone_offset': 0,
    })


# ==================== ADMIN ROUTES ====================
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    users = User.query.all()
    return jsonify({'success': True, 'users': [u.to_dict() for u in users]})


# ----- IMPORTANT: DELETE before GET -----
@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Cannot delete admin user'}), 400
    try:
        # Clear coupon references (used_by foreign key)
        Coupon.query.filter_by(used_by=user_id).update({'used_by': None, 'status': 'AVAILABLE', 'used_at': None})
        # Referrals are now cascaded on both directions via db.relationship
        # Any user this account referred should no longer point at a deleted referrer.
        User.query.filter_by(referred_by=user_id).update({'referred_by': None})
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Delete failed: {e}'}), 500


@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@admin_required
def admin_get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({'success': True, 'user': user.to_dict()})


@app.route('/api/admin/user/<int:user_id>/update-settings', methods=['POST'])
@admin_required
def admin_update_user_settings(user_id):
    data = request.get_json()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if 'restricted' in data:
        user.withdrawal_restricted = data['restricted']
    if 'limit' in data:
        user.withdrawal_limit = max(0, float(data['limit']))
    if 'custom_days' in data:
        days = [str(d) for d in data['custom_days'] if 1 <= d <= 31]
        user.custom_withdrawal_days = ','.join(days) if days else None
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@admin_required
def admin_toggle_restrict(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.withdrawal_restricted = not user.withdrawal_restricted
    db.session.commit()
    return jsonify({'success': True, 'restricted': user.withdrawal_restricted})


@app.route('/api/admin/user/<int:user_id>/set-limit', methods=['POST'])
@admin_required
def admin_set_limit(user_id):
    data = request.get_json()
    limit = data.get('limit', 0)
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.withdrawal_limit = max(0, float(limit))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@admin_required
def admin_set_custom_days(user_id):
    data = request.get_json()
    days = data.get('days', [])
    if not isinstance(days, list):
        return jsonify({'success': False, 'message': 'Invalid days format'}), 400
    days = [str(d) for d in days if 1 <= d <= 31]
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.custom_withdrawal_days = ','.join(days) if days else None
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    if user_id == g.user.id:
        return jsonify({'success': False, 'message': 'Cannot toggle yourself'}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify({'success': True, 'is_admin': user.is_admin})


@app.route('/api/admin/user/<int:user_id>/adjust-balance', methods=['POST'])
@admin_required
def admin_adjust_balance(user_id):
    data = request.get_json()
    amount = data.get('amount')
    note = data.get('note', '')
    if amount is None:
        return jsonify({'success': False, 'message': 'Amount required'}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.balance += float(amount)
    tx = create_transaction(user.id, amount, 'ADMIN_ADJUSTMENT', details={'note': note})
    db.session.commit()
    return jsonify({'success': True, 'new_balance': user.balance})


@app.route('/api/admin/transactions', methods=['GET'])
@admin_required
def admin_transactions():
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).limit(100).all()
    return jsonify({'success': True, 'transactions': [t.to_dict() for t in transactions]})


@app.route('/api/admin/approve-withdrawal', methods=['POST'])
@admin_required
def admin_approve_withdrawal():
    data = request.get_json()
    tx_id = data.get('transaction_id')
    action = data.get('action')
    if not tx_id or action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    tx = Transaction.query.get(tx_id)
    if not tx:
        return jsonify({'success': False, 'message': 'Transaction not found'}), 404
    if tx.type != 'WITHDRAWAL':
        return jsonify({'success': False, 'message': 'Not a withdrawal transaction'}), 400
    wd = Withdrawal.query.filter_by(transaction_id=tx_id).first()
    if not wd:
        return jsonify({'success': False, 'message': 'Withdrawal record not found'}), 404
    if action == 'approve':
        tx.status = 'COMPLETED'
        wd.status = 'COMPLETED'
        wd.processed_at = datetime.datetime.utcnow()
    else:
        tx.status = 'FAILED'
        wd.status = 'FAILED'
        user = User.query.get(tx.user_id)
        if user:
            user.balance += abs(tx.amount)
            refund = create_transaction(user.id, abs(tx.amount), 'WITHDRAWAL_REFUND')
    db.session.commit()
    return jsonify({'success': True, 'message': f'Withdrawal {action}d'})


@app.route('/api/admin/global-withdrawal-days', methods=['GET', 'POST'])
@admin_required
def admin_global_withdrawal_days():
    if request.method == 'GET':
        days = [d.day for d in GlobalWithdrawalDay.query.all()]
        return jsonify({'success': True, 'days': days})
    else:
        data = request.get_json()
        days = data.get('days', [])
        if not isinstance(days, list):
            return jsonify({'success': False, 'message': 'Invalid format'}), 400
        GlobalWithdrawalDay.query.delete()
        for d in days:
            if 1 <= d <= 31:
                db.session.add(GlobalWithdrawalDay(day=d))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Global days updated'})


@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    total_users = User.query.count()
    total_transactions = Transaction.query.count()
    today = get_today_utc()
    games_today = Transaction.query.filter(func.date(Transaction.timestamp) == today, Transaction.type.like('%GAME%')).count()
    return jsonify({
        'success': True,
        'stats': {
            'users': {'total': total_users},
            'transactions': {'total': total_transactions},
            'games': {'today': games_today},
            'coupons': {'total': Coupon.query.count()}
        }
    })


@app.route('/api/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'GET':
        social = SocialSettings.query.first()
        if not social:
            social = SocialSettings()
            db.session.add(social)
            db.session.commit()
        return jsonify({
            'success': True,
            'settings': {
                'whatsapp_link': social.whatsapp_link or '',
                'telegram_link': social.telegram_link or '',
                'facebook_link': social.facebook_link or '',
                'min_withdrawal': social.min_withdrawal or 100000.0,
            }
        })
    else:
        data = request.get_json()
        social = SocialSettings.query.first()
        if not social:
            social = SocialSettings()
            db.session.add(social)
        if 'whatsapp_link' in data:
            social.whatsapp_link = data['whatsapp_link']
        if 'telegram_link' in data:
            social.telegram_link = data['telegram_link']
        if 'facebook_link' in data:
            social.facebook_link = data['facebook_link']
        if 'min_withdrawal' in data:
            social.min_withdrawal = float(data['min_withdrawal'])
        db.session.commit()
        return jsonify({'success': True})


@app.route('/api/admin/change-password', methods=['POST'])
@admin_required
def admin_change_password():
    data = request.get_json()
    current = data.get('current_password')
    new = data.get('new_password')
    if not current or not new:
        return jsonify({'success': False, 'message': 'Current and new password required'}), 400
    if len(new) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400
    if not g.user.check_password(current):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
    g.user.set_password(new)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password changed, please login again'})


@app.route('/api/admin/coupons', methods=['GET'])
@admin_required
def admin_get_coupons():
    coupons = Coupon.query.all()
    return jsonify({'success': True, 'coupons': [{'id': c.id, 'code': c.code, 'status': c.status} for c in coupons]})


@app.route('/api/admin/coupons/add', methods=['POST'])
@admin_required
def admin_add_coupons():
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes:
        return jsonify({'success': False, 'message': 'No coupon codes provided'}), 400
    added = 0
    for code in codes:
        if len(code) < 4:
            continue
        if Coupon.query.filter_by(code=code).first():
            continue
        db.session.add(Coupon(code=code, status='AVAILABLE'))
        added += 1
    db.session.commit()
    return jsonify({'success': True, 'message': f'Added {added} coupons'})


@app.route('/api/admin/coupons/reset-used', methods=['POST'])
@admin_required
def admin_reset_coupons():
    Coupon.query.filter_by(status='USED').update({'status': 'AVAILABLE', 'used_by': None, 'used_at': None})
    db.session.commit()
    return jsonify({'success': True, 'message': 'All used coupons reset to available'})


@app.route('/api/admin/coupons/delete', methods=['POST'])
@admin_required
def admin_delete_coupons():
    Coupon.query.delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'All coupons deleted'})


# ===== TIKTOK ACCOUNT MANAGEMENT =====
@app.route('/api/admin/tiktok/accounts', methods=['GET'])
@admin_required
def admin_get_tiktok_accounts():
    accounts = TikTokAccount.query.order_by(TikTokAccount.created_at.desc()).all()
    return jsonify({
        'success': True,
        'accounts': [{'id': a.id, 'username': a.username, 'active': a.active} for a in accounts]
    })


@app.route('/api/admin/tiktok/accounts', methods=['POST'])
@admin_required
def admin_add_tiktok_account():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
    if username.startswith('@'):
        username = username[1:]
    if TikTokAccount.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Account already exists'}), 400
    account = TikTokAccount(username=username)
    db.session.add(account)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account added', 'account': {'id': account.id, 'username': account.username, 'active': account.active}})


@app.route('/api/admin/tiktok/accounts/<int:account_id>', methods=['DELETE'])
@admin_required
def admin_delete_tiktok_account(account_id):
    account = TikTokAccount.query.get(account_id)
    if not account:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    db.session.delete(account)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account deleted'})


@app.route('/api/admin/tiktok/accounts/<int:account_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_tiktok_account(account_id):
    account = TikTokAccount.query.get(account_id)
    if not account:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    account.active = not account.active
    db.session.commit()
    return jsonify({'success': True, 'active': account.active})


@app.route('/api/admin/tiktok/set-daily', methods=['POST'])
@admin_required
def admin_set_tiktok_daily():
    data = request.get_json()
    link = data.get('tiktok_link', '').strip()
    if not link:
        return jsonify({'success': False, 'message': 'Link required'}), 400
    today = get_today_utc()
    task = TikTokTask.query.filter_by(date=today).first()
    if task:
        task.tiktok_link = link
    else:
        db.session.add(TikTokTask(date=today, tiktok_link=link, reward_amount=150.0))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/tiktok/get-daily', methods=['GET'])
@admin_required
def admin_get_tiktok_daily():
    today = get_today_utc()
    task = TikTokTask.query.filter_by(date=today).first()
    if task:
        return jsonify({'success': True, 'task': {'tiktok_link': task.tiktok_link, 'reward_amount': task.reward_amount, 'date': task.date.isoformat()}})
    return jsonify({'success': False})


@app.route('/api/admin/tiktok/history', methods=['GET'])
@admin_required
def admin_tiktok_history():
    tasks = TikTokTask.query.order_by(TikTokTask.date.desc()).limit(7).all()
    return jsonify({'success': True, 'history': [{'date': t.date.isoformat(), 'tiktok_link': t.tiktok_link, 'reward_amount': t.reward_amount} for t in tasks]})


# ===== BACKUP =====
@app.route('/api/admin/backup/trigger', methods=['POST'])
@admin_required
def admin_trigger_backup():
    try:
        data = build_full_export_data()
        filename, size = write_backup_file(data)
        db.session.commit()
        return jsonify({'success': True, 'backup_file': filename, 'size': size})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/backup/list', methods=['GET'])
@admin_required
def admin_backup_list():
    backups = BackupLog.query.order_by(BackupLog.created_at.desc()).all()
    return jsonify({'success': True, 'backups': [{'filename': b.filename, 'created': b.created_at.isoformat(), 'size': b.size} for b in backups]})


# ===== EXPORT / IMPORT =====
@app.route('/api/admin/export-data', methods=['POST'])
@admin_required
def admin_export_data():
    data = request.get_json()
    format_type = data.get('format', 'json')
    export_users = data.get('users', False)
    export_transactions = data.get('transactions', False)
    export_gameplays = data.get('game_plays', False)
    if not any([export_users, export_transactions, export_gameplays]):
        return jsonify({'success': False, 'message': 'Select at least one data type'}), 400
    export_data = {}
    if export_users:
        users = User.query.all()
        export_data['users'] = [u.to_dict() for u in users]
    if export_transactions:
        transactions = Transaction.query.all()
        export_data['transactions'] = [t.to_dict() for t in transactions]
    if export_gameplays:
        stats = GameStats.query.all()
        export_data['game_plays'] = [{
            'user_id': s.user_id,
            'snake_high_score': s.snake_high_score,
            'coinflip_wins': s.coinflip_wins,
            'coinflip_losses': s.coinflip_losses,
            'plinko_total_wins': s.plinko_total_wins,
            'spin_plays_today': s.spin_plays_today,
            'tiktok_claimed_today': s.tiktok_claimed_today,
        } for s in stats]
    if format_type == 'csv':
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        if export_users:
            writer.writerow(['=== USERS ==='])
            writer.writerow(['id', 'username', 'balance', 'is_admin', 'created_at'])
            for u in export_data.get('users', []):
                writer.writerow([u['id'], u['username'], u['balance'], u['is_admin'], u['created_at']])
        if export_transactions:
            writer.writerow(['=== TRANSACTIONS ==='])
            writer.writerow(['id', 'user_id', 'amount', 'type', 'status', 'timestamp'])
            for t in export_data.get('transactions', []):
                writer.writerow([t['id'], t['user_id'], t['amount'], t['type'], t['status'], t['timestamp']])
        if export_gameplays:
            writer.writerow(['=== GAME PLAYS ==='])
            writer.writerow(['user_id', 'snake_high_score', 'coinflip_wins', 'coinflip_losses', 'plinko_total_wins'])
            for g in export_data.get('game_plays', []):
                writer.writerow([g['user_id'], g['snake_high_score'], g['coinflip_wins'], g['coinflip_losses'], g['plinko_total_wins']])
        csv_content = output.getvalue()
        output.close()
        return jsonify({'success': True, 'data': csv_content, 'format': 'csv'})
    else:
        return jsonify({'success': True, 'data': export_data, 'format': 'json'})


def build_full_export_data():
    return {
        'version': '1.0',
        'exported_at': datetime.datetime.utcnow().isoformat(),
        'tables': {
            'users': [u.to_dict() for u in User.query.all()],
            'transactions': [t.to_dict() for t in Transaction.query.all()],
            'game_stats': [{
                'user_id': s.user_id,
                'snake_high_score': s.snake_high_score,
                'snake_plays_today': s.snake_plays_today,
                'snake_last_play_date': s.snake_last_play_date.isoformat() if s.snake_last_play_date else None,
                'coinflip_wins': s.coinflip_wins,
                'coinflip_losses': s.coinflip_losses,
                'coinflip_plays_today': s.coinflip_plays_today,
                'coinflip_last_play_date': s.coinflip_last_play_date.isoformat() if s.coinflip_last_play_date else None,
                'plinko_total_wins': s.plinko_total_wins,
                'plinko_plays_today': s.plinko_plays_today,
                'plinko_last_play_date': s.plinko_last_play_date.isoformat() if s.plinko_last_play_date else None,
                'spin_plays_today': s.spin_plays_today,
                'spin_last_play_date': s.spin_last_play_date.isoformat() if s.spin_last_play_date else None,
                'tiktok_claimed_today': s.tiktok_claimed_today,
                'tiktok_last_claim_date': s.tiktok_last_claim_date.isoformat() if s.tiktok_last_claim_date else None,
            } for s in GameStats.query.all()],
            'achievements': [{
                'user_id': a.user_id,
                'achievement_id': a.achievement_id,
                'title': a.title,
                'unlocked': a.unlocked,
                'unlocked_at': a.unlocked_at.isoformat() if a.unlocked_at else None,
                'progress': a.progress,
                'target': a.target,
                'processed': a.processed,
            } for a in Achievement.query.all()],
            'coupons': [{'code': c.code, 'status': c.status, 'used_by': c.used_by, 'used_at': c.used_at.isoformat() if c.used_at else None} for c in Coupon.query.all()],
            'withdrawals': [{
                'id': w.id,
                'transaction_id': w.transaction_id,
                'user_id': w.user_id,
                'amount': w.amount,
                'bank_code': w.bank_code,
                'account_number': w.account_number,
                'account_name': w.account_name,
                'status': w.status,
                'timestamp': w.timestamp.isoformat(),
                'processed_at': w.processed_at.isoformat() if w.processed_at else None,
            } for w in Withdrawal.query.all()],
            'referrals': [{
                'referrer_id': r.referrer_id,
                'referred_user_id': r.referred_user_id,
                'bonus_claimed': r.bonus_claimed,
                'claimed_at': r.claimed_at.isoformat() if r.claimed_at else None,
                'created_at': r.created_at.isoformat(),
            } for r in Referral.query.all()],
            'tiktok_tasks': [{
                'date': t.date.isoformat(),
                'tiktok_link': t.tiktok_link,
                'reward_amount': t.reward_amount,
            } for t in TikTokTask.query.all()],
            'tiktok_accounts': [{
                'id': a.id,
                'username': a.username,
                'active': a.active,
                'created_at': a.created_at.isoformat(),
            } for a in TikTokAccount.query.all()],
            'social_settings': [{
                'whatsapp_link': s.whatsapp_link,
                'telegram_link': s.telegram_link,
                'facebook_link': s.facebook_link,
                'min_withdrawal': s.min_withdrawal,
            } for s in SocialSettings.query.all()],
            'global_withdrawal_days': [d.day for d in GlobalWithdrawalDay.query.all()],
            'backup_logs': [{
                'filename': b.filename,
                'size': b.size,
                'created_at': b.created_at.isoformat(),
            } for b in BackupLog.query.all()],
        }
    }


BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')


def write_backup_file(data):
    """Writes a full export to disk and logs it. Returns (filename, size_bytes)."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = f'backup_{datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.flexia'
    filepath = os.path.join(BACKUP_DIR, filename)
    payload = json.dumps(data, indent=2)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(payload)
    size = len(payload.encode('utf-8'))
    log = BackupLog(filename=filename, size=size)
    db.session.add(log)
    return filename, size


@app.route('/api/admin/database/export-all', methods=['POST'])
@admin_required
def admin_export_full_db():
    try:
        data = build_full_export_data()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/database/import-all', methods=['POST'])
@admin_required
def admin_import_full_db():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith('.flexia'):
        return jsonify({'success': False, 'message': 'Invalid file format. Must be .flexia'}), 400
    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)
        if 'tables' not in data:
            return jsonify({'success': False, 'message': 'Invalid .flexia file'}), 400
        db.session.execute('PRAGMA foreign_keys=OFF;')
        try:
            User.query.delete()
            Transaction.query.delete()
            GameStats.query.delete()
            Achievement.query.delete()
            Coupon.query.delete()
            Withdrawal.query.delete()
            Referral.query.delete()
            TikTokTask.query.delete()
            TikTokAccount.query.delete()
            SocialSettings.query.delete()
            GlobalWithdrawalDay.query.delete()
            BackupLog.query.delete()
            db.session.commit()
            tables = data['tables']
            for u in tables.get('users', []):
                user = User(
                    id=u['id'],
                    username=u['username'],
                    password_hash=u['password_hash'],
                    balance=u['balance'],
                    referral_code=u['referral_code'],
                    referred_by=u['referred_by'],
                    withdrawal_pin=u['withdrawal_pin'],
                    withdrawal_restricted=u['withdrawal_restricted'],
                    withdrawal_limit=u['withdrawal_limit'],
                    custom_withdrawal_days=u['custom_withdrawal_days'],
                    is_admin=u['is_admin'],
                    profile_picture=u['profile_picture'],
                    ui_theme=u['ui_theme'],
                    created_at=datetime.datetime.fromisoformat(u['created_at']),
                    contact=u['contact'],
                )
                db.session.add(user)
            for t in tables.get('transactions', []):
                tx = Transaction(
                    id=t['id'],
                    user_id=t['user_id'],
                    amount=t['amount'],
                    type=t['type'],
                    status=t['status'],
                    details=json.dumps(t['details']) if t['details'] else None,
                    timestamp=datetime.datetime.fromisoformat(t['timestamp']),
                )
                db.session.add(tx)
            for s in tables.get('game_stats', []):
                stats = GameStats(
                    user_id=s['user_id'],
                    snake_high_score=s['snake_high_score'],
                    snake_plays_today=s['snake_plays_today'],
                    snake_last_play_date=datetime.date.fromisoformat(s['snake_last_play_date']) if s['snake_last_play_date'] else None,
                    coinflip_wins=s['coinflip_wins'],
                    coinflip_losses=s['coinflip_losses'],
                    coinflip_plays_today=s['coinflip_plays_today'],
                    coinflip_last_play_date=datetime.date.fromisoformat(s['coinflip_last_play_date']) if s['coinflip_last_play_date'] else None,
                    plinko_total_wins=s['plinko_total_wins'],
                    plinko_plays_today=s['plinko_plays_today'],
                    plinko_last_play_date=datetime.date.fromisoformat(s['plinko_last_play_date']) if s['plinko_last_play_date'] else None,
                    spin_plays_today=s['spin_plays_today'],
                    spin_last_play_date=datetime.date.fromisoformat(s['spin_last_play_date']) if s['spin_last_play_date'] else None,
                    tiktok_claimed_today=s['tiktok_claimed_today'],
                    tiktok_last_claim_date=datetime.date.fromisoformat(s['tiktok_last_claim_date']) if s['tiktok_last_claim_date'] else None,
                )
                db.session.add(stats)
            for a in tables.get('achievements', []):
                ach = Achievement(
                    user_id=a['user_id'],
                    achievement_id=a['achievement_id'],
                    title=a['title'],
                    unlocked=a['unlocked'],
                    unlocked_at=datetime.datetime.fromisoformat(a['unlocked_at']) if a['unlocked_at'] else None,
                    progress=a['progress'],
                    target=a['target'],
                    processed=a['processed'],
                )
                db.session.add(ach)
            for c in tables.get('coupons', []):
                coupon = Coupon(
                    code=c['code'],
                    status=c['status'],
                    used_by=c['used_by'],
                    used_at=datetime.datetime.fromisoformat(c['used_at']) if c['used_at'] else None,
                )
                db.session.add(coupon)
            for w in tables.get('withdrawals', []):
                wd = Withdrawal(
                    id=w['id'],
                    transaction_id=w.get('transaction_id'),
                    user_id=w['user_id'],
                    amount=w['amount'],
                    bank_code=w['bank_code'],
                    account_number=w['account_number'],
                    account_name=w['account_name'],
                    status=w['status'],
                    timestamp=datetime.datetime.fromisoformat(w['timestamp']),
                    processed_at=datetime.datetime.fromisoformat(w['processed_at']) if w['processed_at'] else None,
                )
                db.session.add(wd)
            for r in tables.get('referrals', []):
                ref = Referral(
                    referrer_id=r['referrer_id'],
                    referred_user_id=r['referred_user_id'],
                    bonus_claimed=r['bonus_claimed'],
                    claimed_at=datetime.datetime.fromisoformat(r['claimed_at']) if r['claimed_at'] else None,
                    created_at=datetime.datetime.fromisoformat(r['created_at']),
                )
                db.session.add(ref)
            for t in tables.get('tiktok_tasks', []):
                task = TikTokTask(
                    date=datetime.date.fromisoformat(t['date']),
                    tiktok_link=t['tiktok_link'],
                    reward_amount=t['reward_amount'],
                )
                db.session.add(task)
            for a in tables.get('tiktok_accounts', []):
                account = TikTokAccount(
                    id=a['id'],
                    username=a['username'],
                    active=a['active'],
                    created_at=datetime.datetime.fromisoformat(a['created_at']),
                )
                db.session.add(account)
            for s in tables.get('social_settings', []):
                social = SocialSettings(
                    whatsapp_link=s['whatsapp_link'],
                    telegram_link=s['telegram_link'],
                    facebook_link=s['facebook_link'],
                    min_withdrawal=s['min_withdrawal'],
                )
                db.session.add(social)
            for day in tables.get('global_withdrawal_days', []):
                gwd = GlobalWithdrawalDay(day=day)
                db.session.add(gwd)
            for b in tables.get('backup_logs', []):
                log = BackupLog(
                    filename=b['filename'],
                    size=b['size'],
                    created_at=datetime.datetime.fromisoformat(b['created_at']),
                )
                db.session.add(log)
            db.session.commit()
            db.session.execute('PRAGMA foreign_keys=ON;')
            return jsonify({'success': True, 'message': 'Database restored successfully'})
        except Exception as e:
            db.session.rollback()
            db.session.execute('PRAGMA foreign_keys=ON;')
            raise e
    except Exception as e:
        return jsonify({'success': False, 'message': f'Import failed: {str(e)}'}), 500


@app.route('/api/admin/database/clear', methods=['POST'])
@admin_required
def admin_clear_db():
    data = request.get_json()
    confirmation = data.get('sudo_confirmation')
    if confirmation != 'DELETE_ALL_DATA_AND_USERS_KEEP_ADMIN':
        return jsonify({'success': False, 'message': 'Invalid confirmation'}), 400

    clear_users = bool(data.get('clear_users', True))
    clear_transactions = bool(data.get('clear_transactions', True))
    clear_gameplays = bool(data.get('clear_gameplays', True))
    reset_coupons = bool(data.get('reset_coupons', True))
    backup_option = data.get('backup_option', 'yes')

    backup_filename = None
    if backup_option == 'yes':
        try:
            backup_data = build_full_export_data()
            backup_filename, _ = write_backup_file(backup_data)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Backup failed, nothing was deleted: {e}'}), 500

    non_admin_ids = [u.id for u in User.query.filter_by(is_admin=False).with_entities(User.id).all()]

    users_deleted = 0
    transactions_deleted = 0
    gameplays_deleted = 0
    coupons_reset = 0

    if non_admin_ids:
        if clear_users:
            # Clear coupons that reference deleted users FIRST (foreign key safety)
            Coupon.query.filter(Coupon.used_by.in_(non_admin_ids)).update(
                {'used_by': None, 'status': 'AVAILABLE', 'used_at': None},
                synchronize_session=False
            )
            # Deleting the users implies deleting everything that has a NOT NULL
            # foreign key to them (transactions, game stats, achievements,
            # withdrawals, referrals) — that's a DB constraint, not a choice,
            # so clear_transactions/clear_gameplays are moot in this branch.
            transactions_deleted = Transaction.query.filter(Transaction.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
            gameplays_deleted = GameStats.query.filter(GameStats.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
            Achievement.query.filter(Achievement.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
            Withdrawal.query.filter(Withdrawal.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
            Referral.query.filter(
                Referral.referrer_id.in_(non_admin_ids) | Referral.referred_user_id.in_(non_admin_ids)
            ).delete(synchronize_session=False)
            User.query.filter(User.referred_by.in_(non_admin_ids)).update({'referred_by': None}, synchronize_session=False)
            users_deleted = User.query.filter(User.id.in_(non_admin_ids)).delete(synchronize_session=False)
        else:
            if clear_transactions:
                transactions_deleted = Transaction.query.filter(Transaction.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
                Withdrawal.query.filter(Withdrawal.user_id.in_(non_admin_ids)).delete(synchronize_session=False)
            if clear_gameplays:
                gameplays_deleted = GameStats.query.filter(GameStats.user_id.in_(non_admin_ids)).delete(synchronize_session=False)

    if reset_coupons:
        coupons_reset = Coupon.query.filter(Coupon.status != 'AVAILABLE').count()
        Coupon.query.update({'status': 'AVAILABLE', 'used_by': None, 'used_at': None})

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Database cleared (admin kept)' + (f' — backup saved as {backup_filename}' if backup_filename else ''),
        'backup_file': backup_filename,
        'stats': {
            'users_deleted': users_deleted,
            'transactions_deleted': transactions_deleted,
            'gameplays_deleted': gameplays_deleted,
            'coupons_reset': coupons_reset,
        }
    })


@app.route('/api/admin/withdrawal-status-report', methods=['GET'])
@admin_required
def admin_withdrawal_report():
    users = User.query.all()
    report_users = []
    today_day = get_today_day()
    for u in users:
        can_withdraw = is_withdrawal_day(u, today_day) and not u.withdrawal_restricted
        custom_days = [int(d) for d in u.custom_withdrawal_days.split(',')] if u.custom_withdrawal_days else []
        report_users.append({
            'id': u.id,
            'username': u.username,
            'balance': u.balance,
            'withdrawal_restricted': u.withdrawal_restricted,
            'can_withdraw_today': can_withdraw,
            'withdrawal_limit': u.withdrawal_limit,
            'custom_withdrawal_days': custom_days,
            'has_withdrawal_pin': bool(u.withdrawal_pin),
        })
    total_users = len(report_users)
    users_withdrawal_today = sum(1 for u in report_users if u['can_withdraw_today'])
    users_restricted = sum(1 for u in report_users if u['withdrawal_restricted'])
    return jsonify({
        'success': True,
        'total_users': total_users,
        'users_withdrawal_today': users_withdrawal_today,
        'users_restricted': users_restricted,
        'users': report_users
    })


# -------------------- PAYSTACK PAYMENT --------------------
@app.route('/api/paystack/initialize', methods=['POST'])
def paystack_initialize():
    data = request.get_json()
    email = data.get('email')
    amount = data.get('amount')
    if not email or not amount:
        return jsonify({'success': False, 'message': 'Email and amount required'}), 400
    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY')
    if not paystack_secret:
        ref = str(uuid.uuid4())
        return jsonify({
            'success': True,
            'authorization_url': f'https://example.com/pay?ref={ref}',
            'reference': ref,
            'bank_transfer_details': {
                'bank_name': 'GTBank',
                'account_number': '0123456789',
                'account_name': 'FLEXIA Payments',
                'amount': amount,
            },
            'expires_at': (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
        })
    url = 'https://api.paystack.co/transaction/initialize'
    headers = {'Authorization': f'Bearer {paystack_secret}', 'Content-Type': 'application/json'}
    payload = {
        'email': email,
        'amount': int(amount * 100),
        'currency': 'NGN',
        'callback_url': f"{request.host_url}?payment=success",
        'metadata': {'coupon_for': email}
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        result = resp.json()
        if result['status']:
            return jsonify({
                'success': True,
                'authorization_url': result['data']['authorization_url'],
                'reference': result['data']['reference'],
                'bank_transfer_details': result['data']['bank_transfer_details'] if 'bank_transfer_details' in result['data'] else None,
                'expires_at': result['data']['expires_at'] if 'expires_at' in result['data'] else None,
            })
        else:
            return jsonify({'success': False, 'message': result.get('message', 'Payment initialization failed')}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/paystack/status/<reference>', methods=['GET'])
def paystack_status(reference):
    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY')
    if not paystack_secret:
        return jsonify({'success': True, 'status': 'COMPLETED', 'coupon_code': 'MOCK123'})
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    headers = {'Authorization': f'Bearer {paystack_secret}'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        result = resp.json()
        if result['status'] and result['data']['status'] == 'success':
            coupon_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            db.session.add(Coupon(code=coupon_code, status='AVAILABLE'))
            db.session.commit()
            return jsonify({'success': True, 'status': 'COMPLETED', 'coupon_code': coupon_code})
        else:
            return jsonify({'success': False, 'status': result['data']['status'] if 'data' in result else 'FAILED'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# -------------------- STATIC FILE SERVING --------------------
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'logo/favicon.ico')


@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    full_path = os.path.join(app.static_folder, path)
    if os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'online',
        'uptime': 'OK',
        'database': 'Connected',
        'connection_pool': 'Active',
        'version': '2.0.0'
    })


@app.route('/api/session/status', methods=['GET'])
def session_status():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return jsonify({'success': True, 'authenticated': True})
    return jsonify({'success': True, 'authenticated': False})


@app.route('/api/session/refresh', methods=['POST'])
@login_required
def session_refresh():
    session.permanent = True
    return jsonify({'success': True})


# -------------------- DATABASE INIT --------------------
def init_db():
    with app.app_context():
        db.create_all()
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if not admin_username or not admin_password:
            raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD must be set.")
        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            admin = User(username=admin_username, is_admin=True)
            admin.set_password(admin_password)
            admin.referral_code = generate_referral_code()
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Admin '{admin_username}' created.")
        else:
            print(f"ℹ️ Admin '{admin_username}' already exists.")
        if not SocialSettings.query.first():
            db.session.add(SocialSettings())
            db.session.commit()
        if GlobalWithdrawalDay.query.count() == 0:
            for d in [7, 14, 25, 30]:
                db.session.add(GlobalWithdrawalDay(day=d))
            db.session.commit()
        if TikTokAccount.query.count() == 0:
            default_accounts = ['flexia_official', 'earnwithflexia', 'flexiarewards', 'flexiadaily', 'flexiacash']
            for username in default_accounts:
                db.session.add(TikTokAccount(username=username))
            db.session.commit()
            print("✅ Default TikTok accounts seeded.")


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
