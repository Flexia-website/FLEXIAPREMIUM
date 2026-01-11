// script.js - FLEXIA Frontend Logic v12.0 - FIXED VERSION
// ✅ ALL GLOBAL FUNCTIONS WORKING ✅ NO BACKEND CHANGES NEEDED

//========== CONFIGURATION========
const CONFIG = {
  MIN_WITHDRAWAL: 100000,
  REFERRAL_BONUS: 7500,
  TIKTOK_REWARD: 150,
  SNAKE_REWARD: 200,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100,
  CLAIM_COOLDOWN: 1000
};

//========== CORE APP==========
const App = {
  currentUser: null,
  balanceVisible: true,
  lastBalanceUpdate: 0,
  
  init: async function () {
    await this.checkAuth();
    if (document.getElementById('app-screen')) {
      await Profile.load();
      await Banking.loadBanks();
      this.setupTheme();
    }
  },
  
  checkAuth: async function () {
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
  },
  
  closeModal: function (modalId) {
    document.getElementById(modalId).classList.add('hidden');
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

//========== AUTHENTICATION========
const Auth = {
  login: async function () {
    const identifier = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');
    
    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
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
    } catch (error) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
    }
  },
  
  register: async function () {
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    const coupon = document.getElementById('reg-coupon').value.trim().toUpperCase();
    const referral = document.getElementById('reg-referral').value.trim();
    const contact = document.getElementById('reg-contact')?.value.trim() || '';
    const messageEl = document.getElementById('register-message');
    
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
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').value = password;
        document.querySelector('.tab[data-tab="login"]').click();
      }
    } catch (error) {
      messageEl.textContent = 'Network error. Please try again.';
      messageEl.className = 'message error';
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

//========== PROFILE=========
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
            <button class="btn-primary" onclick="Profile.setProfilePicture()" 
                    style="margin-top:10px;">
              <i class="fas fa-upload"></i> Update Picture
            </button>
        `;
        
        if (data.user.profile_picture) {
          html += `
            <div style="margin-top:15px;text-align:center;">
              <img src="${data.user.profile_picture}" 
                   style="width:100px;height:100px;border-radius:15px;border:3px solid #8000FF;">
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
    }
  }
};

//========== REFERRALS========
const Referral = {
  open: async function () {
    if (!App.currentUser) return;
    
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
    }
  }
};

//========== BANKING & WITHDRAWALS=========
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
    const userRes = await fetch('/api/user/profile');
    const userData = await userRes.json();
    if (!userData.success) {
      App.showMessage('Session expired. Please log in again.', 'error');
      return;
    }
    
    const user = userData.user;
    if (!user.withdrawal_pin) {
      App.showMessage('You must set a withdrawal PIN before cashing out.', 'info');
      Settings.setWithdrawalPin();
      return;
    }
    
    const amount = parseFloat(document.getElementById('withdraw-amount').value);
    const bankCode = document.getElementById('bank-select').value;
    const accountNumber = document.getElementById('account-number').value.trim();
    const accountName = document.getElementById('account-name-manual').value.trim();
    
    if (!amount || amount < CONFIG.MIN_WITHDRAWAL) {
      App.showMessage(`Minimum withdrawal: ₦${CONFIG.MIN_WITHDRAWAL.toLocaleString()}`, 'error');
      return;
    }
    
    if (amount > user.balance) {
      App.showMessage('Insufficient balance.', 'error');
      return;
    }
    
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      App.showMessage('Invalid bank details.', 'error');
      return;
    }
    
    const pin = prompt('Enter your 4–6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required.', 'error');
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
    }
  }
};

//========== ACHIEVEMENTS =========
const Achievements = {
  open: async function () {
    if (!App.currentUser) return;
    
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
    }
  },
  
  claimAllRewards: async function () {
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
    }
  },
  
  verifyTikTokFollow: async function () {
    const msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = 'Claiming reward...';
    msgEl.className = 'message';
    
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
    
    setTimeout(() => initSpinWheel(), 150);
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
    
    const prizes = [1000, 500, 200, 100, 50, 0];
    const prizeIndex = Math.floor(Math.random() * prizes.length);
    const reward = prizes[prizeIndex];
    
    const degreesPerSegment = 60;
    const targetAngle = prizeIndex * degreesPerSegment;
    const randomOffset = (Math.random() - 0.5) * 30;
    
    const fullSpins = 5 + Math.floor(Math.random() * 3);
    const totalRotation = (fullSpins * 360) + (360 - targetAngle + randomOffset);
    
    wheel.style.transition = 'transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
    wheel.style.transform = `rotate(${totalRotation}deg)`;
    
    try {
      const result = await this.reportSpin(reward);
      
      setTimeout(() => {
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
            resultEl.innerHTML = `<p style="font-size: 1.1rem; font-weight: bold;">${resultMsg}</p>`;
            resultEl.classList.remove('hidden');
          }
          
          button.innerHTML = '<i class="fas fa-check"></i> COME BACK TOMORROW';
          
          if (reward > 0) {
            App.showMessage(`✅ Spin wheel: Won ₦${reward.toLocaleString()}!`, 'success');
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
      }, 4200);
      
    } catch (err) {
      console.error('Spin error:', err);
      setTimeout(() => {
        if (msgEl) {
          msgEl.textContent = 'Network error. Please try again later.';
          msgEl.className = 'message error';
        }
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
        App.showMessage('Network error during spin', 'error');
      }, 4200);
    }
  }
};

// ==================== SPIN WHEEL FUNCTIONS ====================
function initSpinWheel() {
  const wheel = document.getElementById('wheel');
  if (!wheel) return;
  
  wheel.innerHTML = '';
  
  const segments = [
    { class: 'segment-1', color: '#FF0055' },
    { class: 'segment-2', color: '#FF5C5C' },
    { class: 'segment-3', color: '#FFCC00' },
    { class: 'segment-4', color: '#00FF55' },
    { class: 'segment-5', color: '#00CCFF' },
    { class: 'segment-6', color: '#8000FF' }
  ];
  
  segments.forEach(seg => {
    const div = document.createElement('div');
    div.className = `wheel-segment ${seg.class}`;
    wheel.appendChild(div);
  });
  
  const labelsDiv = document.createElement('div');
  labelsDiv.className = 'wheel-labels';
  
  const labels = ['₦1000', '₦500', '₦200', '₦100', '₦50', 'TRY AGAIN'];
  labels.forEach((label, index) => {
    const labelDiv = document.createElement('div');
    labelDiv.className = `wheel-label label-${index + 1}`;
    labelDiv.textContent = label;
    labelDiv.style.setProperty('--rotation', index * 60);
    labelsDiv.appendChild(labelDiv);
  });
  
  wheel.appendChild(labelsDiv);
  
  const center = document.createElement('div');
  center.className = 'wheel-center';
  wheel.appendChild(center);
}

// Auto-initialize when modal opens
document.addEventListener('DOMContentLoaded', function() {
  const spinModal = document.getElementById('spin-modal');
  if (spinModal) {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          const isVisible = !spinModal.classList.contains('hidden');
          if (isVisible) {
            setTimeout(() => initSpinWheel(), 100);
          }
        }
      });
    });
    
    observer.observe(spinModal, { 
      attributes: true, 
      attributeFilter: ['class'] 
    });
  }
});

//========== SETTINGS & LOGOUT =========
const Settings = {
  open: async function () {
    if (!App.currentUser) return;
    
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
          <p><strong>Username:</strong> ${user.username}</p>
          <p><strong>Balance:</strong> ₦${user.balance.toLocaleString()}</p>
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
    }
  },
  
  logout: async function () {
    if (!confirm('Are you sure you want to logout?')) return;
    
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
    
    window.location.href = '/';
  }
};

//========== DOM READY ===========
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
      tab.classList.add('active');
      const targetForm = tab.dataset.tab + '-form';
      document.getElementById(targetForm).classList.add('active');
    });
  });
  
  const buyCouponBtn = document.querySelector('[onclick="Auth.buyCoupon()"]');
  if (buyCouponBtn) {
    buyCouponBtn.onclick = () => Auth.buyCoupon();
  }
  
  App.init();
});

// ==================== GLOBAL FUNCTIONS FOR GAME PAGES ====================
// FIXED VERSION - ALL FUNCTIONS PROPERLY EXPORTED
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
    window.goBackToDashboard = () => window.location.href = 'index.html';
    
    // Game claim functions (DIRECT API CALLS)
    window.claimSnakeReward = async function(apples) {
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
    };
    
    window.claimCoinFlipReward = async function(bet, won) {
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
    };
    
    window.claimPlinkoReward = async function(bet, multiplier) {
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
        }
    };
    
    console.log('✅ FLEXIA Script v12.0 - ALL FUNCTIONS LOADED');
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
