// ================================
// FLEXIA Frontend Logic v10.9 — FULLY COMPLETE
// ✅ TikTok Daily ✅ Fixed Registration ✅ Fixed Spin Wheel
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
    alert(text);
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
    const identifier = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');
    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
      return;
    }
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
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const phoneRegex = /^234\d{10}$/;
    if (contact && !emailRegex.test(contact) && !phoneRegex.test(contact)) {
      messageEl.textContent = 'Contact must be valid email or Nigerian phone (234...)';
      messageEl.className = 'message error';
      return;
    }
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
  },
  buyCoupon: async function () {
    try {
      const res = await fetch('/api/coupon/whatsapp-numbers');
      const data = await res.json();
      const number = (data.success && data.number) ? data.number.trim() : '2348160881049';
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
        const stats = data.user.game_stats || {};
        let html = `
          <p><strong>Username:</strong> ${data.user.username}</p>
          <p><strong>Balance:</strong> ₦${data.user.balance.toLocaleString()}</p>
          <p><strong>Referral Code:</strong> ${data.user.referral_code}</p>
          <p><strong>Joined:</strong> ${new Date(data.user.created_at).toLocaleDateString()}</p>
          <p><strong>Snake High Score:</strong> ${stats.snake?.high_score || 0}</p>
          <p><strong>Coin Flip Wins:</strong> ${stats.coin_flip?.wins || 0}</p>
          <p><strong>Plinko Total Wins:</strong> ${stats.plinko?.total_wins || 0}</p>
        `;
        html += `
          <p><strong>Profile Picture</strong></p>
          <input type="text" id="profile-pic-url" placeholder="Enter image URL" style="width:100%;padding:8px;margin:5px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:4px;">
          <button class="btn-primary" onclick="Profile.setProfilePicture()">Update Picture</button>
          ${data.user.profile_picture ? `<img src="${data.user.profile_picture}" style="width:80px;height:80px;border-radius:10px;margin-top:10px;">` : ''}
        `;
        document.getElementById('profile-data').innerHTML = html;
      }
    } catch (err) {
      console.error('Failed to load profile', err);
      document.getElementById('profile-data').innerHTML = '<p>Failed to load profile.</p>';
    }
  },
  setProfilePicture: async function () {
    const url = document.getElementById('profile-pic-url').value.trim();
    if (!url) return;
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
      App.showMessage('Failed to update picture', 'error');
    }
  }
};

//========== REFERRALS========
const Referral = {
  open: async function () {
    if (!App.currentUser) return;
    const res = await fetch('/api/user/profile');
    const data = await res.json();
    if (data.success) {
      const unclaimed = data.referrals.unclaimed_bonus;
      const html = `
        <p><strong>Your Referral Code:</strong> <strong>${data.user.referral_code}</strong></p>
        <p>Share this code to earn ₦${CONFIG.REFERRAL_BONUS.toLocaleString()} per friend!</p>
        <p><strong>Referred Users:</strong> ${data.referrals.count}</p>
        <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
        ${unclaimed > 0
          ? `<button class="btn-primary" onclick="Referral.claimBonuses()">Claim Now</button>`
          : '<p>All bonuses claimed!</p>'
        }
      `;
      document.getElementById('referral-data').innerHTML = html;
      App.showModal('referral-modal');
    }
  },
  claimBonuses: async function () {
    const res = await fetch('/api/referral/claim', {
      method: 'POST',
      credentials: 'include'
    });
    const data = await res.json();
    if (!data.success) {
      App.showMessage(data.message, 'error');
      return;
    }
    App.showMessage(`₦${data.claimed.toLocaleString()} referral bonus claimed!`, 'success');
    App.currentUser.balance = data.new_balance;
    App.refreshBalance();
    Referral.open();
  }
};

//========== BANKING & WITHDRAWALS=========
const Banking = {
  banks: [],
  async loadBanks() {
    const res = await fetch('/api/admin/banks');
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
    }
  },
  openWithdraw: function () {
    if (!App.currentUser) return;
    document.getElementById('withdrawal-message').textContent = '';
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
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      App.showMessage('Invalid bank details.', 'error');
      return;
    }
    const pin = prompt('Enter your 4–6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required.', 'error');
      return;
    }
    const res = await fetch('/api/banking/withdraw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount, bank_code: bankCode, account_number: accountNumber, account_name: accountName, pin }),
      credentials: 'include'
    });
    const data = await res.json();
    const msgEl = document.getElementById('withdrawal-message');
    msgEl.textContent = data.message;
    msgEl.className = data.success ? 'message success' : 'message error';
    if (data.success) {
      App.currentUser.balance = data.new_balance;
      App.refreshBalance();
      App.showMessage('✅ Withdrawal submitted for manual review!', 'success');
      App.closeModal('withdrawal-modal');
    }
  }
};

//========== GAMES & TIKTOK DAILY =========
const Games = {
  openSnake: () => window.location.href = 'snake.html',
  openCoinFlip: () => window.location.href = 'coin-flip.html',
  openPlinko: () => window.location.href = 'plinko.html',
  
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
        setTimeout(() => App.closeModal('tiktok-modal'), 2000);
      } else {
        msgEl.textContent = data.message || 'Failed to claim reward.';
        msgEl.className = 'message error';
      }
    } catch (err) {
      console.error('TikTok claim error:', err);
      msgEl.textContent = 'Network error. Please try again.';
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
  
  // ✅ PERFECT: Spin Wheel Function
  openSpinWheel: function () {
    if (!App.currentUser) return;
    
    // Reset wheel position
    const wheel = document.getElementById('wheel');
    if (wheel) {
      wheel.style.transition = 'none';
      wheel.style.transform = 'rotate(0deg)';
    }
    
    document.getElementById('spin-result').classList.add('hidden');
    document.getElementById('spin-message').textContent = '';
    const button = document.getElementById('spin-button');
    if (button) button.disabled = false;
    
    App.showModal('spin-modal');
    
    // Initialize wheel if not already done
    setTimeout(() => {
      if (!document.getElementById('wheel').querySelector('.wheel-segments')) {
        initSpinWheel();
      }
    }, 100);
  },
  
  // ✅ PERFECT: Spin Wheel Logic
  spinWheel: async function () {
    const button = document.getElementById('spin-button');
    const wheel = document.getElementById('wheel');
    if (button.disabled || !wheel) return;
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    
    // Prizes in order (clockwise from top)
    const prizes = [1000, 500, 200, 100, 50, 0];
    const segmentAngle = 360 / prizes.length; // 60 degrees
    
    // Randomly select a prize
    const prizeIndex = Math.floor(Math.random() * prizes.length);
    const reward = prizes[prizeIndex];
    
    // Calculate rotation to land on selected segment
    // Each segment is 60°, we want to land in the middle (30° offset)
    const targetAngle = (prizeIndex * segmentAngle) + (segmentAngle / 2);
    
    // Add 5 full rotations plus the target angle
    const rotations = 5;
    const totalDegrees = (rotations * 360) + (360 - targetAngle) + 180; // +180 to land at pointer
    
    // Apply the rotation
    wheel.style.transition = 'transform 4s cubic-bezier(0.2, 0.8, 0.4, 1)';
    wheel.style.transform = `rotate(${totalDegrees}deg)`;
    
    // Report to backend
    const res = await fetch('/api/games/spin/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reward })
    });
    
    const data = await res.json();
    
    setTimeout(() => {
      const msgEl = document.getElementById('spin-message');
      if (data.success) {
        App.currentUser.balance = data.new_balance;
        App.refreshBalance();
        msgEl.textContent = `🎉 You won ₦${data.reward.toLocaleString()}!`;
        msgEl.className = 'message success';
      } else {
        msgEl.textContent = data.message || 'Spin failed.';
        msgEl.className = 'message error';
      }
      
      document.getElementById('spin-result').innerHTML = `<p>${msgEl.textContent}</p>`;
      document.getElementById('spin-result').classList.remove('hidden');
      button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN AGAIN (Tomorrow)';
    }, 4100);
  }
};

//========== SETTINGS & LOGOUT =========
const Settings = {
  open: async function () {
    if (!App.currentUser) return;
    const res = await fetch('/api/user/profile');
    const data = await res.json();
    if (!data.success) {
      App.showMessage('Failed to load settings', 'error');
      return;
    }
    const user = data.user;
    const hasPin = !!user.withdrawal_pin;
    let html = `
      <p><strong>Account Settings</strong></p>
      <p><strong>Username:</strong> ${user.username}</p>
      <p><strong>Balance:</strong> ₦${user.balance.toLocaleString()}</p>
    `;
    const socialRes = await fetch('/api/admin/settings');
    const socialData = await socialRes.json();
    if (socialData.success) {
      const s = socialData.settings;
      html += `<p><strong>Join Our Community</strong></p>`;
      if (s.whatsapp_link) html += `<a href="${s.whatsapp_link}" target="_blank" class="social-link"><i class="fab fa-whatsapp"></i> WhatsApp Group</a><br>`;
      if (s.telegram_link) html += `<a href="${s.telegram_link}" target="_blank" class="social-link"><i class="fab fa-telegram"></i> Telegram Group</a><br>`;
      if (s.facebook_link) html += `<a href="${s.facebook_link}" target="_blank" class="social-link"><i class="fab fa-facebook"></i> Facebook Group</a><br>`;
      if (!(s.whatsapp_link || s.telegram_link || s.facebook_link)) {
        html += `<p class="small-text">No social links configured yet</p>`;
      }
      html += `<br>`;
    }
    if (user.is_admin) {
      html += `<button class="btn-primary" onclick="Settings.changePassword()">🔐 Change Password</button><br><br>`;
    }
    html += `
      <button class="btn-primary" onclick="Settings.${hasPin ? 'changeWithdrawalPin' : 'setWithdrawalPin'}()">
        ${hasPin ? 'Change' : 'Set'} Withdrawal PIN
      </button><br><br>
      <button class="btn-primary" onclick="App.toggleTheme()">
        🌙 ${document.body.classList.contains('dark-mode') ? 'Day Mode' : 'Night Mode'}
      </button><br><br>
      <button class="btn-primary" style="background:#d32f2f;" onclick="Settings.logout()">🚪 Logout</button>
    `;
    document.getElementById('settings-data').innerHTML = html;
    const style = document.createElement('style');
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
      .small-text {
        font-size: 0.8rem;
        color: #A0A0B5;
        margin: 10px 0;
      }
    `;
    if (!document.getElementById('social-style')) {
      style.id = 'social-style';
      document.head.appendChild(style);
    }
    App.showModal('settings-modal');
  },
  setWithdrawalPin: async function (isChange = false) {
    let pin = prompt(`${isChange ? 'Enter your CURRENT' : 'Create a'} 4-6 digit Withdrawal PIN:`);
    if (!pin) return;
    if (!/^\d{4,6}$/.test(pin)) {
      App.showMessage('PIN must be 4 to 6 digits.', 'error');
      return;
    }
    if (isChange) {
      const verifyRes = await fetch('/api/user/verify-withdrawal-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
        credentials: 'include'
      });
      const verifyData = await verifyRes.json();
      if (!verifyData.success) {
        App.showMessage('Incorrect current PIN.', 'error');
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
    const res = await fetch('/api/user/set-withdrawal-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: newPin }),
      credentials: 'include'
    });
    const data = await res.json();
    App.showMessage(data.message, data.success ? 'success' : 'error');
    if (data.success) {
      App.closeModal('settings-modal');
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
    const res = await fetch('/api/user/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPass, new_password: newPass }),
      credentials: 'include'
    });
    const data = await res.json();
    App.showMessage(data.message, data.success ? 'success' : 'error');
    if (data.success) {
      App.closeModal('settings-modal');
    }
  },
  logout: async function () {
    try {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) {
      console.warn('Logout endpoint failed — using fallback');
    }
    document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax' +
      (window.location.protocol === 'https:' ? '; secure' : '');
    window.location.href = '/';
  }
};

// ✅ PERFECT: SPIN WHEEL INITIALIZATION
function initSpinWheel() {
  const wheel = document.getElementById('wheel');
  if (!wheel) return;
  
  // Clear existing segments
  const existingSegments = wheel.querySelector('.wheel-segments');
  if (existingSegments) {
    existingSegments.remove();
  }
  
  const prizes = [1000, 500, 200, 100, 50, 0];
  const labels = ['₦1000', '₦500', '₦200', '₦100', '₦50', 'TRY AGAIN'];
  
  // Create segments container
  const segmentsContainer = document.createElement('div');
  segmentsContainer.className = 'wheel-segments';
  
  // Create each segment with perfectly positioned text
  for (let i = 0; i < prizes.length; i++) {
    const segment = document.createElement('div');
    segment.className = 'wheel-segment';
    
    const text = document.createElement('div');
    text.className = 'segment-text';
    text.textContent = labels[i];
    
    segment.appendChild(text);
    segmentsContainer.appendChild(segment);
  }
  
  wheel.appendChild(segmentsContainer);
}

// Add to Games object
const GamesSpinWheel = {
  // ✅ PERFECT: Open Spin Wheel Modal
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
    
    document.getElementById('spin-result').classList.add('hidden');
    document.getElementById('spin-message').textContent = '';
    const button = document.getElementById('spin-button');
    if (button) {
      button.disabled = false;
      button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
    }
    
    App.showModal('spin-modal');
    
    // Initialize wheel after modal is shown
    setTimeout(() => {
      initSpinWheel();
    }, 100);
  },
  
  // ✅ PERFECT: Spin Wheel Logic
  spinWheel: async function () {
    const button = document.getElementById('spin-button');
    const wheel = document.getElementById('wheel');
    const msgEl = document.getElementById('spin-message');
    
    if (!button || !wheel || button.disabled) return;
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
    msgEl.textContent = '';
    msgEl.className = 'message';
    
    // Prizes array matches the wheel segments (clockwise from top)
    // Order: ₦1000 (top), ₦500, ₦200, ₦100, ₦50, Try Again
    const prizes = [1000, 500, 200, 100, 50, 0];
    const segmentAngle = 360 / prizes.length; // 60 degrees per segment
    
    // Randomly select a prize
    const prizeIndex = Math.floor(Math.random() * prizes.length);
    const reward = prizes[prizeIndex];
    
    // Calculate the target angle
    // The wheel starts with ₦1000 at the top (0°)
    // We need to rotate so the selected segment lands at the pointer (top)
    const baseAngle = prizeIndex * segmentAngle;
    
    // Add randomness within the segment (±20 degrees from center)
    const randomOffset = (Math.random() - 0.5) * 40;
    const targetAngle = baseAngle + randomOffset;
    
    // Add multiple full rotations for dramatic effect (5-7 spins)
    const rotations = 5 + Math.floor(Math.random() * 3);
    const totalDegrees = (rotations * 360) + (360 - targetAngle);
    
    // Reset transition and apply rotation
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    
    // Force reflow
    void wheel.offsetWidth;
    
    // Apply the spin
    wheel.style.transition = 'transform 4s cubic-bezier(0.2, 0.8, 0.4, 1)';
    wheel.style.transform = `rotate(${totalDegrees}deg)`;
    
    // Report to backend
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
          App.currentUser.balance = data.new_balance;
          App.refreshBalance();
          msgEl.textContent = reward > 0 
            ? `🎉 Congratulations! You won ₦${reward.toLocaleString()}!`
            : `😢 Better luck tomorrow!`;
          msgEl.className = 'message success';
        } else {
          msgEl.textContent = data.message || 'Spin failed. Please try again.';
          msgEl.className = 'message error';
        }
        
        button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN AGAIN (Tomorrow)';
        document.getElementById('spin-result').innerHTML = `<p>${msgEl.textContent}</p>`;
        document.getElementById('spin-result').classList.remove('hidden');
      }, 4200);
      
    } catch (err) {
      console.error('Spin error:', err);
      setTimeout(() => {
        msgEl.textContent = 'Network error. Please try again.';
        msgEl.className = 'message error';
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
      }, 4200);
    }
  }
};

// Merge spin wheel functions into Games object if it exists
if (typeof Games !== 'undefined') {
  Games.openSpinWheel = GamesSpinWheel.openSpinWheel;
  Games.spinWheel = GamesSpinWheel.spinWheel;
}

// Initialize spin wheel when modal is opened
document.addEventListener('DOMContentLoaded', () => {
  // Initialize when spin modal is opened
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.target.id === 'spin-modal' && 
          !mutation.target.classList.contains('hidden')) {
        setTimeout(() => initSpinWheel(), 100);
      }
    });
  });
  
  const spinModal = document.getElementById('spin-modal');
  if (spinModal) {
    observer.observe(spinModal, { 
      attributes: true, 
      attributeFilter: ['class'] 
    });
  }
});

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

// ==================== FIXED SPIN WHEEL FUNCTIONS ====================
// Replace your existing spin wheel functions with these

function initSpinWheel() {
  const wheel = document.getElementById('wheel');
  if (!wheel) return;
  
  // Clear existing content
  wheel.innerHTML = '';
  
  // Create 6 colored segments
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
  
  // Create labels container
  const labelsDiv = document.createElement('div');
  labelsDiv.className = 'wheel-labels';
  
  // Create 6 labels
  const labels = ['₦1000', '₦500', '₦200', '₦100', '₦50', 'TRY AGAIN'];
  labels.forEach((label, index) => {
    const labelDiv = document.createElement('div');
    labelDiv.className = `wheel-label label-${index + 1}`;
    labelDiv.textContent = label;
    labelDiv.style.setProperty('--rotation', index * 60);
    labelsDiv.appendChild(labelDiv);
  });
  
  wheel.appendChild(labelsDiv);
  
  // Create center hub
  const center = document.createElement('div');
  center.className = 'wheel-center';
  wheel.appendChild(center);
}

// Update Games.openSpinWheel function
Games.openSpinWheel = function() {
  if (!App.currentUser) return;
  
  const wheel = document.getElementById('wheel');
  const button = document.getElementById('spin-button');
  const msgEl = document.getElementById('spin-message');
  const resultEl = document.getElementById('spin-result');
  
  // Reset wheel
  if (wheel) {
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    void wheel.offsetWidth; // Force reflow
  }
  
  // Reset button
  if (button) {
    button.disabled = false;
    button.innerHTML = '<i class="fas fa-sync-alt"></i> SPIN WHEEL';
  }
  
  // Clear messages
  if (msgEl) {
    msgEl.textContent = '';
    msgEl.className = 'message';
  }
  
  if (resultEl) {
    resultEl.classList.add('hidden');
  }
  
  // Show modal
  App.showModal('spin-modal');
  
  // Initialize wheel after modal opens
  setTimeout(() => initSpinWheel(), 150);
};

// Update Games.spinWheel function
Games.spinWheel = async function() {
  const button = document.getElementById('spin-button');
  const wheel = document.getElementById('wheel');
  const msgEl = document.getElementById('spin-message');
  
  if (!button || !wheel || button.disabled) return;
  
  // Disable button
  button.disabled = true;
  button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';
  
  // Clear messages
  if (msgEl) {
    msgEl.textContent = '';
    msgEl.className = 'message';
  }
  
  // Prize array (matching wheel order from top clockwise)
  const prizes = [1000, 500, 200, 100, 50, 0];
  const prizeIndex = Math.floor(Math.random() * prizes.length);
  const reward = prizes[prizeIndex];
  
  // Calculate rotation
  const degreesPerSegment = 60;
  const targetAngle = prizeIndex * degreesPerSegment;
  const randomOffset = (Math.random() - 0.5) * 30; // Random within segment
  
  // Full spins + target position
  const fullSpins = 5 + Math.floor(Math.random() * 3);
  const totalRotation = (fullSpins * 360) + (360 - targetAngle + randomOffset);
  
  // Apply spin animation
  wheel.style.transition = 'transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
  wheel.style.transform = `rotate(${totalRotation}deg)`;
  
  // Send to backend
  try {
    const res = await fetch('/api/games/spin/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ reward })
    });
    
    const data = await res.json();
    
    // Show result after animation
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
      } else {
        // Error from backend
        if (msgEl) {
          msgEl.textContent = data.message || 'Spin failed. Please try again.';
          msgEl.className = 'message error';
        }
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync-alt"></i> TRY AGAIN';
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
    }, 4200);
  }
};

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