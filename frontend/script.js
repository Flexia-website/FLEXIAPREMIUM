// script.js - FLEXIA Frontend Logic v17.0 - COMPLETE VERSION
// ✅ FULL REGISTRATION WITH COUPON VALIDATION ✅ PAYSTACK BUY COUPON ✅ SESSION MANAGEMENT ✅ FIXED LOGIN

//========== EMBEDDED CSS ========
const embeddedCSS = `
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

var style = document.createElement('style');
style.textContent = embeddedCSS;
document.head.appendChild(style);

//========== CONFIGURATION ========
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
    'coinflip': 12,
    'plinko': 12,
    'spin': 1,
    'tiktok': 3
  },
  PAYSTACK_MIN_AMOUNT: window.APP_CONFIG?.PAYSTACK?.MIN_AMOUNT || 500
};

//========== CORE APP ==========
var App = {
  currentUser: null,
  balanceVisible: true,
  lastBalanceUpdate: 0,

  init: async function () {
    console.log('App.init() called');
    await this.checkAuth();
    if (document.getElementById('app-screen')) {
      await Profile.load();
      await Banking.loadBanks();
      this.setupTheme();
      this.setupAutoRefresh();
      this.updateGameCards();
      if (this.currentUser) {
        await TodayEarnings.fetch();
        SessionManager.init();
      }
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
        this.refreshBalance();
        document.getElementById('dashboard-username').textContent = data.user.username;
        document.getElementById('dashboard-avatar').textContent = data.user.username.charAt(0).toUpperCase();
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
    console.log('Showing app screen');
    var authScreen = document.getElementById('auth-screen');
    var appScreen = document.getElementById('app-screen');
    
    if (authScreen) {
      authScreen.style.display = 'none';
    }
    if (appScreen) {
      appScreen.style.display = 'block';
      appScreen.classList.add('active');
    }
  },

  showAuthScreen: function () {
    console.log('Showing auth screen');
    var authScreen = document.getElementById('auth-screen');
    var appScreen = document.getElementById('app-screen');
    
    if (authScreen) {
      authScreen.style.display = 'flex';
    }
    if (appScreen) {
      appScreen.style.display = 'none';
      appScreen.classList.remove('active');
    }
  },

  refreshBalance: function (force) {
    if (force === undefined) force = false;
    if (!this.currentUser) return;
    var now = Date.now();
    if (!force && (now - this.lastBalanceUpdate) < 3000) {
      return;
    }
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
      gameRewardsEl.textContent = gameTotal.toLocaleString(undefined, {
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

    this.lastBalanceUpdate = now;
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
          this.refreshBalance(true);
          await TodayEarnings.fetch();
        }
      }
    } catch (e) { /* silent fail */ }
  },

  updateBalance: function (newBalance) {
    if (this.currentUser) {
      this.currentUser.balance = newBalance;
      this.refreshBalance(true);
      TodayEarnings.fetch();
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
    document.getElementById(modalId).classList.remove('hidden');
  },

  closeModal: function (modalId) {
    document.getElementById(modalId).classList.add('hidden');
  },

  showMessage: function (text, type, duration) {
    if (type === undefined) type = 'info';
    if (duration === undefined) duration = 5000;
    document.querySelectorAll('.global-message').forEach(function(el) { el.remove(); });
    var messageEl = document.createElement('div');
    messageEl.className = 'global-message ' + type;
    messageEl.textContent = text;
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

  setupAutoRefresh: function () {
    var self = this;
    setInterval(function() { self.fetchFreshBalance(); }, 10000);
    setInterval(function() { self.updateGameCards(); }, 30000);
    document.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'visible') {
        self.fetchFreshBalance();
        SessionManager.handleAppResume();
      }
    });
    window.addEventListener('storage', function(e) {
      if (e.key === 'flexia_balance' && e.newValue && self.currentUser) {
        var val = parseFloat(e.newValue);
        if (!isNaN(val)) {
          self.currentUser.balance = val;
          self.refreshBalance(true);
          TodayEarnings.fetch();
        }
      }
    });
  },

  async updateGameCards() {
    if (!this.currentUser) return;
    var games = [
      { type: 'snake', element: document.querySelector('.activity-card .icon.snake')?.closest('.activity-card') },
      { type: 'coinflip', element: document.querySelector('.activity-card .icon.coin')?.closest('.activity-card') },
      { type: 'plinko', element: document.querySelector('.activity-card .icon.plinko')?.closest('.activity-card') }
    ];
    for (var i = 0; i < games.length; i++) {
      var game = games[i];
      if (!game.element) continue;
      try {
        var response = await this.requestWithTimeout('/api/games/access?game=' + game.type, {
          credentials: 'include',
          headers: { 'Cache-Control': 'no-cache' }
        });
        if (response.ok) {
          var data = await response.json();
          if (data.success) {
            if (data.can_play) {
              game.element.classList.remove('disabled');
              game.element.style.opacity = '1';
              game.element.style.filter = 'none';
              game.element.style.cursor = 'pointer';
              var badge = game.element.querySelector('.badge');
              if (badge && data.remaining_plays !== undefined) {
                badge.textContent = data.remaining_plays + ' left';
              }
            } else {
              game.element.classList.add('disabled');
              var badge = game.element.querySelector('.badge');
              if (badge) {
                badge.textContent = 'LIMIT';
                badge.style.background = '#ff4757';
              }
            }
          }
        }
      } catch (error) {
        console.error('Failed to update ' + game.type + ' card:', error);
      }
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

//========== SESSION PERSISTENCE & RECOVERY ==========
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
      App.showMessage('Connection restored. Refreshing...', 'info', 3000);
      self.handleAppResume();
    });
    
    window.addEventListener('offline', function() {
      App.showMessage('No internet connection. Reconnecting...', 'warning', 5000);
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
        
        if (document.getElementById('auth-screen') && 
            document.getElementById('auth-screen').style.display !== 'none') {
          App.showMessage('Session restored. Welcome back!', 'success', 3000);
          await App.checkAuth();
        }
        return true;
      } else {
        if (document.getElementById('app-screen') && 
            document.getElementById('app-screen').style.display !== 'none') {
          App.showAuthScreen();
          App.showMessage('Session expired. Please login again.', 'warning', 4000);
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
        TodayEarnings.fetch();
        App.updateGameCards();
        App.showMessage('App reloaded successfully', 'success', 2000);
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

// Save state on beforeunload
window.addEventListener('beforeunload', function() {
  SessionManager.saveState();
  SessionManager.saveScrollPosition();
});

//========== AUTHENTICATION ==========
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
        App.showAppScreen();
        App.refreshBalance();
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';

        var loginPassword = document.getElementById('login-password');
        if (loginPassword.type === 'text') {
          loginPassword.type = 'password';
          var toggleBtn = loginPassword.nextElementSibling;
          if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.setAttribute('title', 'Show password');
          }
        }
        await TodayEarnings.fetch();
        SessionManager.init();
        console.log('Login successful, dashboard shown');
      }
    } catch (error) {
      messageEl.textContent = error.message || 'Network error. Please try again.';
      messageEl.className = 'message error';
    }
  },

  register: async function () {
    var username = document.getElementById('reg-username').value.trim();
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
        body: JSON.stringify({ username: username, password: password, coupon_code: coupon, referral_code: referral, contact: contact })
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
    try {
      var response = await App.requestWithTimeout('/api/whatsapp/numbers');
      var data = await response.json();
      var number = (data.success && data.numbers && data.numbers[0]) ? data.numbers[0].number.trim() : '2348160881049';
      window.open('https://wa.me/' + number, '_blank');
    } catch (error) {
      window.open('https://wa.me/2348160881049', '_blank');
    }
  }
};

//========== TODAY'S EARNINGS ==========
var TodayEarnings = {
  async fetch() {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/user/today-earnings', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
      if (data.success) {
        this.render(data);
      }
    } catch (error) {
      console.error('Failed to fetch today earnings:', error);
    }
  },

  render: function(data) {
    var total = data.total_earned || 0;
    var breakdown = data.breakdown || {};
    var caps = data.caps || {};

    document.getElementById('today-earnings-total').textContent = total.toFixed(2);

    var gameMap = {
      'SNAKE_REWARD': 'today-snake',
      'COINFLIP_WIN': 'today-coinflip',
      'PLINKO_WIN': 'today-plinko',
      'TIKTOK_DAILY': 'today-tiktok',
      'REFERRAL_BONUS': 'today-referral',
      'LOGIN_BONUS': 'today-login',
      'ACHIEVEMENT_REWARD': 'today-achievement',
      'SPIN_REWARD': 'today-spin'
    };

    Object.keys(gameMap).forEach(function(type) {
      var el = document.getElementById(gameMap[type]);
      if (el) {
        var amount = breakdown[type] || 0;
        el.textContent = amount.toFixed(2);
      }
    });

    var capMap = {
      'snake': 'today-snake',
      'coinflip': 'today-coinflip',
      'plinko': 'today-plinko'
    };
    Object.keys(capMap).forEach(function(game) {
      var el = document.getElementById(capMap[game]);
      if (el && caps[game]) {
        var earned = caps[game].earned || 0;
        var cap = caps[game].cap || 0;
        var parent = el.closest('.earnings-item');
        if (parent) {
          var label = parent.querySelector('span:last-child');
          if (label) {
            label.innerHTML = '₦' + earned.toFixed(2) + ' / ₦' + cap;
            if (earned >= cap) {
              label.innerHTML += ' ✓';
              label.style.color = '#34d399';
            } else if (earned > cap * 0.8) {
              label.style.color = '#fbbf24';
            } else {
              label.style.color = '';
            }
          }
        }
      }
    });

    var updateEl = document.getElementById('today-earnings-update');
    if (updateEl) {
      updateEl.textContent = 'Updated ' + new Date().toLocaleTimeString();
    }
  },

  refresh: async function() {
    await this.fetch();
  }
};

// Auto-refresh every 30 seconds
setInterval(function() {
  if (document.getElementById('app-screen') && document.getElementById('app-screen').style.display !== 'none') {
    TodayEarnings.refresh();
  }
}, 30000);

//========== WITHDRAWAL DAY CHECK ==========
async function checkWithdrawalDay() {
  try {
    var response = await fetch('/api/withdrawal/check-day', {
      credentials: 'include'
    });
    var data = await response.json();
    if (data.success) {
      var today = new Date().getDate();
      var days = data.custom_withdrawal_days.length > 0
        ? data.custom_withdrawal_days
        : data.global_withdrawal_days;
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
    App.showMessage('Unable to check withdrawal day. Please try again.', 'warning', 5000);
    return true;
  }
}

function showWithdrawalDayModal(canWithdraw, today, days) {
  var existingModal = document.getElementById('withdrawal-day-modal');
  if (existingModal) existingModal.remove();
  var sortedDays = days ? days.slice().sort(function(a,b){return a-b;}) : [];
  var modal = document.createElement('div');
  modal.id = 'withdrawal-day-modal';
  modal.className = 'withdrawal-day-modal';
  modal.innerHTML = `
    <div class="withdrawal-day-modal-content">
      <div class="withdrawal-day-icon ${canWithdraw ? 'allowed' : 'not-allowed'}">
        ${canWithdraw ? '✅' : '❌'}
      </div>
      <h3 class="withdrawal-day-title">
        ${canWithdraw ? 'Withdrawal Allowed Today!' : 'Withdrawal Not Allowed Today'}
      </h3>
      <div class="withdrawal-day-message">
        <p class="withdrawal-day-text">
          ${canWithdraw
            ? 'You <strong>CAN</strong> withdraw today (Day ' + today + ')!'
            : 'You <strong>cannot</strong> withdraw today (Day ' + today + ').'
          }
        </p>
        <div class="withdrawal-day-info">
          <i class="fas fa-calendar-day"></i>
          <span>Today: Day ${today}</span>
        </div>
        ${days && days.length > 0 ? `
          <div class="withdrawal-day-days">
            <strong>Withdrawal Days:</strong>
            <div style="margin-top: 8px;">
              ${sortedDays.map(function(day) {
                return '<span class="withdrawal-day-day ' + (day === today ? 'current' : '') + '">Day ' + day + (day === today ? ' (Today)' : '') + '</span>';
              }).join('')}
            </div>
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
  var modal = document.getElementById('withdrawal-day-modal');
  if (modal) modal.remove();
}

function getNextAllowedDay(currentDay, allowedDays) {
  if (!allowedDays || allowedDays.length === 0) return 'Unknown';
  var sorted = allowedDays.slice().sort(function(a,b){return a-b;});
  for (var i = 0; i < sorted.length; i++) {
    if (sorted[i] > currentDay) return 'Day ' + sorted[i];
  }
  return 'Day ' + sorted[0] + ' (next month)';
}

//========== PAYSTACK PAYMENT ==========
var PaystackPayment = {
  timerInterval: null,
  timerSeconds: 3600,

  async initiate() {
    var email = document.getElementById('payment-email').value.trim();
    var amount = parseFloat(document.getElementById('payment-amount').value);
    var btn = document.getElementById('paystack-pay-btn');
    var msg = document.getElementById('payment-message');

    if (!email || email.indexOf('@') === -1) {
      msg.textContent = 'Please enter a valid email address';
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
      var response = await App.requestWithTimeout('/api/paystack/initialize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email, amount: amount })
      });

      var data = await response.json();

      if (data.success) {
        msg.textContent = 'Payment initialized!';
        msg.className = 'message success';

        sessionStorage.setItem('paystack_ref', data.reference);
        sessionStorage.setItem('paystack_email', email);

        if (data.bank_transfer_details) {
          this.showBankTransferDetails(data.bank_transfer_details, data.expires_at);
          this.startTimer(data.expires_at);
        }

        setTimeout(function() {
          window.location.href = data.authorization_url;
        }, 2000);
      } else {
        msg.textContent = data.message || 'Payment initialization failed';
        msg.className = 'message error';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
      }
    } catch (error) {
      console.error('Payment error:', error);
      msg.textContent = error.message || 'Network error. Please try again.';
      msg.className = 'message error';
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
    }
  },

  showBankTransferDetails: function(details, expiresAt) {
    var container = document.getElementById('bank-transfer-info');
    var detailsDiv = document.getElementById('transfer-details');

    container.style.display = 'block';
    container.classList.add('visible');

    detailsDiv.innerHTML = `
      <div class="row">
        <span class="label">Bank</span>
        <span class="value">${details.bank_name || 'GTBank'}</span>
      </div>
      <div class="row">
        <span class="label">Account Number</span>
        <span class="value account-number">${details.account_number || '0123456789'}</span>
      </div>
      <div class="row">
        <span class="label">Account Name</span>
        <span class="value">${details.account_name || 'FLEXIA Payments'}</span>
      </div>
      <div class="row">
        <span class="label">Amount to Transfer</span>
        <span class="value" style="color:#00FF55;font-weight:bold;">₦${details.amount || '500.00'}</span>
      </div>
    `;

    if (expiresAt) {
      this.timerSeconds = Math.floor((new Date(expiresAt) - new Date()) / 1000);
      if (this.timerSeconds < 0) this.timerSeconds = 3600;
    } else {
      this.timerSeconds = 3600;
    }

    container.scrollIntoView({ behavior: 'smooth', block: 'center' });
  },

  startTimer: function(expiresAt) {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
    }

    if (expiresAt) {
      this.timerSeconds = Math.floor((new Date(expiresAt) - new Date()) / 1000);
      if (this.timerSeconds < 0) this.timerSeconds = 3600;
    } else {
      this.timerSeconds = 3600;
    }

    var timerEl = document.getElementById('payment-timer-value');

    var self = this;
    this.timerInterval = setInterval(function() {
      self.timerSeconds--;

      if (self.timerSeconds <= 0) {
        clearInterval(self.timerInterval);
        timerEl.textContent = '00:00';
        timerEl.className = 'payment-timer-value expired';
        document.getElementById('bank-transfer-info').style.borderColor = '#FF0000';

        var msg = document.getElementById('payment-message');
        msg.textContent = 'Payment window expired. Please start a new payment.';
        msg.className = 'message error';

        document.getElementById('paystack-pay-btn').disabled = true;
        return;
      }

      var minutes = Math.floor(self.timerSeconds / 60);
      var seconds = self.timerSeconds % 60;
      timerEl.textContent = String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');

      if (self.timerSeconds < 300) {
        timerEl.className = 'payment-timer-value danger';
      } else if (self.timerSeconds < 600) {
        timerEl.className = 'payment-timer-value warning';
      } else {
        timerEl.className = 'payment-timer-value';
      }
    }, 1000);
  },

  closeModal: function() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }

    document.getElementById('bank-transfer-info').style.display = 'none';
    document.getElementById('bank-transfer-info').classList.remove('visible');
    document.getElementById('payment-timer-value').textContent = '60:00';
    document.getElementById('payment-timer-value').className = 'payment-timer-value';

    App.closeModal('paystack-payment-modal');
  },

  async checkStatus(reference) {
    try {
      var response = await App.requestWithTimeout('/api/paystack/status/' + reference, {
        credentials: 'include'
      });
      var data = await response.json();
      return data;
    } catch (error) {
      console.error('Status check error:', error);
      return { success: false, message: 'Failed to check status' };
    }
  },

  openRegistrationPayment: function() {
    App.showModal('paystack-payment-modal');
    document.getElementById('payment-message').textContent = '';
    document.getElementById('payment-message').className = 'message';
    document.getElementById('paystack-pay-btn').disabled = false;
    document.getElementById('paystack-pay-btn').innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
    document.getElementById('bank-transfer-info').style.display = 'none';
    document.getElementById('bank-transfer-info').classList.remove('visible');
    document.getElementById('payment-timer-value').textContent = '60:00';
    document.getElementById('payment-timer-value').className = 'payment-timer-value';

    var regEmail = document.getElementById('reg-contact')?.value || '';
    if (regEmail && regEmail.indexOf('@') !== -1) {
      document.getElementById('payment-email').value = regEmail;
    }

    var modalInfo = document.querySelector('#paystack-payment-modal .modal-info');
    if (modalInfo) {
      modalInfo.innerHTML = `
        Pay via <strong>Bank Transfer</strong> or <strong>Card</strong> and receive your coupon code via email.
        <br><br>
        <span style="color: #00FF55; font-size: 0.85rem;">
          <i class="fas fa-info-circle"></i> After payment, use the coupon code to register!
        </span>
      `;
    }
  },

  openDashboardPayment: function() {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return;
    }
    App.showModal('paystack-payment-modal');
    document.getElementById('payment-message').textContent = '';
    document.getElementById('payment-message').className = 'message';
    document.getElementById('paystack-pay-btn').disabled = false;
    document.getElementById('paystack-pay-btn').innerHTML = '<i class="fas fa-credit-card"></i> Pay Now';
    document.getElementById('bank-transfer-info').style.display = 'none';
    document.getElementById('bank-transfer-info').classList.remove('visible');
    document.getElementById('payment-timer-value').textContent = '60:00';
    document.getElementById('payment-timer-value').className = 'payment-timer-value';

    if (App.currentUser && App.currentUser.email) {
      document.getElementById('payment-email').value = App.currentUser.email;
    } else if (App.currentUser && App.currentUser.contact) {
      document.getElementById('payment-email').value = App.currentUser.contact;
    }

    var modalInfo = document.querySelector('#paystack-payment-modal .modal-info');
    if (modalInfo) {
      modalInfo.innerHTML = `
        Pay via <strong>Bank Transfer</strong> or <strong>Card</strong> and receive your coupon code via email.
      `;
    }
  }
};

//========== GAME MANAGER ==========
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

  async safeClaim(endpoint, data, gameType) {
    if (gameType === undefined) gameType = 'unknown';
    if (this.pendingRequests.has(gameType)) {
      console.warn('Already claiming ' + gameType + ', ignoring duplicate');
      return { success: false, message: "Please wait for the current claim to complete" };
    }
    this.pendingRequests.set(gameType, true);
    try {
      var response = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Request-ID': Date.now().toString() },
        credentials: 'include',
        body: JSON.stringify(data)
      }, 15000);
      var result = await response.json();
      this.lastClaimTime = Date.now();
      return result;
    } catch (error) {
      console.error('Claim error:', error);
      if (error.name === 'AbortError') {
        return { success: false, message: "Request timed out. Please try again." };
      }
      return { success: false, message: error.message || "Connection error." };
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

//========== GAME LIMITER ==========
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
    'snake': { icon: '🐍', title: 'Snake Game Limit Reached', message: 'You have played Snake 5 times today. Come back tomorrow for more fun!' },
    'coinflip': { icon: '🪙', title: 'Coin Flip Limit Reached', message: 'You have played Coin Flip 2 times today. Daily limit reached!' },
    'plinko': { icon: '🎯', title: 'Plinko Limit Reached', message: 'You have played Plinko 2 times today. Try again tomorrow!' },
    'spin': { icon: '🎡', title: 'Daily Spin Limit Reached', message: 'You have already used your daily spin today! Come back tomorrow.' },
    'tiktok': { icon: '📱', title: 'TikTok Daily Limit Reached', message: 'You have already claimed TikTok reward today! Come back tomorrow.' }
  },

  async checkAndNavigate(gameType, targetUrl) {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return false;
    }
    try {
      var response = await App.requestWithTimeout('/api/games/access?game=' + gameType, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
      if (!data.success) {
        App.showMessage('Failed to check game access. Please try again.', 'error');
        return false;
      }
      if (data.can_play === false) {
        this.showLimitModal(gameType, data);
        return false;
      }
      window.location.href = targetUrl;
      return true;
    } catch (error) {
      console.error('Game access check error:', error);
      App.showMessage('Could not verify game limits. Proceeding to game...', 'warning');
      window.location.href = targetUrl;
      return true;
    }
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

//========== ENHANCED GAME LIMITER WITH AUTO-LOGOUT ==========
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
      if (!data.success) {
        if (data.force_logout || data.action_required === 'logout') {
          this.showForceLogoutModal(gameType, data);
          return false;
        }
        App.showMessage(data.message || 'Failed to check game access', 'error');
        return false;
      }
      if (!data.can_play) {
        this.showLimitReachedModal(gameType, data);
        return false;
      }
      window.location.href = targetUrl;
      return true;
    } catch (error) {
      console.error('Game access check error:', error);
      App.showMessage('Could not verify game limits. Proceeding to game...', 'warning');
      window.location.href = targetUrl;
      return true;
    }
  },

  showForceLogoutModal: function(gameType, data) {
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
    modal.style.zIndex = '10002';
    modal.innerHTML = `
      <div class="force-logout-modal-content">
        <div class="game-limit-icon">🚫</div>
        <h3 class="game-limit-title">Daily Limit Reached</h3>
        <div class="game-limit-message">
          <p class="game-limit-text" style="font-size:1.1rem;line-height:1.6;">
            <strong>You've played ${played}/${max} times today!</strong><br><br>
            Daily limits reset at <strong>${resetTime}</strong>.<br>
            You will now be logged out automatically.
          </p>
          <div class="game-limit-info">
            <i class="fas fa-calendar-day"></i>
            <span>Played Today: ${played}/${max}</span>
          </div>
          <div class="game-limit-info">
            <i class="fas fa-clock"></i>
            <span>Reset Time: ${resetTime}</span>
          </div>
          <div class="game-limit-info" style="color:#ff6b6b;">
            <i class="fas fa-exclamation-triangle"></i>
            <span>Auto-logout in <span id="logout-countdown" class="force-logout-countdown">10</span> seconds</span>
          </div>
        </div>
        <div class="game-limit-buttons">
          <button class="game-limit-btn-ok" onclick="EnhancedGameLimiter.performLogout('${gameType}')">
            <i class="fas fa-sign-out-alt"></i> Logout Now
          </button>
          <button class="game-limit-btn-alternative" onclick="EnhancedGameLimiter.closeModal()">
            <i class="fas fa-home"></i> Return to Dashboard
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    var countdown = 10;
    var countdownEl = document.getElementById('logout-countdown');
    var countdownInterval = setInterval(function() {
      countdown--;
      if (countdownEl) countdownEl.textContent = countdown;
      if (countdown <= 0) {
        clearInterval(countdownInterval);
        EnhancedGameLimiter.performLogout(gameType);
      }
    }, 1000);
    modal.countdownInterval = countdownInterval;
  },

  async performLogout(gameType) {
    try {
      await fetch('/api/games/force-logout/' + gameType, {
        method: 'POST',
        credentials: 'include'
      });
      document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
      this.showLogoutMessage();
      setTimeout(function() {
        window.location.href = '/?reason=daily_limit_reached&game=' + gameType;
      }, 2000);
    } catch (error) {
      console.error('Logout error:', error);
      window.location.href = '/?reason=daily_limit_reached';
    }
  },

  showLogoutMessage: function() {
    var message = document.createElement('div');
    message.className = 'global-message warning';
    message.style.position = 'fixed';
    message.style.top = '50%';
    message.style.left = '50%';
    message.style.transform = 'translate(-50%, -50%)';
    message.style.zIndex = '10003';
    message.style.fontSize = '1.2rem';
    message.innerHTML = `
      <div style="text-align:center;">
        <div style="font-size:3rem;margin-bottom:20px;">🚫</div>
        <h3 style="margin-bottom:15px;">Daily Limit Reached</h3>
        <p>You have been logged out automatically.<br>Please come back tomorrow!</p>
        <p style="font-size:0.9rem;opacity:0.8;">Redirecting to login page...</p>
      </div>
    `;
    document.body.appendChild(message);
    setTimeout(function() { if (message.parentNode) message.remove(); }, 3000);
  },

  closeModal: function() {
    var modal = document.getElementById('force-logout-modal');
    if (modal) {
      if (modal.countdownInterval) clearInterval(modal.countdownInterval);
      modal.remove();
    }
    GameLimiter.closeModal();
    window.location.href = '/';
  },

  showLimitReachedModal: function(gameType, data) {
    GameLimiter.showLimitModal(gameType, data);
  }
};

//========== PROFILE ==========
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
        App.refreshBalance(true);
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
      App.showMessage('Please enter an image URL', 'error');
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
        App.showMessage('Profile picture updated!', 'success');
        Profile.load();
      } else {
        App.showMessage(data.message || 'Failed to update picture', 'error');
      }
    } catch (error) {
      App.showMessage('Network error. Please try again.', 'error');
    }
  }
};

//========== REFERRALS ==========
var Referral = {
  open: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      if (data.success) {
        var unclaimed = data.referrals.unclaimed_bonus;
        var html = `
          <div class="referral-section">
            <h4><i class="fas fa-users"></i> Your Referral Program</h4>
            <p><strong>Your Referral Code:</strong> <code style="font-size:1.2em;background:#8000FF;padding:5px 10px;border-radius:5px;">${data.user.referral_code}</code></p>
            <p>Share this code to earn <strong>₦${CONFIG.REFERRAL_BONUS.toLocaleString()}</strong> per friend!</p>
            <p><strong>Referred Users:</strong> ${data.referrals.count}</p>
            <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
            ${unclaimed > 0
              ? '<button class="btn-primary" onclick="Referral.claimBonuses()" style="margin-top:15px;"><i class="fas fa-gift"></i> Claim ₦' + unclaimed.toLocaleString() + ' Bonus</button>'
              : '<p style="color:#00FF55;margin-top:15px;">All bonuses claimed!</p>'
            }
          </div>
          <div class="referral-section" style="margin-top:20px;">
            <h4><i class="fas fa-share-alt"></i> Share Your Link</h4>
            <div style="background:#151535;padding:10px;border-radius:5px;border:1px solid #8000FF;margin:10px 0;">
              ${window.location.origin}/?ref=${data.user.referral_code}
            </div>
            <button class="btn-secondary" onclick="Referral.copyReferralLink('${data.user.referral_code}')" style="margin-top:10px;">
              <i class="fas fa-copy"></i> Copy Link
            </button>
          </div>
        `;
        document.getElementById('referral-data').innerHTML = html;
        App.showModal('referral-modal');
      }
    } catch (error) {
      console.error('Referral load error:', error);
      App.showMessage('Failed to load referral data', 'error');
    }
  },

  copyReferralLink: function (code) {
    var link = window.location.origin + '/?ref=' + code;
    navigator.clipboard.writeText(link).then(function() {
      App.showMessage('Referral link copied to clipboard!', 'success');
    }).catch(function() {
      var textarea = document.createElement('textarea');
      textarea.value = link;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      App.showMessage('Link copied!', 'success');
    });
  },

  claimBonuses: async function () {
    try {
      var result = await GameManager.safeClaim('/api/referral/claim', {}, 'referral');
      if (!result.success) {
        App.showMessage(result.message, 'error');
        return;
      }
      App.showMessage('Bonuses claimed: ₦' + result.claimed.toLocaleString(), 'success');
      App.updateBalance(result.new_balance);
      Referral.open();
    } catch (error) {
      App.showMessage('Failed to claim bonus. Please try again.', 'error');
    }
  }
};

//========== BANKING ==========
var Banking = {
  banks: [],

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
    App.showModal('withdrawal-modal');
  },

  processWithdrawal: async function () {
    var userRes = await App.requestWithTimeout('/api/user/profile');
    var userData = await userRes.json();
    if (!userData.success) {
      App.showMessage('Session expired. Please log in again.', 'error');
      return;
    }
    var user = userData.user;
    if (!user.withdrawal_pin) {
      App.showMessage('You must set a withdrawal PIN before cashing out.', 'info');
      Settings.setWithdrawalPin();
      return;
    }
    var amount = parseFloat(document.getElementById('withdraw-amount').value);
    var bankCode = document.getElementById('bank-select').value;
    var accountNumber = document.getElementById('account-number').value.trim();
    var accountName = document.getElementById('account-name-manual').value.trim();
    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      App.showMessage('Minimum withdrawal: ₦' + CONFIG.MIN_WITHDRAWAL.toLocaleString(), 'error');
      return;
    }
    var combinedBalance = parseFloat(user.balance);
    if (amount > combinedBalance) {
      App.showMessage('Insufficient balance. Total available: ₦' + combinedBalance.toLocaleString(undefined, { minimumFractionDigits: 2 }), 'error');
      return;
    }
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      App.showMessage('Invalid bank details.', 'error');
      return;
    }
    var pin = prompt('Enter your 4-6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required.', 'error');
      return;
    }
    var msgEl = document.getElementById('withdrawal-message');
    msgEl.textContent = 'Processing withdrawal...';
    msgEl.className = 'message info';
    try {
      var result = await GameManager.safeClaim('/api/banking/withdraw', {
        amount: amount, bank_code: bankCode, account_number: accountNumber,
        account_name: accountName, pin: pin
      }, 'withdrawal');
      msgEl.textContent = result.message;
      msgEl.className = result.success ? 'message success' : 'message error';
      if (result.success) {
        App.updateBalance(result.new_balance);
        App.showMessage('Withdrawal submitted for manual review!', 'success');
        await TodayEarnings.refresh();
        setTimeout(function() { App.closeModal('withdrawal-modal'); }, 2000);
      }
    } catch (error) {
      msgEl.textContent = 'Network error. Please try again.';
      msgEl.className = 'message error';
    }
  }
};

//========== ACHIEVEMENTS ==========
var Achievements = {
  open: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/achievements');
      var data = await response.json();
      if (data.success) {
        this.achievementsData = data;
        window.location.href = 'achievements.html';
      } else {
        App.showMessage('Failed to load achievements', 'error');
      }
    } catch (error) {
      console.error('Achievements error:', error);
      App.showMessage('Failed to load achievements', 'error');
    }
  },

  claimAllRewards: async function () {
    try {
      var result = await GameManager.safeClaim('/api/achievements/claim', {}, 'achievements');
      if (result.success) {
        App.showMessage('Achievement rewards claimed! New balance: ₦' + result.new_balance.toLocaleString(), 'success');
        App.updateBalance(result.new_balance);
        await TodayEarnings.refresh();
      } else {
        App.showMessage(result.message || 'Failed to claim rewards', 'error');
      }
    } catch (error) {
      App.showMessage('Network error. Please try again.', 'error');
    }
  }
};

//========== GAMES ==========
var Games = {
  openSnake: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'); },
  openCoinFlip: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'); },
  openPlinko: function() { return EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'); },

  reportSnake: async function (apples) {
    return await GameManager.safeClaim('/api/games/snake/report', { apples_eaten: apples }, 'snake');
  },

  reportCoinFlip: async function (bet, won) {
    return await GameManager.safeClaim('/api/games/coinflip/report', { bet: bet, won: won }, 'coinflip');
  },

  reportPlinko: async function (bet, multiplier) {
    return await GameManager.safeClaim('/api/games/plinko/report', { bet: bet, multiplier: multiplier }, 'plinko');
  },

  reportSpin: async function (_unused) {
    return await GameManager.safeClaim('/api/spin/execute', {}, 'spin');
  },

  openTikTok: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/games/check-limit-with-logout/tiktok', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      var data = await response.json();
      if (!data.success) {
        if (data.force_logout || data.action_required === 'logout') {
          EnhancedGameLimiter.showForceLogoutModal('tiktok', data);
          return;
        }
      }
      if (!data.can_play) {
        EnhancedGameLimiter.showLimitReachedModal('tiktok', data);
        return;
      }
    } catch (error) {
      console.error('TikTok access check error:', error);
    }

    var msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = '';
    msgEl.className = 'message';
    try {
      var response = await App.requestWithTimeout('/api/games/tiktok/daily');
      var data = await response.json();
      if (!data.success) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">' + (data.message || 'No TikTok task available today.') + '</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (data.already_claimed) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff9800;">You have already claimed today\'s TikTok reward!</p>';
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      if (!data.task || !data.task.tiktok_link) {
        document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">Admin hasn\'t set a TikTok task for today.</p>';
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
          <p class="small-text">Search <strong>@${username}</strong> on TikTok and follow the account</p>
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
      document.getElementById('tiktok-instructions').innerHTML = '<p style="color:#ff5252;">Failed to load TikTok task. Please try again.</p>';
      document.querySelector('.action-buttons').style.display = 'none';
      App.showModal('tiktok-modal');
    }
  },

  verifyTikTokFollow: async function () {
    var msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = 'Claiming reward...';
    msgEl.className = 'message';
    try {
      var result = await GameManager.safeClaim('/api/games/tiktok/follow-daily', {}, 'tiktok');
      if (result.success) {
        App.updateBalance(result.new_balance);
        msgEl.textContent = 'Success! ₦' + result.reward + ' added to your balance.';
        msgEl.className = 'message success';
        await TodayEarnings.refresh();
        setTimeout(function() {
          App.closeModal('tiktok-modal');
          App.showMessage('TikTok reward claimed: ₦' + result.reward, 'success');
        }, 2000);
      } else {
        msgEl.textContent = result.message || 'Failed to claim reward.';
        msgEl.className = 'message error';
      }
    } catch (error) {
      msgEl.textContent = error.message || 'Network error';
      msgEl.className = 'message error';
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
      if (!data.success) {
        if (data.force_logout || data.action_required === 'logout') {
          EnhancedGameLimiter.showForceLogoutModal('spin', data);
          return;
        }
      }
      if (!data.can_play) {
        EnhancedGameLimiter.showLimitReachedModal('spin', data);
        return;
      }
    } catch (error) {
      console.error('Spin access check error:', error);
    }
    var wheel = document.getElementById('wheel');
    var button = document.getElementById('spin-button');
    var msgEl = document.getElementById('spin-message');
    var resultEl = document.getElementById('spin-result');
    if (wheel) {
      wheel.style.transition = 'none';
      wheel.style.transform = 'rotate(0deg)';
      void wheel.offsetWidth;
    }
    if (button) {
      button.disabled = false;
      button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
    }
    if (msgEl) {
      msgEl.textContent = '';
      msgEl.className = 'message';
    }
    if (resultEl) {
      resultEl.classList.add('hidden');
    }
    App.showModal('spin-modal');
    setTimeout(function() { initSpinWheel(); }, 150);
  },

  spinWheel: async function() {
    var button = document.getElementById('spin-button');
    var wheel = document.getElementById('wheel');
    var msgEl = document.getElementById('spin-message');
    if (!button || !wheel || button.disabled) return;
    button.disabled = true;
    GameManager.setButtonLoading('spin-button', true);
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    if (msgEl) {
      msgEl.textContent = '';
      msgEl.className = 'message';
    }
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    var svgEl = document.getElementById('wheel-svg');
    if (svgEl) {
      svgEl.style.transition = 'none';
      svgEl.style.transform = 'rotate(0deg)';
    }
    void wheel.offsetWidth;
    try {
      var result = await this.reportSpin(null);
      if (!result.success) {
        button.disabled = false;
        GameManager.setButtonLoading('spin-button', false);
        button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        if (msgEl) {
          msgEl.textContent = result.message || 'Spin failed. Please try again.';
          msgEl.className = 'message error';
        }
        App.showMessage(result.message || 'Spin failed', 'error');
        return;
      }
      var reward = result.reward;
      var prizeIndex = result.prize_index !== undefined ? result.prize_index : 5;
      var segmentMidpointFromTop = prizeIndex * 60 + 30;
      var angleToPointer = (360 - segmentMidpointFromTop) % 360;
      var fullSpins = 6 + Math.floor(Math.random() * 3);
      var totalRotation = (fullSpins * 360) + angleToPointer;
      var svgWheel = document.getElementById('wheel-svg');
      var spinTarget = svgWheel || wheel;
      spinTarget.style.transition = 'none';
      spinTarget.style.transform = 'rotate(0deg)';
      void spinTarget.offsetWidth;
      spinTarget.style.transition = 'transform 5s cubic-bezier(0.17, 0.67, 0.05, 1.0)';
      spinTarget.style.transform = 'rotate(' + totalRotation + 'deg)';
      setTimeout(function() {
        GameManager.setButtonLoading('spin-button', false);
        App.updateBalance(result.new_balance);
        var resultMsg = reward > 0
          ? '🎉 Congratulations! You won ₦' + reward.toLocaleString() + '!'
          : 'Better luck tomorrow!';
        if (msgEl) {
          msgEl.textContent = resultMsg;
          msgEl.className = reward > 0 ? 'message success' : 'message warning';
        }
        var resultEl = document.getElementById('spin-result');
        if (resultEl) {
          resultEl.innerHTML = '<p style="font-size:1.1rem;font-weight:bold;">' + resultMsg + '</p>';
          resultEl.classList.remove('hidden');
        }
        button.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
        if (reward > 0) {
          App.showMessage('You won ₦' + reward.toLocaleString() + '!', 'success');
          TodayEarnings.refresh();
        }
      }, 5200);
    } catch (err) {
      console.error('Spin error:', err);
      button.disabled = false;
      GameManager.setButtonLoading('spin-button', false);
      if (msgEl) {
        msgEl.textContent = 'Network error. Please try again.';
        msgEl.className = 'message error';
      }
      button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
      App.showMessage('Network error during spin', 'error');
    }
  }
};

//========== SETTINGS ==========
var Settings = {
  open: async function () {
    if (!App.currentUser) return;
    try {
      var response = await App.requestWithTimeout('/api/user/profile');
      var data = await response.json();
      if (!data.success) {
        App.showMessage('Failed to load settings', 'error');
        return;
      }
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
        var socialResponse = await App.requestWithTimeout('/api/admin/settings');
        var socialData = await socialResponse.json();
        if (socialData.success) {
          var s = socialData.settings;
          html += '<div class="settings-section"><h4><i class="fas fa-users"></i> Join Our Community</h4>';
          if (s.whatsapp_link) html += '<a href="' + s.whatsapp_link + '" target="_blank" class="social-link"><i class="fab fa-whatsapp"></i> WhatsApp Group</a><br>';
          if (s.telegram_link) html += '<a href="' + s.telegram_link + '" target="_blank" class="social-link"><i class="fab fa-telegram"></i> Telegram Group</a><br>';
          if (s.facebook_link) html += '<a href="' + s.facebook_link + '" target="_blank" class="social-link"><i class="fab fa-facebook"></i> Facebook Group</a><br>';
          if (!(s.whatsapp_link || s.telegram_link || s.facebook_link)) {
            html += '<p class="small-text">No social links configured yet</p>';
          }
          html += '</div>';
        }
      } catch (e) {
        console.error('Social links error:', e);
      }
      if (user.is_admin) {
        html += `
          <div class="settings-section">
            <h4><i class="fas fa-shield-alt"></i> Admin Actions</h4>
            <button class="btn-primary" onclick="Settings.changePassword()" style="width:100%;">
              <i class="fas fa-key"></i> Change Password
            </button>
          </div>
        `;
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
            <i class="fas fa-moon"></i> ${document.body.classList.contains('dark-mode') ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
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
      document.getElementById('settings-data').innerHTML = html;
      App.showModal('settings-modal');
    } catch (error) {
      console.error('Settings error:', error);
      App.showMessage('Failed to load settings', 'error');
    }
  },

  setWithdrawalPin: async function (isChange) {
    if (isChange === undefined) isChange = false;
    var currentPin = '';
    if (isChange) {
      currentPin = prompt('Enter your CURRENT 4-6 digit Withdrawal PIN:');
      if (!currentPin) return;
      if (!/^\d{4,6}$/.test(currentPin)) {
        App.showMessage('Current PIN must be 4 to 6 digits.', 'error');
        return;
      }
      try {
        var response = await App.requestWithTimeout('/api/user/verify-withdrawal-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: currentPin }),
          credentials: 'include'
        });
        var verifyData = await response.json();
        if (!verifyData.success) {
          App.showMessage('Incorrect current PIN.', 'error');
          return;
        }
      } catch (error) {
        App.showMessage('Verification failed. Please try again.', 'error');
        return;
      }
    }
    var newPin = prompt('Enter your NEW 4-6 digit Withdrawal PIN:');
    if (!newPin || !/^\d{4,6}$/.test(newPin)) {
      App.showMessage('New PIN must be 4 to 6 digits.', 'error');
      return;
    }
    var confirmPin = prompt('Confirm your new PIN:');
    if (newPin !== confirmPin) {
      App.showMessage('PINs do not match.', 'error');
      return;
    }
    try {
      var result = await GameManager.safeClaim('/api/user/set-withdrawal-pin', { pin: newPin }, 'setpin');
      if (result.success) {
        App.showMessage('PIN ' + (isChange ? 'changed' : 'set') + ' successfully!', 'success');
        App.closeModal('settings-modal');
      } else {
        App.showMessage(result.message, 'error');
      }
    } catch (error) {
      App.showMessage('Failed to set PIN. Please try again.', 'error');
    }
  },

  changeWithdrawalPin: function () {
    this.setWithdrawalPin(true);
  },

  changePassword: async function () {
    var oldPass = prompt("Enter your current password:");
    if (!oldPass) return;
    var newPass = prompt("Enter a new password (min 6 characters):");
    if (!newPass || newPass.length < 6) {
      App.showMessage("Password must be at least 6 characters.", "error");
      return;
    }
    var confirmPass = prompt("Confirm your new password:");
    if (newPass !== confirmPass) {
      App.showMessage("Passwords do not match.", "error");
      return;
    }
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
        App.showMessage("Password changed successfully!", "success");
        App.closeModal('settings-modal');
        if (isAdmin && data.message && data.message.indexOf('login again') !== -1) {
          setTimeout(function() {
            if (confirm("Admin password changed. Logout and login again?")) {
              Settings.logout();
            }
          }, 1000);
        }
      } else {
        App.showMessage(data.message || "Failed to change password", "error");
      }
    } catch (error) {
      App.showMessage("Network error. Please try again.", "error");
    }
  },

  logout: async function () {
    if (!confirm('Are you sure you want to logout?')) return;
    try {
      await App.requestWithTimeout('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) {
      console.warn('Logout endpoint failed');
    }
    document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
      (window.location.protocol === 'https:' ? '; secure' : '');
    window.location.href = '/';
  }
};

//========== SPIN WHEEL ==========
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

//========== DOM READY ==========
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

  // Auto-fill coupon from URL parameter
  var urlParams = new URLSearchParams(window.location.search);
  var coupon = urlParams.get('coupon');
  var tab = urlParams.get('tab');

  if (coupon) {
    document.getElementById('reg-coupon').value = coupon;
    if (tab === 'register') {
      document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
      document.querySelector('[data-tab="register"]').classList.add('active');
      document.querySelectorAll('.auth-form').forEach(function(f) { f.classList.remove('active'); });
      document.getElementById('register-form').classList.add('active');
    }
    setTimeout(function() {
      if (typeof App !== 'undefined' && App.showMessage) {
        App.showMessage('Coupon code loaded! Complete your registration.', 'success', 5000);
      }
    }, 1000);
  }

  // Check payment status on return
  var ref = urlParams.get('ref');
  if (ref) {
    setTimeout(async function() {
      var result = await PaystackPayment.checkStatus(ref);
      if (result.success && result.status === 'COMPLETED') {
        App.showMessage('Payment successful! Coupon: ' + (result.coupon_code || 'Check your email'), 'success');
        window.history.replaceState({}, document.title, window.location.pathname);
      } else if (result.success && result.status === 'PENDING') {
        App.showMessage('Payment is still processing. Check your email in a few minutes.', 'info');
      }
    }, 2000);
  }

  setTimeout(function() {
    var snakeCard = document.querySelector('.activity-card .icon.snake')?.closest('.activity-card');
    var coinflipCard = document.querySelector('.activity-card .icon.coin')?.closest('.activity-card');
    var plinkoCard = document.querySelector('.activity-card .icon.plinko')?.closest('.activity-card');
    if (snakeCard) snakeCard.onclick = function() { EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'); };
    if (coinflipCard) coinflipCard.onclick = function() { EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'); };
    if (plinkoCard) plinkoCard.onclick = function() { EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'); };
  }, 1000);

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

  // Restore scroll position
  var scrollPos = sessionStorage.getItem('flexia_scroll_position');
  if (scrollPos) {
    setTimeout(function() {
      window.scrollTo(0, parseInt(scrollPos));
      sessionStorage.removeItem('flexia_scroll_position');
    }, 300);
  }
});

//========== GLOBAL EXPORTS ==========
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
window.TodayEarnings = TodayEarnings;
window.PaystackPayment = PaystackPayment;
window.SessionManager = SessionManager;
window.checkWithdrawalDay = checkWithdrawalDay;
window.closeWithdrawalDayModal = closeWithdrawalDayModal;
window.openSnakeGame = function() { EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'); };
window.openCoinFlipGame = function() { EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'); };
window.openPlinkoGame = function() { EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'); };
window.openTikTokGame = Games.openTikTok;
window.openSpinWheelGame = Games.openSpinWheel;
window.checkDailyLimit = GameManager.checkDailyLimit;
window.updateBalance = App.updateBalance;
window.showMessage = App.showMessage;
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

console.log('FLEXIA Script v17.0 - COMPLETE VERSION LOADED');
