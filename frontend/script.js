// ============================================================
// FLEXIA Frontend - COMPLETE PRODUCTION VERSION v17.0
// All features: Auth, Games, Banking, Referrals, Achievements
// No auto-refresh, no user notifications, premium UI
// ============================================================

// ========== CONFIGURATION ==========
const CONFIG = {
  MIN_WITHDRAWAL: 100000,
  REFERRAL_BONUS: 7500,
  TIKTOK_REWARD: 150,
  SNAKE_REWARD: 20,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100,
  CLAIM_COOLDOWN: 2000,
  GAME_DAILY_LIMITS: {
    'snake': 17,
    'coinflip': 12,
    'plinko': 12,
    'spin': 1,
    'tiktok': 3
  },
  PAYSTACK_MIN_AMOUNT: 500
};

// ========== DOM UTILITY ==========
function $(id) { return document.getElementById(id); }
function qs(sel) { return document.querySelector(sel); }
function qsa(sel) { return document.querySelectorAll(sel); }

// ========== APP CORE ==========
const App = {
  currentUser: null,
  balanceVisible: true,

  async init() {
    await this.checkAuth();
    if ($('app-screen')) {
      await Profile.load();
      await Banking.loadBanks();
      this.setupTheme();
      if (this.currentUser) {
        SessionManager.init();
        this.updateBalanceDisplay();
      }
    }
  },

  async checkAuth() {
    try {
      const res = await fetch('/api/user/profile', { credentials: 'include' });
      const data = await res.json();
      if (data.success) {
        this.currentUser = data.user;
        this.showAppScreen();
        this.updateBalanceDisplay();
        $('dashboard-username').textContent = data.user.username;
        $('dashboard-avatar').textContent = data.user.username.charAt(0).toUpperCase();
        if (data.user.ui_theme === 'dark') document.body.classList.add('dark-mode');
        SessionManager.init();
        console.log('User logged in:', data.user.username);
      } else {
        this.showAuthScreen();
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      this.showAuthScreen();
    }
  },

  showAppScreen() {
    $('auth-screen').style.display = 'none';
    $('app-screen').style.display = 'block';
    $('app-screen').classList.add('active');
  },

  showAuthScreen() {
    $('auth-screen').style.display = 'flex';
    $('app-screen').style.display = 'none';
    $('app-screen').classList.remove('active');
  },

  updateBalanceDisplay() {
    if (!this.currentUser) return;
    const bal = $('balance-display');
    if (bal) {
      bal.textContent = this.currentUser.balance.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }
    const minEl = $('withdraw-min');
    if (minEl) minEl.textContent = '₦' + CONFIG.MIN_WITHDRAWAL.toLocaleString();

    const gameTypes = ['COINFLIP_WIN', 'PLINKO_WIN', 'PLINKO_REPORT', 'SNAKE_REWARD'];
    const gameTotal = (this.currentUser.transactions || [])
      .filter(t => gameTypes.includes(t.type) && parseFloat(t.amount || 0) > 0)
      .reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);

    const grd = $('game-rewards-display');
    if (grd) {
      grd.textContent = '₦' + gameTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    const totalBal = parseFloat(this.currentUser.balance);
    const refTikTokBal = Math.max(0, totalBal - gameTotal);
    const fmt = (v) => '₦' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const wdRef = $('withdraw-ref-balance');
    if (wdRef) wdRef.textContent = fmt(refTikTokBal);

    const wdGame = $('withdraw-game-balance');
    if (wdGame) wdGame.textContent = fmt(gameTotal);

    const wdBal = $('withdraw-balance');
    if (wdBal) wdBal.textContent = fmt(totalBal);
  },

  async fetchFreshBalance() {
    if (!this.currentUser) return;
    try {
      const res = await fetch('/api/user/profile', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.user) {
          this.currentUser.balance = parseFloat(data.user.balance);
          if (data.user.transactions) this.currentUser.transactions = data.user.transactions;
          this.updateBalanceDisplay();
        }
      }
    } catch (e) { /* silent */ }
  },

  updateBalance(newBalance) {
    if (this.currentUser) {
      this.currentUser.balance = newBalance;
      this.updateBalanceDisplay();
    }
  },

  showModal(modalId) {
    qsa('.modal').forEach(m => m.classList.add('hidden'));
    $(modalId).classList.remove('hidden');
  },

  closeModal(modalId) {
    $(modalId).classList.add('hidden');
  },

  showMessage(text, type = 'info', duration = 5000) {
    if (type === 'error' || type === 'warning') {
      const existing = document.querySelector('.global-message');
      if (existing) existing.remove();
      const el = document.createElement('div');
      el.className = 'global-message ' + type;
      el.style.display = 'block';
      el.textContent = text;
      document.body.appendChild(el);
      setTimeout(() => {
        el.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => { if (el.parentNode) el.remove(); }, 300);
      }, duration);
    }
  },

  toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    fetch('/api/user/set-theme', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dark_mode: isDark })
    }).catch(console.error);
  },

  setupTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    if (saved === 'dark') document.body.classList.add('dark-mode');
  },

  async requestWithTimeout(url, options = {}, timeout = 10000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') throw new Error('Request timed out');
      throw error;
    }
  }
};

// ========== SESSION MANAGER ==========
const SessionManager = {
  lastActiveTime: null,
  sessionCheckInterval: null,

  init() {
    this.checkSessionStatus();
    this.trackActivity();
    this.sessionCheckInterval = setInterval(() => this.refreshSessionIfActive(), 300000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') this.handleAppResume();
    });
    window.addEventListener('online', () => this.handleAppResume());
    console.log('Session Manager initialized');
  },

  async checkSessionStatus() {
    try {
      const res = await fetch('/api/session/status', { credentials: 'include' });
      const data = await res.json();
      if (data.success && data.authenticated) {
        this.lastActiveTime = Date.now();
        return true;
      }
      return false;
    } catch (error) {
      console.error('Session check error:', error);
      return false;
    }
  },

  async refreshSessionIfActive() {
    if (App.currentUser) {
      try {
        const res = await fetch('/api/session/refresh', {
          method: 'POST',
          credentials: 'include'
        });
        if (res.ok) {
          const data = await res.json();
          if (data.success) this.lastActiveTime = Date.now();
        }
      } catch (error) {
        console.warn('Session refresh failed:', error);
      }
    }
  },

  trackActivity() {
    const events = ['click', 'touchstart', 'scroll', 'keydown', 'mousemove'];
    const handler = () => { this.lastActiveTime = Date.now(); };
    events.forEach(event => document.addEventListener(event, handler, { passive: true }));
  },

  handleAppResume() {
    this.checkSessionStatus().then(isValid => {
      if (isValid && App.currentUser) {
        App.fetchFreshBalance();
      } else if (isValid && !App.currentUser) {
        App.checkAuth();
      }
    });
  },

  saveState() {
    if (App.currentUser) {
      try {
        localStorage.setItem('flexia_session_state', JSON.stringify({
          userId: App.currentUser.id,
          username: App.currentUser.username,
          balance: App.currentUser.balance,
          lastActive: Date.now()
        }));
      } catch (e) { /* ignore */ }
    }
  },

  restoreFromLocalStorage() {
    try {
      const saved = localStorage.getItem('flexia_session_state');
      if (saved) {
        const state = JSON.parse(saved);
        const age = Date.now() - state.lastActive;
        if (age < 1800000 && !App.currentUser) {
          this.checkSessionStatus().then(isValid => {
            if (isValid) App.checkAuth();
          });
        }
      }
    } catch (e) { /* ignore */ }
  }
};

window.addEventListener('beforeunload', () => SessionManager.saveState());

// ========== AUTH ==========
const Auth = {
  togglePasswordVisibility(fieldId) {
    const field = $(fieldId);
    const toggle = field.nextElementSibling;
    if (field.type === 'password') {
      field.type = 'text';
      toggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
    } else {
      field.type = 'password';
      toggle.innerHTML = '<i class="fas fa-eye"></i>';
    }
  },

  initPasswordToggles() {
    ['login-password', 'reg-password'].forEach(id => {
      const field = $(id);
      if (field && !field.parentNode.classList.contains('password-container')) {
        const container = document.createElement('div');
        container.className = 'password-container';
        field.parentNode.insertBefore(container, field);
        container.appendChild(field);
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        toggle.innerHTML = '<i class="fas fa-eye"></i>';
        toggle.onclick = () => this.togglePasswordVisibility(id);
        container.appendChild(toggle);
      }
    });
  },

  async login() {
    const username = $('login-username').value.trim();
    const password = $('login-password').value;
    const msg = $('login-message');

    if (!username || !password) {
      msg.textContent = 'Please fill all fields';
      msg.className = 'message error';
      return;
    }

    try {
      const res = await App.requestWithTimeout('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();

      msg.textContent = data.message;
      msg.className = data.success ? 'message success' : 'message error';

      if (data.success) {
        App.currentUser = data.user;
        App.showAppScreen();
        App.updateBalanceDisplay();
        $('login-username').value = '';
        $('login-password').value = '';
        SessionManager.init();
      }
    } catch (error) {
      msg.textContent = error.message || 'Network error';
      msg.className = 'message error';
    }
  },

  async register() {
    const username = $('reg-username').value.trim();
    const password = $('reg-password').value;
    const coupon = $('reg-coupon').value.trim().toUpperCase();
    const referral = $('reg-referral').value.trim();
    const contact = $('reg-contact').value.trim() || '';
    const msg = $('register-message');
    const btn = $('register-btn');

    if (!username || !password || !coupon) {
      msg.textContent = 'All required fields must be filled';
      msg.className = 'message error';
      return;
    }
    if (username.length < 3) {
      msg.textContent = 'Username must be at least 3 characters';
      msg.className = 'message error';
      return;
    }
    if (password.length < 6) {
      msg.textContent = 'Password must be at least 6 characters';
      msg.className = 'message error';
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> CHECKING...';
    msg.textContent = 'Checking coupon...';
    msg.className = 'message info';

    try {
      const check = await App.requestWithTimeout('/api/auth/validate-coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coupon_code: coupon })
      });
      const couponData = await check.json();

      if (!couponData.success) {
        msg.textContent = couponData.message || 'Invalid coupon';
        msg.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
        return;
      }

      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> CREATING...';
      msg.textContent = 'Creating account...';
      msg.className = 'message info';

      const res = await App.requestWithTimeout('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, coupon_code: coupon, referral_code: referral, contact })
      });
      const data = await res.json();

      if (data.success) {
        msg.textContent = 'Account created! Please login.';
        msg.className = 'message success';
        ['reg-username', 'reg-password', 'reg-coupon', 'reg-referral', 'reg-contact'].forEach(id => $(id).value = '');
        setTimeout(() => {
          qsa('.tab').forEach(t => t.classList.remove('active'));
          qs('[data-tab="login"]').classList.add('active');
          qsa('.auth-form').forEach(f => f.classList.remove('active'));
          $('login-form').classList.add('active');
          $('login-message').textContent = 'Account created! Please login.';
          $('login-message').className = 'message success';
          $('login-username').value = username;
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
        }, 2000);
      } else {
        msg.textContent = data.message || 'Registration failed';
        msg.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
      }
    } catch (error) {
      msg.textContent = error.message || 'Network error';
      msg.className = 'message error';
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
    }
  },

  buyCoupon() {
    window.open('https://wa.me/2348160881049', '_blank');
  }
};

// ========== WITHDRAWAL DAY CHECK ==========
async function checkWithdrawalDay() {
  try {
    const res = await fetch('/api/withdrawal/check-day', { credentials: 'include' });
    const data = await res.json();
    if (data.success) {
      const today = new Date().getDate();
      const days = data.custom_withdrawal_days.length > 0 ? data.custom_withdrawal_days : data.global_withdrawal_days;
      if (!data.can_withdraw) {
        showWithdrawalDayModal(false, today, days);
        return false;
      } else {
        showWithdrawalDayModal(true, today, days);
        return true;
      }
    }
  } catch (error) {
    console.error('Withdrawal day check error:', error);
    return true;
  }
}

function showWithdrawalDayModal(canWithdraw, today, days) {
  const existing = document.getElementById('withdrawal-day-modal');
  if (existing) existing.remove();
  const sortedDays = days ? [...days].sort((a, b) => a - b) : [];
  const modal = document.createElement('div');
  modal.id = 'withdrawal-day-modal';
  modal.className = 'withdrawal-day-modal';
  modal.innerHTML = `
    <div class="withdrawal-day-modal-content">
      <div class="withdrawal-day-icon ${canWithdraw ? 'allowed' : 'not-allowed'}">${canWithdraw ? '✅' : '❌'}</div>
      <h3 class="withdrawal-day-title">${canWithdraw ? 'Withdrawal Allowed Today!' : 'Withdrawal Not Allowed Today'}</h3>
      <div class="withdrawal-day-message">
        <p class="withdrawal-day-text">You <strong>${canWithdraw ? 'CAN' : 'CANNOT'}</strong> withdraw today (Day ${today}).</p>
        <div class="withdrawal-day-info"><i class="fas fa-calendar-day"></i> <span>Today: Day ${today}</span></div>
        ${days && days.length > 0 ? `
          <div class="withdrawal-day-days">
            <strong>Withdrawal Days:</strong>
            <div style="margin-top: 8px;">${sortedDays.map(d => '<span class="withdrawal-day-day ' + (d === today ? 'current' : '') + '">Day ' + d + (d === today ? ' (Today)' : '') + '</span>').join('')}</div>
          </div>
        ` : ''}
        ${!canWithdraw ? `
          <div class="withdrawal-day-info" style="color: #ff6b6b;">
            <i class="fas fa-clock"></i>
            <span>Next allowed day: ${getNextAllowedDay(today, sortedDays)}</span>
          </div>
        ` : ''}
      </div>
      <div class="withdrawal-day-buttons">
        ${canWithdraw ? `
          <button class="withdrawal-day-btn-primary" onclick="closeWithdrawalDayModal(); Banking.openWithdraw();">
            <i class="fas fa-money-bill-wave"></i> Proceed to Withdrawal
          </button>
        ` : `
          <button class="withdrawal-day-btn-primary" onclick="closeWithdrawalDayModal();">
            <i class="fas fa-check-circle"></i> OK, I Understand
          </button>
        `}
        <button class="withdrawal-day-btn-secondary" onclick="closeWithdrawalDayModal()">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

function closeWithdrawalDayModal() {
  const modal = document.getElementById('withdrawal-day-modal');
  if (modal) modal.remove();
}

function getNextAllowedDay(currentDay, allowedDays) {
  if (!allowedDays || allowedDays.length === 0) return 'Unknown';
  const sorted = [...allowedDays].sort((a, b) => a - b);
  for (const d of sorted) {
    if (d > currentDay) return 'Day ' + d;
  }
  return 'Day ' + sorted[0] + ' (next month)';
}

// ========== PAYSTACK PAYMENT ==========
const PaystackPayment = {
  timerInterval: null,
  timerSeconds: 3600,

  async initiate() {
    const email = $('payment-email').value.trim();
    const amount = parseFloat($('payment-amount').value);
    const btn = $('paystack-pay-btn');
    const msg = $('payment-message');

    if (!email || !email.includes('@')) {
      msg.textContent = 'Valid email required';
      msg.className = 'message error';
      return;
    }
    if (!amount || amount < CONFIG.PAYSTACK_MIN_AMOUNT) {
      msg.textContent = 'Minimum amount is ₦' + CONFIG.PAYSTACK_MIN_AMOUNT;
      msg.className = 'message error';
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    msg.textContent = 'Initializing payment...';
    msg.className = 'message info';

    try {
      const res = await App.requestWithTimeout('/api/paystack/initialize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, amount })
      });
      const data = await res.json();

      if (data.success) {
        msg.textContent = 'Payment initialized!';
        msg.className = 'message success';
        sessionStorage.setItem('paystack_ref', data.reference);
        sessionStorage.setItem('paystack_email', email);
        if (data.bank_transfer_details) {
          this.showBankTransferDetails(data.bank_transfer_details, data.expires_at);
          this.startTimer(data.expires_at);
        }
        setTimeout(() => window.location.href = data.authorization_url, 2000);
      } else {
        msg.textContent = data.message || 'Payment failed';
        msg.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
      }
    } catch (error) {
      msg.textContent = error.message || 'Network error';
      msg.className = 'message error';
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
    }
  },

  showBankTransferDetails(details, expiresAt) {
    const container = $('bank-transfer-info');
    const detailsDiv = $('transfer-details');
    container.style.display = 'block';
    container.classList.add('visible');
    detailsDiv.innerHTML = `
      <div class="row"><span class="label">Bank</span><span class="value">${details.bank_name || 'GTBank'}</span></div>
      <div class="row"><span class="label">Account Number</span><span class="value account-number">${details.account_number || '0123456789'}</span></div>
      <div class="row"><span class="label">Account Name</span><span class="value">${details.account_name || 'FLEXIA Payments'}</span></div>
      <div class="row"><span class="label">Amount</span><span class="value" style="color:#00FF55;font-weight:bold;">₦${details.amount || '500.00'}</span></div>
    `;
    this.timerSeconds = expiresAt ? Math.floor((new Date(expiresAt) - new Date()) / 1000) : 3600;
    if (this.timerSeconds < 0) this.timerSeconds = 3600;
    container.scrollIntoView({ behavior: 'smooth', block: 'center' });
  },

  startTimer(expiresAt) {
    if (this.timerInterval) clearInterval(this.timerInterval);
    this.timerSeconds = expiresAt ? Math.floor((new Date(expiresAt) - new Date()) / 1000) : 3600;
    if (this.timerSeconds < 0) this.timerSeconds = 3600;
    const timerEl = $('payment-timer-value');
    this.timerInterval = setInterval(() => {
      this.timerSeconds--;
      if (this.timerSeconds <= 0) {
        clearInterval(this.timerInterval);
        timerEl.textContent = '00:00';
        timerEl.className = 'payment-timer-value expired';
        $('bank-transfer-info').style.borderColor = '#FF0000';
        $('payment-message').textContent = 'Payment window expired. Start a new payment.';
        $('payment-message').className = 'message error';
        $('paystack-pay-btn').disabled = true;
        return;
      }
      const m = String(Math.floor(this.timerSeconds / 60)).padStart(2, '0');
      const s = String(this.timerSeconds % 60).padStart(2, '0');
      timerEl.textContent = m + ':' + s;
      timerEl.className = 'payment-timer-value' +
        (this.timerSeconds < 300 ? ' danger' : this.timerSeconds < 600 ? ' warning' : '');
    }, 1000);
  },

  closeModal() {
    if (this.timerInterval) clearInterval(this.timerInterval);
    this.timerInterval = null;
    $('bank-transfer-info').style.display = 'none';
    $('bank-transfer-info').classList.remove('visible');
    $('payment-timer-value').textContent = '60:00';
    $('payment-timer-value').className = 'payment-timer-value';
    App.closeModal('paystack-payment-modal');
  },

  async checkStatus(reference) {
    try {
      const res = await App.requestWithTimeout('/api/paystack/status/' + reference, {
        credentials: 'include'
      });
      return await res.json();
    } catch (error) {
      console.error('Status check error:', error);
      return { success: false, message: 'Failed to check status' };
    }
  },

  openRegistrationPayment() {
    App.showModal('paystack-payment-modal');
    $('payment-message').textContent = '';
    $('payment-message').className = 'message';
    $('paystack-pay-btn').disabled = false;
    $('paystack-pay-btn').innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
    $('bank-transfer-info').style.display = 'none';
    $('bank-transfer-info').classList.remove('visible');
    $('payment-timer-value').textContent = '60:00';
    $('payment-timer-value').className = 'payment-timer-value';
    const regEmail = $('reg-contact')?.value || '';
    if (regEmail && regEmail.includes('@')) $('payment-email').value = regEmail;
    const info = document.querySelector('#paystack-payment-modal .modal-info');
    if (info) {
      info.innerHTML = `Pay via <strong>Bank Transfer</strong> or <strong>Card</strong> and receive your coupon code via email.`;
    }
  }
};

// ========== GAME MANAGER ==========
const GameManager = {
  pendingRequests: new Map(),

  async safeClaim(endpoint, data, gameType = 'unknown') {
    if (this.pendingRequests.has(gameType)) {
      return { success: false, message: "Please wait for the current claim to complete" };
    }
    this.pendingRequests.set(gameType, true);
    try {
      const res = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(data)
      }, 15000);
      const result = await res.json();
      return result;
    } catch (error) {
      console.error('Claim error:', error);
      return { success: false, message: error.message || "Connection error." };
    } finally {
      this.pendingRequests.delete(gameType);
    }
  },

  async checkDailyLimit(gameType) {
    try {
      const res = await App.requestWithTimeout('/api/games/limit-check?game=' + gameType, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      if (!res.ok) return { can_play: true, remaining: 999 };
      return await res.json();
    } catch (error) {
      console.error('Limit check error:', error);
      return { can_play: true, remaining: 999 };
    }
  }
};

// ========== GAME LIMITER ==========
const GameLimiter = {
  dailyLimits: CONFIG.GAME_DAILY_LIMITS,
  gameMessages: {
    'snake': { icon: '🐍', title: 'Snake Limit Reached', message: 'You have played Snake 5 times today. Come back tomorrow!' },
    'coinflip': { icon: '🪙', title: 'Coin Flip Limit Reached', message: 'Daily coin flip limit reached!' },
    'plinko': { icon: '🎯', title: 'Plinko Limit Reached', message: 'Daily plinko limit reached!' },
    'spin': { icon: '🎡', title: 'Spin Limit Reached', message: 'You have already spun today!' },
    'tiktok': { icon: '📱', title: 'TikTok Limit Reached', message: 'Daily TikTok limit reached!' }
  },

  showLimitModal(gameType, data) {
    const existing = document.getElementById('game-limit-modal');
    if (existing) existing.remove();
    const info = this.gameMessages[gameType] || { icon: '🎮', title: 'Limit Reached', message: 'Daily limit reached.' };
    const limit = this.dailyLimits[gameType] || 5;
    const played = data?.played_today || limit;
    const modal = document.createElement('div');
    modal.id = 'game-limit-modal';
    modal.className = 'game-limit-modal';
    modal.innerHTML = `
      <div class="game-limit-modal-content">
        <div class="game-limit-icon">${info.icon}</div>
        <h3 class="game-limit-title">${info.title}</h3>
        <div class="game-limit-message">
          <p class="game-limit-text">${info.message}</p>
          <div class="game-limit-info"><i class="fas fa-calendar-day"></i> <span>Daily Limit: ${played}/${limit} plays</span></div>
          <div class="game-limit-info"><i class="fas fa-clock"></i> <span>Reset Time: Midnight (00:00 GMT)</span></div>
        </div>
        <div class="game-limit-buttons">
          <button class="game-limit-btn-ok" onclick="GameLimiter.closeModal()"><i class="fas fa-check-circle"></i> OK</button>
          <button class="game-limit-btn-alternative" onclick="GameLimiter.suggestAlternative('${gameType}')"><i class="fas fa-gamepad"></i> Try Another</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  },

  closeModal() {
    const modal = document.getElementById('game-limit-modal');
    if (modal) modal.remove();
    const alt = document.getElementById('alternative-games-modal');
    if (alt) alt.remove();
  },

  suggestAlternative(currentGame) {
    this.closeModal();
    const alternatives = Object.keys(this.dailyLimits).filter(g => g !== currentGame);
    let html = `
      <div id="alternative-games-modal" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:10001;backdrop-filter:blur(10px);">
        <div style="background:linear-gradient(135deg,#0f3460,#1a1a2e);border-radius:20px;padding:30px;max-width:400px;width:90%;border:2px solid #00D4FF;text-align:center;">
          <h3 style="color:white;font-family:Orbitron,sans-serif;font-size:1.5rem;margin-bottom:20px;">🎮 Try These Games</h3>
          <div style="display:flex;flex-direction:column;gap:15px;margin:20px 0;">
    `;
    const gameUrls = {
      'snake': 'snake.html',
      'coinflip': 'coinflip.html',
      'plinko': 'plinko.html',
      'spin': 'Games.openSpinWheel()',
      'tiktok': 'Games.openTikTok()'
    };
    const gameIcons = { 'snake': '🐍', 'coinflip': '🪙', 'plinko': '🎯', 'spin': '🎡', 'tiktok': '📱' };
    const gameNames = { 'snake': 'Snake', 'coinflip': 'Coin Flip', 'plinko': 'Plinko', 'spin': 'Spin', 'tiktok': 'TikTok' };
    for (const g of alternatives) {
      const url = gameUrls[g] || '#';
      const click = typeof url === 'string' && url.includes('()') ? url : `window.location.href="${url}"`;
      html += `
        <button onclick="${click}" style="background:linear-gradient(135deg,#8000FF,#6C00FF);color:white;border:none;padding:15px;border-radius:10px;font-family:Orbitron,sans-serif;font-weight:700;cursor:pointer;transition:all 0.3s;text-align:left;display:flex;align-items:center;gap:15px;">
          <span style="font-size:1.5rem;">${gameIcons[g] || '🎮'}</span>
          <div><div style="font-size:1.1rem;">${gameNames[g] || g}</div><div style="font-size:0.8rem;opacity:0.8;">Play & earn</div></div>
        </button>
      `;
    }
    html += `
          </div>
          <button onclick="GameLimiter.closeModal()" style="background:transparent;color:#A0A0B5;border:1px solid #A0A0B5;padding:12px;border-radius:10px;font-family:Orbitron,sans-serif;cursor:pointer;width:100%;margin-top:15px;">Close</button>
        </div>
      </div>
    `;
    const el = document.createElement('div');
    el.innerHTML = html;
    document.body.appendChild(el.firstElementChild);
  }
};

// ========== ENHANCED GAME LIMITER ==========
const EnhancedGameLimiter = {
  async checkAndHandleGameAccess(gameType, targetUrl) {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return false;
    }
    try {
      const res = await App.requestWithTimeout('/api/games/check-limit-with-logout/' + gameType, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      const data = await res.json();
      if (!data.success || !data.can_play) {
        this.showInformativeModal(gameType, data);
        return false;
      }
      window.location.href = targetUrl;
      return true;
    } catch (error) {
      console.error('Game access check error:', error);
      window.location.href = targetUrl;
      return true;
    }
  },

  showInformativeModal(gameType, data) {
    const existing = document.getElementById('force-logout-modal');
    if (existing) existing.remove();
    const info = GameLimiter.gameMessages[gameType] || { icon: '🎮', title: 'Limit Reached', message: 'Daily limit reached.' };
    const played = data?.played_today || 0;
    const max = data?.max_plays || CONFIG.GAME_DAILY_LIMITS[gameType] || 5;
    const resetTime = data?.reset_time || 'midnight (00:00 UTC)';
    const modal = document.createElement('div');
    modal.id = 'force-logout-modal';
    modal.className = 'premium-modal-overlay';
    modal.innerHTML = `
      <div class="premium-modal-content">
        <div class="modal-icon">⏰</div>
        <h3 class="modal-title">${info.title}</h3>
        <div class="modal-message">
          <p>You've played <strong>${played}/${max}</strong> times today.</p>
          <p>Limits reset at <strong>${resetTime}</strong>.</p>
          <p style="margin-top: 12px; color: #fbbf24;">Come back tomorrow to play again!</p>
        </div>
        <div class="modal-actions">
          <button class="premium-btn primary" onclick="EnhancedGameLimiter.closeModal()">
            <i class="fas fa-home"></i> Go to Dashboard
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  },

  closeModal() {
    const modal = document.getElementById('force-logout-modal');
    if (modal) modal.remove();
  }
};

// ========== PROFILE ==========
const Profile = {
  async open() {
    if (!App.currentUser) return;
    await this.load();
    App.showModal('profile-modal');
  },

  async load() {
    try {
      const res = await App.requestWithTimeout('/api/user/profile');
      const data = await res.json();
      if (data.success) {
        App.currentUser = data.user;
        App.updateBalanceDisplay();
        const stats = data.user.game_stats || {};
        let html = `
          <div class="profile-section">
            <h4><i class="fas fa-user-circle"></i> Account Information</h4>
            <p><strong>Username:</strong> ${data.user.username}</p>
            <p><strong>Balance:</strong> ₦${data.user.balance.toLocaleString()}</p>
            <p><strong>Referral Code:</strong> ${data.user.referral_code}</p>
            <p><strong>Joined:</strong> ${new Date(data.user.created_at).toLocaleDateString()}</p>
          </div>
          <div class="profile-section">
            <h4><i class="fas fa-chart-line"></i> Game Stats</h4>
            <p><strong>Snake High Score:</strong> ${stats.snake?.high_score || 0}</p>
            <p><strong>Coin Flip Wins:</strong> ${stats.coin_flip?.wins || 0}</p>
            <p><strong>Plinko Total Wins:</strong> ${stats.plinko?.total_wins || 0}</p>
          </div>
          <div class="profile-section">
            <h4><i class="fas fa-image"></i> Profile Picture</h4>
            <input type="text" id="profile-pic-url" placeholder="Enter image URL" style="width:100%;padding:8px;margin:5px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:4px;">
            <button class="btn-primary" onclick="Profile.setProfilePicture()" style="margin-top:10px;">
              <i class="fas fa-upload"></i> Update Picture
            </button>
        `;
        if (data.user.profile_picture) {
          html += `<div style="margin-top:15px;text-align:center;"><img src="${data.user.profile_picture}" style="width:100px;height:100px;border-radius:15px;border:3px solid #8000FF;"></div>`;
        }
        $('profile-data').innerHTML = html;
      }
    } catch (err) {
      console.error('Profile load failed:', err);
      $('profile-data').innerHTML = '<p class="error">Failed to load profile.</p>';
    }
  },

  async setProfilePicture() {
    const url = $('profile-pic-url').value.trim();
    if (!url) return;
    try {
      const res = await App.requestWithTimeout('/api/user/set-profile-picture', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picture_url: url })
      });
      const data = await res.json();
      if (data.success) this.load();
    } catch (error) { /* silent */ }
  }
};

// ========== REFERRALS ==========
const Referral = {
  async open() {
    if (!App.currentUser) return;
    try {
      const res = await App.requestWithTimeout('/api/user/profile');
      const data = await res.json();
      if (data.success) {
        const unclaimed = data.referrals.unclaimed_bonus;
        let html = `
          <div class="referral-section">
            <h4><i class="fas fa-users"></i> Your Referral Program</h4>
            <p><strong>Your Referral Code:</strong> <code style="font-size:1.2em;background:#8000FF;padding:5px 10px;border-radius:5px;">${data.user.referral_code}</code></p>
            <p>Share this code to earn <strong>₦${CONFIG.REFERRAL_BONUS.toLocaleString()}</strong> per friend!</p>
            <p><strong>Referred Users:</strong> ${data.referrals.count}</p>
            <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
            ${unclaimed > 0 ? '<button class="btn-primary" onclick="Referral.claimBonuses()" style="margin-top:15px;"><i class="fas fa-gift"></i> Claim ₦' + unclaimed.toLocaleString() + ' Bonus</button>' : '<p style="color:#00FF55;margin-top:15px;">All bonuses claimed!</p>'}
          </div>
          <div class="referral-section" style="margin-top:20px;">
            <h4><i class="fas fa-share-alt"></i> Share Your Link</h4>
            <div style="background:#151535;padding:10px;border-radius:5px;border:1px solid #8000FF;margin:10px 0;">${window.location.origin}/?ref=${data.user.referral_code}</div>
            <button class="btn-secondary" onclick="Referral.copyReferralLink('${data.user.referral_code}')" style="margin-top:10px;"><i class="fas fa-copy"></i> Copy Link</button>
          </div>
        `;
        $('referral-data').innerHTML = html;
        App.showModal('referral-modal');
      }
    } catch (error) { console.error('Referral load error:', error); }
  },

  copyReferralLink(code) {
    const link = window.location.origin + '/?ref=' + code;
    navigator.clipboard.writeText(link).catch(() => {
      const ta = document.createElement('textarea');
      ta.value = link;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
  },

  async claimBonuses() {
    try {
      const result = await GameManager.safeClaim('/api/referral/claim', {}, 'referral');
      if (result.success) {
        App.updateBalance(result.new_balance);
        this.open();
      }
    } catch (error) { /* silent */ }
  }
};

// ========== BANKING ==========
const Banking = {
  banks: [],

  async loadBanks() {
    try {
      const res = await App.requestWithTimeout('/api/banking/banks');
      const data = await res.json();
      if (data.success) {
        this.banks = data.banks;
        const select = $('bank-select');
        if (select) {
          select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
          data.banks.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b.code;
            opt.textContent = b.name;
            select.appendChild(opt);
          });
        }
      } else {
        this.loadFallbackBanks();
      }
    } catch (err) {
      console.error('Error loading banks:', err);
      this.loadFallbackBanks();
    }
  },

  loadFallbackBanks() {
    const fallback = [
      {code: "057", name: "Zenith Bank Plc"}, {code: "058", name: "GTBank"},
      {code: "044", name: "Access Bank"}, {code: "033", name: "UBA"},
      {code: "011", name: "First Bank"}, {code: "070", name: "Fidelity Bank"},
      {code: "050", name: "Ecobank"}, {code: "039", name: "Stanbic IBTC"},
      {code: "214", name: "FCMB"}, {code: "232", name: "Sterling Bank"},
      {code: "032", name: "Union Bank"}, {code: "035", name: "Wema Bank"},
      {code: "082", name: "Keystone Bank"}, {code: "215", name: "Unity Bank"},
      {code: "076", name: "Polaris Bank"}, {code: "565", name: "OPay"},
      {code: "100", name: "PalmPay"}, {code: "50211", name: "Kuda Bank"},
      {code: "566", name: "VBank"}, {code: "035A", name: "ALAT by Wema"}
    ];
    this.banks = fallback;
    const select = $('bank-select');
    if (select) {
      select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
      fallback.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b.code;
        opt.textContent = b.name;
        select.appendChild(opt);
      });
    }
  },

  async openWithdraw() {
    if (!App.currentUser) return;
    const can = await checkWithdrawalDay();
    if (!can) return;
    $('withdrawal-message').textContent = '';
    if (this.banks.length === 0) await this.loadBanks();
    $('withdraw-amount').value = '';
    $('bank-select').selectedIndex = 0;
    $('account-number').value = '';
    $('account-name-manual').value = '';
    App.showModal('withdrawal-modal');
  },

  async processWithdrawal() {
    const userRes = await App.requestWithTimeout('/api/user/profile');
    const userData = await userRes.json();
    const msg = $('withdrawal-message');
    if (!userData.success) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Session expired. Please login again.</div>`;
      return;
    }
    const user = userData.user;
    if (!user.withdrawal_pin) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-info-circle"></i> You must set a withdrawal PIN first.</div>`;
      Settings.setWithdrawalPin();
      return;
    }
    const amount = parseFloat($('withdraw-amount').value);
    const bankCode = $('bank-select').value;
    const accountNumber = $('account-number').value.trim();
    const accountName = $('account-name-manual').value.trim();

    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Minimum withdrawal: ₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}</div>`;
      return;
    }
    if (amount > parseFloat(user.balance)) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Insufficient balance.</div>`;
      return;
    }
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Invalid bank details.</div>`;
      return;
    }
    const pin = prompt('Enter your 4-6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Valid PIN required.</div>`;
      return;
    }

    msg.innerHTML = `<div class="alert-box info"><i class="fas fa-spinner fa-spin"></i> Processing...</div>`;
    try {
      const result = await GameManager.safeClaim('/api/banking/withdraw', {
        amount, bank_code: bankCode, account_number: accountNumber,
        account_name: accountName, pin
      }, 'withdrawal');
      if (result.success) {
        msg.innerHTML = `<div class="alert-box success"><i class="fas fa-check-circle"></i> ${result.message}</div>`;
        App.updateBalance(result.new_balance);
        setTimeout(() => App.closeModal('withdrawal-modal'), 2000);
      } else {
        msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message}</div>`;
      }
    } catch (error) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error.</div>`;
    }
  }
};

// ========== ACHIEVEMENTS ==========
const Achievements = {
  open() {
    if (!App.currentUser) return;
    window.location.href = 'achievements.html';
  },

  async claimAllRewards() {
    try {
      const result = await GameManager.safeClaim('/api/achievements/claim', {}, 'achievements');
      if (result.success) App.updateBalance(result.new_balance);
    } catch (error) { /* silent */ }
  }
};

// ========== GAMES ==========
const Games = {
  openSnake() { return EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'); },
  openCoinFlip() { return EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'); },
  openPlinko() { return EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'); },

  reportSnake(apples) {
    return GameManager.safeClaim('/api/games/snake/report', { apples_eaten: apples }, 'snake');
  },

  reportCoinFlip(bet, won) {
    return GameManager.safeClaim('/api/games/coinflip/report', { bet, won }, 'coinflip');
  },

  reportPlinko(bet, multiplier) {
    return GameManager.safeClaim('/api/games/plinko/report', { bet, multiplier }, 'plinko');
  },

  reportSpin() {
    return GameManager.safeClaim('/api/spin/execute', {}, 'spin');
  },

  async openTikTok() {
    if (!App.currentUser) return;
    try {
      const res = await App.requestWithTimeout('/api/games/check-limit-with-logout/tiktok', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      const data = await res.json();
      if (!data.success || !data.can_play) {
        EnhancedGameLimiter.showInformativeModal('tiktok', data);
        return;
      }
    } catch (error) { console.error('TikTok access error:', error); }

    const msg = $('tiktok-message');
    msg.textContent = '';
    msg.className = 'message';
    try {
      const res = await App.requestWithTimeout('/api/games/tiktok/daily');
      const data = await res.json();
      if (!data.success) {
        $('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">' + (data.message || 'No task today.') + '</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (data.already_claimed) {
        $('tiktok-instructions').innerHTML = '<p style="color:#ff9800;">Already claimed today!</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (!data.task || !data.task.tiktok_link) {
        $('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">Admin hasn\'t set a task for today.</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      try {
        const url = new URL(data.task.tiktok_link);
        const username = url.pathname.split('/')[1] || data.task.tiktok_link;
        $('tiktok-account-name').textContent = '@' + username;
        $('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display"><strong>@${username}</strong></div>
          <p class="small-text">Search <strong>@${username}</strong> on TikTok and follow</p>
        `;
      } catch (e) {
        $('tiktok-account-name').textContent = data.task.tiktok_link;
        $('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display"><strong>${data.task.tiktok_link}</strong></div>
          <p class="small-text">Open this link in TikTok and follow</p>
        `;
      }
      document.querySelector('.action-buttons').style.display = 'flex';
      App.showModal('tiktok-modal');
    } catch (err) {
      console.error('TikTok load error:', err);
      $('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">Failed to load task.</p>';
      document.querySelector('.action-buttons').style.display = 'none';
      App.showModal('tiktok-modal');
    }
  },

  async verifyTikTokFollow() {
    const msg = $('tiktok-message');
    msg.innerHTML = '<div class="alert-box info"><i class="fas fa-spinner fa-spin"></i> Claiming...</div>';
    try {
      const result = await GameManager.safeClaim('/api/games/tiktok/follow-daily', {}, 'tiktok');
      if (result.success) {
        App.updateBalance(result.new_balance);
        msg.innerHTML = `<div class="alert-box success"><i class="fas fa-check-circle"></i> Claimed ₦${result.reward}!</div>`;
        setTimeout(() => App.closeModal('tiktok-modal'), 2000);
      } else {
        msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message || 'Failed.'}</div>`;
      }
    } catch (error) {
      msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error.</div>`;
    }
  },

  openTikTokApp() {
    const name = $('tiktok-account-name');
    const username = name.textContent.replace('@', '');
    if (username) {
      window.open('snssdk1233://user/@' + username, '_blank');
      setTimeout(() => window.open('https://www.tiktok.com/@' + username, '_blank'), 500);
    }
  },

  async openSpinWheel() {
    if (!App.currentUser) return;
    try {
      const res = await App.requestWithTimeout('/api/games/check-limit-with-logout/spin', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      const data = await res.json();
      if (!data.success || !data.can_play) {
        EnhancedGameLimiter.showInformativeModal('spin', data);
        return;
      }
    } catch (error) { console.error('Spin access error:', error); }

    const wheel = $('wheel');
    const btn = $('spin-button');
    const msg = $('spin-message');
    const result = $('spin-result');
    if (wheel) {
      wheel.style.transition = 'none';
      wheel.style.transform = 'rotate(0deg)';
      void wheel.offsetWidth;
    }
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
    }
    if (msg) { msg.textContent = ''; msg.className = 'message'; }
    if (result) result.classList.add('hidden');
    App.showModal('spin-modal');
    setTimeout(() => initSpinWheel(), 150);
  },

  async spinWheel() {
    const btn = $('spin-button');
    const wheel = $('wheel');
    const msg = $('spin-message');
    if (!btn || !wheel || btn.disabled) return;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    if (msg) { msg.textContent = ''; msg.className = 'message'; }
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    const svgEl = document.getElementById('wheel-svg');
    if (svgEl) { svgEl.style.transition = 'none'; svgEl.style.transform = 'rotate(0deg)'; }
    void wheel.offsetWidth;
    try {
      const result = await this.reportSpin();
      if (!result.success) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        if (msg) msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message || 'Spin failed'}</div>`;
        return;
      }
      const reward = result.reward;
      const prizeIndex = result.prize_index !== undefined ? result.prize_index : 5;
      const angleToPointer = (360 - (prizeIndex * 60 + 30)) % 360;
      const totalRotation = (6 + Math.floor(Math.random() * 3)) * 360 + angleToPointer;
      const spinTarget = document.getElementById('wheel-svg') || wheel;
      spinTarget.style.transition = 'none';
      spinTarget.style.transform = 'rotate(0deg)';
      void spinTarget.offsetWidth;
      spinTarget.style.transition = 'transform 5s cubic-bezier(0.17, 0.67, 0.05, 1.0)';
      spinTarget.style.transform = 'rotate(' + totalRotation + 'deg)';
      setTimeout(() => {
        App.updateBalance(result.new_balance);
        const msgText = reward > 0 ? '🎉 Won ₦' + reward.toLocaleString() + '!' : 'Better luck tomorrow!';
        if (msg) msg.innerHTML = `<div class="alert-box ${reward > 0 ? 'success' : 'warning'}"><i class="fas fa-${reward > 0 ? 'check-circle' : 'info-circle'}"></i> ${msgText}</div>`;
        const resEl = $('spin-result');
        if (resEl) { resEl.innerHTML = '<p style="font-size:1.1rem;font-weight:bold;">' + msgText + '</p>'; resEl.classList.remove('hidden'); }
        btn.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
        btn.disabled = true;
      }, 5200);
    } catch (error) {
      console.error('Spin error:', error);
      btn.disabled = false;
      if (msg) msg.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error.</div>`;
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
    }
  }
};

// ========== SETTINGS ==========
const Settings = {
  async open() {
    if (!App.currentUser) return;
    try {
      const res = await App.requestWithTimeout('/api/user/profile');
      const data = await res.json();
      if (!data.success) return;
      const user = data.user;
      const hasPin = !!user.withdrawal_pin;
      let html = `
        <div class="settings-section">
          <h4><i class="fas fa-user-cog"></i> Account Settings</h4>
          <p><strong>Username:</strong> ${user.username}</p>
          <p><strong>Balance:</strong> ₦${user.balance.toLocaleString()}</p>
        </div>
      `;
      try {
        const sr = await App.requestWithTimeout('/api/admin/settings');
        const sd = await sr.json();
        if (sd.success) {
          const s = sd.settings;
          html += '<div class="settings-section"><h4><i class="fas fa-users"></i> Community</h4>';
          if (s.whatsapp_link) html += '<a href="' + s.whatsapp_link + '" target="_blank" class="social-link"><i class="fab fa-whatsapp"></i> WhatsApp</a><br>';
          if (s.telegram_link) html += '<a href="' + s.telegram_link + '" target="_blank" class="social-link"><i class="fab fa-telegram"></i> Telegram</a><br>';
          if (s.facebook_link) html += '<a href="' + s.facebook_link + '" target="_blank" class="social-link"><i class="fab fa-facebook"></i> Facebook</a><br>';
          html += '</div>';
        }
      } catch (e) { /* silent */ }
      if (user.is_admin) {
        html += `<div class="settings-section"><h4><i class="fas fa-shield-alt"></i> Admin</h4><button class="btn-primary" onclick="Settings.changePassword()" style="width:100%;"><i class="fas fa-key"></i> Change Password</button></div>`;
      }
      html += `
        <div class="settings-section">
          <h4><i class="fas fa-lock"></i> Security</h4>
          <button class="btn-primary" onclick="Settings.${hasPin ? 'changeWithdrawalPin' : 'setWithdrawalPin'}()" style="width:100%;">
            <i class="fas fa-key"></i> ${hasPin ? 'Change' : 'Set'} Withdrawal PIN
          </button>
        </div>
        <div class="settings-section">
          <h4><i class="fas fa-palette"></i> Appearance</h4>
          <button class="btn-primary" onclick="App.toggleTheme()" style="width:100%;">
            <i class="fas fa-moon"></i> ${document.body.classList.contains('dark-mode') ? 'Switch to Light' : 'Switch to Dark'}
          </button>
        </div>
        <div class="settings-section">
          <h4><i class="fas fa-shopping-cart"></i> Buy Coupon</h4>
          <button class="btn-primary" onclick="PaystackPayment.openDashboardPayment()" style="width:100%;background:linear-gradient(135deg,#00CCFF,#8000FF);">
            <i class="fas fa-credit-card"></i> Buy Coupon via Paystack
          </button>
        </div>
        <div class="settings-section">
          <h4><i class="fas fa-sign-out-alt"></i> Session</h4>
          <button class="btn-primary" style="background:#d32f2f;width:100%;" onclick="Settings.logout()">
            <i class="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      `;
      $('settings-data').innerHTML = html;
      App.showModal('settings-modal');
    } catch (error) { console.error('Settings error:', error); }
  },

  setWithdrawalPin: async function(isChange = false) {
    let currentPin = '';
    if (isChange) {
      currentPin = prompt('Enter your CURRENT 4-6 digit PIN:');
      if (!currentPin || !/^\d{4,6}$/.test(currentPin)) return;
      try {
        const res = await App.requestWithTimeout('/api/user/verify-withdrawal-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: currentPin }),
          credentials: 'include'
        });
        const data = await res.json();
        if (!data.success) return;
      } catch (error) { return; }
    }
    const newPin = prompt('Enter your NEW 4-6 digit PIN:');
    if (!newPin || !/^\d{4,6}$/.test(newPin)) return;
    const confirmPin = prompt('Confirm your new PIN:');
    if (newPin !== confirmPin) return;
    try {
      const result = await GameManager.safeClaim('/api/user/set-withdrawal-pin', { pin: newPin }, 'setpin');
      if (result.success) App.closeModal('settings-modal');
    } catch (error) { /* silent */ }
  },

  changeWithdrawalPin() { this.setWithdrawalPin(true); },

  async changePassword() {
    const oldPass = prompt("Enter your current password:");
    if (!oldPass) return;
    const newPass = prompt("Enter a new password (min 6 chars):");
    if (!newPass || newPass.length < 6) return;
    const confirmPass = prompt("Confirm your new password:");
    if (newPass !== confirmPass) return;
    try {
      const isAdmin = App.currentUser && App.currentUser.is_admin;
      const endpoint = isAdmin ? '/api/admin/change-password' : '/api/user/change-password';
      const res = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ current_password: oldPass, new_password: newPass })
      });
      const data = await res.json();
      if (data.success) {
        App.closeModal('settings-modal');
        if (isAdmin && data.message && data.message.includes('login again')) {
          setTimeout(() => { if (confirm("Password changed. Logout and login again?")) Settings.logout(); }, 1000);
        }
      }
    } catch (error) { /* silent */ }
  },

  logout: async function() {
    if (!confirm('Logout?')) return;
    try {
      await App.requestWithTimeout('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) { /* silent */ }
    document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
      (window.location.protocol === 'https:' ? '; secure' : '');
    window.location.href = '/';
  }
};

// ========== SPIN WHEEL ==========
function initSpinWheel() {
  const container = $('wheel');
  if (!container) return;
  container.innerHTML = '';
  container.style.cssText = 'position:relative;width:280px;height:280px;margin:0 auto;';
  const prizes = [
    { label: '₦1000', color: '#FF0055', textColor: '#fff' },
    { label: '₦500',  color: '#FF8C00', textColor: '#fff' },
    { label: '₦200',  color: '#FFCC00', textColor: '#111' },
    { label: '₦100',  color: '#00C851', textColor: '#fff' },
    { label: '₦50',   color: '#00CCFF', textColor: '#111' },
    { label: '0',     color: '#8000FF', textColor: '#fff' }
  ];
  const N = prizes.length, cx = 140, cy = 140, r = 130, sliceDeg = 360 / N;
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('id', 'wheel-svg');
  svg.setAttribute('viewBox', '0 0 280 280');
  svg.setAttribute('width', '280');
  svg.setAttribute('height', '280');
  svg.style.cssText = 'display:block;border-radius:50%;overflow:hidden;filter:drop-shadow(0 0 18px rgba(128,0,255,0.5));';
  function polarToCart(cx, cy, r, angleDeg) {
    const rad = (angleDeg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }
  prizes.forEach((prize, i) => {
    const startAngle = i * sliceDeg, endAngle = startAngle + sliceDeg, midAngle = startAngle + sliceDeg / 2;
    const p1 = polarToCart(cx, cy, r, startAngle);
    const p2 = polarToCart(cx, cy, r, endAngle);
    const path = document.createElementNS(svgNS, 'path');
    path.setAttribute('d', ['M ' + cx + ' ' + cy, 'L ' + p1.x + ' ' + p1.y, 'A ' + r + ' ' + r + ' 0 0 1 ' + p2.x + ' ' + p2.y, 'Z'].join(' '));
    path.setAttribute('fill', prize.color);
    path.setAttribute('stroke', '#0A0A1F');
    path.setAttribute('stroke-width', '2');
    svg.appendChild(path);
    const lp = polarToCart(cx, cy, r * 0.72, midAngle);
    const text = document.createElementNS(svgNS, 'text');
    text.setAttribute('x', lp.x);
    text.setAttribute('y', lp.y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('transform', 'rotate(' + midAngle + ', ' + lp.x + ', ' + lp.y + ')');
    text.setAttribute('fill', prize.textColor);
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', 'bold');
    text.setAttribute('font-family', 'Orbitron, Arial, sans-serif');
    text.textContent = prize.label;
    svg.appendChild(text);
  });
  const centerCircle = document.createElementNS(svgNS, 'circle');
  centerCircle.setAttribute('cx', cx);
  centerCircle.setAttribute('cy', cy);
  centerCircle.setAttribute('r', '22');
  centerCircle.setAttribute('fill', '#0A0A1F');
  centerCircle.setAttribute('stroke', '#8000FF');
  centerCircle.setAttribute('stroke-width', '3');
  svg.appendChild(centerCircle);
  const centerText = document.createElementNS(svgNS, 'text');
  centerText.setAttribute('x', cx);
  centerText.setAttribute('y', cy);
  centerText.setAttribute('text-anchor', 'middle');
  centerText.setAttribute('dominant-baseline', 'middle');
  centerText.setAttribute('fill', '#8000FF');
  centerText.setAttribute('font-size', '14');
  centerText.textContent = '★';
  svg.appendChild(centerText);
  container.appendChild(svg);
  const pointer = document.createElement('div');
  pointer.style.cssText = `position:absolute;top:-14px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:12px solid transparent;border-right:12px solid transparent;border-top:22px solid #FFD700;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5));z-index:10;`;
  container.appendChild(pointer);
}

// ========== DOM INIT ==========
document.addEventListener('DOMContentLoaded', function() {
  qsa('.tab').forEach(tab => {
    tab.addEventListener('click', function() {
      qsa('.tab').forEach(t => t.classList.remove('active'));
      qsa('.auth-form').forEach(f => f.classList.remove('active'));
      tab.classList.add('active');
      $(tab.dataset.tab + '-form').classList.add('active');
    });
  });

  Auth.initPasswordToggles();
  App.init();

  const urlParams = new URLSearchParams(window.location.search);
  const coupon = urlParams.get('coupon');
  const tab = urlParams.get('tab');
  if (coupon) {
    $('reg-coupon').value = coupon;
    if (tab === 'register') {
      qsa('.tab').forEach(t => t.classList.remove('active'));
      qs('[data-tab="register"]').classList.add('active');
      qsa('.auth-form').forEach(f => f.classList.remove('active'));
      $('register-form').classList.add('active');
    }
  }

  const ref = urlParams.get('ref');
  if (ref) {
    setTimeout(async () => {
      const result = await PaystackPayment.checkStatus(ref);
      if (result.success && result.status === 'COMPLETED') {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }, 2000);
  }

  const spinModal = $('spin-modal');
  if (spinModal) {
    const observer = new MutationObserver(() => {
      if (!spinModal.classList.contains('hidden')) setTimeout(initSpinWheel, 100);
    });
    observer.observe(spinModal, { attributes: true, attributeFilter: ['class'] });
  }
});

// ========== GLOBAL EXPORTS ==========
window.App = App;
window.Games = Games;
window.Auth = Auth;
window.Profile = Profile;
window.Referral = Referral;
window.Banking = Banking;
window.Achievements = Achievements;
window.Settings = Settings;
window.PaystackPayment = PaystackPayment;
window.SessionManager = SessionManager;
window.GameLimiter = GameLimiter;
window.EnhancedGameLimiter = EnhancedGameLimiter;
window.checkWithdrawalDay = checkWithdrawalDay;
window.closeWithdrawalDayModal = closeWithdrawalDayModal;
window.updateBalance = App.updateBalance.bind(App);
window.showMessage = App.showMessage.bind(App);
window.goBackToDashboard = () => window.location.href = 'index.html';
