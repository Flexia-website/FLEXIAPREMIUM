// script.js - FLEXIA Frontend Logic v12.0 - WITH LOGIN/LOGOUT ANIMATIONS
// ✅ ALL ANIMATIONS WORKING ✅ PERFECTLY SIZED SPIN WHEEL ✅

//========== CONFIGURATION ========
const CONFIG = {
  MIN_WITHDRAWAL: 100000,
  REFERRAL_BONUS: 7500,
  TIKTOK_REWARD: 150,
  SNAKE_REWARD: 200,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100,
  CLAIM_COOLDOWN: 1000,
  ANIMATION_DURATION: 600 // Animation duration in ms
};

//========== CORE APP ==========
const App = {
  currentUser: null,
  balanceVisible: true,
  lastBalanceUpdate: 0,
  isLoading: false,
  
  init: async function () {
    await this.checkAuth();
    if (document.getElementById('app-screen')) {
      await Profile.load();
      await Banking.loadBanks();
      this.setupTheme();
      
      // Initialize spin wheel visuals
      setTimeout(() => {
        if (window.Games && typeof Games.enhanceSpinVisuals === 'function') {
          Games.enhanceSpinVisuals();
        }
      }, 1000);
    }
  },
  
  checkAuth: async function () {
    this.showLoading(true);
    try {
      const res = await fetch('/api/user/profile');
      const data = await res.json();
      if (data.success) {
        this.currentUser = data.user;
        this.showAppScreen();
        this.refreshBalance();
        document.getElementById('welcome-text').textContent = `Welcome, ${data.user.username}!`;
        document.getElementById('user-avatar').textContent = data.user.username.charAt(0).toUpperCase();
        if (data.user.ui_theme === 'dark') {
          document.body.classList.add('dark-mode');
        }
      } else {
        this.showAuthScreen();
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      this.showAuthScreen();
    } finally {
      this.showLoading(false);
    }
  },
  
  showAppScreen: function () {
    const authScreen = document.getElementById('auth-screen');
    const appScreen = document.getElementById('app-screen');
    
    if (!authScreen || !appScreen) return;
    
    // Add leaving animation to auth screen
    authScreen.classList.remove('hidden');
    authScreen.classList.add('leaving');
    
    // Show app screen with entering animation
    appScreen.classList.remove('hidden');
    appScreen.classList.add('entering');
    
    // After animation completes, hide auth screen
    setTimeout(() => {
      authScreen.classList.add('hidden');
      authScreen.classList.remove('leaving');
      appScreen.classList.remove('entering');
      
      // Refresh balance after screen transition
      this.refreshBalance(true);
    }, CONFIG.ANIMATION_DURATION);
  },
  
  showAuthScreen: function () {
    const authScreen = document.getElementById('auth-screen');
    const appScreen = document.getElementById('app-screen');
    
    if (!authScreen || !appScreen) return;
    
    // Add leaving animation to app screen
    appScreen.classList.remove('hidden');
    appScreen.classList.add('leaving');
    
    // Show auth screen with entering animation
    authScreen.classList.remove('hidden');
    authScreen.classList.add('entering');
    
    // After animation completes, hide app screen
    setTimeout(() => {
      appScreen.classList.add('hidden');
      appScreen.classList.remove('leaving');
      authScreen.classList.remove('entering');
      
      // Clear any remaining messages
      this.clearAuthMessages();
    }, CONFIG.ANIMATION_DURATION);
  },
  
  clearAuthMessages: function() {
    document.getElementById('login-message').textContent = '';
    document.getElementById('login-message').className = 'message';
    document.getElementById('register-message').textContent = '';
    document.getElementById('register-message').className = 'message';
  },
  
  refreshBalance: function (force = false) {
    if (!this.currentUser) return;
    
    const now = Date.now();
    if (!force && (now - this.lastBalanceUpdate) < 5000) {
      return;
    }
    
    const display = document.getElementById('balance-display');
    if (display) {
      display.textContent = this.currentUser.balance.toLocaleString(undefined, { 
        minimumFractionDigits: 2,
        maximumFractionDigits: 2 
      });
    }
    
    const withdrawBalance = document.getElementById('withdraw-balance');
    if (withdrawBalance) {
      withdrawBalance.textContent = `₦${this.currentUser.balance.toLocaleString(undefined, { 
        minimumFractionDigits: 2,
        maximumFractionDigits: 2 
      })}`;
    }
    
    const minEl = document.getElementById('withdraw-min');
    if (minEl) minEl.textContent = `₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}`;
    
    this.lastBalanceUpdate = now;
  },
  
  updateBalance: function (newBalance) {
    if (this.currentUser) {
      this.currentUser.balance = newBalance;
      this.refreshBalance(true);
    }
  },
  
  toggleBalance: function () {
    this.balanceVisible = !this.balanceVisible;
    const display = document.getElementById('balance-display');
    if (display) {
      display.textContent = this.balanceVisible
        ? this.currentUser.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })
        : '••••••••';
    }
  },
  
  showModal: function (modalId) {
    document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
    document.getElementById(modalId).classList.remove('hidden');
    
    // Initialize particles when spin modal opens
    if (modalId === 'spin-modal' && window.Games && window.Games.createParticles) {
      setTimeout(() => Games.createParticles(), 100);
    }
  },
  
  closeModal: function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('hidden');
    }
  },
  
  showMessage: function (text, type = 'info', duration = 5000) {
    const messageEl = document.createElement('div');
    messageEl.className = `global-message ${type}`;
    messageEl.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      padding: 15px 25px;
      background: ${type === 'success' ? 'rgba(0, 255, 85, 0.9)' : 
                   type === 'error' ? 'rgba(255, 0, 85, 0.9)' : 
                   'rgba(0, 204, 255, 0.9)'};
      color: white;
      border-radius: 8px;
      font-weight: 600;
      z-index: 9999;
      box-shadow: 0 4px 15px rgba(0,0,0,0.3);
      min-width: 300px;
      text-align: center;
      animation: slideIn 0.3s ease-out;
    `;
    messageEl.textContent = text;
    document.body.appendChild(messageEl);
    
    setTimeout(() => {
      messageEl.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => {
        if (messageEl.parentNode) {
          messageEl.remove();
        }
      }, 300);
    }, duration);
  },
  
  showLoading: function (show) {
    this.isLoading = show;
    
    // Create or get loading overlay
    let loadingOverlay = document.getElementById('loading-overlay');
    
    if (show) {
      if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = `
          <div class="loading-spinner"></div>
          <div class="loading-text">LOADING...</div>
        `;
        document.body.appendChild(loadingOverlay);
      } else {
        loadingOverlay.classList.remove('hidden');
      }
    } else if (loadingOverlay) {
      loadingOverlay.classList.add('hidden');
      // Remove after animation
      setTimeout(() => {
        if (loadingOverlay && loadingOverlay.parentNode) {
          loadingOverlay.remove();
        }
      }, 300);
    }
    
    // Disable/enable buttons during loading
    document.querySelectorAll('button').forEach(btn => {
      if (show) {
        btn.disabled = true;
      } else {
        btn.disabled = false;
      }
    });
  },
  
  toggleTheme: function () {
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
  
  setupTheme: function () {
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
      document.body.classList.add('dark-mode');
    }
  }
};

// Add CSS animations for messages
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }
  @keyframes slideOut {
    from { opacity: 1; transform: translateX(-50%) translateY(0); }
    to { opacity: 0; transform: translateX(-50%) translateY(-20px); }
  }
`;
document.head.appendChild(style);

//========== GAME MANAGER ==========
const GameManager = {
  lastClaimTime: 0,
  isClaiming: false,
  
  canClaimNow() {
    const now = Date.now();
    return (now - this.lastClaimTime) >= CONFIG.CLAIM_COOLDOWN;
  },
  
  async checkDailyLimit(gameType) {
    try {
      const response = await fetch(`/api/games/limit-check?game=${gameType}`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      if (!response.ok) {
        return { can_play: true, remaining: 999 };
      }
      
      return await response.json();
    } catch (error) {
      return { can_play: true, remaining: 999 };
    }
  }
};

//========== AUTHENTICATION =========
const Auth = {
  isLoggingIn: false,
  isRegistering: false,
  
  // Password toggle function
  togglePasswordVisibility: function(fieldId) {
    const passwordField = document.getElementById(fieldId);
    const toggleBtn = passwordField.nextElementSibling;
    
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
  
  // Setup password toggles
  initPasswordToggles: function() {
    // Setup login password toggle
    const loginPasswordField = document.getElementById('login-password');
    if (loginPasswordField && !loginPasswordField.parentNode?.classList?.contains('password-container')) {
      const loginContainer = document.createElement('div');
      loginContainer.className = 'password-container';
      
      // Move the input into the container
      loginPasswordField.parentNode.insertBefore(loginContainer, loginPasswordField);
      loginContainer.appendChild(loginPasswordField);
      
      // Create toggle button
      const loginToggle = document.createElement('button');
      loginToggle.type = 'button';
      loginToggle.className = 'password-toggle';
      loginToggle.innerHTML = '<i class="fas fa-eye"></i>';
      loginToggle.setAttribute('title', 'Show password');
      loginToggle.setAttribute('aria-label', 'Toggle password visibility');
      loginToggle.onclick = () => this.togglePasswordVisibility('login-password');
      loginContainer.appendChild(loginToggle);
    }
    
    // Setup registration password toggle
    const regPasswordField = document.getElementById('reg-password');
    if (regPasswordField && !regPasswordField.parentNode?.classList?.contains('password-container')) {
      const regContainer = document.createElement('div');
      regContainer.className = 'password-container';
      
      // Move the input into the container
      regPasswordField.parentNode.insertBefore(regContainer, regPasswordField);
      regContainer.appendChild(regPasswordField);
      
      // Create toggle button
      const regToggle = document.createElement('button');
      regToggle.type = 'button';
      regToggle.className = 'password-toggle';
      regToggle.innerHTML = '<i class="fas fa-eye"></i>';
      regToggle.setAttribute('title', 'Show password');
      regToggle.setAttribute('aria-label', 'Toggle password visibility');
      regToggle.onclick = () => this.togglePasswordVisibility('reg-password');
      regContainer.appendChild(regToggle);
    }
  },
  
  login: async function () {
    if (this.isLoggingIn) return;
    
    const identifier = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');
    const loginBtn = document.querySelector('#login-form .btn-primary');
    const authContainer = document.querySelector('.auth-container');
    
    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
      return;
    }
    
    this.isLoggingIn = true;
    
    // Show loading state
    if (loginBtn) {
      loginBtn.classList.add('loading');
      loginBtn.disabled = true;
    }
    
    if (authContainer) {
      authContainer.classList.add('logging-in');
    }
    
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, password })
      });
      
      const data = await res.json();
      messageEl.textContent = data.message;
      messageEl.className = data.success ? 'message success' : 'message error';
      
      if (data.success) {
        App.currentUser = data.user;
        
        // Small delay for success message to show
        setTimeout(() => {
          App.showAppScreen();
          App.refreshBalance();
          document.getElementById('login-username').value = '';
          document.getElementById('login-password').value = '';
          
          // Reset password visibility after login
          const loginPassword = document.getElementById('login-password');
          if (loginPassword.type === 'text') {
            loginPassword.type = 'password';
            const toggleBtn = loginPassword.nextElementSibling;
            if (toggleBtn) {
              toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
              toggleBtn.setAttribute('title', 'Show password');
            }
          }
        }, 1000);
      }
    } catch (error) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
    } finally {
      this.isLoggingIn = false;
      
      // Remove loading state
      if (loginBtn) {
        loginBtn.classList.remove('loading');
        loginBtn.disabled = false;
      }
      
      if (authContainer) {
        authContainer.classList.remove('logging-in');
      }
    }
  },
  
  register: async function () {
    if (this.isRegistering) return;
    
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    const coupon = document.getElementById('reg-coupon').value.trim().toUpperCase();
    const referral = document.getElementById('reg-referral').value.trim();
    const contact = document.getElementById('reg-contact')?.value.trim() || '';
    const messageEl = document.getElementById('register-message');
    const registerBtn = document.querySelector('#register-form .btn-primary');
    const authContainer = document.querySelector('.auth-container');
    
    if (!username || !password || !coupon) {
      messageEl.textContent = 'All fields required';
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
    
    this.isRegistering = true;
    
    // Show loading state
    if (registerBtn) {
      registerBtn.classList.add('loading');
      registerBtn.disabled = true;
    }
    
    if (authContainer) {
      authContainer.classList.add('logging-in');
    }
    
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, coupon_code: coupon, referral_code: referral, contact })
      });
      
      const data = await res.json();
      messageEl.textContent = data.message;
      messageEl.className = data.success ? 'message success' : 'message error';
      
      if (data.success) {
        // Reset password visibility after registration
        const regPassword = document.getElementById('reg-password');
        if (regPassword.type === 'text') {
          regPassword.type = 'password';
          const toggleBtn = regPassword.nextElementSibling;
          if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.setAttribute('title', 'Show password');
          }
        }
        
        // Switch to login tab after short delay
        setTimeout(() => {
          document.querySelector('.tab[data-tab="login"]').click();
          document.getElementById('login-username').value = username;
          document.getElementById('login-password').value = password;
        }, 1500);
      }
    } catch (error) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
    } finally {
      this.isRegistering = false;
      
      // Remove loading state
      if (registerBtn) {
        registerBtn.classList.remove('loading');
        registerBtn.disabled = false;
      }
      
      if (authContainer) {
        authContainer.classList.remove('logging-in');
      }
    }
  },
  
  buyCoupon: async function () {
    try {
      const res = await fetch('/api/whatsapp/numbers');
      const data = await res.json();
      const number = (data.success && data.numbers && data.numbers[0]) ? data.numbers[0].number.trim() : '2348160881049';
      window.open(`https://wa.me/${number}`, '_blank');
    } catch (error) {
      window.open('https://wa.me/2348160881049', '_blank');
    }
  }
};

//========== PROFILE =========
const Profile = {
  open: async function () {
    if (!App.currentUser) return;
    await this.load();
    App.showModal('profile-modal');
  },
  
  load: async function () {
    try {
      const res = await fetch('/api/user/profile');
      const data = await res.json();
      if (data.success) {
        App.currentUser = data.user;
        App.refreshBalance(true);
        
        const stats = data.user.game_stats || {};
        let html = `
          <div class="profile-info">
            <div class="profile-item">
              <span class="label"><i class="fas fa-user"></i> Username</span>
              <span class="value">${data.user.username}</span>
            </div>
            <div class="profile-item">
              <span class="label"><i class="fas fa-wallet"></i> Balance</span>
              <span class="value">₦${data.user.balance.toLocaleString()}</span>
            </div>
            <div class="profile-item">
              <span class="label"><i class="fas fa-ticket-alt"></i> Referral Code</span>
              <span class="value">${data.user.referral_code}</span>
            </div>
            <div class="profile-item">
              <span class="label"><i class="fas fa-calendar"></i> Joined</span>
              <span class="value">${new Date(data.user.created_at).toLocaleDateString()}</span>
            </div>
          </div>
          
          <div class="profile-section">
            <h4><i class="fas fa-chart-line"></i> Game Stats</h4>
            <div class="profile-info">
              <div class="profile-item">
                <span class="label">Snake High Score</span>
                <span class="value">${stats.snake?.high_score || 0}</span>
              </div>
              <div class="profile-item">
                <span class="label">Coin Flip Wins</span>
                <span class="value">${stats.coin_flip?.wins || 0}</span>
              </div>
              <div class="profile-item">
                <span class="label">Plinko Total Wins</span>
                <span class="value">${stats.plinko?.total_wins || 0}</span>
              </div>
            </div>
          </div>
          
          <div class="profile-section">
            <h4><i class="fas fa-image"></i> Profile Picture</h4>
            <input type="text" id="profile-pic-url" placeholder="Enter image URL" 
                   style="width:100%;padding:8px;margin:5px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:4px;">
            <button class="btn-primary" onclick="Profile.setProfilePicture()" 
                    style="margin-top:10px;">
              <i class="fas fa-upload"></i> Update Picture
            </button>
        `;
        
        if (data.user.profile_picture) {
          html += `
            <div style="margin-top:15px;text-align:center;">
              <img src="${data.user.profile_picture}" class="profile-pic-preview">
            </div>
          `;
        }
        
        document.getElementById('profile-data').innerHTML = html;
      }
    } catch (err) {
      console.error('Failed to load profile', err);
      document.getElementById('profile-data').innerHTML = 
        '<p class="error">Failed to load profile. Please try again.</p>';
    }
  },
  
  setProfilePicture: async function () {
    const url = document.getElementById('profile-pic-url').value.trim();
    if (!url) {
      App.showMessage('Please enter an image URL', 'error');
      return;
    }
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/user/set-profile-picture', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picture_url: url })
      });
      
      const data = await res.json();
      if (data.success) {
        App.showMessage('Profile picture updated!', 'success');
        Profile.load();
      } else {
        App.showMessage(data.message || 'Failed to update picture', 'error');
      }
    } catch (error) {
      App.showMessage('Network error. Please try again.', 'error');
    } finally {
      App.showLoading(false);
    }
  }
};

//========== REFERRALS ========
const Referral = {
  open: async function () {
    if (!App.currentUser) return;
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/user/profile');
      const data = await res.json();
      
      if (data.success) {
        const unclaimed = data.referrals.unclaimed_bonus;
        const html = `
          <div class="referral-section">
            <h4><i class="fas fa-users"></i> Your Referral Program</h4>
            <p><strong>Your Referral Code:</strong> <code style="font-size:1.2em;background:#8000FF;padding:5px 10px;border-radius:5px;">${data.user.referral_code}</code></p>
            <p>Share this code to earn <strong>₦${CONFIG.REFERRAL_BONUS.toLocaleString()}</strong> per friend!</p>
            <p><strong>Referred Users:</strong> ${data.referrals.count}</p>
            <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
            
            ${unclaimed > 0
              ? `<button class="btn-primary" onclick="Referral.claimBonuses()" style="margin-top:15px;">
                   <i class="fas fa-gift"></i> Claim ₦${unclaimed.toLocaleString()} Bonus
                 </button>`
              : '<p style="color:#00FF55;margin-top:15px;">All bonuses claimed! 🎉</p>'
            }
          </div>
          
          <div class="referral-section" style="margin-top:20px;">
            <h4><i class="fas fa-share-alt"></i> Share Your Link</h4>
            <div style="background:#151535;padding:10px;border-radius:5px;border:1px solid #8000FF;margin:10px 0;">
              ${window.location.origin}/?ref=${data.user.referral_code}
            </div>
            <button class="btn-secondary" onclick="Referral.copyReferralLink('${data.user.referral_code}')" 
                    style="margin-top:10px;">
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
    } finally {
      App.showLoading(false);
    }
  },
  
  copyReferralLink: function (code) {
    const link = `${window.location.origin}/?ref=${code}`;
    navigator.clipboard.writeText(link).then(() => {
      App.showMessage('Referral link copied to clipboard!', 'success');
    }).catch(() => {
      const textarea = document.createElement('textarea');
      textarea.value = link;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      App.showMessage('Link copied!', 'success');
    });
  },
  
  claimBonuses: async function () {
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/referral/claim', {
        method: 'POST',
        credentials: 'include'
      });
      
      const data = await res.json();
      if (!data.success) {
        App.showMessage(data.message, 'error');
        return;
      }
      
      App.showMessage(`✅ ₦${data.claimed.toLocaleString()} referral bonus claimed!`, 'success');
      App.updateBalance(data.new_balance);
      Referral.open();
    } catch (error) {
      App.showMessage('Failed to claim bonus. Please try again.', 'error');
    } finally {
      App.showLoading(false);
    }
  }
};

//========== BANKING & WITHDRAWALS =========
const Banking = {
  banks: [],
  
  async loadBanks() {
    try {
      const res = await fetch('/api/banking/banks');
      const data = await res.json();
      if (data.success) {
        this.banks = data.banks;
        const select = document.getElementById('bank-select');
        if (select) {
          select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
          data.banks.forEach(bank => {
            const opt = document.createElement('option');
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
  
  loadFallbackBanks() {
    const fallbackBanks = [
      {code: "057", name: "Zenith Bank Plc"},
      {code: "058", name: "GTBank"},
      {code: "044", name: "Access Bank"},
      {code: "033", name: "UBA"},
      {code: "011", name: "First Bank"},
      {code: "070", name: "Fidelity Bank"},
      {code: "050", name: "Ecobank"},
      {code: "039", name: "Stanbic IBTC"},
      {code: "214", name: "FCMB"},
      {code: "232", name: "Sterling Bank"},
      {code: "032", name: "Union Bank"},
      {code: "035", name: "Wema Bank"},
      {code: "082", name: "Keystone Bank"},
      {code: "215", name: "Unity Bank"},
      {code: "076", name: "Polaris Bank"},
      {code: "565", name: "OPay"},
      {code: "100", name: "PalmPay"},
      {code: "50211", name: "Kuda Bank"},
      {code: "566", name: "VBank"},
      {code: "035A", name: "ALAT by Wema"}
    ];
    
    this.banks = fallbackBanks;
    const select = document.getElementById('bank-select');
    if (select) {
      select.innerHTML = '<option value="" disabled selected>Select Bank</option>';
      fallbackBanks.forEach(bank => {
        const opt = document.createElement('option');
        opt.value = bank.code;
        opt.textContent = bank.name;
        select.appendChild(opt);
      });
    }
  },
  
  openWithdraw: async function () {
    if (!App.currentUser) return;
    document.getElementById('withdrawal-message').textContent = '';
    
    if (this.banks.length === 0) {
      await this.loadBanks();
    }
    
    document.getElementById('withdraw-amount').value = '';
    document.getElementById('bank-select').selectedIndex = 0;
    document.getElementById('account-number').value = '';
    document.getElementById('account-name-manual').value = '';
    
    App.showModal('withdrawal-modal');
  },
  
  processWithdrawal: async function () {
    App.showLoading(true);
    
    const userRes = await fetch('/api/user/profile');
    const userData = await userRes.json();
    if (!userData.success) {
      App.showMessage('Session expired. Please log in again.', 'error');
      App.showLoading(false);
      return;
    }
    
    const user = userData.user;
    if (!user.withdrawal_pin) {
      App.showMessage('You must set a withdrawal PIN before cashing out.', 'info');
      App.showLoading(false);
      Settings.setWithdrawalPin();
      return;
    }
    
    const amount = parseFloat(document.getElementById('withdraw-amount').value);
    const bankCode = document.getElementById('bank-select').value;
    const accountNumber = document.getElementById('account-number').value.trim();
    const accountName = document.getElementById('account-name-manual').value.trim();
    
    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      App.showMessage(`Minimum withdrawal: ₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}`, 'error');
      App.showLoading(false);
      return;
    }
    
    if (amount > user.balance) {
      App.showMessage('Insufficient balance.', 'error');
      App.showLoading(false);
      return;
    }
    
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      App.showMessage('Invalid bank details.', 'error');
      App.showLoading(false);
      return;
    }
    
    const pin = prompt('Enter your 4–6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required.', 'error');
      App.showLoading(false);
      return;
    }
    
    const msgEl = document.getElementById('withdrawal-message');
    msgEl.textContent = 'Processing withdrawal...';
    msgEl.className = 'message info';
    
    try {
      const res = await fetch('/api/banking/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          amount, 
          bank_code: bankCode, 
          account_number: accountNumber, 
          account_name: accountName, 
          pin 
        }),
        credentials: 'include'
      });
      
      const data = await res.json();
      msgEl.textContent = data.message;
      msgEl.className = data.success ? 'message success' : 'message error';
      
      if (data.success) {
        App.updateBalance(data.new_balance);
        App.showMessage('✅ Withdrawal submitted for manual review!', 'success');
        setTimeout(() => App.closeModal('withdrawal-modal'), 2000);
      }
    } catch (error) {
      msgEl.textContent = 'Network error. Please try again.';
      msgEl.className = 'message error';
    } finally {
      App.showLoading(false);
    }
  }
};

//========== ACHIEVEMENTS =========
const Achievements = {
  open: async function () {
    if (!App.currentUser) return;
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/achievements');
      const data = await res.json();
      
      if (data.success) {
        this.achievementsData = data;
        window.location.href = 'achievements.html';
      } else {
        App.showMessage('Failed to load achievements', 'error');
      }
    } catch (error) {
      console.error('Achievements error:', error);
      App.showMessage('Failed to load achievements', 'error');
    } finally {
      App.showLoading(false);
    }
  },
  
  claimAllRewards: async function () {
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/achievements/claim', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await res.json();
      if (data.success) {
        App.showMessage(`✅ Achievement rewards claimed! New balance: ₦${data.new_balance.toLocaleString()}`, 'success');
        App.updateBalance(data.new_balance);
      } else {
        App.showMessage(data.message || 'Failed to claim rewards', 'error');
      }
    } catch (error) {
      App.showMessage('Network error. Please try again.', 'error');
    } finally {
      App.showLoading(false);
    }
  }
};

//========== GAMES & TIKTOK DAILY =========
const Games = {
  openSnake: () => window.location.href = 'snake.html',
  openCoinFlip: () => window.location.href = 'coinflip.html',
  openPlinko: () => window.location.href = 'plinko.html',
  
  reportSnake: async function (apples) {
    try {
      const response = await fetch('/api/games/snake/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ apples_eaten: apples })
      });
      
      return await response.json();
    } catch (error) {
      return { success: false, message: error.message };
    }
  },
  
  reportCoinFlip: async function (bet, won) {
    try {
      const response = await fetch('/api/games/coinflip/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ bet: bet, won: won })
      });
      
      return await response.json();
    } catch (error) {
      return { success: false, message: error.message };
    }
  },
  
  reportPlinko: async function (bet, multiplier) {
    try {
      const response = await fetch('/api/games/plinko/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ bet: bet, multiplier: multiplier })
      });
      
      return await response.json();
    } catch (error) {
      return { success: false, message: error.message };
    }
  },
  
  reportSpin: async function (reward) {
    try {
      const response = await fetch('/api/games/spin/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ reward: reward })
      });
      
      return await response.json();
    } catch (error) {
      return { success: false, message: error.message };
    }
  },
  
  openTikTok: async function () {
    if (!App.currentUser) return;
    
    App.showLoading(true);
    
    const msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = '';
    msgEl.className = 'message';
    
    try {
      const res = await fetch('/api/games/tiktok/daily', {
        credentials: 'include'
      });
      
      const data = await res.json();
      
      if (!data.success) {
        document.getElementById('tiktok-instructions').innerHTML = `
          <p style="color:#ff5252;">${data.message || 'No TikTok task available today.'}</p>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      if (data.already_claimed) {
        document.getElementById('tiktok-instructions').innerHTML = `
          <p style="color:#ff9800;">You have already claimed today's TikTok reward! 🎉</p>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      if (!data.task || !data.task.tiktok_link) {
        document.getElementById('tiktok-instructions').innerHTML = `
          <p style="color:#ff5252;">Admin hasn't set a TikTok task for today.</p>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      try {
        const url = new URL(data.task.tiktok_link);
        const username = url.pathname.split('/')[1] || data.task.tiktok_link;
        document.getElementById('tiktok-account-name').textContent = '@' + username;
        document.getElementById('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display">
            <strong>@${username}</strong>
          </div>
          <p class="small-text">Search <strong>@${username}</strong> on TikTok and follow the account</p>
        `;
      } catch (e) {
        document.getElementById('tiktok-account-name').textContent = data.task.tiktok_link;
        document.getElementById('tiktok-instructions').innerHTML = `
          <p>Earn <strong>₦${data.task.reward_amount}</strong> for following on TikTok</p>
          <div class="tiktok-account-display">
            <strong>${data.task.tiktok_link}</strong>
          </div>
          <p class="small-text">Open this link in TikTok and follow</p>
        `;
      }
      
      document.querySelector('.action-buttons').style.display = 'flex';
      App.showModal('tiktok-modal');
    } catch (err) {
      console.error('TikTok load error:', err);
      document.getElementById('tiktok-instructions').innerHTML = `
        <p style="color:#ff5252;">Failed to load TikTok task. Please try again.</p>
      `;
      document.querySelector('.action-buttons').style.display = 'none';
      App.showModal('tiktok-modal');
    } finally {
      App.showLoading(false);
    }
  },
  
  verifyTikTokFollow: async function () {
    const msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = 'Claiming reward...';
    msgEl.className = 'message';
    
    App.showLoading(true);
    
    try {
      const response = await fetch('/api/games/tiktok/follow-daily', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({})
      });
      
      const result = await response.json();
      
      if (result.success) {
        App.updateBalance(result.new_balance);
        msgEl.textContent = `✅ Success! ₦${result.reward} added to your balance.`;
        msgEl.className = 'message success';
        
        setTimeout(() => {
          App.closeModal('tiktok-modal');
          App.showMessage(`✅ TikTok reward claimed: ₦${result.reward}`, 'success');
        }, 2000);
      } else {
        msgEl.textContent = result.message || 'Failed to claim reward.';
        msgEl.className = 'message error';
      }
    } catch (error) {
      msgEl.textContent = error.message || 'Network error';
      msgEl.className = 'message error';
    } finally {
      App.showLoading(false);
    }
  },
  
  openTikTokApp: function () {
    const usernameEl = document.getElementById('tiktok-account-name');
    const username = usernameEl.textContent.replace('@', '');
    if (username) {
      window.open(`snssdk1233://user/@${username}`, '_blank');
      setTimeout(() => {
        window.open(`https://www.tiktok.com/@${username}`, '_blank');
      }, 500);
    }
  },
  
  openSpinWheel: function() {
    if (!App.currentUser) return;
    
    const wheel = document.getElementById('wheel');
    const button = document.getElementById('spin-button');
    const msgEl = document.getElementById('spin-message');
    const resultEl = document.getElementById('spin-result');
    
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
    
    // Create particles when modal opens
    setTimeout(() => {
      if (this.createParticles) {
        this.createParticles();
      }
    }, 150);
  },
  
  spinWheel: async function() {
    const button = document.getElementById('spin-button');
    const wheel = document.getElementById('wheel');
    const msgEl = document.getElementById('spin-message');
    
    if (!button || !wheel || button.disabled) return;
    
    try {
      const limitCheck = await GameManager.checkDailyLimit('spin');
      if (!limitCheck.can_play) {
        App.showMessage(`Daily spin limit reached! You've already spun today.`, 'error');
        return;
      }
    } catch (error) {
      console.error('Limit check failed:', error);
    }
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    
    if (msgEl) {
      msgEl.textContent = '';
      msgEl.className = 'message';
    }
    
    // Add haptic feedback if available
    if (navigator.vibrate) {
      navigator.vibrate([50, 30, 50]);
    }
    
    // Add spinning glow effect
    if (this.addSpinGlow) {
      this.addSpinGlow();
    }
    
    // Play spin sound
    if (this.playSound) {
      this.playSound('spin');
    }
    
    const prizes = [1000, 500, 200, 100, 50, 0];
    const prizeIndex = Math.floor(Math.random() * prizes.length);
    const reward = prizes[prizeIndex];
    
    const degreesPerSegment = 60;
    const targetAngle = prizeIndex * degreesPerSegment;
    const randomOffset = (Math.random() - 0.5) * 30;
    
    const fullSpins = 5 + Math.floor(Math.random() * 3);
    const totalRotation = (fullSpins * 360) + (360 - targetAngle + randomOffset);
    
    // Use CSS animation class for smoother spin
    wheel.style.willChange = 'transform';
    wheel.classList.add('wheel-spinning');
    wheel.style.setProperty('--spin-rotation', totalRotation);
    
    App.showLoading(true);
    
    try {
      const result = await this.reportSpin(reward);
      
      setTimeout(() => {
        App.showLoading(false);
        
        if (result.success) {
          App.updateBalance(result.new_balance);
          
          const resultMsg = reward > 0 
            ? `🎉 Congratulations! You won ₦${reward.toLocaleString()}!`
            : `😢 Better luck tomorrow!`;
          
          if (msgEl) {
            msgEl.textContent = resultMsg;
            msgEl.className = reward > 0 ? 'message success' : 'message warning';
          }
          
          const resultEl = document.getElementById('spin-result');
          if (resultEl) {
            resultEl.innerHTML = `<p style="font-size: 1rem; font-weight: bold;">${resultMsg}</p>`;
            resultEl.classList.remove('hidden');
          }
          
          button.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
          
          if (reward > 0) {
            App.showMessage(`✅ Spin wheel: Won ₦${reward.toLocaleString()}!`, 'success');
            
            // Play win sound
            if (this.playSound) {
              this.playSound('win');
            }
            
            // Show win celebration
            if (this.createWinCelebration) {
              this.createWinCelebration(reward);
            }
            
            // Show animated counter
            if (this.showWinCounter) {
              this.showWinCounter(reward);
            }
          } else {
            // Play lose sound
            if (this.playSound) {
              this.playSound('lose');
            }
          }
        } else {
          if (msgEl) {
            msgEl.textContent = result.message || 'Spin failed. Please try again.';
            msgEl.className = 'message error';
          }
          button.disabled = false;
          button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
          
          App.showMessage(result.message || 'Spin failed', 'error');
        }
        
        // Remove animation class
        wheel.classList.remove('wheel-spinning');
      }, 4200);
      
    } catch (err) {
      console.error('Spin error:', err);
      setTimeout(() => {
        App.showLoading(false);
        
        if (msgEl) {
          msgEl.textContent = 'Network error. Please try again later.';
          msgEl.className = 'message error';
        }
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        App.showMessage('Network error during spin', 'error');
        
        // Remove animation class
        wheel.classList.remove('wheel-spinning');
      }, 4200);
    }
  }
};

// ==================== SPIN WHEEL VISUAL EFFECTS ====================

Games.enhanceSpinVisuals = function() {
    console.log('🎨 Enhancing spin wheel visuals...');
    
    // Create particles for background
    Games.createParticles = () => {
        const particlesContainer = document.getElementById('spin-particles');
        if (!particlesContainer) return;
        
        particlesContainer.innerHTML = '';
        
        for (let i = 0; i < 12; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.cssText = `
                width: ${1 + Math.random() * 3}px;
                height: ${1 + Math.random() * 3}px;
                background: ${['#8000FF', '#00CCFF', '#FF0055', '#00FF55'][Math.floor(Math.random() * 4)]};
                border-radius: 50%;
                opacity: ${0.15 + Math.random() * 0.2};
                animation: floatParticle ${3 + Math.random() * 4}s infinite linear;
                animation-delay: ${Math.random() * 5}s;
                top: ${Math.random() * 100}%;
                left: ${Math.random() * 100}%;
            `;
            particlesContainer.appendChild(particle);
        }
    };
    
    // Create win celebration
    Games.createWinCelebration = function(amount) {
        if (amount <= 0) return;
        
        const celebration = document.createElement('div');
        celebration.className = 'win-celebration';
        celebration.id = 'win-celebration';
        
        // Create confetti
        for (let i = 0; i < 80; i++) {
            const confetti = document.createElement('div');
            confetti.className = 'confetti';
            confetti.style.cssText = `
                left: ${Math.random() * 100}%;
                background: ${['#FF0055', '#00FF55', '#00CCFF', '#FFCC00', '#8000FF'][Math.floor(Math.random() * 5)]};
                animation: confettiFall ${1 + Math.random() * 2}s ease-in forwards;
                animation-delay: ${Math.random() * 0.5}s;
                transform: rotate(${Math.random() * 360}deg);
            `;
            celebration.appendChild(confetti);
        }
        
        document.body.appendChild(celebration);
        
        // Remove after animation
        setTimeout(() => {
            if (celebration.parentNode) {
                celebration.remove();
            }
        }, 3000);
    };
    
    // Add spinning glow effect
    Games.addSpinGlow = function() {
        const wheel = document.getElementById('wheel');
        if (wheel) {
            wheel.classList.add('spinning-glow');
            
            // Remove after spin
            setTimeout(() => {
                wheel.classList.remove('spinning-glow');
            }, 4000);
        }
    };
    
    // Show animated counter for win amount
    Games.showWinCounter = function(amount) {
        if (amount <= 0) return;
        
        const resultEl = document.getElementById('spin-result');
        if (resultEl) {
            resultEl.innerHTML = `
                <p class="counter-animation" style="
                    text-align: center;
                    margin: 8px 0;
                    font-size: 1.8rem;
                ">
                    🎉 ₦${amount.toLocaleString()}! 🎉
                </p>
                <p style="text-align: center; color: #00FF55; font-weight: 600; font-size: 0.9rem;">
                    Added to your balance!
                </p>
            `;
            resultEl.classList.remove('hidden');
        }
    };
    
    // Simple sound effects system
    Games.playSound = function(type) {
        if (typeof Audio === 'undefined') return;
        
        try {
            // Create audio context for better mobile support
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create oscillator for simple sounds
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Set sound parameters based on type
            if (type === 'spin') {
                oscillator.frequency.setValueAtTime(300, audioContext.currentTime);
                oscillator.frequency.exponentialRampToValueAtTime(100, audioContext.currentTime + 0.5);
                gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.5);
            } else if (type === 'win') {
                // Winning chime
                oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime); // C5
                oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime + 0.1); // E5
                oscillator.frequency.setValueAtTime(783.99, audioContext.currentTime + 0.2); // G5
                gainNode.gain.setValueAtTime(0.15, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.5);
            } else if (type === 'lose') {
                // Sad sound
                oscillator.frequency.setValueAtTime(200, audioContext.currentTime);
                oscillator.frequency.exponentialRampToValueAtTime(100, audioContext.currentTime + 0.3);
                gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.3);
            }
        } catch (error) {
            console.log('Audio play failed:', error);
            // Fallback to silent
        }
    };
    
    console.log('✅ Spin wheel visual effects enhanced');
};

// Initialize visuals when page loads
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (window.Games) {
            Games.enhanceSpinVisuals();
        }
    }, 2000);
});

//========== SETTINGS & LOGOUT =========
const Settings = {
  open: async function () {
    if (!App.currentUser) return;
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/user/profile');
      const data = await res.json();
      if (!data.success) {
        App.showMessage('Failed to load settings', 'error');
        return;
      }
      
      const user = data.user;
      const hasPin = !!user.withdrawal_pin;
      let html = `
        <div class="settings-section">
          <h4><i class="fas fa-user-cog"></i> Account Settings</h4>
          <div class="profile-info">
            <div class="profile-item">
              <span class="label">Username</span>
              <span class="value">${user.username}</span>
            </div>
            <div class="profile-item">
              <span class="label">Balance</span>
              <span class="value">₦${user.balance.toLocaleString()}</span>
            </div>
          </div>
        </div>
      `;
      
      try {
        const socialRes = await fetch('/api/admin/settings');
        const socialData = await socialRes.json();
        if (socialData.success) {
          const s = socialData.settings;
          html += `
            <div class="settings-section">
              <h4><i class="fas fa-users"></i> Join Our Community</h4>
          `;
          if (s.whatsapp_link) html += `
            <a href="${s.whatsapp_link}" target="_blank" class="social-link">
              <i class="fab fa-whatsapp"></i> WhatsApp Group
            </a><br>`;
          if (s.telegram_link) html += `
            <a href="${s.telegram_link}" target="_blank" class="social-link">
              <i class="fab fa-telegram"></i> Telegram Group
            </a><br>`;
          if (s.facebook_link) html += `
            <a href="${s.facebook_link}" target="_blank" class="social-link">
              <i class="fab fa-facebook"></i> Facebook Group
            </a><br>`;
          if (!(s.whatsapp_link || s.telegram_link || s.facebook_link)) {
            html += `<p class="small-text">No social links configured yet</p>`;
          }
          html += `</div>`;
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
          <h4><i class="fas fa-sign-out-alt"></i> Session</h4>
          <button class="btn-primary" style="background:#d32f2f;width:100%;" onclick="Settings.logout()">
            <i class="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      `;
      
      document.getElementById('settings-data').innerHTML = html;
      
      if (!document.getElementById('social-style')) {
        const style = document.createElement('style');
        style.id = 'social-style';
        style.textContent = `
          .social-link {
            display: inline-block;
            margin: 5px 0;
            padding: 8px 15px;
            background: rgba(30,30,69,0.8);
            border: 1px solid #8000FF;
            border-radius: 8px;
            color: #8000FF;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
          }
          .social-link:hover {
            background: rgba(128,0,255,0.2);
            transform: translateY(-2px);
          }
          .settings-section {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #252540;
          }
          .settings-section:last-child {
            border-bottom: none;
          }
          .small-text {
            font-size: 0.8rem;
            color: #A0A0B5;
            margin: 10px 0;
          }
        `;
        document.head.appendChild(style);
      }
      
      App.showModal('settings-modal');
    } catch (error) {
      console.error('Settings error:', error);
      App.showMessage('Failed to load settings', 'error');
    } finally {
      App.showLoading(false);
    }
  },
  
  setWithdrawalPin: async function (isChange = false) {
    let currentPin = '';
    if (isChange) {
      currentPin = prompt('Enter your CURRENT 4-6 digit Withdrawal PIN:');
      if (!currentPin) return;
      if (!/^\d{4,6}$/.test(currentPin)) {
        App.showMessage('Current PIN must be 4 to 6 digits.', 'error');
        return;
      }
      
      try {
        const verifyRes = await fetch('/api/user/verify-withdrawal-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: currentPin }),
          credentials: 'include'
        });
        
        const verifyData = await verifyRes.json();
        if (!verifyData.success) {
          App.showMessage('Incorrect current PIN.', 'error');
          return;
        }
      } catch (error) {
        App.showMessage('Verification failed. Please try again.', 'error');
        return;
      }
    }
    
    const newPin = prompt('Enter your NEW 4-6 digit Withdrawal PIN:');
    if (!newPin || !/^\d{4,6}$/.test(newPin)) {
      App.showMessage('New PIN must be 4 to 6 digits.', 'error');
      return;
    }
    
    const confirmPin = prompt('Confirm your new PIN:');
    if (newPin !== confirmPin) {
      App.showMessage('PINs do not match.', 'error');
      return;
    }
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/user/set-withdrawal-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: newPin }),
        credentials: 'include'
      });
      
      const data = await res.json();
      if (data.success) {
        App.showMessage('PIN ' + (isChange ? 'changed' : 'set') + ' successfully!', 'success');
        App.closeModal('settings-modal');
      } else {
        App.showMessage(data.message, 'error');
      }
    } catch (error) {
      App.showMessage('Failed to set PIN. Please try again.', 'error');
    } finally {
      App.showLoading(false);
    }
  },
  
  changeWithdrawalPin: function () {
    this.setWithdrawalPin(true);
  },
  
  changePassword: async function () {
    const oldPass = prompt("Enter your current password:");
    if (!oldPass) return;
    
    const newPass = prompt("Enter a new password (min 6 characters):");
    if (!newPass || newPass.length < 6) {
      App.showMessage("Password must be at least 6 characters.", "error");
      return;
    }
    
    const confirmPass = prompt("Confirm your new password:");
    if (newPass !== confirmPass) {
      App.showMessage("Passwords do not match.", "error");
      return;
    }
    
    App.showLoading(true);
    
    try {
      const res = await fetch('/api/user/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPass, new_password: newPass }),
        credentials: 'include'
      });
      
      const data = await res.json();
      if (data.success) {
        App.showMessage("Password changed successfully!", "success");
        App.closeModal('settings-modal');
      } else {
        App.showMessage(data.message, "error");
      }
    } catch (error) {
      App.showMessage("Failed to change password. Please try again.", "error");
    } finally {
      App.showLoading(false);
    }
  },
  
  logout: async function () {
    if (!confirm('Are you sure you want to logout?')) return;
    
    App.showLoading(true);
    
    try {
      await fetch('/api/auth/logout', { 
        method: 'POST', 
        credentials: 'include' 
      });
    } catch (e) {
      console.warn('Logout endpoint failed');
    }
    
    document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
      (window.location.protocol === 'https:' ? '; secure' : '');
    
    // Add small delay before showing auth screen
    setTimeout(() => {
      App.showLoading(false);
      App.showAuthScreen();
      App.currentUser = null;
    }, 500);
  }
};

//========== DOM READY ===========
document.addEventListener('DOMContentLoaded', () => {
  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
      tab.classList.add('active');
      const targetForm = tab.dataset.tab + '-form';
      document.getElementById(targetForm).classList.add('active');
    });
  });
  
  // Buy coupon button
  const buyCouponBtn = document.querySelector('[onclick="Auth.buyCoupon()"]');
  if (buyCouponBtn) {
    buyCouponBtn.onclick = () => Auth.buyCoupon();
  }
  
  // Initialize password toggles
  Auth.initPasswordToggles();
  
  // Initialize main app
  setTimeout(() => {
    App.init();
  }, 300);
});

// ==================== GLOBAL FUNCTIONS FOR GAME PAGES ====================
// COMPLETE FINAL VERSION - EVERYTHING INCLUDED
(function() {
    // Export all functions to window
    window.App = App;
    window.GameManager = GameManager;
    window.Games = Games;
    window.Auth = Auth;
    window.Profile = Profile;
    window.Referral = Referral;
    window.Banking = Banking;
    window.Achievements = Achievements;
    window.Settings = Settings;
    
    // Game navigation
    window.openSnakeGame = () => window.location.href = 'snake.html';
    window.openCoinFlipGame = () => window.location.href = 'coinflip.html';
    window.openPlinkoGame = () => window.location.href = 'plinko.html';
    window.openTikTokGame = Games.openTikTok;
    window.openSpinWheelGame = Games.openSpinWheel;
    
    // Critical API functions
    window.checkDailyLimit = GameManager.checkDailyLimit;
    window.updateBalance = App.updateBalance;
    window.showMessage = App.showMessage;
    window.showLoading = App.showLoading;
    window.goBackToDashboard = () => window.location.href = 'index.html';
    
    // Game claim functions (DIRECT API CALLS)
    window.claimSnakeReward = async function(apples) {
        App.showLoading(true);
        try {
            const response = await fetch('/api/games/snake/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ apples_eaten: apples })
            });
            return await response.json();
        } catch (error) {
            return { success: false, message: error.message };
        } finally {
            App.showLoading(false);
        }
    };
    
    window.claimCoinFlipReward = async function(bet, won) {
        App.showLoading(true);
        try {
            const response = await fetch('/api/games/coinflip/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ bet: bet, won: won })
            });
            return await response.json();
        } catch (error) {
            return { success: false, message: error.message };
        } finally {
            App.showLoading(false);
        }
    };
    
    window.claimPlinkoReward = async function(bet, multiplier) {
        App.showLoading(true);
        try {
            const response = await fetch('/api/games/plinko/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ bet: bet, multiplier: multiplier })
            });
            return await response.json();
        } catch (error) {
            return { success: false, message: error.message };
        } finally {
            App.showLoading(false);
        }
    };
    
    // Universal game result reporter
    window.reportGameResult = async function(gameType, data) {
        const endpoints = {
            'snake': '/api/games/snake/report',
            'coinflip': '/api/games/coinflip/report',
            'plinko': '/api/games/plinko/report',
            'spin': '/api/games/spin/report'
        };
        
        const endpoint = endpoints[gameType];
        if (!endpoint) {
            return { success: false, message: 'Unknown game type' };
        }
        
        App.showLoading(true);
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            return { success: false, message: error.message };
        } finally {
            App.showLoading(false);
        }
    };
    
    console.log('✅ FLEXIA Script v12.0 - COMPLETE WITH ANIMATIONS LOADED');
    console.log('🎯 Spin Wheel: 260px container, 240px SVG - Perfectly sized!');
    console.log('✨ Login/Logout animations: ACTIVE');
})();

// Emergency fallback loader
document.addEventListener('DOMContentLoaded', function() {
    // Double-check critical functions
    setTimeout(() => {
        const required = ['checkDailyLimit', 'claimSnakeReward', 'claimCoinFlipReward', 'claimPlinkoReward'];
        required.forEach(func => {
            if (typeof window[func] !== 'function') {
                console.warn(`Function ${func} missing, creating emergency fallback`);
                
                if (func === 'checkDailyLimit') {
                    window.checkDailyLimit = async () => ({ can_play: true, played_today: 0, max_per_day: 999 });
                } else if (func === 'claimSnakeReward') {
                    window.claimSnakeReward = async (apples) => ({
                        success: false,
                        message: 'Please refresh the page to load game functions'
                    });
                }
            }
        });
    }, 1000);
});
