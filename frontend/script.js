// ============================================================
// FLEXIA Frontend - COMPLETE PRODUCTION VERSION v17.9
// Fixed: Receipt bank details, Referral list + claim history, No emojis
// ============================================================

// ========== EMBEDDED CSS ==========
var embeddedCSS = `
  .password-container {
    position: relative;
    width: 100%;
    margin-bottom: 15px;
  }
  .password-container input {
    width: 100%;
    padding-left: 45px !important;
    padding-right: 45px !important;
    box-sizing: border-box !important;
  }
  .password-toggle {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: #A0A0B5;
    cursor: pointer;
    font-size: 1.1rem;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: color 0.2s, background 0.2s;
    z-index: 10;
  }
  .password-toggle:hover {
    color: #8000FF;
    background: rgba(128, 0, 255, 0.1);
  }
  .btn-loading {
    position: relative;
    color: transparent !important;
    pointer-events: none;
  }
  .btn-loading::after {
    content: '';
    position: absolute;
    left: 50%;
    top: 50%;
    width: 20px;
    height: 20px;
    margin: -10px 0 0 -10px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .global-message {
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    padding: 12px 24px;
    background: rgba(0, 0, 0, 0.9);
    color: white;
    border-radius: 8px;
    z-index: 10000;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    animation: slideDown 0.3s ease-out;
    max-width: 90%;
    text-align: center;
    border-left: 4px solid;
    font-weight: 600;
    display: none;
  }
  .global-message.success { border-left-color: #00ff88; background: rgba(0,255,136,0.1); }
  .global-message.error { border-left-color: #ff0055; background: rgba(255,0,85,0.1); }
  .global-message.warning { border-left-color: #ffaa00; background: rgba(255,170,0,0.1); }
  .global-message.info { border-left-color: #00ccff; background: rgba(0,204,255,0.1); }
  @keyframes slideDown {
    from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }
  @keyframes slideOut {
    from { opacity: 1; transform: translateX(-50%) translateY(0); }
    to { opacity: 0; transform: translateX(-50%) translateY(-20px); }
  }
`;

// Inject CSS
(function() {
  var style = document.createElement('style');
  style.textContent = embeddedCSS;
  document.head.appendChild(style);
})();

// ========== CONFIGURATION ==========
var CONFIG = {
  MIN_WITHDRAWAL: window.APP_CONFIG?.MIN_WITHDRAWAL || 100000,
  REFERRAL_BONUS: window.APP_CONFIG?.REFERRAL_BONUS || 7500,
  TIKTOK_REWARD: window.APP_CONFIG?.REWARDS?.TIKTOK_BASE || 150,
  SNAKE_REWARD: window.APP_CONFIG?.REWARDS?.SNAKE_APPLE || 200,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100,
  CLAIM_COOLDOWN: 2000,
  GAME_DAILY_LIMITS: window.APP_CONFIG?.GAME_DAILY_LIMITS || {
    'snake': 17,
    'coinflip': 5,
    'plinko': 5,
    'spin': 1,
    'tiktok': 3
  },
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 2000
};

// ========== CORE APP ==========
var App = {
  currentUser: null,
  balanceVisible: true,
  lastBalanceUpdate: 0,
  _balanceRefreshInterval: null,

  init: async function () {
    console.log('App.init() called');
    await this.checkAuth();
    if (document.getElementById('app-screen') && this.currentUser) {
      await Profile.load();
      await Banking.loadBanks();
      this.setupTheme();
      SessionManager.init();
      this.updateBalanceDisplay();
      this.startBalanceRefresh();
    }
  },

  startBalanceRefresh: function() {
    if (this._balanceRefreshInterval) {
      clearInterval(this._balanceRefreshInterval);
    }
    this._balanceRefreshInterval = setInterval(function() {
      App.fetchFreshBalance();
    }, 30000);
  },

  stopBalanceRefresh: function() {
    if (this._balanceRefreshInterval) {
      clearInterval(this._balanceRefreshInterval);
      this._balanceRefreshInterval = null;
    }
  },

  checkAuth: async function () {
    console.log('App.checkAuth() called');
    try {
      fetch('/api/config').then(function(r) {
        return r.json();
      }).then(function(cfg) {
        if (cfg.success && cfg.min_withdrawal != null) {
          CONFIG.MIN_WITHDRAWAL = cfg.min_withdrawal;
          var minEl = document.getElementById('withdraw-min');
          if (minEl) minEl.textContent = '₦' + cfg.min_withdrawal.toLocaleString();
        }
      }).catch(function() {});

      var response = await this.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      console.log('Auth check response:', data);
      
      if (data.success) {
        this.currentUser = data.user;
        this.showAppScreen();
        if (!document.getElementById('app-screen')) {
          // On the login page, showAppScreen() already redirected to the dashboard.
          return;
        }
        this.updateBalanceDisplay();
        var usernameEl = document.getElementById('dashboard-username');
        var avatarEl = document.getElementById('dashboard-avatar');
        if (usernameEl) usernameEl.textContent = data.user.username;
        if (avatarEl) avatarEl.textContent = data.user.username.charAt(0).toUpperCase();
        if (data.user.ui_theme === 'dark') {
          document.body.classList.add('dark-mode');
        }
        SessionManager.init();
        console.log('User logged in:', data.user.username);
      } else {
        console.log('No valid session, showing auth screen');
        this.showAuthScreen();
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      this.showAuthScreen();
    }
  },

  showAppScreen: function () {
    // Login page: successful auth redirects to the dashboard.
    if (document.getElementById('auth-screen') && !document.getElementById('app-screen')) {
      window.location.href = 'index.html';
      return;
    }
    console.log('Showing app screen');
    var appScreen = document.getElementById('app-screen');
    if (appScreen) {
      appScreen.style.display = 'block';
      appScreen.classList.add('active');
    }
  },

  showAuthScreen: function () {
    // Dashboard page: no valid session, send the user to login.
    if (document.getElementById('app-screen') && !document.getElementById('auth-screen')) {
      window.location.href = 'login.html';
      return;
    }
    console.log('Showing auth screen');
    var authScreen = document.getElementById('auth-screen');
    if (authScreen) {
      authScreen.style.display = 'flex';
    }
    this.stopBalanceRefresh();
  },

  updateBalanceDisplay: function () {
    if (!this.currentUser) return;
    var display = document.getElementById('balance-display');
    if (display) {
      display.textContent = this.currentUser.balance.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }
    var minEl = document.getElementById('withdraw-min');
    if (minEl) minEl.textContent = '₦' + CONFIG.MIN_WITHDRAWAL.toLocaleString();

    var gameRewardsEl = document.getElementById('game-rewards-display');
    var gameTypes = ['COINFLIP_WIN', 'PLINKO_WIN', 'PLINKO_REPORT', 'SNAKE_REWARD'];
    var gameTotal = (this.currentUser.transactions || [])
      .filter(function(t) { return gameTypes.indexOf(t.type) !== -1 && parseFloat(t.amount || 0) > 0; })
      .reduce(function(sum, t) { return sum + parseFloat(t.amount || 0); }, 0);

    if (gameRewardsEl) {
      gameRewardsEl.textContent = '₦' + gameTotal.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }

    var totalBal = parseFloat(this.currentUser.balance);
    var refTikTokBal = Math.max(0, totalBal - gameTotal);
    var fmt = function(v) { return '₦' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };

    var wdRef = document.getElementById('withdraw-ref-balance');
    if (wdRef) wdRef.textContent = fmt(refTikTokBal);

    var wdGame = document.getElementById('withdraw-game-balance');
    if (wdGame) wdGame.textContent = fmt(gameTotal);

    var withdrawBalance = document.getElementById('withdraw-balance');
    if (withdrawBalance) {
      withdrawBalance.textContent = fmt(totalBal);
    }

    this.lastBalanceUpdate = Date.now();
  },

  fetchFreshBalance: async function () {
    if (!this.currentUser) return;
    try {
      fetch('/api/config').then(function(r) { return r.json(); }).then(function(cfg) {
        if (cfg.success && cfg.min_withdrawal != null) {
          CONFIG.MIN_WITHDRAWAL = cfg.min_withdrawal;
          var minEl = document.getElementById('withdraw-min');
          if (minEl) minEl.textContent = '₦' + cfg.min_withdrawal.toLocaleString();
        }
      }).catch(function() {});

      var response = await this.requestWithTimeout('/api/user/profile', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      if (response.ok) {
        var data = await response.json();
        if (data.success && data.user && data.user.balance !== undefined) {
          this.currentUser.balance = parseFloat(data.user.balance);
          if (data.user.transactions) this.currentUser.transactions = data.user.transactions;
          this.updateBalanceDisplay();
        }
      }
    } catch (e) { /* silent fail */ }
  },

  updateBalance: function (newBalance) {
    if (this.currentUser) {
      this.currentUser.balance = newBalance;
      this.updateBalanceDisplay();
      localStorage.setItem('flexia_balance', newBalance);
    }
  },

  toggleBalance: function () {
    this.balanceVisible = !this.balanceVisible;
    var display = document.getElementById('balance-display');
    if (display) {
      display.textContent = this.balanceVisible
        ? this.currentUser.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })
        : '••••••••';
    }
  },

  showModal: function (modalId) {
    document.querySelectorAll('.modal').forEach(function(m) { m.classList.add('hidden'); });
    var modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('hidden');
    } else {
      console.error('Modal not found:', modalId);
    }
  },

  closeModal: function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) modal.classList.add('hidden');
  },

  showMessage: function (text, type, duration) {
    if (type === undefined) type = 'info';
    if (duration === undefined) duration = 5000;
    document.querySelectorAll('.global-message').forEach(function(el) { el.remove(); });
    var messageEl = document.createElement('div');
    messageEl.className = 'global-message ' + type;
    messageEl.textContent = text;
    messageEl.style.display = 'block';
    document.body.appendChild(messageEl);
    setTimeout(function() {
      messageEl.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(function() {
        if (messageEl.parentNode) {
          messageEl.remove();
        }
      }, 300);
    }, duration);
  },

  toggleTheme: function () {
    document.body.classList.toggle('dark-mode');
    var isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    fetch('/api/user/set-theme', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dark_mode: isDark })
    }).catch(console.error);
  },

  setupTheme: function () {
    var savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
      document.body.classList.add('dark-mode');
    }
  },

  requestWithTimeout: async function(url, options, timeout) {
    if (options === undefined) options = {};
    if (timeout === undefined) timeout = 10000;
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, timeout);
    try {
      var response = await fetch(url, Object.assign({}, options, { signal: controller.signal }));
      clearTimeout(timeoutId);
      var contentType = response.headers.get('content-type');
      if (!contentType || contentType.indexOf('application/json') === -1) {
        throw new Error('Server returned non-JSON response. Please try again.');
      }
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out. Please try again.');
      }
      throw error;
    }
  }
};

// ========== SESSION PERSISTENCE & RECOVERY ==========
var SessionManager = {
  lastActiveTime: null,
  sessionCheckInterval: null,

  init: function() {
    this.checkSessionStatus();
    this.trackActivity();
    var self = this;
    this.sessionCheckInterval = setInterval(function() { self.refreshSessionIfActive(); }, 300000);
    
    document.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'visible') {
        self.handleAppResume();
      }
    });
    
    window.addEventListener('online', function() {
      self.handleAppResume();
    });
    
    console.log('Session Manager initialized');
  },

  checkSessionStatus: async function() {
    try {
      var response = await fetch('/api/session/status', {
        credentials: 'include'
      });
      var data = await response.json();
      
      if (data.success && data.authenticated) {
        this.lastActiveTime = Date.now();
        return true;
      } else {
        if (document.getElementById('app-screen') && 
            document.getElementById('app-screen').style.display !== 'none') {
          App.showAuthScreen();
        }
        return false;
      }
    } catch (error) {
      console.error('Session check error:', error);
      return false;
    }
  },

  refreshSessionIfActive: async function() {
    if (App.currentUser) {
      try {
        var response = await fetch('/api/session/refresh', {
          method: 'POST',
          credentials: 'include'
        });
        var data = await response.json();
        if (data.success) {
          this.lastActiveTime = Date.now();
          console.log('Session refreshed');
        }
      } catch (error) {
        console.warn('Session refresh failed:', error);
      }
    }
  },

  trackActivity: function() {
    var events = ['click', 'touchstart', 'scroll', 'keydown', 'mousemove'];
    var self = this;
    var activityHandler = function() {
      self.lastActiveTime = Date.now();
    };
    events.forEach(function(event) {
      document.addEventListener(event, activityHandler, { passive: true });
    });
  },

  handleAppResume: function() {
    console.log('App resumed, checking session...');
    var self = this;
    this.checkSessionStatus().then(function(isValid) {
      if (isValid && App.currentUser) {
        App.fetchFreshBalance();
      } else if (isValid && !App.currentUser) {
        App.checkAuth();
      }
    });
    this.restoreFromLocalStorage();
  },

  saveState: function() {
    if (App.currentUser) {
      try {
        var state = {
          userId: App.currentUser.id,
          username: App.currentUser.username,
          balance: App.currentUser.balance,
          lastActive: Date.now(),
          savedAt: new Date().toISOString()
        };
        localStorage.setItem('flexia_session_state', JSON.stringify(state));
      } catch (e) {
        console.warn('Failed to save session state:', e);
      }
    }
  },

  restoreFromLocalStorage: function() {
    try {
      var saved = localStorage.getItem('flexia_session_state');
      if (saved) {
        var state = JSON.parse(saved);
        var age = Date.now() - state.lastActive;
        if (age < 1800000 && !App.currentUser) {
          console.log('Restoring session from localStorage');
          this.checkSessionStatus().then(function(isValid) {
            if (isValid) {
              App.checkAuth();
            }
          });
        }
      }
    } catch (e) {
      console.warn('Failed to restore from localStorage:', e);
    }
  },

  saveScrollPosition: function() {
    try {
      sessionStorage.setItem('flexia_scroll_position', window.scrollY.toString());
    } catch (e) { /* ignore */ }
  },

  saveActiveTab: function(tab) {
    try {
      sessionStorage.setItem('flexia_active_tab', tab);
    } catch (e) { /* ignore */ }
  }
};

window.addEventListener('beforeunload', function() {
  SessionManager.saveState();
  SessionManager.saveScrollPosition();
});

// ========== AUTHENTICATION ==========
var Auth = {
  togglePasswordVisibility: function(fieldId) {
    var passwordField = document.getElementById(fieldId);
    var toggleBtn = passwordField.nextElementSibling;
    if (passwordField.type === 'password') {
      passwordField.type = 'text';
      toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
      toggleBtn.setAttribute('title', 'Hide password');
    } else {
      passwordField.type = 'password';
      toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
      toggleBtn.setAttribute('title', 'Show password');
    }
  },

  initPasswordToggles: function() {
    var loginPasswordField = document.getElementById('login-password');
    if (loginPasswordField && !loginPasswordField.parentNode?.classList?.contains('password-container')) {
      var loginContainer = document.createElement('div');
      loginContainer.className = 'password-container';
      loginPasswordField.parentNode.insertBefore(loginContainer, loginPasswordField);
      loginContainer.appendChild(loginPasswordField);
      var loginToggle = document.createElement('button');
      loginToggle.type = 'button';
      loginToggle.className = 'password-toggle';
      loginToggle.innerHTML = '<i class="fas fa-eye"></i>';
      loginToggle.setAttribute('title', 'Show password');
      loginToggle.setAttribute('aria-label', 'Toggle password visibility');
      loginToggle.onclick = function() { Auth.togglePasswordVisibility('login-password'); };
      loginContainer.appendChild(loginToggle);
    }
    var regPasswordField = document.getElementById('reg-password');
    if (regPasswordField && !regPasswordField.parentNode?.classList?.contains('password-container')) {
      var regContainer = document.createElement('div');
      regContainer.className = 'password-container';
      regPasswordField.parentNode.insertBefore(regContainer, regPasswordField);
      regContainer.appendChild(regPasswordField);
      var regToggle = document.createElement('button');
      regToggle.type = 'button';
      regToggle.className = 'password-toggle';
      regToggle.innerHTML = '<i class="fas fa-eye"></i>';
      regToggle.setAttribute('title', 'Show password');
      regToggle.setAttribute('aria-label', 'Toggle password visibility');
      regToggle.onclick = function() { Auth.togglePasswordVisibility('reg-password'); };
      regContainer.appendChild(regToggle);
    }
  },

  login: async function () {
    var identifier = document.getElementById('login-username').value.trim();
    var password = document.getElementById('login-password').value;
    var messageEl = document.getElementById('login-message');

    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
      return;
    }

    try {
      var response = await App.requestWithTimeout('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, password: password })
      });
      var data = await response.json();

      messageEl.textContent = data.message;
      messageEl.className = data.success ? 'message success' : 'message error';

      if (data.success) {
        App.currentUser = data.user;
        console.log('Login successful, redirecting to dashboard');
        window.location.href = 'index.html';
      }
    } catch (error) {
      messageEl.textContent = error.message || 'Network error. Please try again.';
      messageEl.className = 'message error';
    }
  },

  register: async function () {
    var username = document.getElementById('reg-username').value.trim().toLowerCase();
    var password = document.getElementById('reg-password').value;
    var coupon = document.getElementById('reg-coupon').value.trim().toUpperCase();
    var referral = document.getElementById('reg-referral').value.trim();
    var contact = document.getElementById('reg-contact')?.value.trim() || '';
    var messageEl = document.getElementById('register-message');
    var btn = document.getElementById('register-btn');

    if (!username || !password || !coupon) {
      messageEl.textContent = 'All required fields must be filled';
      messageEl.className = 'message error';
      return;
    }

    if (username.length < 3) {
      messageEl.textContent = 'Username must be at least 3 characters';
      messageEl.className = 'message error';
      return;
    }

    if (password.length < 6) {
      messageEl.textContent = 'Password must be at least 6 characters';
      messageEl.className = 'message error';
      return;
    }

    if (coupon.length < 4) {
      messageEl.textContent = 'Please enter a valid coupon code';
      messageEl.className = 'message error';
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> CHECKING COUPON...';
    messageEl.textContent = 'Checking coupon code...';
    messageEl.className = 'message info';

    try {
      var couponCheck = await App.requestWithTimeout('/api/auth/validate-coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coupon_code: coupon })
      });
      var couponData = await couponCheck.json();

      if (!couponData.success) {
        messageEl.textContent = couponData.message || 'Invalid coupon code. Please check and try again.';
        messageEl.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
        return;
      }

      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> CREATING ACCOUNT...';
      messageEl.textContent = 'Creating your account...';
      messageEl.className = 'message info';

      var response = await App.requestWithTimeout('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username,
          password: password,
          coupon_code: coupon,
          referral_code: referral,
          contact: contact
        })
      });

      var data = await response.json();

      if (data.success) {
        messageEl.textContent = 'Account created successfully! Please login.';
        messageEl.className = 'message success';

        document.getElementById('reg-username').value = '';
        document.getElementById('reg-password').value = '';
        document.getElementById('reg-coupon').value = '';
        document.getElementById('reg-referral').value = '';
        document.getElementById('reg-contact').value = '';

        setTimeout(function() {
          document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
          document.querySelector('[data-tab="login"]').classList.add('active');
          document.querySelectorAll('.auth-form').forEach(function(f) { f.classList.remove('active'); });
          document.getElementById('login-form').classList.add('active');
          document.getElementById('login-message').textContent = 'Account created! Please login with your credentials.';
          document.getElementById('login-message').className = 'message success';
          document.getElementById('login-username').value = username;
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
        }, 2000);

      } else {
        messageEl.textContent = data.message || 'Registration failed. Please try again.';
        messageEl.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
      }

    } catch (error) {
      console.error('Registration error:', error);
      messageEl.textContent = error.message || 'Network error. Please try again.';
      messageEl.className = 'message error';
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-user-plus"></i> CREATE ACCOUNT';
    }
  },

  buyCoupon: async function () {
    window.open('https://chat-3zot.onrender.com', '_blank');
  }
};

// ========== WITHDRAWAL DAY CHECK - FIXED USING SERVER TIME ==========
async function checkWithdrawalDay() {
  try {
    var response = await fetch('/api/withdrawal/check-day', {
      credentials: 'include'
    });
    var data = await response.json();
    
    if (data.success) {
      var today = data.today;
      var days = data.used_days || data.global_withdrawal_days || [];
      var canWithdraw = data.can_withdraw;
      var timezoneDisplay = data.timezone_display || 'UTC';
      var todayDate = data.today_date || new Date().toISOString().split('T')[0];
      
      if (!canWithdraw) {
        showWithdrawalDayModal(false, today, days, timezoneDisplay, todayDate);
        return false;
      }
      return true;
    } else {
      return true;
    }
  } catch (error) {
    console.error('Withdrawal day check error:', error);
    return true;
  }
}

function showWithdrawalDayModal(canWithdraw, today, days, timezoneDisplay, todayDate) {
  var existingModal = document.getElementById('withdrawal-day-modal');
  if (existingModal) existingModal.remove();
  
  var sortedDays = days ? days.slice().sort(function(a,b){return a-b;}) : [];
  var nextDay = getNextAllowedDay(today, sortedDays);
  var todayDateDisplay = todayDate || new Date().toISOString().split('T')[0];
  var timezoneInfo = timezoneDisplay || 'UTC';
  
  var modal = document.createElement('div');
  modal.id = 'withdrawal-day-modal';
  modal.className = 'withdrawal-day-modal';
  
  var modalContent = document.createElement('div');
  modalContent.className = 'withdrawal-day-modal-content ' + (canWithdraw ? 'allowed' : '');
  
  var daysHTML = '';
  if (sortedDays.length > 0) {
    var allDays = [];
    for (var i = 1; i <= 31; i++) {
      var isCurrent = i === today;
      var isAllowed = sortedDays.includes(i);
      var dayClass = 'withdrawal-day-day';
      if (isCurrent) dayClass += ' current';
      if (isAllowed) dayClass += ' allowed';
      else dayClass += ' disabled';
      allDays.push('<span class="' + dayClass + '">' + i + '</span>');
    }
    daysHTML = allDays.join('');
  } else {
    daysHTML = '<span style="color:#ff6b6b;">No withdrawal days configured</span>';
  }
  
  modalContent.innerHTML = `
    <div class="withdrawal-day-icon ${canWithdraw ? 'allowed' : 'not-allowed'}">
      ${canWithdraw ? '✅' : '🚫'}
    </div>
    <h3 class="withdrawal-day-title ${canWithdraw ? 'allowed' : 'not-allowed'}">
      ${canWithdraw ? 'Withdrawal Allowed Today!' : 'Withdrawal Not Allowed Today'}
    </h3>
    <p class="withdrawal-day-subtitle">
      ${canWithdraw 
        ? 'You <strong>CAN</strong> withdraw today (Day <strong>' + today + '</strong>)'
        : 'You <strong>CANNOT</strong> withdraw today (Day <strong>' + today + '</strong>)'
      }
      <br><small style="color:#666;">Server Time: ${timezoneInfo} • Date: ${todayDateDisplay}</small>
    </p>
    
    <div class="withdrawal-day-info-row">
      <i class="fas fa-calendar-day"></i>
      <span>Today: Day ${today}</span>
      <span style="margin-left:auto;font-size:0.7rem;color:#666;">${timezoneInfo}</span>
    </div>
    
    <div class="withdrawal-day-days-container">
      <div class="withdrawal-day-days-label">
        <i class="fas fa-calendar-alt"></i> Withdrawal Days
      </div>
      <div class="withdrawal-day-days-grid">
        ${daysHTML}
      </div>
    </div>
    
    ${!canWithdraw ? `
      <div class="withdrawal-day-next">
        <i class="fas fa-clock"></i>
        <span>Next allowed day: <strong>${nextDay}</strong></span>
      </div>
    ` : ''}
    
    <div style="margin-top:8px;font-size:0.7rem;color:#666;border-top:1px solid rgba(255,255,255,0.05);padding-top:8px;">
      Server Timezone: ${timezoneInfo}
    </div>
    
    <div class="withdrawal-day-buttons">
      ${canWithdraw ? `
        <button class="withdrawal-day-btn-primary allowed" onclick="closeWithdrawalDayModal(); Banking.openWithdraw();">
          <i class="fas fa-money-bill-wave"></i> Withdraw Now
        </button>
      ` : `
        <button class="withdrawal-day-btn-primary" onclick="closeWithdrawalDayModal();">
          <i class="fas fa-check-circle"></i> OK, I Understand
        </button>
      `}
      <button class="withdrawal-day-btn-secondary" onclick="closeWithdrawalDayModal();">
        <i class="fas fa-times"></i> Close
      </button>
    </div>
  `;
  
  modal.appendChild(modalContent);
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
  
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      closeWithdrawalDayModal();
    }
  });
  
  document.addEventListener('keydown', function handler(e) {
    if (e.key === 'Escape') {
      closeWithdrawalDayModal();
      document.removeEventListener('keydown', handler);
    }
  });
}

function closeWithdrawalDayModal() {
  var modal = document.getElementById('withdrawal-day-modal');
  if (modal) modal.remove();
  document.body.style.overflow = '';
}

function getNextAllowedDay(currentDay, allowedDays) {
  if (!allowedDays || allowedDays.length === 0) return 'Unknown';
  var sorted = allowedDays.slice().sort(function(a,b){return a-b;});
  for (var i = 0; i < sorted.length; i++) {
    if (sorted[i] > currentDay) return 'Day ' + sorted[i];
  }
  return 'Day ' + sorted[0] + ' (next month)';
}

// ========== GAME MANAGER ==========
var GameManager = {
  lastClaimTime: 0,
  pendingRequests: new Map(),

  async checkDailyLimit(gameType) {
    try {
      var response = await App.requestWithTimeout('/api/games/limit-check?game=' + gameType, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
      });
      if (!response.ok) {
        console.warn('Limit check failed, assuming can play');
        return { can_play: true, remaining: 999 };
      }
      return await response.json();
    } catch (error) {
      console.error('Limit check error:', error);
      return { can_play: true, remaining: 999 };
    }
  },

  safeClaim: async function(endpoint, data, gameType) {
    if (gameType === undefined) gameType = 'unknown';
    if (this.pendingRequests.has(gameType)) {
      console.warn('Already claiming ' + gameType + ', ignoring duplicate');
      return { success: false, message: "Please wait for the current claim to complete" };
    }
    this.pendingRequests.set(gameType, true);

    try {
      var attempts = 0;
      var maxAttempts = CONFIG.MAX_RETRY_ATTEMPTS || 3;
      var lastError = null;

      while (attempts < maxAttempts) {
        attempts++;
        try {
          var response = await App.requestWithTimeout(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Request-ID': Date.now().toString() },
            credentials: 'include',
            body: JSON.stringify(data)
          }, 15000);
          var result = await response.json();
          this.lastClaimTime = Date.now();

          if (!result.success && result.message &&
              (result.message.toLowerCase().includes('wait') ||
               result.message.toLowerCase().includes('rate') ||
               result.message.toLowerCase().includes('cooldown'))) {
            console.log('Rate limited, waiting ' + (CONFIG.RETRY_DELAY * attempts) + 'ms before retry');
            await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY * attempts));
            continue;
          }

          return result;
        } catch (error) {
          console.error('Claim attempt ' + attempts + ' failed:', error);
          lastError = error;
          if (attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY * attempts));
          }
        }
      }

      if (lastError && lastError.name === 'AbortError') {
        return { success: false, message: "Request timed out. Please try again." };
      }
      return { success: false, message: lastError ? lastError.message : "Connection error. Please try again." };
    } finally {
      this.pendingRequests.delete(gameType);
    }
  },

  setButtonLoading: function(buttonId, isLoading) {
    var button = document.getElementById(buttonId);
    if (!button) return;
    if (isLoading) {
      button.classList.add('btn-loading');
      button.disabled = true;
    } else {
      button.classList.remove('btn-loading');
      button.disabled = false;
    }
  }
};

// ========== GAME LIMITER ==========
var GameLimiter = {
  dailyLimits: CONFIG.GAME_DAILY_LIMITS,
  gameFriendlyNames: {
    'snake': 'Snake Game',
    'coinflip': 'Coin Flip',
    'plinko': 'Plinko 3D',
    'spin': 'Daily Spin',
    'tiktok': 'TikTok Follow'
  },
  gameMessages: {
    'snake': { icon: '🐍', title: 'Snake Game Limit Reached', message: 'You have played Snake 17 times today. Come back tomorrow for more fun!' },
    'coinflip': { icon: '🪙', title: 'Coin Flip Limit Reached', message: 'You have played Coin Flip 5 times today. Daily limit reached!' },
    'plinko': { icon: '🎯', title: 'Plinko Limit Reached', message: 'You have played Plinko 5 times today. Try again tomorrow!' },
    'spin': { icon: '🎡', title: 'Daily Spin Limit Reached', message: 'You have already used your daily spin today! Come back tomorrow.' },
    'tiktok': { icon: '📱', title: 'TikTok Daily Limit Reached', message: 'You have already claimed TikTok reward today! Come back tomorrow.' }
  },

  showLimitModal: function(gameType, data) {
    var existingModal = document.getElementById('game-limit-modal');
    if (existingModal) existingModal.remove();

    var gameInfo = this.gameMessages[gameType] || {
      icon: '🎮',
      title: 'Game Limit Reached',
      message: 'You have reached your daily limit for this game.'
    };

    var limit = this.dailyLimits[gameType] || 5;
    var played = data?.played_today || limit;

    var modal = document.createElement('div');
    modal.id = 'game-limit-modal';
    modal.className = 'game-limit-modal';
    modal.innerHTML = `
      <div class="game-limit-modal-content">
        <div class="game-limit-icon">${gameInfo.icon}</div>
        <h3 class="game-limit-title">${gameInfo.title}</h3>
        <div class="game-limit-message">
          <p class="game-limit-text">${gameInfo.message}</p>
          <div class="game-limit-info">
            <i class="fas fa-calendar-day"></i>
            <span>Daily Limit: ${played}/${limit} plays</span>
          </div>
          <div class="game-limit-info">
            <i class="fas fa-clock"></i>
            <span>Reset Time: Midnight (00:00 GMT)</span>
          </div>
        </div>
        <div class="game-limit-buttons">
          <button class="game-limit-btn-ok" onclick="GameLimiter.closeModal()">
            <i class="fas fa-check-circle"></i> OK, I Understand
          </button>
          <button class="game-limit-btn-alternative" onclick="GameLimiter.suggestAlternative('${gameType}')">
            <i class="fas fa-gamepad"></i> Try Another Game
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  },

  closeModal: function() {
    var modal = document.getElementById('game-limit-modal');
    if (modal) modal.remove();
  },

  suggestAlternative: function(currentGame) {
    this.closeModal();
    var alternativeGames = Object.keys(this.gameFriendlyNames).filter(function(game) { return game !== currentGame; });
    var alternativesHTML = `
      <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:10001;backdrop-filter:blur(10px);">
        <div style="background:linear-gradient(135deg,#0f3460,#1a1a2e);border-radius:20px;padding:30px;max-width:400px;width:90%;border:2px solid #00D4FF;box-shadow:0 20px 40px rgba(0,212,255,0.3);text-align:center;animation:slideIn 0.4s ease-out;">
          <h3 style="color:white;font-family:Orbitron,sans-serif;font-size:1.5rem;margin-bottom:20px;">🎮 Try These Games Instead</h3>
          <div style="display:flex;flex-direction:column;gap:15px;margin:20px 0;">
    `;
    var self = this;
    alternativeGames.forEach(function(gameType) {
      var gameName = self.gameFriendlyNames[gameType];
      var emoji = gameType === 'snake' ? '🐍' : gameType === 'coinflip' ? '🪙' : gameType === 'plinko' ? '🎯' : gameType === 'spin' ? '🎡' : '📱';
      var onclick = '';
      if (gameType === 'snake') onclick = 'window.location.href="snake.html"';
      else if (gameType === 'coinflip') onclick = 'window.location.href="coinflip.html"';
      else if (gameType === 'plinko') onclick = 'window.location.href="plinko.html"';
      else if (gameType === 'spin') onclick = 'Games.openSpinWheel()';
      else if (gameType === 'tiktok') onclick = 'Games.openTikTok()';
      alternativesHTML += `
        <button onclick="${onclick}" style="background:linear-gradient(135deg,#8000FF,#6C00FF);color:white;border:none;padding:15px;border-radius:10px;font-family:Orbitron,sans-serif;font-weight:700;cursor:pointer;transition:all 0.3s ease;text-align:left;display:flex;align-items:center;gap:15px;">
          <span style="font-size:1.5rem;">${emoji}</span>
          <div style="text-align:left;">
            <div style="font-size:1.1rem;">${gameName}</div>
            <div style="font-size:0.8rem;opacity:0.8;">${self.getGameDescription(gameType)}</div>
          </div>
        </button>
      `;
    });
    alternativesHTML += `
          </div>
          <button onclick="GameLimiter.closeAlternativeModal()" style="background:transparent;color:#A0A0B5;border:1px solid #A0A0B5;padding:12px;border-radius:10px;font-family:Orbitron,sans-serif;cursor:pointer;transition:all 0.3s ease;width:100%;margin-top:15px;">Close</button>
        </div>
      </div>
    `;
    var altModal = document.createElement('div');
    altModal.innerHTML = alternativesHTML;
    altModal.id = 'alternative-games-modal';
    document.body.appendChild(altModal);
  },

  getGameDescription: function(gameType) {
    var descriptions = {
      'snake': 'Eat apples, earn ₦200 each',
      'coinflip': 'Bet & double your money',
      'plinko': 'Bet & multiply your earnings',
      'spin': 'Spin & win up to ₦1000',
      'tiktok': 'Follow & earn ₦150 daily'
    };
    return descriptions[gameType] || 'Earn rewards';
  },

  closeAlternativeModal: function() {
    var modal = document.getElementById('alternative-games-modal');
    if (modal) modal.remove();
  }
};

// ========== ENHANCED GAME LIMITER ==========
var EnhancedGameLimiter = {
  async checkAndHandleGameAccess(gameType, targetUrl) {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return false;
    }
    try {
      var response = await App.requestWithTimeout('/api/games/check-limit-with-logout/' + gameType, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
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

  showInformativeModal: function(gameType, data) {
    var existing = document.getElementById('force-logout-modal');
    if (existing) existing.remove();
    
    var gameInfo = GameLimiter.gameMessages[gameType] || {
      icon: '🎮',
      title: 'Daily Limit Reached',
      message: 'You have reached your daily limit for this game.'
    };
    var played = data.played_today || 0;
    var max = data.max_plays || CONFIG.GAME_DAILY_LIMITS[gameType] || 5;
    var resetTime = data.reset_time || 'midnight (00:00 UTC)';

    var modal = document.createElement('div');
    modal.id = 'force-logout-modal';
    modal.className = 'game-limit-modal';
    modal.innerHTML = `
      <div class="game-limit-modal-content">
        <div class="game-limit-icon">⏰</div>
        <h3 class="game-limit-title">Daily Limit Reached</h3>
        <div class="game-limit-message">
          <p style="font-size:1.1rem;line-height:1.6;">
            <strong>You've played ${played}/${max} times today!</strong>
          </p>
          <p>Daily limits reset at <strong>${resetTime}</strong>.</p>
          <p style="margin-top:12px;color:#fbbf24;">Come back tomorrow to play again!</p>
        </div>
        <div class="game-limit-buttons">
          <button class="game-limit-btn-ok" onclick="EnhancedGameLimiter.closeModal(); window.location.href='index.html'">
            <i class="fas fa-home"></i> Go to Dashboard
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  },

  closeModal: function() {
    var modal = document.getElementById('force-logout-modal');
    if (modal) modal.remove();
  },

  showLimitReachedModal: function(gameType, data) {
    GameLimiter.showLimitModal(gameType, data);
  }
};

// ========== PROFILE ==========
var Profile = {
  open: async function () {
    if (!App.currentUser) return;
    await this.load();
    App.showModal('profile-modal');
  },

  load: async function () {
    try {
      var response = await App.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      if (data.success) {
        App.currentUser = data.user;
        App.updateBalanceDisplay();
        var stats = data.user.game_stats || {};
        var html = `
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
            <input type="text" id="profile-pic-url" placeholder="Enter image URL"
                   style="width:100%;padding:8px;margin:5px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:4px;">
            <button class="btn-primary" onclick="Profile.setProfilePicture()" style="margin-top:10px;">
              <i class="fas fa-upload"></i> Update Picture
            </button>
        `;
        if (data.user.profile_picture) {
          html += `
            <div style="margin-top:15px;text-align:center;">
              <img src="${data.user.profile_picture}" style="width:100px;height:100px;border-radius:15px;border:3px solid #8000FF;">
            </div>
          `;
        }
        document.getElementById('profile-data').innerHTML = html;
      }
    } catch (err) {
      console.error('Failed to load profile', err);
      document.getElementById('profile-data').innerHTML = '<p class="error">Failed to load profile. Please try again.</p>';
    }
  },

  setProfilePicture: async function () {
    var url = document.getElementById('profile-pic-url').value.trim();
    if (!url) {
      return;
    }
    try {
      var response = await App.requestWithTimeout('/api/user/set-profile-picture', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picture_url: url })
      });
      var data = await response.json();
      if (data.success) {
        this.load();
      }
    } catch (error) {
      // silent
    }
  }
};

// ========== REFERRALS (UPDATED) ==========
var Referral = {
  open: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      if (data.success) {
        var referrals = data.user.referrals || {};
        var referredUsers = referrals.referred_users || [];
        var claimHistory = referrals.claim_history || [];
        var unclaimed = referrals.unclaimed_bonus || 0;
        var referralCount = referrals.count || 0;

        // Build referred users list
        var usersHtml = '';
        if (referredUsers.length === 0) {
          usersHtml = '<p style="color:#A0A0B5;font-size:0.85rem;">No referred users yet.</p>';
        } else {
          usersHtml = '<div style="max-height:160px;overflow-y:auto;margin:8px 0;">';
          referredUsers.forEach(function(u) {
            var statusLabel = u.bonus_claimed ? 'Claimed' : 'Unclaimed';
            var statusColor = u.bonus_claimed ? '#00FF55' : '#FFA500';
            usersHtml += `
              <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:0.85rem;">
                <span>${u.username}</span>
                <span style="color:${statusColor};font-weight:600;">${statusLabel}</span>
              </div>
            `;
          });
          usersHtml += '</div>';
        }

        // Build claim history
        var historyHtml = '';
        if (claimHistory.length === 0) {
          historyHtml = '<p style="color:#A0A0B5;font-size:0.85rem;">No referral bonuses claimed yet.</p>';
        } else {
          historyHtml = '<div style="max-height:120px;overflow-y:auto;margin:8px 0;">';
          claimHistory.forEach(function(tx) {
            var amt = parseFloat(tx.amount) || 0;
            historyHtml += `
              <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:0.8rem;">
                <span>${new Date(tx.timestamp).toLocaleDateString()}</span>
                <span style="color:#00FF55;font-weight:600;">+₦${amt.toLocaleString()}</span>
              </div>
            `;
          });
          historyHtml += '</div>';
        }

        var html = `
          <div class="referral-section">
            <h4><i class="fas fa-users"></i> Your Referral Program</h4>
            <p><strong>Your Referral Code:</strong> <code style="font-size:1.2em;background:#8000FF;padding:5px 10px;border-radius:5px;">${data.user.referral_code}</code></p>
            <p>Share this code to earn <strong>₦${CONFIG.REFERRAL_BONUS.toLocaleString()}</strong> per friend!</p>
            <p><strong>Referred Users:</strong> ${referralCount}</p>
            <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
            ${unclaimed > 0
              ? '<button class="btn-primary" onclick="Referral.claimBonuses()" style="margin-top:15px;"><i class="fas fa-gift"></i> Claim ₦' + unclaimed.toLocaleString() + ' Bonus</button>'
              : '<p style="color:#00FF55;margin-top:15px;">All bonuses claimed!</p>'
            }
          </div>
          <div class="referral-section">
            <h4><i class="fas fa-user-friends"></i> Referred Users</h4>
            ${usersHtml}
          </div>
          <div class="referral-section">
            <h4><i class="fas fa-history"></i> Claim History</h4>
            ${historyHtml}
          </div>
          <div class="referral-section" style="margin-top:20px;">
            <h4><i class="fas fa-share-alt"></i> Share Your Link</h4>
            <div style="background:#151535;padding:10px;border-radius:5px;border:1px solid #8000FF;margin:10px 0;word-break:break-all;">
              ${window.location.origin}/?ref=${data.user.referral_code}
            </div>
            <button class="btn-secondary" onclick="Referral.copyReferralLink('${data.user.referral_code}')" style="margin-top:10px;">
              <i class="fas fa-copy"></i> Copy Link
            </button>
          </div>
        `;
        document.getElementById('referral-data').innerHTML = html;
        App.showModal('referral-modal');
      } else {
        alert('Failed to load referral data. Please try again.');
      }
    } catch (error) {
      console.error('Referral load error:', error);
      alert('Failed to load referral data. Please try again.');
    }
  },

  copyReferralLink: function (code) {
    var link = window.location.origin + '/?ref=' + code;
    navigator.clipboard.writeText(link).then(function() {
      alert('Referral link copied to clipboard!');
    }).catch(function() {
      var textarea = document.createElement('textarea');
      textarea.value = link;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      alert('Referral link copied!');
    });
  },

  claimBonuses: async function () {
    var btn = document.querySelector('#referral-data .btn-primary');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Claiming...';
    }
    try {
      var result = await GameManager.safeClaim('/api/referral/claim', {}, 'referral');
      if (!result.success) {
        alert(result.message || 'Failed to claim bonus');
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-gift"></i> Claim ₦' + (result.claimed_amount || 0).toLocaleString() + ' Bonus';
        }
        return;
      }
      App.updateBalance(result.new_balance);
      var claimedAmt = result.claimed_amount || 0;
      App.showMessage('Claimed ₦' + claimedAmt.toLocaleString() + ' bonus!', 'success', 4000);
      this.open(); // refresh modal
    } catch (error) {
      console.error('Claim error:', error);
      alert('Network error. Please try again.');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-gift"></i> Claim Bonus';
      }
    }
  }
};

// ========== BANKING ==========
var Banking = {
  banks: [],
  verifyingAccount: false,
  verificationTimeout: null,

  async loadBanks() {
    try {
      var response = await App.requestWithTimeout('/api/banking/banks');
      var data = await response.json();
      if (data.success) {
        this.banks = data.banks;
        var select = document.getElementById('bank-select');
        if (select) {
          select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
          data.banks.forEach(function(bank) {
            var opt = document.createElement('option');
            opt.value = bank.code;
            opt.textContent = bank.name;
            select.appendChild(opt);
          });
        }
      } else {
        console.error('Failed to load banks:', data.message);
        this.loadFallbackBanks();
      }
    } catch (err) {
      console.error('Error loading banks:', err);
      this.loadFallbackBanks();
    }
  },

  loadFallbackBanks: function() {
    var fallbackBanks = [
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
    this.banks = fallbackBanks;
    var select = document.getElementById('bank-select');
    if (select) {
      select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
      fallbackBanks.forEach(function(bank) {
        var opt = document.createElement('option');
        opt.value = bank.code;
        opt.textContent = bank.name;
        select.appendChild(opt);
      });
    }
  },

  verifyAccount: async function() {
    var bankCode = document.getElementById('bank-select').value;
    var accountNumber = document.getElementById('account-number').value.trim();
    var nameDisplay = document.getElementById('account-name-display');
    var nameField = document.getElementById('account-name-manual');
    var spinner = document.getElementById('verify-spinner');
    var statusEl = document.getElementById('account-verification-status');
    
    if (!bankCode || !accountNumber || accountNumber.length < 10) {
      return;
    }
    
    spinner.style.display = 'inline-block';
    this.verifyingAccount = true;
    
    if (this.verificationTimeout) {
      clearTimeout(this.verificationTimeout);
    }
    
    try {
      var response = await App.requestWithTimeout('/api/banking/verify-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          bank_code: bankCode,
          account_number: accountNumber
        })
      }, 10000);
      
      var data = await response.json();
      
      spinner.style.display = 'none';
      this.verifyingAccount = false;
      
      if (data.success) {
        nameDisplay.style.display = 'block';
        nameDisplay.style.borderColor = 'rgba(0,255,85,0.3)';
        nameDisplay.style.background = 'rgba(0,255,85,0.05)';
        document.getElementById('verified-account-name').textContent = data.account_name;
        if (!nameField.value) {
          nameField.value = data.account_name;
        }
        nameField.style.borderColor = '#00FF55';
        nameField.style.background = 'rgba(0,255,85,0.05)';
        statusEl.innerHTML = '<i class="fas fa-check-circle" style="color: #00FF55;"></i>';
      } else {
        nameDisplay.style.display = 'block';
        nameDisplay.style.borderColor = 'rgba(255,165,0,0.3)';
        nameDisplay.style.background = 'rgba(255,165,0,0.05)';
        document.getElementById('verified-account-name').textContent = 'Verification failed - you may enter name manually';
        document.getElementById('verified-account-name').style.color = '#FFA500';
        statusEl.innerHTML = '<i class="fas fa-exclamation-triangle" style="color: #FFA500;"></i>';
        
        this.verificationTimeout = setTimeout(() => {
          nameDisplay.style.display = 'none';
          statusEl.innerHTML = '';
        }, 5000);
      }
    } catch (error) {
      console.error('Verification error:', error);
      spinner.style.display = 'none';
      this.verifyingAccount = false;
      
      nameDisplay.style.display = 'block';
      nameDisplay.style.borderColor = 'rgba(255,165,0,0.3)';
      nameDisplay.style.background = 'rgba(255,165,0,0.05)';
      document.getElementById('verified-account-name').textContent = 'Network error - you may enter name manually';
      document.getElementById('verified-account-name').style.color = '#FFA500';
      statusEl.innerHTML = '<i class="fas fa-exclamation-triangle" style="color: #FFA500;"></i>';
      
      this.verificationTimeout = setTimeout(() => {
        nameDisplay.style.display = 'none';
        statusEl.innerHTML = '';
      }, 5000);
    }
  },

  openWithdraw: async function () {
    if (!App.currentUser) return;
    var canWithdraw = await checkWithdrawalDay();
    if (!canWithdraw) return;
    document.getElementById('withdrawal-message').textContent = '';
    if (this.banks.length === 0) await this.loadBanks();
    document.getElementById('withdraw-amount').value = '';
    document.getElementById('bank-select').selectedIndex = 0;
    document.getElementById('account-number').value = '';
    document.getElementById('account-name-manual').value = '';
    document.getElementById('account-name-display').style.display = 'none';
    document.getElementById('account-verification-status').innerHTML = '';
    App.showModal('withdrawal-modal');
  },

  processWithdrawal: async function () {
    var userRes = await App.requestWithTimeout('/api/user/profile');
    var userData = await userRes.json();
    var msgEl = document.getElementById('withdrawal-message');
    
    if (!userData.success) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Session expired. Please log in again.</div>`;
      return;
    }
    
    var user = userData.user;
    if (!user.withdrawal_pin) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-info-circle"></i> You must set a withdrawal PIN first.</div>`;
      Settings.setWithdrawalPin();
      return;
    }
    
    var amount = parseFloat(document.getElementById('withdraw-amount').value);
    var bankCode = document.getElementById('bank-select').value;
    var accountNumber = document.getElementById('account-number').value.trim();
    var accountName = document.getElementById('account-name-manual').value.trim();

    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Minimum withdrawal: ₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}</div>`;
      return;
    }
    
    var combinedBalance = parseFloat(user.balance);
    if (amount > combinedBalance) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Insufficient balance. Total available: ₦${combinedBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>`;
      return;
    }
    
    if (!bankCode) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Please select a bank.</div>`;
      return;
    }
    
    if (!accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Please enter a valid 10-digit account number.</div>`;
      return;
    }
    
    if (!accountName) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Please enter the account name.</div>`;
      return;
    }

    PinModal.open('Enter Withdrawal PIN', function(pin) {
      Banking._submitWithdrawal(amount, bankCode, accountNumber, accountName, pin);
    });
  },

  _submitWithdrawal: async function (amount, bankCode, accountNumber, accountName, pin) {
    var msgEl = document.getElementById('withdrawal-message');
    msgEl.innerHTML = `<div class="alert-box info"><i class="fas fa-spinner fa-spin"></i> Processing withdrawal...</div>`;
    try {
      var result = await GameManager.safeClaim('/api/banking/withdraw', {
        amount: amount, 
        bank_code: bankCode, 
        account_number: accountNumber,
        account_name: accountName, 
        pin: pin
      }, 'withdrawal');
      
      if (result.success) {
        msgEl.innerHTML = `<div class="alert-box success"><i class="fas fa-check-circle"></i> ${result.message}</div>`;
        App.updateBalance(result.new_balance);
        setTimeout(function() { App.closeModal('withdrawal-modal'); }, 2000);
      } else {
        msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message}</div>`;
      }
    } catch (error) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error. Please try again.</div>`;
    }
  }
};

// ========== PIN MODAL ==========
var PinModal = {
  _callback: null,
  _context: null,

  open: function(title, callback, context) {
    this._callback = callback;
    this._context = context || null;
    document.getElementById('pin-modal-title').textContent = title;
    document.getElementById('pin-input').value = '';
    document.getElementById('pin-modal-message').textContent = '';
    document.getElementById('pin-modal-message').className = 'message';
    App.showModal('pin-modal');
    document.getElementById('pin-input').focus();
  },

  close: function() {
    App.closeModal('pin-modal');
    this._callback = null;
    this._context = null;
  },

  submit: function() {
    var pin = document.getElementById('pin-input').value.trim();
    var msgEl = document.getElementById('pin-modal-message');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      msgEl.textContent = 'Please enter a 4-6 digit PIN.';
      msgEl.className = 'message error';
      return;
    }
    msgEl.textContent = '';
    msgEl.className = 'message';
    if (this._callback) {
      this._callback(pin, this._context);
    }
    this.close();
  }
};

// ========== ACHIEVEMENTS ==========
var Achievements = {
  open: function () {
    if (!App.currentUser) return;
    window.location.href = 'achievements.html';
  },

  claimAllRewards: async function () {
    try {
      var result = await GameManager.safeClaim('/api/achievements/claim', {}, 'achievements');
      if (result.success) {
        App.updateBalance(result.new_balance);
      }
    } catch (error) {
      // silent
    }
  }
};

// ========== GAMES ==========
var Games = {
  openSnake: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'); },
  openCoinFlip: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'); },
  openPlinko: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'); },

  reportSnake: async function (apples) {
    var result = await GameManager.safeClaim('/api/games/snake/report', { apples_eaten: apples }, 'snake');
    if (result && result.success && result.new_balance !== undefined) {
      App.updateBalance(result.new_balance);
    }
    return result;
  },

  reportCoinFlip: async function (bet, won) {
    var result = await GameManager.safeClaim('/api/games/coinflip/report', { bet: bet, won: won }, 'coinflip');
    if (result && result.success && result.new_balance !== undefined) {
      App.updateBalance(result.new_balance);
    }
    return result;
  },

  reportPlinko: async function (bet, multiplier) {
    var result = await GameManager.safeClaim('/api/games/plinko/report', { bet: bet, multiplier: multiplier }, 'plinko');
    if (result && result.success && result.new_balance !== undefined) {
      App.updateBalance(result.new_balance);
    }
    return result;
  },

  reportSpin: async function (_unused) {
    var result = await GameManager.safeClaim('/api/spin/execute', {}, 'spin');
    if (result && result.success && result.new_balance !== undefined) {
      App.updateBalance(result.new_balance);
    }
    return result;
  },

  openTikTok: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/games/check-limit-with-logout/tiktok', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
      if (!data.success || !data.can_play) {
        EnhancedGameLimiter.showInformativeModal('tiktok', data);
        return;
      }
    } catch (error) {
      console.error('TikTok access error:', error);
    }

    var msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = '';
    msgEl.className = 'message';
    try {
      var response = await App.requestWithTimeout('/api/games/tiktok/daily');
      var data = await response.json();
      if (!data.success) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">' + (data.message || 'No task today.') + '</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (data.already_claimed) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff9800;">Already claimed today!</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (!data.task || !data.task.tiktok_link) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">No task for today.</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      try {
        var url = new URL(data.task.tiktok_link);
        var username = url.pathname.split('/')[1] || data.task.tiktok_link;
        document.getElementById('tiktok-account-name').textContent = '@' + username;
        document.getElementById('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display"><strong>@${username}</strong></div>
          <p class="small-text">Search <strong>@${username}</strong> on TikTok and follow</p>
        `;
      } catch (e) {
        document.getElementById('tiktok-account-name').textContent = data.task.tiktok_link;
        document.getElementById('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display"><strong>${data.task.tiktok_link}</strong></div>
          <p class="small-text">Open this link in TikTok and follow</p>
        `;
      }
      document.querySelector('.action-buttons').style.display = 'flex';
      App.showModal('tiktok-modal');
    } catch (err) {
      console.error('TikTok load error:', err);
      document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">Failed to load task.</p>';
      document.querySelector('.action-buttons').style.display = 'none';
      App.showModal('tiktok-modal');
    }
  },

  verifyTikTokFollow: async function () {
    var msgEl = document.getElementById('tiktok-message');
    msgEl.innerHTML = '<div class="alert-box info"><i class="fas fa-spinner fa-spin"></i> Claiming...</div>';
    try {
      var result = await GameManager.safeClaim('/api/games/tiktok/follow-daily', {}, 'tiktok');
      if (result.success) {
        App.updateBalance(result.new_balance);
        msgEl.innerHTML = `<div class="alert-box success"><i class="fas fa-check-circle"></i> Claimed ₦${result.reward}!</div>`;
        setTimeout(function() { App.closeModal('tiktok-modal'); }, 2000);
      } else {
        msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message || 'Failed.'}</div>`;
      }
    } catch (error) {
      msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error.</div>`;
    }
  },

  openTikTokApp: function () {
    var usernameEl = document.getElementById('tiktok-account-name');
    var username = usernameEl.textContent.replace('@', '');
    if (username) {
      window.open('snssdk1233://user/@' + username, '_blank');
      setTimeout(function() {
        window.open('https://www.tiktok.com/@' + username, '_blank');
      }, 500);
    }
  },

  openSpinWheel: async function() {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/games/check-limit-with-logout/spin', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
      if (!data.success || !data.can_play) {
        EnhancedGameLimiter.showInformativeModal('spin', data);
        return;
      }
    } catch (error) {
      console.error('Spin access error:', error);
    }

    var wheel = document.getElementById('wheel');
    var btn = document.getElementById('spin-button');
    var msgEl = document.getElementById('spin-message');
    var resultEl = document.getElementById('spin-result');
    var wheelSvg = document.getElementById('wheel-svg');
    if (wheelSvg) {
      wheelSvg.style.transition = 'none';
      wheelSvg.style.transform = 'rotate(0deg)';
      void wheelSvg.offsetWidth;
    }
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
    }
    if (msgEl) { msgEl.textContent = ''; msgEl.className = 'message'; }
    if (resultEl) resultEl.classList.add('hidden');
    App.showModal('spin-modal');
    setTimeout(function() { initSpinWheel(); }, 150);
  },

  spinWheel: async function() {
    var btn = document.getElementById('spin-button');
    var wheel = document.getElementById('wheel');
    var wheelSvg = document.getElementById('wheel-svg');
    var msgEl = document.getElementById('spin-message');
    var resultEl = document.getElementById('spin-result');

    if (!btn || !wheel || !wheelSvg || btn.disabled) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    if (msgEl) {
      msgEl.textContent = '';
      msgEl.className = 'message';
    }
    if (resultEl) resultEl.classList.add('hidden');

    wheelSvg.style.transition = 'none';
    wheelSvg.style.transform = 'rotate(0deg)';
    void wheelSvg.offsetWidth;

    try {
      var result = await this.reportSpin();

      if (!result.success) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        if (msgEl) {
          msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> ${result.message || 'Spin failed'}</div>`;
        }
        return;
      }

      var reward = result.reward;
      var prizeIndex = result.prize_index !== undefined ? result.prize_index : 5;
      var angleToPointer = (360 - (prizeIndex * 60 + 30)) % 360;
      var extraRotations = 6 + Math.floor(Math.random() * 3);
      var totalRotation = extraRotations * 360 + angleToPointer;

      wheelSvg.style.transition = 'transform 5s cubic-bezier(0.17, 0.67, 0.05, 1.0)';
      wheelSvg.style.transform = `rotate(${totalRotation}deg)`;

      setTimeout(() => {
        App.updateBalance(result.new_balance);
        var msgText = reward > 0 ? `Won ₦${reward.toLocaleString()}!` : 'Better luck tomorrow!';
        if (msgEl) {
          msgEl.innerHTML = `<div class="alert-box ${reward > 0 ? 'success' : 'warning'}"><i class="fas fa-${reward > 0 ? 'check-circle' : 'info-circle'}"></i> ${msgText}</div>`;
        }
        if (resultEl) {
          resultEl.innerHTML = `<p style="font-size:1.1rem;font-weight:bold;">${msgText}</p>`;
          resultEl.classList.remove('hidden');
        }
        btn.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
        btn.disabled = true;
      }, 5200);

    } catch (error) {
      console.error('Spin error:', error);
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
      if (msgEl) {
        msgEl.innerHTML = `<div class="alert-box warning"><i class="fas fa-exclamation-triangle"></i> Network error. Please try again.</div>`;
      }
    }
  }
};

// ========== SETTINGS ==========
var Settings = {
  open: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      if (!data.success) return;
      var user = data.user;
      var hasPin = !!user.withdrawal_pin;
      var html = `
        <div class="settings-section">
          <h4><i class="fas fa-user-cog"></i> Account Settings</h4>
          <p><strong>Username:</strong> ${user.username}</p>
          <p><strong>Balance:</strong> ₦${user.balance.toLocaleString()}</p>
        </div>
      `;
      try {
        var sr = await App.requestWithTimeout('/api/social-links');
        var sd = await sr.json();
        if (sd.success) {
          var s = sd;
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
          <p style="font-size:0.8rem;color:#A0A0B5;margin-bottom:8px;">Coupons are for new users who want to register on the platform.</p>
          <button class="btn-primary" onclick="window.location.href='login.html?tab=register'" style="width:100%;background:linear-gradient(135deg,#00CCFF,#8000FF);">
            <i class="fas fa-user-plus"></i> Go to Registration to Buy
          </button>
        </div>
        <div class="settings-section">
          <h4><i class="fas fa-sign-out-alt"></i> Session</h4>
          <button class="btn-primary" style="background:#d32f2f;width:100%;" onclick="Settings.logout()">
            <i class="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      `;
      document.getElementById('settings-data').innerHTML = html;
      App.showModal('settings-modal');
    } catch (error) { console.error('Settings error:', error); }
  },

  setWithdrawalPin: async function (isChange) {
    if (isChange === undefined) isChange = false;
    var self = this;
    if (isChange) {
      PinModal.open('Enter CURRENT PIN', function(currentPin) {
        self._verifyAndSetNewPin(currentPin);
      });
    } else {
      PinModal.open('Set New PIN', function(newPin) {
        self._saveNewPin(newPin);
      });
    }
  },

  _verifyAndSetNewPin: async function (currentPin) {
    try {
      var response = await App.requestWithTimeout('/api/user/verify-withdrawal-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: currentPin }),
        credentials: 'include'
      });
      var data = await response.json();
      if (!data.success) {
        alert('Incorrect current PIN');
        return;
      }
      PinModal.open('Enter NEW PIN', function(newPin) {
        this._saveNewPin(newPin);
      });
    } catch (error) { alert('Error verifying PIN'); }
  },

  _saveNewPin: async function (newPin) {
    if (!newPin || !/^\d{4,6}$/.test(newPin)) {
      alert('PIN must be 4-6 digits');
      return;
    }
    try {
      var result = await GameManager.safeClaim('/api/user/set-withdrawal-pin', { pin: newPin }, 'setpin');
      if (result.success) {
        App.closeModal('settings-modal');
        alert('PIN set successfully');
      } else {
        alert(result.message || 'Failed to set PIN');
      }
    } catch (error) { alert('Network error'); }
  },

  changeWithdrawalPin: function () { this.setWithdrawalPin(true); },

  changePassword: async function () {
    var oldPass = prompt("Enter your current password:");
    if (!oldPass) return;
    var newPass = prompt("Enter a new password (min 6 chars):");
    if (!newPass || newPass.length < 6) return;
    var confirmPass = prompt("Confirm your new password:");
    if (newPass !== confirmPass) return;
    try {
      var isAdmin = App.currentUser && App.currentUser.is_admin;
      var endpoint = isAdmin ? '/api/admin/change-password' : '/api/user/change-password';
      var response = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ current_password: oldPass, new_password: newPass })
      });
      var data = await response.json();
      if (data.success) {
        App.closeModal('settings-modal');
        if (isAdmin && data.message && data.message.indexOf('login again') !== -1) {
          setTimeout(function() { if (confirm("Password changed. Logout and login again?")) Settings.logout(); }, 1000);
        }
      }
    } catch (error) { /* silent */ }
  },

  logout: async function () {
    if (!confirm('Logout?')) return;
    try {
      await App.requestWithTimeout('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) { /* silent */ }
    document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
      (window.location.protocol === 'https:' ? '; secure' : '');
    window.location.href = 'login.html';
  }
};

// ========== SPIN WHEEL ==========
function initSpinWheel() {
  var container = document.getElementById('wheel');
  if (!container) return;
  container.innerHTML = '';
  container.style.cssText = 'position:relative;width:280px;height:280px;margin:0 auto;';

  var prizes = [
    { label: '₦1000', color: '#FF0055', textColor: '#fff' },
    { label: '₦500',  color: '#FF8C00', textColor: '#fff' },
    { label: '₦200',  color: '#FFCC00', textColor: '#111' },
    { label: '₦100',  color: '#00C851', textColor: '#fff' },
    { label: '₦50',   color: '#00CCFF', textColor: '#111' },
    { label: '0',     color: '#8000FF', textColor: '#fff' }
  ];

  var N = prizes.length, cx = 140, cy = 140, r = 130, sliceDeg = 360 / N;
  var svgNS = 'http://www.w3.org/2000/svg';
  var svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('id', 'wheel-svg');
  svg.setAttribute('viewBox', '0 0 280 280');
  svg.setAttribute('width', '280');
  svg.setAttribute('height', '280');
  svg.style.cssText = 'display:block;border-radius:50%;overflow:hidden;filter:drop-shadow(0 0 18px rgba(128,0,255,0.5));';

  function polarToCart(cx, cy, r, angleDeg) {
    var rad = (angleDeg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  prizes.forEach(function(prize, i) {
    var startAngle = i * sliceDeg, endAngle = startAngle + sliceDeg, midAngle = startAngle + sliceDeg / 2;
    var p1 = polarToCart(cx, cy, r, startAngle);
    var p2 = polarToCart(cx, cy, r, endAngle);
    var path = document.createElementNS(svgNS, 'path');
    var d = ['M ' + cx + ' ' + cy, 'L ' + p1.x + ' ' + p1.y, 'A ' + r + ' ' + r + ' 0 0 1 ' + p2.x + ' ' + p2.y, 'Z'].join(' ');
    path.setAttribute('d', d);
    path.setAttribute('fill', prize.color);
    path.setAttribute('stroke', '#0A0A1F');
    path.setAttribute('stroke-width', '2');
    svg.appendChild(path);

    var lp = polarToCart(cx, cy, r * 0.72, midAngle);
    var text = document.createElementNS(svgNS, 'text');
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

  var centerCircle = document.createElementNS(svgNS, 'circle');
  centerCircle.setAttribute('cx', cx);
  centerCircle.setAttribute('cy', cy);
  centerCircle.setAttribute('r', '22');
  centerCircle.setAttribute('fill', '#0A0A1F');
  centerCircle.setAttribute('stroke', '#8000FF');
  centerCircle.setAttribute('stroke-width', '3');
  svg.appendChild(centerCircle);

  var centerText = document.createElementNS(svgNS, 'text');
  centerText.setAttribute('x', cx);
  centerText.setAttribute('y', cy);
  centerText.setAttribute('text-anchor', 'middle');
  centerText.setAttribute('dominant-baseline', 'middle');
  centerText.setAttribute('fill', '#8000FF');
  centerText.setAttribute('font-size', '14');
  centerText.textContent = '★';
  svg.appendChild(centerText);
  container.appendChild(svg);

  var pointer = document.createElement('div');
  pointer.style.cssText = `
    position:absolute;top:-14px;left:50%;
    transform:translateX(-50%);
    width:0;height:0;
    border-left:12px solid transparent;
    border-right:12px solid transparent;
    border-top:22px solid #FFD700;
    filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5));
    z-index:10;
  `;
  container.appendChild(pointer);
  container._currentRotation = 0;
}

// ========== DOM READY ==========
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
      document.querySelectorAll('.auth-form').forEach(function(f) { f.classList.remove('active'); });
      tab.classList.add('active');
      var targetForm = tab.dataset.tab + '-form';
      document.getElementById(targetForm).classList.add('active');
    });
  });

  var buyCouponBtn = document.querySelector('[onclick="Auth.buyCoupon()"]');
  if (buyCouponBtn) {
    buyCouponBtn.onclick = function() { Auth.buyCoupon(); };
  }

  Auth.initPasswordToggles();
  App.init();

  if (document.getElementById('reg-coupon')) {
    var urlParams = new URLSearchParams(window.location.search);
    var coupon = urlParams.get('coupon');
    var tab = urlParams.get('tab');
    var ref = urlParams.get('ref');

    if (coupon) {
      document.getElementById('reg-coupon').value = coupon;
      if (tab === 'register') {
        document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
        document.querySelector('[data-tab="register"]').classList.add('active');
        document.querySelectorAll('.auth-form').forEach(function(f) { f.classList.remove('active'); });
        document.getElementById('register-form').classList.add('active');
      }
    }

    if (ref) {
      document.getElementById('reg-referral').value = ref;
      document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
      document.querySelector('[data-tab="register"]').classList.add('active');
      document.querySelectorAll('.auth-form').forEach(function(f) { f.classList.remove('active'); });
      document.getElementById('register-form').classList.add('active');
    }
  }

  var accountInput = document.getElementById('account-number');
  if (accountInput) {
    accountInput.addEventListener('input', function() {
      if (this.value.length >= 10 && document.getElementById('bank-select').value) {
        Banking.verifyAccount();
      }
    });
    
    accountInput.addEventListener('keyup', function() {
      if (this.value.length < 10) {
        document.getElementById('account-name-display').style.display = 'none';
        document.getElementById('account-name-manual').value = '';
        document.getElementById('account-verification-status').innerHTML = '';
      }
    });
  }
  
  var bankSelect = document.getElementById('bank-select');
  if (bankSelect) {
    bankSelect.addEventListener('change', function() {
      var accountNumber = document.getElementById('account-number').value.trim();
      if (accountNumber.length >= 10) {
        Banking.verifyAccount();
      }
    });
  }

  var spinModal = document.getElementById('spin-modal');
  if (spinModal) {
    var observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.attributeName === 'class') {
          var isVisible = !spinModal.classList.contains('hidden');
          if (isVisible) setTimeout(function() { initSpinWheel(); }, 100);
        }
      });
    });
    observer.observe(spinModal, { attributes: true, attributeFilter: ['class'] });
  }

  var scrollPos = sessionStorage.getItem('flexia_scroll_position');
  if (scrollPos) {
    setTimeout(function() {
      window.scrollTo(0, parseInt(scrollPos));
      sessionStorage.removeItem('flexia_scroll_position');
    }, 300);
  }
});

// ========== GLOBAL EXPORTS ==========
window.App = App;
window.GameManager = GameManager;
window.GameLimiter = GameLimiter;
window.EnhancedGameLimiter = EnhancedGameLimiter;
window.Games = Games;
window.Auth = Auth;
window.Profile = Profile;
window.Referral = Referral;
window.Banking = Banking;
window.Achievements = Achievements;
window.Settings = Settings;
window.SessionManager = SessionManager;
window.PinModal = PinModal;
window.checkWithdrawalDay = checkWithdrawalDay;
window.closeWithdrawalDayModal = closeWithdrawalDayModal;
window.updateBalance = App.updateBalance.bind(App);
window.showMessage = App.showMessage.bind(App);
window.goBackToDashboard = function() { window.location.href = 'index.html'; };

window.claimSnakeReward = async function(apples) {
  return await GameManager.safeClaim('/api/games/snake/report', { apples_eaten: apples }, 'snake');
};
window.claimCoinFlipReward = async function(bet, won) {
  return await GameManager.safeClaim('/api/games/coinflip/report', { bet: bet, won: won }, 'coinflip');
};
window.claimPlinkoReward = async function(bet, multiplier) {
  return await GameManager.safeClaim('/api/games/plinko/report', { bet: bet, multiplier: multiplier }, 'plinko');
};

console.log('FLEXIA Script v17.9 - 5-play limit applied');
