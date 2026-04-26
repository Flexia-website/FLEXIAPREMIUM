// script.js - FLEXIA Frontend Logic v14.0 - COMPLETE VERSION
// ✅ ALL FIXES APPLIED ✅ DAILY PLAY LIMITS ✅ AUTO-LOGOUT ✅ WITHDRAWAL DAY CHECK ✅ BEAUTIFUL UI

//========== EMBEDDED CSS ========
const embeddedCSS = `
  /* Password visibility toggle */
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
  
  /* Game button loading states */
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
  
  /* Global messages */
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
  }
  
  .global-message.success {
    border-left-color: #00ff88;
    background: rgba(0, 255, 136, 0.1);
  }
  
  .global-message.error {
    border-left-color: #ff0055;
    background: rgba(255, 0, 85, 0.1);
  }
  
  .global-message.warning {
    border-left-color: #ffaa00;
    background: rgba(255, 170, 0, 0.1);
  }
  
  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(-20px);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
  }
  
  @keyframes slideOut {
    from {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
    to {
      opacity: 0;
      transform: translateX(-50%) translateY(-20px);
    }
  }
  
  /* Social links */
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
  
  /* Settings sections */
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
  
  /* Profile sections */
  .profile-section {
    margin-bottom: 20px;
    padding: 15px;
    background: rgba(30,30,69,0.5);
    border-radius: 8px;
    border-left: 4px solid #8000FF;
  }
  
  .profile-section h4 {
    margin-top: 0;
    color: #8000FF;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .profile-section p {
    margin: 8px 0;
    display: flex;
    justify-content: space-between;
  }
  
  .profile-section strong {
    color: #A0A0B5;
  }
  
  /* Referral sections */
  .referral-section {
    margin-bottom: 25px;
    padding: 20px;
    background: rgba(30,30,69,0.5);
    border-radius: 10px;
    border: 1px solid rgba(128, 0, 255, 0.3);
  }
  
  .referral-section h4 {
    margin-top: 0;
    color: #8000FF;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .referral-section code {
    display: inline-block;
    padding: 5px 10px;
    background: rgba(128, 0, 255, 0.2);
    border-radius: 5px;
    font-family: monospace;
    margin: 10px 0;
  }
  
  /* TikTok display */
  .tiktok-account-display {
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #8000FF;
    border-radius: 10px;
    padding: 15px;
    margin: 15px 0;
    text-align: center;
    font-size: 1.2rem;
  }
  
  /* Spin wheel */
  .wheel-container {
    position: relative;
    width: 300px;
    height: 300px;
    margin: 20px auto;
  }
  
  .wheel {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    position: relative;
    overflow: hidden;
    border: 5px solid #8000FF;
    box-shadow: 0 0 20px rgba(128, 0, 255, 0.5);
  }
  
  .wheel-segment {
    position: absolute;
    width: 50%;
    height: 50%;
    transform-origin: 100% 100%;
    left: 0;
    top: 0;
    border-radius: 0 100% 0 0;
  }
  
  .wheel-segment.segment-1 { background: #FF0055; transform: rotate(0deg); }
  .wheel-segment.segment-2 { background: #FF5C5C; transform: rotate(60deg); }
  .wheel-segment.segment-3 { background: #FFCC00; transform: rotate(120deg); }
  .wheel-segment.segment-4 { background: #00FF55; transform: rotate(180deg); }
  .wheel-segment.segment-5 { background: #00CCFF; transform: rotate(240deg); }
  .wheel-segment.segment-6 { background: #8000FF; transform: rotate(300deg); }
  
  .wheel-center {
    position: absolute;
    width: 50px;
    height: 50px;
    background: white;
    border-radius: 50%;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10;
    border: 5px solid #8000FF;
  }
  
  .wheel-labels {
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
  }
  
  .wheel-label {
    position: absolute;
    left: 50%;
    top: 15%;
    transform: translateX(-50%) rotate(var(--rotation));
    transform-origin: 50% 150px;
    color: white;
    font-weight: bold;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
  }
  
  /* Game limits display */
  .limit-display {
    background: rgba(30,30,69,0.8);
    padding: 10px;
    border-radius: 5px;
    margin: 10px 0;
    border-left: 3px solid #00FF55;
  }
  
  .limit-display.warning {
    border-left-color: #FFAA00;
  }
  
  .limit-display.danger {
    border-left-color: #FF0055;
  }
  
  /* Game Limit Modal Styles */
  .game-limit-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(10px);
  }
  
  .game-limit-modal-content {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 20px;
    padding: 30px;
    max-width: 400px;
    width: 90%;
    border: 2px solid #8000FF;
    box-shadow: 0 20px 40px rgba(128, 0, 255, 0.3);
    text-align: center;
    animation: slideIn 0.4s ease-out;
  }
  
  .game-limit-icon {
    font-size: 4rem;
    margin-bottom: 20px;
    color: #ff4757;
    animation: pulse 2s infinite;
  }
  
  .game-limit-title {
    color: white;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.5rem;
    margin-bottom: 15px;
  }
  
  .game-limit-message {
    background: rgba(255, 71, 87, 0.1);
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
    border: 1px solid rgba(255, 71, 87, 0.3);
  }
  
  .game-limit-text {
    color: #ffb8c6;
    font-size: 1.1rem;
    line-height: 1.5;
    margin-bottom: 15px;
  }
  
  .game-limit-info {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-top: 15px;
    color: #ffcc00;
  }
  
  .game-limit-buttons {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 25px;
  }
  
  .game-limit-btn-ok {
    background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
    color: white;
    border: none;
    padding: 15px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
  }
  
  .game-limit-btn-ok:hover {
    transform: translateY(-2px);
  }
  
  .game-limit-btn-alternative {
    background: transparent;
    color: #00D4FF;
    border: 1px solid #00D4FF;
    padding: 12px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 0.9rem;
  }
  
  .game-limit-btn-alternative:hover {
    background: rgba(0, 212, 255, 0.1);
  }
  
  /* Force Logout Modal Styles */
  .force-logout-modal-content {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 20px;
    padding: 30px;
    max-width: 450px;
    width: 90%;
    border: 2px solid #ff4757;
    box-shadow: 0 20px 40px rgba(255, 71, 87, 0.3);
    text-align: center;
    animation: slideIn 0.4s ease-out;
  }
  
  .force-logout-countdown {
    color: #ff6b6b;
    font-weight: bold;
    font-size: 1.2rem;
    animation: pulse 1s infinite;
  }
  
  /* Withdrawal Day Check Modal */
  .withdrawal-day-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    backdrop-filter: blur(10px);
  }
  
  .withdrawal-day-modal-content {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 20px;
    padding: 30px;
    max-width: 450px;
    width: 90%;
    border: 2px solid #ffcc00;
    box-shadow: 0 20px 40px rgba(255, 204, 0, 0.3);
    text-align: center;
    animation: slideIn 0.4s ease-out;
  }
  
  .withdrawal-day-icon {
    font-size: 4rem;
    margin-bottom: 20px;
  }
  
  .withdrawal-day-icon.allowed {
    color: #00ff88;
  }
  
  .withdrawal-day-icon.not-allowed {
    color: #ff6b6b;
  }
  
  .withdrawal-day-title {
    color: white;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.5rem;
    margin-bottom: 15px;
  }
  
  .withdrawal-day-message {
    background: rgba(255, 204, 0, 0.1);
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
    border: 1px solid rgba(255, 204, 0, 0.3);
  }
  
  .withdrawal-day-text {
    color: #ffd166;
    font-size: 1.1rem;
    line-height: 1.5;
    margin-bottom: 15px;
  }
  
  .withdrawal-day-info {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-top: 15px;
    color: #00D4FF;
  }
  
  .withdrawal-day-days {
    background: rgba(128, 0, 255, 0.2);
    border-radius: 8px;
    padding: 10px;
    margin: 15px 0;
    border: 1px solid #8000FF;
  }
  
  .withdrawal-day-days strong {
    color: #8000FF;
    display: block;
    margin-bottom: 5px;
  }
  
  .withdrawal-day-day {
    display: inline-block;
    padding: 5px 10px;
    margin: 3px;
    background: rgba(128, 0, 255, 0.3);
    border-radius: 5px;
    font-weight: bold;
  }
  
  .withdrawal-day-day.current {
    background: #00ff88;
    color: #000;
  }
  
  .withdrawal-day-buttons {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 25px;
  }
  
  .withdrawal-day-btn-primary {
    background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
    color: white;
    border: none;
    padding: 15px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
  }
  
  .withdrawal-day-btn-primary:hover {
    transform: translateY(-2px);
  }
  
  .withdrawal-day-btn-secondary {
    background: transparent;
    color: #A0A0B5;
    border: 1px solid #A0A0B5;
    padding: 12px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 0.9rem;
  }
  
  .withdrawal-day-btn-secondary:hover {
    background: rgba(160, 160, 181, 0.1);
  }
  
  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-30px) scale(0.9);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
  }
  
  /* Game Card Disabled State */
  .activity-card.disabled {
    opacity: 0.5;
    filter: grayscale(0.7);
    cursor: not-allowed !important;
    position: relative;
  }
  
  .activity-card.disabled::after {
    content: "LIMIT REACHED";
    position: absolute;
    top: 10px;
    right: 10px;
    background: #ff4757;
    color: white;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: bold;
    letter-spacing: 1px;
  }
  
  .activity-card.disabled .card-badge {
    background: #ff4757 !important;
  }
  
  /* PIN Change Modal Styles */
  .pin-change-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10002;
    backdrop-filter: blur(10px);
  }
  
  .pin-change-modal-content {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 20px;
    padding: 30px;
    max-width: 400px;
    width: 90%;
    border: 2px solid #8000FF;
    box-shadow: 0 20px 40px rgba(128, 0, 255, 0.3);
    text-align: center;
    animation: slideIn 0.4s ease-out;
  }
  
  .pin-change-icon {
    font-size: 3rem;
    margin-bottom: 20px;
    color: #8000FF;
  }
  
  .pin-change-title {
    color: white;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.5rem;
    margin-bottom: 20px;
  }
  
  .pin-input-group {
    margin-bottom: 20px;
    text-align: left;
  }
  
  .pin-input-group label {
    display: block;
    color: #A0A0B5;
    margin-bottom: 8px;
    font-size: 0.9rem;
  }
  
  .pin-input {
    width: 100%;
    padding: 12px 15px;
    background: rgba(30, 30, 69, 0.8);
    border: 2px solid #252540;
    border-radius: 10px;
    color: white;
    font-size: 1.1rem;
    font-family: monospace;
    letter-spacing: 3px;
    text-align: center;
  }
  
  .pin-input:focus {
    border-color: #8000FF;
    outline: none;
    box-shadow: 0 0 0 2px rgba(128, 0, 255, 0.2);
  }
  
  .pin-change-buttons {
    display: flex;
    gap: 10px;
    margin-top: 25px;
  }
  
  .pin-change-btn-primary {
    flex: 1;
    background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
    color: white;
    border: none;
    padding: 15px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .pin-change-btn-primary:hover {
    transform: translateY(-2px);
  }
  
  .pin-change-btn-secondary {
    flex: 1;
    background: transparent;
    color: #A0A0B5;
    border: 1px solid #A0A0B5;
    padding: 15px;
    border-radius: 10px;
    font-family: 'Orbitron', sans-serif;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .pin-change-btn-secondary:hover {
    background: rgba(160, 160, 181, 0.1);
  }
`;

// Inject CSS into document
const style = document.createElement('style');
style.textContent = embeddedCSS;
document.head.appendChild(style);

//========== CONFIGURATION ========
const CONFIG = {
  MIN_WITHDRAWAL: 100000,
  REFERRAL_BONUS: 7500,
  TIKTOK_REWARD: 150,
  SNAKE_REWARD: 200,
  COIN_FLIP_MIN_BET: 100,
  PLINKO_MIN_BET: 100,
  CLAIM_COOLDOWN: 2000,
  GAME_DAILY_LIMITS: {
    'snake': 5,
    'coinflip': 2,
    'plinko': 2,
    'spin': 1,
    'tiktok': 1
  }
};

//========== CORE APP ==========
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
      this.setupAutoRefresh();
      this.updateGameCards();
    }
  },
  
  checkAuth: async function () {
    try {
      const response = await this.requestWithTimeout('/api/user/profile');
      const data = await response.json();
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
    if (!force && (now - this.lastBalanceUpdate) < 3000) {
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
    // Remove existing messages
    document.querySelectorAll('.global-message').forEach(el => el.remove());
    
    const messageEl = document.createElement('div');
    messageEl.className = `global-message ${type}`;
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
    
    // Save to backend
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
  },
  
  setupAutoRefresh: function () {
    // Refresh balance every 10 seconds
    setInterval(() => this.refreshBalance(), 10000);
    // Update game cards every 30 seconds
    setInterval(() => this.updateGameCards(), 30000);
  },
  
  async updateGameCards() {
    if (!this.currentUser) return;
    
    const games = [
      { type: 'snake', element: document.querySelector('.activity-card[onclick*="snake.html"]') },
      { type: 'coinflip', element: document.querySelector('.activity-card[onclick*="coinflip.html"]') },
      { type: 'plinko', element: document.querySelector('.activity-card[onclick*="plinko.html"]') }
    ];
    
    for (const game of games) {
      if (!game.element) continue;
      
      try {
        const response = await this.requestWithTimeout(`/api/games/access?game=${game.type}`, {
          credentials: 'include',
          headers: { 'Cache-Control': 'no-cache' }
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            if (data.can_play) {
              game.element.classList.remove('disabled');
              game.element.style.opacity = '1';
              game.element.style.filter = 'none';
              game.element.style.cursor = 'pointer';
              
              // Update badge if exists
              const badge = game.element.querySelector('.card-badge');
              if (badge && data.remaining_plays) {
                badge.textContent = `${data.remaining_plays}/${data.max_plays} left`;
              }
            } else {
              game.element.classList.add('disabled');
              game.element.style.opacity = '0.5';
              game.element.style.filter = 'grayscale(0.7)';
              game.element.style.cursor = 'not-allowed';
              
              const badge = game.element.querySelector('.card-badge');
              if (badge) {
                badge.textContent = `LIMIT REACHED`;
                badge.style.background = '#ff4757';
              }
            }
          }
        }
      } catch (error) {
        console.error(`Failed to update ${game.type} card:`, error);
      }
    }
  },
  
  requestWithTimeout: async function(url, options = {}, timeout = 10000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
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

//========== WITHDRAWAL DAY CHECK FUNCTION ==========
async function checkWithdrawalDay() {
    try {
        const response = await fetch('/api/withdrawal/check-day', {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show notification to user
            const today = new Date().getDate();
            const days = data.custom_withdrawal_days.length > 0 
                ? data.custom_withdrawal_days 
                : data.global_withdrawal_days;
            
            if (!data.can_withdraw) {
                // Show detailed modal
                showWithdrawalDayModal(false, today, days);
                return false;
            } else {
                // Show success modal
                showWithdrawalDayModal(true, today, days);
                return true;
            }
        }
    } catch (error) {
        console.error('Withdrawal day check error:', error);
        // Show error notification
        App.showMessage('⚠️ Unable to check withdrawal day. Please try again.', 'warning', 5000);
        return true; // Allow withdrawal on error
    }
}

function showWithdrawalDayModal(canWithdraw, today, days) {
    // Remove existing modal
    const existingModal = document.getElementById('withdrawal-day-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const isCustom = days && days.length > 0;
    const sortedDays = days ? [...days].sort((a,b) => a-b) : [];
    
    const modal = document.createElement('div');
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
                        ? `You <strong>CAN</strong> withdraw today (Day ${today})!`
                        : `You <strong>cannot</strong> withdraw today (Day ${today}).`
                    }
                </p>
                
                <div class="withdrawal-day-info">
                    <i class="fas fa-calendar-day"></i>
                    <span>Today: Day ${today}</span>
                </div>
                
                ${days && days.length > 0 ? `
                    <div class="withdrawal-day-days">
                        <strong>${isCustom ? 'Your Allowed Withdrawal Days:' : 'Global Allowed Days:'}</strong>
                        <div style="margin-top: 8px;">
                            ${sortedDays.map(day => `
                                <span class="withdrawal-day-day ${day === today ? 'current' : ''}">
                                    Day ${day}${day === today ? ' (Today)' : ''}
                                </span>
                            `).join('')}
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
                
                <button class="withdrawal-day-btn-secondary" onclick="closeWithdrawalDayModal()">
                    Close
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function closeWithdrawalDayModal() {
    const modal = document.getElementById('withdrawal-day-modal');
    if (modal) {
        modal.remove();
    }
}

function getNextAllowedDay(currentDay, allowedDays) {
    if (!allowedDays || allowedDays.length === 0) return 'Unknown';
    
    // Sort days
    const sorted = [...allowedDays].sort((a,b) => a-b);
    
    // Find next day after current
    for (const day of sorted) {
        if (day > currentDay) {
            return `Day ${day}`;
        }
    }
    
    // Wrap around to first day of next month
    return `Day ${sorted[0]} (next month)`;
}

//========== GAME MANAGER WITH LOCKING ==========
const GameManager = {
  lastClaimTime: 0,
  pendingRequests: new Map(),
  
  async checkDailyLimit(gameType) {
    try {
      const response = await App.requestWithTimeout(`/api/games/limit-check?game=${gameType}`, {
        credentials: 'include',
        headers: { 
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
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
  
  async safeClaim(endpoint, data, gameType = 'unknown') {
    if (this.pendingRequests.has(gameType)) {
      console.warn(`Already claiming ${gameType}, ignoring duplicate`);
      return { 
        success: false, 
        message: "Please wait for the current claim to complete" 
      };
    }
    
    this.pendingRequests.set(gameType, true);
    
    try {
      const response = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Request-ID': Date.now().toString()
        },
        credentials: 'include',
        body: JSON.stringify(data)
      }, 15000);
      
      const result = await response.json();
      this.lastClaimTime = Date.now();
      return result;
      
    } catch (error) {
      console.error('Claim error:', error);
      
      if (error.name === 'AbortError') {
        return { 
          success: false, 
          message: "Request timed out. Please try again." 
        };
      }
      
      return { 
        success: false, 
        message: error.message || "Connection error. Please check your internet and try again." 
      };
      
    } finally {
      this.pendingRequests.delete(gameType);
    }
  },
  
  setButtonLoading: function(buttonId, isLoading) {
    const button = document.getElementById(buttonId);
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

//========== ENHANCED GAME LIMITER WITH FRIENDLY MESSAGES ==========
const GameLimiter = {
  dailyLimits: CONFIG.GAME_DAILY_LIMITS,
  
  gameFriendlyNames: {
    'snake': 'Snake Game',
    'coinflip': 'Coin Flip',
    'plinko': 'Plinko 3D',
    'spin': 'Daily Spin',
    'tiktok': 'TikTok Follow'
  },
  
  gameEmojis: {
    'snake': '🐍',
    'coinflip': '🪙',
    'plinko': '🎯',
    'spin': '🎡',
    'tiktok': '📱'
  },
  
  gameMessages: {
    'snake': {
      icon: '🐍',
      title: 'Snake Game Limit Reached',
      message: 'You have played Snake 5 times today. Come back tomorrow for more fun!'
    },
    'coinflip': {
      icon: '🪙',
      title: 'Coin Flip Limit Reached',
      message: 'You have played Coin Flip 2 times today. Daily limit reached!'
    },
    'plinko': {
      icon: '🎯',
      title: 'Plinko Limit Reached',
      message: 'You have played Plinko 2 times today. Try again tomorrow!'
    },
    'spin': {
      icon: '🎡',
      title: 'Daily Spin Limit Reached',
      message: 'You have already used your daily spin today! Come back tomorrow.'
    },
    'tiktok': {
      icon: '📱',
      title: 'TikTok Daily Limit Reached',
      message: 'You have already claimed TikTok reward today! Come back tomorrow.'
    }
  },
  
  async checkAndNavigate(gameType, targetUrl) {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return false;
    }
    
    try {
      // First check if user can access the game
      const response = await App.requestWithTimeout(`/api/games/access?game=${gameType}`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      
      if (!data.success) {
        App.showMessage('Failed to check game access. Please try again.', 'error');
        return false;
      }
      
      if (data.can_play === false) {
        // Show friendly limit modal
        this.showLimitModal(gameType, data);
        return false;
      }
      
      // User can play, proceed to game
      window.location.href = targetUrl;
      return true;
      
    } catch (error) {
      console.error('Game access check error:', error);
      // On error, still allow navigation but show warning
      App.showMessage('Could not verify game limits. Proceeding to game...', 'warning');
      window.location.href = targetUrl;
      return true;
    }
  },
  
  showLimitModal(gameType, data = null) {
    const existingModal = document.getElementById('game-limit-modal');
    if (existingModal) {
      existingModal.remove();
    }
    
    const gameInfo = this.gameMessages[gameType] || {
      icon: '🎮',
      title: 'Game Limit Reached',
      message: 'You have reached your daily limit for this game.'
    };
    
    const limit = this.dailyLimits[gameType] || 5;
    const played = data?.played_today || limit;
    
    const modal = document.createElement('div');
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
  
  closeModal() {
    const modal = document.getElementById('game-limit-modal');
    if (modal) {
      modal.remove();
    }
  },
  
  suggestAlternative(currentGame) {
    this.closeModal();
    
    // Determine which games to suggest (all except the current one)
    const alternativeGames = Object.keys(this.gameFriendlyNames).filter(game => game !== currentGame);
    
    let alternativesHTML = `
      <div style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
        backdrop-filter: blur(10px);
      ">
        <div style="
          background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 100%);
          border-radius: 20px;
          padding: 30px;
          max-width: 400px;
          width: 90%;
          border: 2px solid #00D4FF;
          box-shadow: 0 20px 40px rgba(0, 212, 255, 0.3);
          text-align: center;
          animation: slideIn 0.4s ease-out;
        ">
          <h3 style="
            color: white;
            font-family: 'Orbitron', sans-serif;
            font-size: 1.5rem;
            margin-bottom: 20px;
          ">
            🎮 Try These Games Instead
          </h3>
          
          <div style="
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin: 20px 0;
          ">
    `;
    
    // Add alternative game buttons
    alternativeGames.forEach(gameType => {
      const gameName = this.gameFriendlyNames[gameType];
      const emoji = this.gameEmojis[gameType] || '🎮';
      
      let onclick = '';
      if (gameType === 'snake') onclick = 'window.location.href=\'snake.html\'';
      else if (gameType === 'coinflip') onclick = 'window.location.href=\'coinflip.html\'';
      else if (gameType === 'plinko') onclick = 'window.location.href=\'plinko.html\'';
      else if (gameType === 'spin') onclick = 'Games.openSpinWheel()';
      else if (gameType === 'tiktok') onclick = 'Games.openTikTok()';
      
      alternativesHTML += `
        <button onclick="${onclick}" style="
          background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
          color: white;
          border: none;
          padding: 15px;
          border-radius: 10px;
          font-family: 'Orbitron', sans-serif;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.3s ease;
          text-align: left;
          display: flex;
          align-items: center;
          gap: 15px;
        ">
          <span style="font-size: 1.5rem;">${emoji}</span>
          <div style="text-align: left;">
            <div style="font-size: 1.1rem;">${gameName}</div>
            <div style="font-size: 0.8rem; opacity: 0.8;">${this.getGameDescription(gameType)}</div>
          </div>
        </button>
      `;
    });
    
    alternativesHTML += `
          </div>
          
          <button onclick="GameLimiter.closeAlternativeModal()" style="
            background: transparent;
            color: #A0A0B5;
            border: 1px solid #A0A0B5;
            padding: 12px;
            border-radius: 10px;
            font-family: 'Orbitron', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            margin-top: 15px;
          ">
            Close
          </button>
        </div>
      </div>
    `;
    
    const altModal = document.createElement('div');
    altModal.innerHTML = alternativesHTML;
    altModal.id = 'alternative-games-modal';
    document.body.appendChild(altModal);
  },
  
  getGameDescription(gameType) {
    const descriptions = {
      'snake': 'Eat apples, earn ₦200 each',
      'coinflip': 'Bet & double your money',
      'plinko': 'Bet & multiply your earnings',
      'spin': 'Spin & win up to ₦1000',
      'tiktok': 'Follow & earn ₦150 daily'
    };
    return descriptions[gameType] || 'Earn rewards';
  },
  
  closeAlternativeModal() {
    const modal = document.getElementById('alternative-games-modal');
    if (modal) {
      modal.remove();
    }
  }
};

//========== ENHANCED GAME LIMITER WITH AUTO-LOGOUT ===========
const EnhancedGameLimiter = {
    async checkAndHandleGameAccess(gameType, targetUrl) {
        if (!App.currentUser) {
            App.showMessage('Please login first', 'error');
            return false;
        }
        
        try {
            // Check game access with logout capability
            const response = await App.requestWithTimeout(`/api/games/check-limit-with-logout/${gameType}`, {
                credentials: 'include',
                headers: { 'Cache-Control': 'no-cache' }
            });
            
            const data = await response.json();
            
            if (!data.success) {
                if (data.force_logout || data.action_required === 'logout') {
                    // Show logout modal and force logout
                    this.showForceLogoutModal(gameType, data);
                    return false;
                }
                
                App.showMessage(data.message || 'Failed to check game access', 'error');
                return false;
            }
            
            if (!data.can_play) {
                // Show limit reached modal with logout option
                this.showLimitReachedModal(gameType, data);
                return false;
            }
            
            // User can play, proceed to game
            window.location.href = targetUrl;
            return true;
            
        } catch (error) {
            console.error('Game access check error:', error);
            App.showMessage('Could not verify game limits. Proceeding to game...', 'warning');
            window.location.href = targetUrl;
            return true;
        }
    },
    
    showForceLogoutModal(gameType, data) {
        const gameInfo = GameLimiter.gameMessages[gameType] || {
            icon: '🎮',
            title: 'Daily Limit Reached',
            message: 'You have reached your daily limit for this game.'
        };
        
        const played = data.played_today || 0;
        const max = data.max_plays || CONFIG.GAME_DAILY_LIMITS[gameType] || 5;
        const resetTime = data.reset_time || 'midnight (00:00 UTC)';
        
        const modal = document.createElement('div');
        modal.id = 'force-logout-modal';
        modal.className = 'game-limit-modal';
        modal.style.zIndex = '10002';
        
        modal.innerHTML = `
            <div class="force-logout-modal-content">
                <div class="game-limit-icon">🚫</div>
                
                <h3 class="game-limit-title">Daily Limit Reached</h3>
                
                <div class="game-limit-message">
                    <p class="game-limit-text" style="font-size: 1.1rem; line-height: 1.6;">
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
                    
                    <div class="game-limit-info" style="color: #ff6b6b;">
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
        
        // Start countdown
        let countdown = 10;
        const countdownEl = document.getElementById('logout-countdown');
        const countdownInterval = setInterval(() => {
            countdown--;
            if (countdownEl) countdownEl.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(countdownInterval);
                this.performLogout(gameType);
            }
        }, 1000);
        
        // Store interval for cleanup
        modal.countdownInterval = countdownInterval;
    },
    
    async performLogout(gameType) {
        try {
            // Call force logout endpoint
            await fetch('/api/games/force-logout/' + gameType, {
                method: 'POST',
                credentials: 'include'
            });
            
            // Clear local session
            document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
            
            // Show logout message
            this.showLogoutMessage();
            
            // Redirect to login page with reason
            setTimeout(() => {
                window.location.href = '/?reason=daily_limit_reached&game=' + gameType;
            }, 2000);
            
        } catch (error) {
            console.error('Logout error:', error);
            // Force redirect anyway
            window.location.href = '/?reason=daily_limit_reached';
        }
    },
    
    showLogoutMessage() {
        const message = document.createElement('div');
        message.className = 'global-message warning';
        message.style.position = 'fixed';
        message.style.top = '50%';
        message.style.left = '50%';
        message.style.transform = 'translate(-50%, -50%)';
        message.style.zIndex = '10003';
        message.style.fontSize = '1.2rem';
        message.innerHTML = `
            <div style="text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 20px;">🚫</div>
                <h3 style="margin-bottom: 15px;">Daily Limit Reached</h3>
                <p>You have been logged out automatically.<br>Please come back tomorrow!</p>
                <p style="font-size: 0.9rem; opacity: 0.8;">Redirecting to login page...</p>
            </div>
        `;
        document.body.appendChild(message);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (message.parentNode) {
                message.remove();
            }
        }, 3000);
    },
    
    closeModal() {
        const modal = document.getElementById('force-logout-modal');
        if (modal) {
            if (modal.countdownInterval) {
                clearInterval(modal.countdownInterval);
            }
            modal.remove();
        }
        
        // Also close regular limit modal if open
        GameLimiter.closeModal();
        
        // Return to dashboard
        window.location.href = '/';
    },
    
    showLimitReachedModal(gameType, data) {
        GameLimiter.showLimitModal(gameType, data);
    }
};

//========== AUTHENTICATION =========
const Auth = {
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
  
  initPasswordToggles: function() {
    const loginPasswordField = document.getElementById('login-password');
    if (loginPasswordField && !loginPasswordField.parentNode?.classList?.contains('password-container')) {
      const loginContainer = document.createElement('div');
      loginContainer.className = 'password-container';
      
      loginPasswordField.parentNode.insertBefore(loginContainer, loginPasswordField);
      loginContainer.appendChild(loginPasswordField);
      
      const loginToggle = document.createElement('button');
      loginToggle.type = 'button';
      loginToggle.className = 'password-toggle';
      loginToggle.innerHTML = '<i class="fas fa-eye"></i>';
      loginToggle.setAttribute('title', 'Show password');
      loginToggle.setAttribute('aria-label', 'Toggle password visibility');
      loginToggle.onclick = () => this.togglePasswordVisibility('login-password');
      loginContainer.appendChild(loginToggle);
    }
    
    const regPasswordField = document.getElementById('reg-password');
    if (regPasswordField && !regPasswordField.parentNode?.classList?.contains('password-container')) {
      const regContainer = document.createElement('div');
      regContainer.className = 'password-container';
      
      regPasswordField.parentNode.insertBefore(regContainer, regPasswordField);
      regContainer.appendChild(regPasswordField);
      
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
    const identifier = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');
    
    if (!identifier || !password) {
      messageEl.textContent = 'Please fill all fields';
      messageEl.className = 'message error';
      return;
    }
    
    try {
      const response = await App.requestWithTimeout('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, password })
      });
      
      const data = await response.json();
      messageEl.textContent = data.message;
      messageEl.className = data.success ? 'message success' : 'message error';
      
      if (data.success) {
        App.currentUser = data.user;
        App.showAppScreen();
        App.refreshBalance();
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
        
        const loginPassword = document.getElementById('login-password');
        if (loginPassword.type === 'text') {
          loginPassword.type = 'password';
          const toggleBtn = loginPassword.nextElementSibling;
          if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.setAttribute('title', 'Show password');
          }
        }
      }
    } catch (error) {
      messageEl.textContent = error.message || 'Network error. Please try again.';
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
      const response = await App.requestWithTimeout('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, coupon_code: coupon, referral_code: referral, contact })
      });
      
      const data = await response.json();
      messageEl.textContent = data.message;
      messageEl.className = data.success ? 'message success' : 'message error';
      
      if (data.success) {
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').value = password;
        
        const regPassword = document.getElementById('reg-password');
        if (regPassword.type === 'text') {
          regPassword.type = 'password';
          const toggleBtn = regPassword.nextElementSibling;
          if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.setAttribute('title', 'Show password');
          }
        }
        document.querySelector('.tab[data-tab="login"]').click();
      }
    } catch (error) {
      messageEl.textContent = error.message || 'Network error. Please try again.';
      messageEl.className = 'message error';
    }
  },
  
  buyCoupon: async function () {
    try {
      const response = await App.requestWithTimeout('/api/whatsapp/numbers');
      const data = await response.json();
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
      const response = await App.requestWithTimeout('/api/user/profile');
      const data = await response.json();
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
      const response = await App.requestWithTimeout('/api/user/set-profile-picture', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picture_url: url })
      });
      
      const data = await response.json();
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

//========== REFERRALS ========
const Referral = {
  open: async function () {
    if (!App.currentUser) return;
    
    try {
      const response = await App.requestWithTimeout('/api/user/profile');
      const data = await response.json();
      
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
      const result = await GameManager.safeClaim(
        '/api/referral/claim',
        {},
        'referral'
      );
      
      if (!result.success) {
        App.showMessage(result.message, 'error');
        return;
      }
      
      App.showMessage(`🎉 ₦${result.claimed.toLocaleString()} referral bonus claimed!`, 'success');
      App.updateBalance(result.new_balance);
      Referral.open();
    } catch (error) {
      App.showMessage('Failed to claim bonus. Please try again.', 'error');
    }
  }
};

//========== BANKING & WITHDRAWALS =========
const Banking = {
  banks: [],
  
  async loadBanks() {
    try {
      const response = await App.requestWithTimeout('/api/banking/banks');
      const data = await response.json();
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
    
    // First check withdrawal day
    const canWithdraw = await checkWithdrawalDay();
    
    if (!canWithdraw) {
        // The modal is already shown by checkWithdrawalDay()
        return;
    }
    
    // Clear withdrawal form
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
    const userRes = await App.requestWithTimeout('/api/user/profile');
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
      const result = await GameManager.safeClaim(
        '/api/banking/withdraw',
        {
          amount, 
          bank_code: bankCode, 
          account_number: accountNumber, 
          account_name: accountName, 
          pin 
        },
        'withdrawal'
      );
      
      msgEl.textContent = result.message;
      msgEl.className = result.success ? 'message success' : 'message error';
      
      if (result.success) {
        App.updateBalance(result.new_balance);
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
      const response = await App.requestWithTimeout('/api/achievements');
      const data = await response.json();
      
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
      const result = await GameManager.safeClaim(
        '/api/achievements/claim',
        {},
        'achievements'
      );
      
      if (result.success) {
        App.showMessage(`🎉 Achievement rewards claimed! New balance: ₦${result.new_balance.toLocaleString()}`, 'success');
        App.updateBalance(result.new_balance);
      } else {
        App.showMessage(result.message || 'Failed to claim rewards', 'error');
      }
    } catch (error) {
      App.showMessage('Network error. Please try again.', 'error');
    }
  }
};

//========== GAMES & TIKTOK DAILY =========
const Games = {
  // Updated game opening functions with enhanced limiter (auto-logout)
  openSnake: () => EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html'),
  openCoinFlip: () => EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html'),
  openPlinko: () => EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html'),
  
  // Game reporting functions
  reportSnake: async function (apples) {
    return await GameManager.safeClaim(
      '/api/games/snake/report', 
      { apples_eaten: apples }, 
      'snake'
    );
  },
  
  reportCoinFlip: async function (bet, won) {
    return await GameManager.safeClaim(
      '/api/games/coinflip/report',
      { bet: bet, won: won },
      'coinflip'
    );
  },
  
  reportPlinko: async function (bet, multiplier) {
    return await GameManager.safeClaim(
      '/api/games/plinko/report',
      { bet: bet, multiplier: multiplier },
      'plinko'
    );
  },
  
  reportSpin: async function (_unused) {
    // Backend decides the reward - frontend just triggers the spin
    return await GameManager.safeClaim(
      '/api/games/spin/execute',
      {},
      'spin'
    );
  },
  
  openTikTok: async function () {
    if (!App.currentUser) return;
    
    // Check TikTok limit first with enhanced limiter
    try {
      const response = await App.requestWithTimeout(`/api/games/check-limit-with-logout/tiktok`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      
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
    
    const msgEl = document.getElementById('tiktok-message');
    msgEl.textContent = '';
    msgEl.className = 'message';
    
    try {
      const response = await App.requestWithTimeout('/api/games/tiktok/daily');
      const data = await response.json();
      
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
      const result = await GameManager.safeClaim(
        '/api/games/tiktok/follow-daily',
        {},
        'tiktok'
      );
      
      if (result.success) {
        App.updateBalance(result.new_balance);
        msgEl.textContent = `✅ Success! ₦${result.reward} added to your balance.`;
        msgEl.className = 'message success';
        
        setTimeout(() => {
          App.closeModal('tiktok-modal');
          App.showMessage(`🎉 TikTok reward claimed: ₦${result.reward}`, 'success');
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
  
  openSpinWheel: async function() {
    if (!App.currentUser) return;
    
    // Check spin limit first with enhanced limiter
    try {
      const response = await App.requestWithTimeout(`/api/games/check-limit-with-logout/spin`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      
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

    // Disable button immediately to prevent double-spin
    button.disabled = true;
    GameManager.setButtonLoading('spin-button', true);
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SPINNING...';

    if (msgEl) {
      msgEl.textContent = '';
      msgEl.className = 'message';
    }

    // Reset wheel to 0 cleanly
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    void wheel.offsetWidth; // force reflow

    try {
      // ✅ STEP 1: Call backend FIRST — backend decides the winner
      const result = await this.reportSpin(null);

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

      const reward = result.reward;
      const prizeIndex = result.prize_index !== undefined ? result.prize_index : 5;

      // ✅ STEP 2: Calculate exact rotation to land on the winning segment
      // Segments: [1000=0°, 500=60°, 200=120°, 100=180°, 50=240°, 0=300°]
      const degreesPerSegment = 60;
      const segmentStartAngle = prizeIndex * degreesPerSegment;

      // Land in the MIDDLE of the winning segment (not the edge)
      const segmentMidpoint = segmentStartAngle + (degreesPerSegment / 2);

      // Pointer is at top. To bring a segment to the top, rotate (360 - angle)
      const angleToTop = (360 - segmentMidpoint) % 360;

      // Add 5-7 full spins for visual effect
      const fullSpins = 5 + Math.floor(Math.random() * 3);
      const totalRotation = (fullSpins * 360) + angleToTop;

      // ✅ STEP 3: Animate wheel to land EXACTLY on the winning segment
      wheel.style.transition = 'transform 5s cubic-bezier(0.25, 0.1, 0.1, 1.0)';
      wheel.style.transform = `rotate(${totalRotation}deg)`;

      // ✅ STEP 4: Show result after animation completes
      setTimeout(() => {
        GameManager.setButtonLoading('spin-button', false);
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
          App.showMessage(`🎡 You won ₦${reward.toLocaleString()}!`, 'success');
        }
      }, 5200); // match the 5s animation duration + 200ms buffer

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

//========== SETTINGS & LOGOUT =========
const Settings = {
  open: async function () {
    if (!App.currentUser) return;
    
    try {
      const response = await App.requestWithTimeout('/api/user/profile');
      const data = await response.json();
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
        const socialResponse = await App.requestWithTimeout('/api/admin/settings');
        const socialData = await socialResponse.json();
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
        const response = await App.requestWithTimeout('/api/user/verify-withdrawal-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: currentPin }),
          credentials: 'include'
        });
        
        const verifyData = await response.json();
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
      const result = await GameManager.safeClaim(
        '/api/user/set-withdrawal-pin',
        { pin: newPin },
        'setpin'
      );
      
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
      // Check if user is admin
      const isAdmin = App.currentUser && App.currentUser.is_admin;
      const endpoint = isAdmin ? '/api/admin/change-password' : '/api/user/change-password';
      
      const response = await App.requestWithTimeout(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ 
          current_password: oldPass,
          new_password: newPass
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        App.showMessage("✅ Password changed successfully!", "success");
        App.closeModal('settings-modal');
        
        // If admin, suggest logout
        if (isAdmin && data.message && data.message.includes('login again')) {
          setTimeout(() => {
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
      await App.requestWithTimeout('/api/auth/logout', { 
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

//========== SPIN WHEEL FUNCTIONS =========
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
  
  Auth.initPasswordToggles();
  App.init();
  
  // Update game card click handlers for enhanced limiter with auto-logout
  setTimeout(() => {
    const snakeCard = document.querySelector('.activity-card[onclick*="snake.html"]');
    const coinflipCard = document.querySelector('.activity-card[onclick*="coinflip.html"]');
    const plinkoCard = document.querySelector('.activity-card[onclick*="plinko.html"]');
    
    if (snakeCard) {
      snakeCard.onclick = () => EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html');
    }
    if (coinflipCard) {
      coinflipCard.onclick = () => EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html');
    }
    if (plinkoCard) {
      plinkoCard.onclick = () => EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html');
    }
  }, 1000);
  
  // Auto-initialize spin wheel when modal opens
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

//========== GLOBAL FUNCTIONS FOR GAME PAGES =========
(function() {
    // Export all functions to window
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
    window.checkWithdrawalDay = checkWithdrawalDay;
    window.closeWithdrawalDayModal = closeWithdrawalDayModal;
    
    // Game navigation with enhanced limits (auto-logout)
    window.openSnakeGame = () => EnhancedGameLimiter.checkAndHandleGameAccess('snake', 'snake.html');
    window.openCoinFlipGame = () => EnhancedGameLimiter.checkAndHandleGameAccess('coinflip', 'coinflip.html');
    window.openPlinkoGame = () => EnhancedGameLimiter.checkAndHandleGameAccess('plinko', 'plinko.html');
    window.openTikTokGame = Games.openTikTok;
    window.openSpinWheelGame = Games.openSpinWheel;
    
    // Critical API functions
    window.checkDailyLimit = GameManager.checkDailyLimit;
    window.updateBalance = App.updateBalance;
    window.showMessage = App.showMessage;
    window.goBackToDashboard = () => window.location.href = 'index.html';
    
    // Game claim functions using safeClaim
    window.claimSnakeReward = async function(apples) {
        return await GameManager.safeClaim(
            '/api/games/snake/report',
            { apples_eaten: apples },
            'snake'
        );
    };
    
    window.claimCoinFlipReward = async function(bet, won) {
        return await GameManager.safeClaim(
            '/api/games/coinflip/report',
            { bet: bet, won: won },
            'coinflip'
        );
    };
    
    window.claimPlinkoReward = async function(bet, multiplier) {
        return await GameManager.safeClaim(
            '/api/games/plinko/report',
            { bet: bet, multiplier: multiplier },
            'plinko'
        );
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
        
        return await GameManager.safeClaim(endpoint, data, gameType);
    };
    
    console.log('✅ FLEXIA Script v14.0 - ALL FUNCTIONS LOADED WITH COMPLETE WITHDRAWAL DAY CHECK');
})();

// Emergency fallback loader
document.addEventListener('DOMContentLoaded', function() {
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


// ==================== DAILY LOGIN BONUS ====================
const LoginBonus = {
  async checkAndClaim() {
    try {
      // Check status first
      const statusRes = await fetch('/api/daily-login-bonus/status', {
        credentials: 'include'
      });
      if (!statusRes.ok) return;
      const status = await statusRes.json();
      if (!status.success || status.already_claimed) return;

      // Auto-claim
      const claimRes = await fetch('/api/daily-login-bonus', {
        method: 'POST',
        credentials: 'include'
      });
      if (!claimRes.ok) return;
      const data = await claimRes.json();
      if (!data.success) return;

      // Show popup
      LoginBonus.showPopup(data);
    } catch (e) {
      console.log('Login bonus check failed:', e);
    }
  },

  showPopup(data) {
    const existing = document.getElementById('login-bonus-popup');
    if (existing) existing.remove();

    const reward = data.reward || 20;
    const streak = data.streak || 1;
    const milestone = data.milestone || null;
    const nextMilestone = data.next_milestone || null;

    const popup = document.createElement('div');
    popup.id = 'login-bonus-popup';
    popup.style.cssText = `
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.85); z-index: 99999;
      display: flex; align-items: center; justify-content: center;
      animation: fadeIn 0.3s ease;
    `;

    const streakDots = Array.from({length: Math.min(streak, 7)}, (_, i) =>
      `<div style="width:12px;height:12px;border-radius:50%;background:${i < streak ? '#00FF55' : '#333'};
       box-shadow:${i < streak ? '0 0 8px #00FF55' : 'none'};"></div>`
    ).join('');

    popup.innerHTML = `
      <div style="background:linear-gradient(135deg,#0A0A1F,#151535);
                  border:2px solid ${milestone ? '#FFD700' : '#8000FF'};
                  border-radius:20px; padding:30px; max-width:340px; width:90%;
                  text-align:center; box-shadow:0 20px 60px rgba(128,0,255,0.4);">
        <div style="font-size:3rem;margin-bottom:10px;">${milestone ? '🏆' : '🎁'}</div>
        <h2 style="color:${milestone ? '#FFD700' : '#8000FF'};margin-bottom:5px;font-size:1.5rem;">
          ${milestone ? milestone : 'Daily Login Bonus!'}
        </h2>
        <div style="font-size:2.5rem;font-weight:bold;color:#00FF55;
                    text-shadow:0 0 15px rgba(0,255,85,0.7);margin:15px 0;">
          +₦${reward.toLocaleString()}
        </div>
        <div style="color:#A0A0B5;margin-bottom:15px;">added to your balance</div>

        <div style="background:rgba(128,0,255,0.1);border-radius:10px;padding:12px;margin-bottom:15px;
                    border:1px solid rgba(128,0,255,0.3);">
          <div style="color:#A0A0B5;font-size:0.85rem;margin-bottom:8px;">LOGIN STREAK</div>
          <div style="display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-bottom:6px;">
            ${streakDots}
          </div>
          <div style="color:#00CCFF;font-weight:bold;">${streak} day${streak !== 1 ? 's' : ''} in a row! 🔥</div>
          ${nextMilestone ? `<div style="color:#FFD700;font-size:0.8rem;margin-top:6px;">${nextMilestone}</div>` : ''}
        </div>

        <button onclick="document.getElementById('login-bonus-popup').remove()"
          style="background:linear-gradient(45deg,#8000FF,#00CCFF);border:none;border-radius:10px;
                 color:#0A0A1F;padding:14px 30px;font-size:1rem;font-weight:bold;
                 cursor:pointer;width:100%;margin-top:5px;">
          CLAIM & CONTINUE
        </button>
      </div>
    `;

    document.body.appendChild(popup);
    popup.addEventListener('click', (e) => {
      if (e.target === popup) popup.remove();
    });

    // Update balance in UI if App object available
    if (typeof App !== 'undefined' && App.updateBalance && data.new_balance) {
      App.updateBalance(data.new_balance);
    }

    // Auto-close after 10 seconds
    setTimeout(() => {
      const p = document.getElementById('login-bonus-popup');
      if (p) p.remove();
    }, 10000);
  }
};

// Auto-check login bonus when page loads (dashboard only)
document.addEventListener('DOMContentLoaded', () => {
  // Only run on main dashboard page
  if (window.location.pathname === '/' || window.location.pathname.endsWith('index.html')) {
    // Slight delay so main content loads first
    setTimeout(() => LoginBonus.checkAndClaim(), 1500);
  }
});

