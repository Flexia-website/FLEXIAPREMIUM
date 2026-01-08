// ================================
// FLEXIA Frontend Logic v10.9.1 — COMPLETE & FIXED
// ✅ Banks showing ✅ Double-click prevention ✅ WhatsApp working ✅ All games working
// ================================

//========== CONFIGURATION========
const CONFIG = {
  MIN_WITHDRAWAL: 100000,
  REFERRAL_BONUS: 7500,
  TIKTOK_REWARD: 150,
  SNAKE_REWARD: 200,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100
};

//========== CORE APP==========
const App = {
  currentUser: null,
  balanceVisible: true,
  isProcessing: false, // ✅ ADDED: Double-click prevention
  
  init: async function () {
    await this.checkAuth();
    if (document.getElementById('app-screen')) {
      await Profile.load();
      await Banking.loadBanks(); // ✅ FIXED: Banks loading
      this.setupTheme();
    }
  },
  
  checkAuth: async function () {
    try {
      const res = await fetch('/api/user/profile', { credentials: 'include' });
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
    }
  },
  
  showAppScreen: function () {
    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('app-screen').classList.remove('hidden');
  },
  
  showAuthScreen: function () {
    document.getElementById('app-screen').classList.add('hidden');
    document.getElementById('auth-screen').classList.remove('hidden');
  },
  
  refreshBalance: function () {
    if (!this.currentUser) return;
    const display = document.getElementById('balance-display');
    if (display) {
      display.textContent = this.currentUser.balance.toLocaleString(undefined, { minimumFractionDigits: 2 });
    }
    const withdrawBalance = document.getElementById('withdraw-balance');
    if (withdrawBalance) {
      withdrawBalance.textContent = `₦${this.currentUser.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    }
    const minEl = document.getElementById('withdraw-min');
    if (minEl) minEl.textContent = `₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}`;
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
  },
  
  closeModal: function (modalId) {
    document.getElementById(modalId).classList.add('hidden');
  },
  
  showMessage: function (text, type = 'info') {
    // Create a message element
    const messageEl = document.createElement('div');
    messageEl.className = `global-message ${type}`;
    messageEl.innerHTML = `
      <div class="message-content">
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${text}</span>
      </div>
      <button class="message-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    // Add styles if not already added
    if (!document.getElementById('message-styles')) {
      const style = document.createElement('style');
      style.id = 'message-styles';
      style.textContent = `
        .global-message {
          position: fixed;
          top: 20px;
          right: 20px;
          padding: 15px 20px;
          border-radius: 8px;
          color: white;
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: space-between;
          min-width: 300px;
          max-width: 400px;
          box-shadow: 0 5px 15px rgba(0,0,0,0.3);
          animation: slideIn 0.3s ease-out;
        }
        .global-message.success { background: linear-gradient(135deg, #00cc66, #00aa44); border-left: 4px solid #00ff55; }
        .global-message.error { background: linear-gradient(135deg, #ff3333, #cc0000); border-left: 4px solid #ff5555; }
        .global-message.info { background: linear-gradient(135deg, #3366ff, #0044cc); border-left: 4px solid #0088ff; }
        .message-content { display: flex; align-items: center; gap: 10px; flex: 1; }
        .message-close { background: none; border: none; color: white; font-size: 20px; cursor: pointer; margin-left: 10px; }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `;
      document.head.appendChild(style);
    }
    
    // Remove existing messages
    document.querySelectorAll('.global-message').forEach(msg => msg.remove());
    
    // Add new message
    document.body.appendChild(messageEl);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (messageEl.parentElement) {
        messageEl.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => messageEl.remove(), 300);
      }
    }, 5000);
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

//========== AUTHENTICATION========
const Auth = {
  login: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    const identifier = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');
    
    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
      App.isProcessing = false;
      return;
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
        App.showAppScreen();
        App.refreshBalance();
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
      }
    } catch (err) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
    } finally {
      App.isProcessing = false;
    }
  },
  
  register: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    const coupon = document.getElementById('reg-coupon').value.trim().toUpperCase();
    const referral = document.getElementById('reg-referral').value.trim();
    const contact = document.getElementById('reg-contact')?.value.trim() || '';
    const messageEl = document.getElementById('register-message');
    
    if (!username || !password || !coupon) {
      messageEl.textContent = 'Username, password and coupon code are required';
      messageEl.className = 'message error';
      App.isProcessing = false;
      return;
    }
    
    // ✅ FIXED: Better validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const phoneRegex = /^(234|0)[789][01]\d{8}$/;
    if (contact && !emailRegex.test(contact) && !phoneRegex.test(contact)) {
      messageEl.textContent = 'Contact must be valid email or Nigerian phone (080/090/070/081)';
      messageEl.className = 'message error';
      App.isProcessing = false;
      return;
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
        // Auto-fill login form
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').value = password;
        // Switch to login tab
        document.querySelector('.tab[data-tab="login"]').click();
        // Clear registration form
        document.getElementById('reg-username').value = '';
        document.getElementById('reg-password').value = '';
        document.getElementById('reg-coupon').value = '';
        document.getElementById('reg-referral').value = '';
        if (document.getElementById('reg-contact')) {
          document.getElementById('reg-contact').value = '';
        }
      }
    } catch (err) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
    } finally {
      App.isProcessing = false;
    }
  },
  
  buyCoupon: async function () {
    try {
      // ✅ FIXED: Correct WhatsApp endpoint
      const res = await fetch('/api/whatsapp/numbers');
      const data = await res.json();
      if (data.success && data.numbers && data.numbers.length > 0) {
        // Get first active WhatsApp number
        const number = data.numbers[0].number;
        window.open(`https://wa.me/${number}`, '_blank');
      } else {
        // Fallback number
        window.open('https://wa.me/2348160881049', '_blank');
      }
    } catch (error) {
      console.error('WhatsApp error:', error);
      window.open('https://wa.me/2348160881049', '_blank');
    }
  }
};

//========== PROFILE=========
const Profile = {
  open: async function () {
    if (!App.currentUser) return;
    await this.load();
    App.showModal('profile-modal');
  },
  
  load: async function () {
    try {
      const res = await fetch('/api/user/profile', { credentials: 'include' });
      const data = await res.json();
      if (data.success) {
        App.currentUser = data.user;
        const stats = data.user.game_stats || {};
        
        let html = `
          <div class="profile-info">
            <p><strong>Username:</strong> ${data.user.username}</p>
            <p><strong>Balance:</strong> ₦${data.user.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
            <p><strong>Referral Code:</strong> <code>${data.user.referral_code}</code></p>
            <p><strong>Joined:</strong> ${new Date(data.user.created_at).toLocaleDateString()}</p>
            <hr>
            <h4>Game Stats</h4>
            <p><strong>Snake High Score:</strong> ${stats.snake?.high_score || 0}</p>
            <p><strong>Coin Flip Wins:</strong> ${stats.coin_flip?.wins || 0} of ${(stats.coin_flip?.wins || 0) + (stats.coin_flip?.losses || 0)}</p>
            <p><strong>Plinko Wins:</strong> ${stats.plinko?.total_wins || 0}</p>
            <hr>
            <h4>Profile Picture</h4>
            <input type="text" id="profile-pic-url" placeholder="Enter image URL (e.g., https://example.com/photo.jpg)" 
                   style="width:100%;padding:10px;margin:10px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:6px;">
            <button class="btn-primary" onclick="Profile.setProfilePicture()" style="width:100%;">
              <i class="fas fa-upload"></i> Update Profile Picture
            </button>
        `;
        
        if (data.user.profile_picture) {
          html += `
            <div style="margin-top:15px;text-align:center;">
              <img src="${data.user.profile_picture}" 
                   style="width:120px;height:120px;border-radius:15px;border:2px solid #8000FF;object-fit:cover;">
            </div>
          `;
        }
        
        html += `</div>`;
        document.getElementById('profile-data').innerHTML = html;
      }
    } catch (err) {
      console.error('Failed to load profile', err);
      document.getElementById('profile-data').innerHTML = `
        <div class="error-message">
          <i class="fas fa-exclamation-triangle"></i>
          <p>Failed to load profile. Please try again.</p>
        </div>
      `;
    }
  },
  
  setProfilePicture: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    const url = document.getElementById('profile-pic-url').value.trim();
    if (!url) {
      App.showMessage('Please enter a valid image URL', 'error');
      App.isProcessing = false;
      return;
    }
    
    // Basic URL validation
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      App.showMessage('URL must start with http:// or https://', 'error');
      App.isProcessing = false;
      return;
    }
    
    try {
      const res = await fetch('/api/user/set-profile-picture', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picture_url: url })
      });
      const data = await res.json();
      if (data.success) {
        App.showMessage('Profile picture updated successfully!', 'success');
        Profile.load(); // Reload profile
      } else {
        App.showMessage(data.message || 'Failed to update picture', 'error');
      }
    } catch (err) {
      App.showMessage('Network error. Please try again.', 'error');
    } finally {
      App.isProcessing = false;
    }
  }
};

//========== REFERRALS========
const Referral = {
  open: async function () {
    if (!App.currentUser) return;
    
    try {
      const res = await fetch('/api/user/profile', { credentials: 'include' });
      const data = await res.json();
      if (data.success) {
        const unclaimed = data.referrals.unclaimed_bonus;
        const html = `
          <div class="referral-info">
            <h4>Your Referral Code</h4>
            <div class="referral-code-display">
              <span class="code">${data.user.referral_code}</span>
              <button class="copy-btn" onclick="Referral.copyCode('${data.user.referral_code}')">
                <i class="fas fa-copy"></i> Copy
              </button>
            </div>
            
            <p class="info-text">Share this code with friends to earn ₦${CONFIG.REFERRAL_BONUS.toLocaleString()} per referral!</p>
            
            <div class="referral-stats">
              <div class="stat">
                <span class="stat-label">Referred Users</span>
                <span class="stat-value">${data.referrals.count}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Unclaimed Bonus</span>
                <span class="stat-value">₦${unclaimed.toLocaleString()}</span>
              </div>
            </div>
            
            ${unclaimed > 0
              ? `<button class="btn-primary" onclick="Referral.claimBonuses()" style="width:100%;margin-top:15px;">
                  <i class="fas fa-gift"></i> Claim ₦${unclaimed.toLocaleString()} Bonus
                </button>`
              : '<p class="success-message">All bonuses claimed! 🎉</p>'
            }
            
            <div class="share-section" style="margin-top:20px;">
              <button class="btn-secondary" onclick="Referral.shareReferral('${data.user.referral_code}')" style="width:100%;">
                <i class="fas fa-share-alt"></i> Share Referral Link
              </button>
            </div>
          </div>
          
          <style>
            .referral-code-display {
              background: rgba(128,0,255,0.1);
              border: 2px solid #8000FF;
              border-radius: 10px;
              padding: 15px;
              display: flex;
              justify-content: space-between;
              align-items: center;
              margin: 15px 0;
            }
            .referral-code-display .code {
              font-family: 'Orbitron', monospace;
              font-size: 1.4rem;
              font-weight: bold;
              color: #00FFCC;
              letter-spacing: 2px;
            }
            .copy-btn {
              background: #8000FF;
              color: white;
              border: none;
              padding: 8px 15px;
              border-radius: 6px;
              cursor: pointer;
              font-weight: 600;
              transition: all 0.3s;
            }
            .copy-btn:hover {
              background: #9000FF;
              transform: translateY(-2px);
            }
            .referral-stats {
              display: flex;
              gap: 20px;
              margin: 20px 0;
            }
            .stat {
              flex: 1;
              text-align: center;
              background: rgba(30,30,69,0.8);
              padding: 15px;
              border-radius: 10px;
              border: 1px solid #8000FF;
            }
            .stat-label {
              display: block;
              color: #A0A0B5;
              font-size: 0.9rem;
              margin-bottom: 5px;
            }
            .stat-value {
              display: block;
              font-size: 1.3rem;
              font-weight: bold;
              color: #00FFCC;
            }
            .info-text {
              color: #A0A0B5;
              margin: 15px 0;
              line-height: 1.5;
            }
            .success-message {
              color: #00FF55;
              text-align: center;
              padding: 10px;
              background: rgba(0,255,85,0.1);
              border-radius: 8px;
              margin: 15px 0;
            }
          </style>
        `;
        
        document.getElementById('referral-data').innerHTML = html;
        App.showModal('referral-modal');
      }
    } catch (err) {
      console.error('Referral error:', err);
      document.getElementById('referral-data').innerHTML = `
        <div class="error-message">
          <i class="fas fa-exclamation-triangle"></i>
          <p>Failed to load referral data.</p>
        </div>
      `;
      App.showModal('referral-modal');
    }
  },
  
  claimBonuses: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    try {
      const res = await fetch('/api/referral/claim', {
        method: 'POST',
        credentials: 'include'
      });
      const data = await res.json();
      
      if (data.success) {
        App.showMessage(`₦${data.claimed.toLocaleString()} referral bonus claimed! 🎉`, 'success');
        App.currentUser.balance = data.new_balance;
        App.refreshBalance();
        Referral.open(); // Refresh referral modal
      } else {
        App.showMessage(data.message || 'Failed to claim bonus', 'error');
      }
    } catch (err) {
      App.showMessage('Network error. Please try again.', 'error');
    } finally {
      App.isProcessing = false;
    }
  },
  
  copyCode: function (code) {
    navigator.clipboard.writeText(code).then(() => {
      App.showMessage('Referral code copied to clipboard!', 'success');
    }).catch(err => {
      console.error('Copy failed:', err);
      App.showMessage('Failed to copy code', 'error');
    });
  },
  
  shareReferral: function (code) {
    const link = `${window.location.origin}?ref=${code}`;
    const message = `Join FLEXIA and start earning! Use my referral code: ${code}\n\n${link}`;
    
    if (navigator.share) {
      navigator.share({
        title: 'FLEXIA Referral',
        text: message,
        url: link
      }).catch(err => {
        console.error('Share failed:', err);
        this.copyLink(link);
      });
    } else {
      this.copyLink(link);
    }
  },
  
  copyLink: function (link) {
    navigator.clipboard.writeText(link).then(() => {
      App.showMessage('Referral link copied to clipboard!', 'success');
    }).catch(err => {
      console.error('Copy failed:', err);
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = link;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      App.showMessage('Link copied!', 'success');
    });
  }
};

//========== BANKING & WITHDRAWALS=========
const Banking = {
  banks: [],
  
  async loadBanks() {
    try {
      // ✅ FIXED: Correct endpoint
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
      }
    } catch (err) {
      console.error('Bank loading error:', err);
    }
  },
  
  openWithdraw: function () {
    if (!App.currentUser) return;
    document.getElementById('withdrawal-message').textContent = '';
    
    // Populate bank dropdown if empty
    if (document.getElementById('bank-select').options.length <= 1) {
      this.loadBanks();
    }
    
    App.showModal('withdrawal-modal');
  },
  
  processWithdrawal: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    const amountInput = document.getElementById('withdraw-amount');
    const bankSelect = document.getElementById('bank-select');
    const accountNumberInput = document.getElementById('account-number');
    const accountNameInput = document.getElementById('account-name-manual');
    const messageEl = document.getElementById('withdrawal-message');
    
    const amount = parseFloat(amountInput.value);
    const bankCode = bankSelect.value;
    const accountNumber = accountNumberInput.value.trim();
    const accountName = accountNameInput.value.trim();
    
    // Validation
    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      App.showMessage(`Minimum withdrawal: ₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}`, 'error');
      App.isProcessing = false;
      return;
    }
    
    if (amount > App.currentUser.balance) {
      App.showMessage('Insufficient balance', 'error');
      App.isProcessing = false;
      return;
    }
    
    if (!bankCode) {
      App.showMessage('Please select a bank', 'error');
      App.isProcessing = false;
      return;
    }
    
    if (!accountNumber || accountNumber.length < 10 || !/^\d+$/.test(accountNumber)) {
      App.showMessage('Please enter a valid 10-digit account number', 'error');
      App.isProcessing = false;
      return;
    }
    
    if (!accountName || accountName.length < 2) {
      App.showMessage('Please enter account name', 'error');
      App.isProcessing = false;
      return;
    }
    
    // Ask for PIN
    const pin = prompt('Enter your 4-6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required (4-6 digits)', 'error');
      App.isProcessing = false;
      return;
    }
    
    messageEl.textContent = 'Processing withdrawal...';
    messageEl.className = 'message';
    
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
      
      if (data.success) {
        // Update balance
        App.currentUser.balance = data.new_balance;
        App.refreshBalance();
        
        // Show success
        App.showMessage('✅ Withdrawal submitted for review! You\'ll be notified when processed.', 'success');
        App.closeModal('withdrawal-modal');
        
        // Clear form
        amountInput.value = '';
        bankSelect.selectedIndex = 0;
        accountNumberInput.value = '';
        accountNameInput.value = '';
      } else {
        messageEl.textContent = data.message || 'Withdrawal failed';
        messageEl.className = 'message error';
        App.showMessage(data.message || 'Withdrawal failed', 'error');
      }
    } catch (err) {
      console.error('Withdrawal error:', err);
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
      App.showMessage('Network error. Please try again.', 'error');
    } finally {
      App.isProcessing = false;
    }
  }
};

//========== GAMES & TIKTOK DAILY =========
const Games = {
  // ✅ FIXED: Add game lock to prevent double-click
  gameLocks: {},
  
  checkGameLock: function(gameType) {
    const now = Date.now();
    if (this.gameLocks[gameType] && now - this.gameLocks[gameType] < 2000) {
      return false; // Still locked
    }
    this.gameLocks[gameType] = now;
    return true;
  },
  
  openSnake: () => window.location.href = 'snake.html',
  openCoinFlip: () => window.location.href = 'coin-flip.html',
  openPlinko: () => window.location.href = 'plinko.html',
  
  openTikTok: async function () {
    if (!App.currentUser) return;
    if (!this.checkGameLock('tiktok')) return;
    
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
          <div class="tiktok-error">
            <i class="fas fa-exclamation-circle"></i>
            <p>${data.message || 'No TikTok task available today.'}</p>
          </div>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      if (data.already_claimed) {
        document.getElementById('tiktok-instructions').innerHTML = `
          <div class="tiktok-success">
            <i class="fas fa-check-circle"></i>
            <p>You have already claimed today's TikTok reward! 🎉</p>
            <p class="small">Come back tomorrow for a new task.</p>
          </div>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      if (!data.task || !data.task.tiktok_link) {
        document.getElementById('tiktok-instructions').innerHTML = `
          <div class="tiktok-error">
            <i class="fas fa-exclamation-circle"></i>
            <p>Admin hasn't set a TikTok task for today.</p>
          </div>
        `;
        document.querySelector('.action-buttons').style.display = 'none';
        App.showModal('tiktok-modal');
        return;
      }
      
      try {
        const url = new URL(data.task.tiktok_link);
        const username = url.pathname.split('/')[1]?.replace('@', '') || data.task.tiktok_link;
        document.getElementById('tiktok-account-name').textContent = '@' + username;
        document.getElementById('tiktok-instructions').innerHTML = `
          <div class="tiktok-task">
            <h4>Today's Task</h4>
            <p>Follow <strong>@${username}</strong> on TikTok to earn:</p>
            <div class="reward-amount">₦${data.task.reward_amount || CONFIG.TIKTOK_REWARD}</div>
            <p class="instructions">
              1. Open TikTok app<br>
              2. Search for <strong>@${username}</strong><br>
              3. Follow the account<br>
              4. Come back here and click "I FOLLOWED"
            </p>
          </div>
        `;
      } catch (e) {
        document.getElementById('tiktok-account-name').textContent = data.task.tiktok_link;
        document.getElementById('tiktok-instructions').innerHTML = `
          <div class="tiktok-task">
            <h4>Today's Task</h4>
            <p>Follow this TikTok account to earn:</p>
            <div class="reward-amount">₦${data.task.reward_amount || CONFIG.TIKTOK_REWARD}</div>
            <p class="instructions">
              1. Click "OPEN TIKTOK" below<br>
              2. Follow the account<br>
              3. Come back here and click "I FOLLOWED"
            </p>
          </div>
        `;
      }
      
      document.querySelector('.action-buttons').style.display = 'flex';
      App.showModal('tiktok-modal');
    } catch (err) {
      console.error('TikTok load error:', err);
      document.getElementById('tiktok-instructions').innerHTML = `
        <div class="tiktok-error">
          <i class="fas fa-exclamation-circle"></i>
          <p>Failed to load TikTok task. Please try again.</p>
        </div>
      `;
      document.querySelector('.action-buttons').style.display = 'none';
      App.showModal('tiktok-modal');
    }
  },
  
  verifyTikTokFollow: async function () {
    if (!this.checkGameLock('tiktok-verify')) return;
    
    const msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = 'Verifying and claiming reward...';
    msgEl.className = 'message';
    
    try {
      const res = await fetch('/api/games/tiktok/follow-daily', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      
      if (data.success) {
        App.currentUser.balance = data.new_balance;
        App.refreshBalance();
        msgEl.textContent = `✅ Success! ₦${data.reward} added to your balance.`;
        msgEl.className = 'message success';
        App.showMessage(`🎉 TikTok reward claimed! +₦${data.reward}`, 'success');
        setTimeout(() => App.closeModal('tiktok-modal'), 2000);
      } else {
        msgEl.textContent = data.message || 'Failed to claim reward.';
        msgEl.className = 'message error';
        App.showMessage(data.message || 'Failed to claim reward', 'error');
      }
    } catch (err) {
      console.error('TikTok claim error:', err);
      msgEl.textContent = 'Network error. Please try again.';
      msgEl.className = 'message error';
      App.showMessage('Network error. Please try again.', 'error');
    }
  },
  
  openTikTokApp: function () {
    const usernameEl = document.getElementById('tiktok-account-name');
    const username = usernameEl.textContent.replace('@', '');
    if (username) {
      // Try to open TikTok app
      window.open(`snssdk1233://user/@${username}`, '_blank');
      // Fallback to web after delay
      setTimeout(() => {
        window.open(`https://www.tiktok.com/@${username}`, '_blank');
      }, 500);
    }
  },
  
  // ✅ PERFECT: Spin Wheel Functions
  openSpinWheel: function () {
    if (!App.currentUser) return;
    
    // Reset wheel position
    const wheel = document.getElementById('wheel');
    if (wheel) {
      wheel.style.transition = 'none';
      wheel.style.transform = 'rotate(0deg)';
      // Force reflow
      void wheel.offsetWidth;
    }
    
    // Reset UI
    document.getElementById('spin-result').classList.add('hidden');
    document.getElementById('spin-message').textContent = '';
    const button = document.getElementById('spin-button');
    if (button) {
      button.disabled = false;
      button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
    }
    
    App.showModal('spin-modal');
    
    // Add wheel styles if not present
    if (!document.getElementById('wheel-styles')) {
      const style = document.createElement('style');
      style.id = 'wheel-styles';
      style.textContent = `
        .wheel-container {
          position: relative;
          width: 300px;
          height: 300px;
          margin: 20px auto;
        }
        #wheel {
          width: 100%;
          height: 100%;
          transition: transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99);
          transform-origin: center;
        }
        .pointer-wrapper {
          position: absolute;
          top: -20px;
          left: 50%;
          transform: translateX(-50%);
          z-index: 10;
        }
        #pointer {
          width: 0;
          height: 0;
          border-left: 15px solid transparent;
          border-right: 15px solid transparent;
          border-top: 30px solid #FF3333;
          position: relative;
        }
        .pointer-tip {
          position: absolute;
          bottom: -25px;
          left: -5px;
          width: 10px;
          height: 30px;
          background: #FF3333;
          border-radius: 5px;
        }
        .wheel-segments {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
        }
        .wheel-segment {
          position: absolute;
          width: 50%;
          height: 50%;
          transform-origin: 100% 100%;
          border-radius: 0 100% 0 0;
        }
        .segment-1 { background: #FF0055; transform: rotate(0deg); }
        .segment-2 { background: #FF5C5C; transform: rotate(60deg); }
        .segment-3 { background: #FFCC00; transform: rotate(120deg); }
        .segment-4 { background: #00FF55; transform: rotate(180deg); }
        .segment-5 { background: #00CCFF; transform: rotate(240deg); }
        .segment-6 { background: #8000FF; transform: rotate(300deg); }
        
        .wheel-labels {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
        }
        .wheel-label {
          position: absolute;
          left: 70%;
          top: 10%;
          transform-origin: 0% 200%;
          color: white;
          font-weight: bold;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
          font-size: 14px;
        }
        .label-1 { transform: rotate(30deg); }
        .label-2 { transform: rotate(90deg); }
        .label-3 { transform: rotate(150deg); }
        .label-4 { transform: rotate(210deg); }
        .label-5 { transform: rotate(270deg); }
        .label-6 { transform: rotate(330deg); }
        
        .wheel-center {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 40px;
          height: 40px;
          background: gold;
          border: 3px solid #333;
          border-radius: 50%;
          z-index: 5;
        }
      `;
      document.head.appendChild(style);
    }
  },
  
  spinWheel: async function () {
    if (App.isProcessing) return;
    App.isProcessing = true;
    
    const button = document.getElementById('spin-button');
    const wheel = document.getElementById('wheel');
    const msgEl = document.getElementById('spin-message');
    const resultEl = document.getElementById('spin-result');
    
    if (!button || !wheel || button.disabled) {
      App.isProcessing = false;
      return;
    }
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    msgEl.textContent = '';
    msgEl.className = 'message';
    resultEl.classList.add('hidden');
    
    // Prize array (matching wheel order from top clockwise)
    const prizes = [1000, 500, 200, 100, 50, 0];
    const prizeIndex = Math.floor(Math.random() * prizes.length);
    const reward = prizes[prizeIndex];
    
    // Calculate rotation
    const degreesPerSegment = 60; // 6 segments = 60° each
    const targetAngle = prizeIndex * degreesPerSegment;
    const randomOffset = (Math.random() - 0.5) * 30; // Random within segment
    
    // Full spins + target position
    const fullSpins = 5 + Math.floor(Math.random() * 3);
    const totalRotation = (fullSpins * 360) + (360 - targetAngle + randomOffset);
    
    // Apply spin animation
    wheel.style.transition = 'transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
    wheel.style.transform = `rotate(${totalRotation}deg)`;
    
    try {
      const res = await fetch('/api/games/spin/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ reward })
      });
      
      const data = await res.json();
      
      // Show result after animation completes
      setTimeout(() => {
        if (data.success) {
          // Update balance
          if (App.currentUser) {
            App.currentUser.balance = data.new_balance;
            App.refreshBalance();
          }
          
          // Show result message
          const resultMsg = reward > 0 
            ? `🎉 Congratulations! You won ₦${reward.toLocaleString()}!`
            : `😢 Better luck tomorrow!`;
          
          msgEl.textContent = resultMsg;
          msgEl.className = reward > 0 ? 'message success' : 'message warning';
          
          resultEl.innerHTML = `<p style="font-size: 1.1rem; font-weight: bold; margin: 0;">${resultMsg}</p>`;
          resultEl.classList.remove('hidden');
          
          button.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
          
          if (reward > 0) {
            App.showMessage(`🎉 Spin wheel reward: ₦${reward.toLocaleString()}!`, 'success');
          }
        } else {
          // Error from backend
          msgEl.textContent = data.message || 'Spin failed. Please try again.';
          msgEl.className = 'message error';
          button.disabled = false;
          button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
          App.showMessage(data.message || 'Spin failed', 'error');
        }
        App.isProcessing = false;
      }, 4200);
      
    } catch (err) {
      console.error('Spin error:', err);
      setTimeout(() => {
        msgEl.textContent = 'Network error. Please try again later.';
        msgEl.className = 'message error';
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        App.showMessage('Network error. Please try again.', 'error');
        App.isProcessing = false;
      }, 4200);
    }
  }
};

//========== SETTINGS & LOGOUT =========
const Settings = {
  open: async function () {
    if (!App.currentUser) return;
    
    try {
      const res = await fetch('/api/user/profile', { credentials: 'include' });
      const data = await res.json();
      if (!data.success) {
        App.showMessage('Failed to load settings', 'error');
        return;
      }
      
      const user = data.user;
      const hasPin = !!user.withdrawal_pin;
      
      let html = `
        <div class="settings-container">
          <div class="settings-section">
            <h4>Account Info</h4>
            <p><strong>Username:</strong> ${user.username}</p>
            <p><strong>Balance:</strong> ₦${user.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
            <p><strong>Joined:</strong> ${new Date(user.created_at).toLocaleDateString()}</p>
          </div>
          
          <div class="settings-section">
            <h4>Security</h4>
            <button class="settings-btn" onclick="Settings.${hasPin ? 'changeWithdrawalPin' : 'setWithdrawalPin'}()">
              <i class="fas fa-lock"></i> ${hasPin ? 'Change' : 'Set'} Withdrawal PIN
            </button>
      `;
      
      if (user.is_admin) {
        html += `
            <button class="settings-btn" onclick="Settings.changePassword()">
              <i class="fas fa-key"></i> Change Password
            </button>
        `;
      }
      
      html += `
          </div>
          
          <div class="settings-section">
            <h4>Appearance</h4>
            <button class="settings-btn" onclick="App.toggleTheme()">
              <i class="fas fa-moon"></i> ${document.body.classList.contains('dark-mode') ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            </button>
          </div>
          
          <div class="settings-section">
            <h4>Community</h4>
      `;
      
      // Load social links
      try {
        const socialRes = await fetch('/api/admin/settings');
        const socialData = await socialRes.json();
        if (socialData.success) {
          const s = socialData.settings;
          if (s.whatsapp_link) html += `
            <a href="${s.whatsapp_link}" target="_blank" class="social-link">
              <i class="fab fa-whatsapp"></i> WhatsApp Group
            </a>`;
          if (s.telegram_link) html += `
            <a href="${s.telegram_link}" target="_blank" class="social-link">
              <i class="fab fa-telegram"></i> Telegram Group
            </a>`;
          if (s.facebook_link) html += `
            <a href="${s.facebook_link}" target="_blank" class="social-link">
              <i class="fab fa-facebook"></i> Facebook Group
            </a>`;
          if (!(s.whatsapp_link || s.telegram_link || s.facebook_link)) {
            html += `<p class="no-links">No social links configured yet</p>`;
          }
        }
      } catch (e) {
        console.error('Social links error:', e);
      }
      
      html += `
          </div>
          
          <div class="settings-section danger-zone">
            <h4>Danger Zone</h4>
            <button class="settings-btn danger" onclick="Settings.logout()">
              <i class="fas fa-sign-out-alt"></i> Logout
            </button>
          </div>
        </div>
        
        <style>
          .settings-container {
            max-height: 60vh;
            overflow-y: auto;
            padding-right: 10px;
          }
          .settings-section {
            background: rgba(30,30,69,0.5);
            border: 1px solid #8000FF;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
          }
          .settings-section h4 {
            color: #00CCFF;
            margin-bottom: 10px;
            font-size: 1rem;
            border-bottom: 1px solid rgba(128,0,255,0.3);
            padding-bottom: 5px;
          }
          .settings-btn {
            display: block;
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            background: rgba(128,0,255,0.2);
            border: 1px solid #8000FF;
            color: #E0E0FF;
            border-radius: 8px;
            text-align: left;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
          }
          .settings-btn:hover {
            background: rgba(128,0,255,0.4);
            transform: translateY(-2px);
          }
          .settings-btn i {
            margin-right: 10px;
            width: 20px;
            text-align: center;
          }
          .settings-btn.danger {
            background: rgba(255,0,0,0.2);
            border-color: #FF3333;
            color: #FFAAAA;
          }
          .settings-btn.danger:hover {
            background: rgba(255,0,0,0.4);
          }
          .social-link {
            display: block;
            padding: 10px;
            margin: 5px 0;
            background: rgba(30,69,30,0.3);
            border: 1px solid #00CC66;
            border-radius: 8px;
            color: #00CC66;
            text-decoration: none;
            transition: all 0.3s;
          }
          .social-link:hover {
            background: rgba(0,255,85,0.2);
            transform: translateY(-2px);
          }
          .social-link i {
            margin-right: 10px;
          }
          .no-links {
            color: #A0A0B5;
            font-style: italic;
            padding: 10px;
            text-align: center;
          }
          .danger-zone {
            border-color: #FF3333;
          }
        </style>
      `;
      
      document.getElementById('settings-data').innerHTML = html;
      App.showModal('settings-modal');
    } catch (err) {
      console.error('Settings error:', err);
      App.showMessage('Failed to load settings', 'error');
    }
  },
  
  setWithdrawalPin: async function (isChange = false) {
    if (App.isProcessing) return;
    
    let currentPin = '';
    if (isChange) {
      currentPin = prompt('Enter your CURRENT 4-6 digit Withdrawal PIN:');
      if (!currentPin || !/^\d{4,6}$/.test(currentPin)) {
        App.showMessage('Current PIN must be 4-6 digits', 'error');
        return;
      }
      
      // Verify current PIN
      try {
        const verifyRes = await fetch('/api/user/verify-withdrawal-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ pin: currentPin })
        });
        const verifyData = await verifyRes.json();
        if (!verifyData.success) {
          App.showMessage('Incorrect current PIN', 'error');
          return;
        }
      } catch (err) {
        App.showMessage('Failed to verify PIN', 'error');
        return;
      }
    }
    
    const newPin = prompt('Enter your NEW 4-6 digit Withdrawal PIN:');
    if (!newPin || !/^\d{4,6}$/.test(newPin)) {
      App.showMessage('New PIN must be 4-6 digits', 'error');
      return;
    }
    
    const confirmPin = prompt('Confirm your new PIN:');
    if (newPin !== confirmPin) {
      App.showMessage('PINs do not match', 'error');
      return;
    }
    
    App.isProcessing = true;
    try {
      const res = await fetch('/api/user/set-withdrawal-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ pin: newPin })
      });
      const data = await res.json();
      App.showMessage(data.message, data.success ? 'success' : 'error');
      if (data.success) {
        App.closeModal('settings-modal');
      }
    } catch (err) {
      App.showMessage('Failed to set PIN', 'error');
    } finally {
      App.isProcessing = false;
    }
  },
  
  changeWithdrawalPin: function () {
    this.setWithdrawalPin(true);
  },
  
  changePassword: async function () {
    if (App.isProcessing) return;
    
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
    
    App.isProcessing = true;
    try {
      const res = await fetch('/api/user/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ old_password: oldPass, new_password: newPass })
      });
      const data = await res.json();
      App.showMessage(data.message, data.success ? 'success' : 'error');
      if (data.success) {
        App.closeModal('settings-modal');
      }
    } catch (err) {
      App.showMessage('Failed to change password', 'error');
    } finally {
      App.isProcessing = false;
    }
  },
  
  logout: async function () {
    if (confirm('Are you sure you want to logout?')) {
      try {
        await fetch('/api/auth/logout', { 
          method: 'POST', 
          credentials: 'include' 
        });
      } catch (e) {
        console.warn('Logout endpoint failed');
      }
      
      // Clear cookies
      document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
        (window.location.protocol === 'https:' ? '; secure' : '');
      
      // Redirect to home
      window.location.href = '/';
    }
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
  
  // Enter key for login
  document.getElementById('login-password')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') Auth.login();
  });
  
  // Enter key for registration
  document.getElementById('reg-coupon')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') Auth.register();
  });
  
  // Initialize app
  App.init();
  
  // Check for referral code in URL
  const urlParams = new URLSearchParams(window.location.search);
  const refCode = urlParams.get('ref');
  if (refCode && document.getElementById('reg-referral')) {
    document.getElementById('reg-referral').value = refCode;
  }
});

//========== GLOBAL ERROR HANDLER ===========
window.addEventListener('error', function(e) {
  console.error('Global error:', e.error);
  // Don't show alert for all errors, just log them
});

// Prevent F5 refresh on modals
document.addEventListener('keydown', function(e) {
  if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
    const modals = document.querySelectorAll('.modal:not(.hidden)');
    if (modals.length > 0) {
      e.preventDefault();
      App.showMessage('Please close the modal before refreshing', 'info');
    }
  }
});

// Auto-refresh balance every 30 seconds
setInterval(() => {
  if (App.currentUser) {
    fetch('/api/user/profile', { credentials: 'include' })
      .then(r => r.json())
      .then(data => {
        if (data.success && App.currentUser) {
          const oldBalance = App.currentUser.balance;
          App.currentUser = data.user;
          if (oldBalance !== data.user.balance) {
            App.refreshBalance();
            if (data.user.balance > oldBalance) {
              App.showMessage(`Balance updated! New: ₦${data.user.balance.toLocaleString()}`, 'success');
            }
          }
        }
      })
      .catch(() => {}); // Silent fail
  }
}, 30000);

// Export for debugging
window.App = App;
window.Auth = Auth;
window.Profile = Profile;
window.Referral = Referral;
window.Banking = Banking;
window.Games = Games;
window.Settings = Settings;
