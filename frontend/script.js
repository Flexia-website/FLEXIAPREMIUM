// script.js - FLEXIA Frontend v12.6 - COMPLETE GAME LIMITS SYSTEM
// ✅ Strict Daily Limits ✅ Auto-Redirect ✅ Real-time Countdown

//========== EMBEDDED CSS ========
const embeddedCSS = `
  /* ========== GLOBAL STYLES ========== */
  * {
    -webkit-tap-highlight-color: transparent;
    user-select: none;
    -webkit-user-select: none;
  }
  
  body {
    overscroll-behavior: none;
    touch-action: manipulation;
  }
  
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
    background: rgba(0, 0, 0, 0.95);
    color: white;
    border-radius: 8px;
    z-index: 10000;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4);
    animation: slideDown 0.3s ease-out;
    max-width: 90%;
    text-align: center;
    border-left: 4px solid;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    backdrop-filter: blur(10px);
  }
  
  .global-message.success {
    border-left-color: #00ff88;
    background: rgba(0, 255, 136, 0.15);
  }
  
  .global-message.error {
    border-left-color: #ff0055;
    background: rgba(255, 0, 85, 0.15);
  }
  
  .global-message.warning {
    border-left-color: #ffaa00;
    background: rgba(255, 170, 0, 0.15);
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
  
  /* Game Limit Modal - NEW COMPLETE VERSION */
  .game-limit-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.97);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(15px);
    animation: fadeIn 0.3s ease-out;
  }
  
  .game-limit-modal-content {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 24px;
    padding: 35px;
    max-width: 420px;
    width: 90%;
    border: 2px solid #ff4757;
    box-shadow: 0 25px 50px rgba(255, 71, 87, 0.4);
    text-align: center;
    animation: modalSlideIn 0.5s cubic-bezier(0.17, 0.67, 0.12, 0.99);
    position: relative;
    overflow: hidden;
  }
  
  .game-limit-modal-content::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255, 71, 87, 0.1) 0%, transparent 70%);
    animation: rotateBg 20s linear infinite;
  }
  
  .game-limit-icon {
    font-size: 4.5rem;
    margin-bottom: 25px;
    color: #ff4757;
    animation: bounce 2s infinite;
    text-shadow: 0 0 30px rgba(255, 71, 87, 0.7);
  }
  
  .game-limit-title {
    color: #ff6b81;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.8rem;
    margin-bottom: 20px;
    text-shadow: 0 0 15px rgba(255, 107, 129, 0.5);
    font-weight: 900;
    letter-spacing: 1px;
  }
  
  .game-limit-message {
    background: rgba(255, 71, 87, 0.12);
    border-radius: 12px;
    padding: 25px;
    margin: 25px 0;
    border: 1px solid rgba(255, 71, 87, 0.3);
    backdrop-filter: blur(5px);
    position: relative;
    z-index: 1;
  }
  
  .game-limit-text {
    color: #ffb8c6;
    font-size: 1.15rem;
    line-height: 1.6;
    margin-bottom: 20px;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 500;
  }
  
  .game-limit-info {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin: 12px 0;
    color: #ffcc00;
    font-size: 1rem;
    font-family: 'Orbitron', sans-serif;
    font-weight: 600;
  }
  
  .game-limit-info i {
    color: #00D4FF;
    font-size: 1.1rem;
  }
  
  .game-limit-countdown {
    font-size: 1.3rem;
    color: #00ff88;
    font-weight: bold;
    margin: 15px 0;
    font-family: 'Orbitron', monospace;
    text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
    padding: 10px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
    border: 1px solid rgba(0, 255, 136, 0.3);
  }
  
  .game-limit-buttons {
    display: flex;
    flex-direction: column;
    gap: 15px;
    margin-top: 30px;
    position: relative;
    z-index: 1;
  }
  
  .game-limit-btn-ok {
    background: linear-gradient(135deg, #ff4757 0%, #ff6b81 100%);
    color: white;
    border: none;
    padding: 18px;
    border-radius: 12px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 900;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1.1rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    position: relative;
    overflow: hidden;
  }
  
  .game-limit-btn-ok::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    transition: left 0.5s;
  }
  
  .game-limit-btn-ok:hover::before {
    left: 100%;
  }
  
  .game-limit-btn-ok:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(255, 71, 87, 0.5);
  }
  
  .game-limit-btn-alternative {
    background: transparent;
    color: #00D4FF;
    border: 2px solid #00D4FF;
    padding: 16px;
    border-radius: 12px;
    font-family: 'Orbitron', sans-serif;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  
  .game-limit-btn-alternative:hover {
    background: rgba(0, 212, 255, 0.15);
    transform: translateY(-2px);
    box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
  }
  
  /* Alternative Games Modal */
  .alternative-games-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.98);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    backdrop-filter: blur(20px);
    animation: fadeIn 0.3s ease-out;
  }
  
  .alternative-games-content {
    background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 100%);
    border-radius: 24px;
    padding: 35px;
    max-width: 480px;
    width: 90%;
    border: 2px solid #8000FF;
    box-shadow: 0 25px 50px rgba(128, 0, 255, 0.5);
    text-align: center;
    animation: modalSlideIn 0.5s ease-out;
  }
  
  .alternative-games-title {
    color: white;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.8rem;
    margin-bottom: 30px;
    text-shadow: 0 0 15px rgba(128, 0, 255, 0.5);
  }
  
  .alternative-games-grid {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin: 25px 0;
  }
  
  .alternative-game-btn {
    background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
    color: white;
    border: none;
    padding: 20px;
    border-radius: 15px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 20px;
    position: relative;
    overflow: hidden;
  }
  
  .alternative-game-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
    transition: left 0.5s;
  }
  
  .alternative-game-btn:hover::before {
    left: 100%;
  }
  
  .alternative-game-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 25px rgba(128, 0, 255, 0.5);
  }
  
  .game-icon {
    font-size: 2.2rem;
    width: 50px;
    text-align: center;
  }
  
  .game-details {
    flex: 1;
    text-align: left;
  }
  
  .game-name {
    font-size: 1.2rem;
    font-weight: 900;
    margin-bottom: 5px;
  }
  
  .game-description {
    font-size: 0.9rem;
    opacity: 0.9;
    font-family: 'Rajdhani', sans-serif;
  }
  
  .game-arrow {
    opacity: 0.7;
    font-size: 1.2rem;
  }
  
  /* Game Card Disabled State */
  .activity-card.disabled {
    opacity: 0.4 !important;
    filter: grayscale(0.9) !important;
    cursor: not-allowed !important;
    position: relative;
    transform: none !important;
    pointer-events: none;
  }
  
  .activity-card.disabled::after {
    content: "LIMIT REACHED";
    position: absolute;
    top: 10px;
    right: 10px;
    background: linear-gradient(135deg, #ff4757 0%, #ff6b81 100%);
    color: white;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: bold;
    letter-spacing: 1px;
    font-family: 'Orbitron', sans-serif;
    text-transform: uppercase;
    box-shadow: 0 4px 12px rgba(255, 71, 87, 0.4);
    z-index: 10;
  }
  
  .activity-card.disabled .card-badge {
    background: #ff4757 !important;
    color: white !important;
  }
  
  /* Badge styles for daily limits */
  .card-badge {
    position: absolute;
    top: 10px;
    right: 10px;
    background: #8000FF;
    color: white;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: bold;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-family: 'Orbitron', sans-serif;
    box-shadow: 0 4px 12px rgba(128, 0, 255, 0.3);
    transition: all 0.3s ease;
  }
  
  .card-badge.danger {
    background: linear-gradient(135deg, #ff4757 0%, #ff6b81 100%) !important;
    animation: pulseBadge 2s infinite;
  }
  
  /* Animations */
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  @keyframes modalSlideIn {
    from {
      opacity: 0;
      transform: translateY(30px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  
  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
  }
  
  @keyframes rotateBg {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  @keyframes pulseBadge {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
  }
  
  @keyframes glow {
    0%, 100% { box-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
    50% { box-shadow: 0 0 20px rgba(0, 255, 204, 0.8); }
  }
  
  @keyframes success {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
  
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
    20%, 40%, 60%, 80% { transform: translateX(5px); }
  }
  
  /* Social links */
  .social-link {
    display: inline-block;
    margin: 5px 0;
    padding: 10px 20px;
    background: rgba(30,30,69,0.8);
    border: 1px solid #8000FF;
    border-radius: 10px;
    color: #8000FF;
    text-decoration: none;
    font-weight: 600;
    transition: all 0.3s;
    font-family: 'Rajdhani', sans-serif;
  }
  
  .social-link:hover {
    background: rgba(128,0,255,0.2);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(128, 0, 255, 0.3);
  }
  
  /* Settings sections */
  .settings-section {
    margin-bottom: 25px;
    padding-bottom: 25px;
    border-bottom: 1px solid #252540;
  }
  
  .settings-section:last-child {
    border-bottom: none;
  }
  
  .small-text {
    font-size: 0.8rem;
    color: #A0A0B5;
    margin: 10px 0;
    font-family: 'Rajdhani', sans-serif;
  }
  
  /* Profile sections */
  .profile-section {
    margin-bottom: 25px;
    padding: 20px;
    background: rgba(30,30,69,0.5);
    border-radius: 12px;
    border-left: 4px solid #8000FF;
    backdrop-filter: blur(5px);
  }
  
  .profile-section h4 {
    margin-top: 0;
    color: #8000FF;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Orbitron', sans-serif;
  }
  
  .profile-section p {
    margin: 10px 0;
    display: flex;
    justify-content: space-between;
    font-family: 'Rajdhani', sans-serif;
  }
  
  .profile-section strong {
    color: #A0A0B5;
    font-weight: 600;
  }
  
  /* Referral sections */
  .referral-section {
    margin-bottom: 30px;
    padding: 25px;
    background: rgba(30,30,69,0.5);
    border-radius: 15px;
    border: 1px solid rgba(128, 0, 255, 0.3);
    backdrop-filter: blur(5px);
  }
  
  .referral-section h4 {
    margin-top: 0;
    color: #8000FF;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Orbitron', sans-serif;
  }
  
  .referral-section code {
    display: inline-block;
    padding: 8px 15px;
    background: rgba(128, 0, 255, 0.2);
    border-radius: 8px;
    font-family: monospace;
    margin: 15px 0;
    font-size: 1.2rem;
    color: #00FFCC;
  }
  
  /* TikTok display */
  .tiktok-account-display {
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #8000FF;
    border-radius: 12px;
    padding: 20px;
    margin: 20px 0;
    text-align: center;
    font-size: 1.3rem;
    font-family: 'Orbitron', sans-serif;
    font-weight: bold;
    backdrop-filter: blur(5px);
  }
  
  /* Action buttons */
  .action-buttons {
    display: flex;
    gap: 15px;
    margin-top: 20px;
  }
  
  .btn-primary {
    background: linear-gradient(135deg, #8000FF 0%, #6C00FF 100%);
    color: white;
    border: none;
    padding: 15px 25px;
    border-radius: 12px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
    flex: 1;
    text-align: center;
  }
  
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(128, 0, 255, 0.4);
  }
  
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
  }
  
  .btn-secondary {
    background: transparent;
    color: #00D4FF;
    border: 2px solid #00D4FF;
    padding: 15px 25px;
    border-radius: 12px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
    flex: 1;
    text-align: center;
  }
  
  .btn-secondary:hover:not(:disabled) {
    background: rgba(0, 212, 255, 0.1);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 212, 255, 0.3);
  }
  
  /* Merchant Button */
  .btn-merchant {
    background: linear-gradient(135deg, #8000FF 0%, #FF3333 100%);
    color: white;
    border: none;
    padding: 16px;
    border-radius: 12px;
    font-family: 'Orbitron', sans-serif;
    font-weight: 900;
    font-size: 1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    margin-top: 20px;
    transition: all 0.3s ease;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  
  .btn-merchant:hover {
    background: linear-gradient(135deg, #9000FF 0%, #FF4444 100%);
    transform: translateY(-3px);
    box-shadow: 0 10px 25px rgba(128, 0, 255, 0.4);
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
    'snake': 10,
    'coinflip': 5,
    'plinko': 5,
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
      this.checkURLParams();
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
  
  checkURLParams: function() {
    const urlParams = new URLSearchParams(window.location.search);
    const limitMessage = urlParams.get('limit_message');
    const gameType = urlParams.get('game_type');
    
    if (limitMessage && gameType && this.currentUser) {
      setTimeout(() => {
        if (window.GameLimiter) {
          GameLimiter.showLimitModal(gameType, {
            played_today: CONFIG.GAME_DAILY_LIMITS[gameType] || 5,
            max_plays: CONFIG.GAME_DAILY_LIMITS[gameType] || 5,
            message: decodeURIComponent(limitMessage)
          });
        }
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
      }, 1500);
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
    
    try {
      const response = await this.requestWithTimeout('/api/games/limits', {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.success) {
          const limits = data.limits;
          
          const games = [
            { type: 'snake', element: document.querySelector('.activity-card[onclick*="snake.html"]') },
            { type: 'coinflip', element: document.querySelector('.activity-card[onclick*="coinflip.html"]') },
            { type: 'plinko', element: document.querySelector('.activity-card[onclick*="plinko.html"]') },
            { type: 'spin', element: document.querySelector('.activity-card[onclick*="customSpinEngine.openModal"]') },
            { type: 'tiktok', element: document.querySelector('.activity-card[onclick*="Games.openTikTok"]') }
          ];
          
          games.forEach(game => {
            if (!game.element) return;
            
            const limit = limits[game.type];
            if (limit) {
              const badge = game.element.querySelector('.card-badge');
              if (badge) {
                badge.textContent = `${limit.remaining}/${limit.max} left`;
                badge.className = limit.remaining > 0 ? 'card-badge' : 'card-badge danger';
              }
              
              if (limit.remaining === 0) {
                game.element.classList.add('disabled');
                game.element.onclick = () => GameLimiter.showLimitModal(game.type, {
                  played_today: limit.played,
                  max_plays: limit.max
                });
              } else {
                game.element.classList.remove('disabled');
                
                switch(game.type) {
                  case 'snake':
                    game.element.onclick = () => GameLimiter.checkAndNavigate('snake', 'snake.html');
                    break;
                  case 'coinflip':
                    game.element.onclick = () => GameLimiter.checkAndNavigate('coinflip', 'coinflip.html');
                    break;
                  case 'plinko':
                    game.element.onclick = () => GameLimiter.checkAndNavigate('plinko', 'plinko.html');
                    break;
                  case 'spin':
                    game.element.onclick = () => customSpinEngine.openModal();
                    break;
                  case 'tiktok':
                    game.element.onclick = () => Games.openTikTok();
                    break;
                }
              }
            }
          });
        }
      }
    } catch (error) {
      console.error('Failed to update game cards:', error);
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
      
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        throw new Error('Server returned non-JSON response');
      }
      
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw error;
    }
  }
};

//========== ENHANCED GAME LIMITER WITH COUNTDOWN ==========
const GameLimiter = {
  dailyLimits: CONFIG.GAME_DAILY_LIMITS,
  countdownInterval: null,
  
  gameFriendlyNames: {
    'snake': 'Snake Game',
    'coinflip': 'Coin Flip',
    'plinko': 'Plinko 3D',
    'spin': 'Daily Spin',
    'tiktok': 'TikTok Follow'
  },
  
  gameIcons: {
    'snake': '🐍',
    'coinflip': '🪙',
    'plinko': '🎯',
    'spin': '🎡',
    'tiktok': '📱'
  },
  
  async checkAndNavigate(gameType, targetUrl) {
    if (!App.currentUser) {
      App.showMessage('Please login first', 'error');
      return false;
    }
    
    try {
      const response = await App.requestWithTimeout(`/api/games/access?game=${gameType}`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      
      if (!data.success) {
        App.showMessage('Failed to check game access', 'error');
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
      App.showMessage('Could not verify game limits', 'warning');
      window.location.href = targetUrl;
      return true;
    }
  },
  
  showLimitModal(gameType, data = null) {
    this.closeModal();
    
    const limit = this.dailyLimits[gameType] || 5;
    const played = data?.played_today || limit;
    const gameName = this.gameFriendlyNames[gameType] || gameType;
    const icon = this.gameIcons[gameType] || '🚫';
    
    const modal = document.createElement('div');
    modal.id = 'game-limit-modal';
    modal.className = 'game-limit-modal';
    
    modal.innerHTML = `
      <div class="game-limit-modal-content">
        <div class="game-limit-icon">${icon}</div>
        
        <h3 class="game-limit-title">DAILY LIMIT REACHED!</h3>
        
        <div class="game-limit-message">
          <p class="game-limit-text">
            You've played <strong>${played}/${limit}</strong> ${gameName} today.
            Come back tomorrow to play again!
          </p>
          
          <div class="game-limit-info">
            <i class="fas fa-calendar-day"></i>
            <span>Daily Limit: ${limit} plays per day</span>
          </div>
          
          <div class="game-limit-info">
            <i class="fas fa-clock"></i>
            <span>Next Reset: <span id="countdown-timer">Calculating...</span></span>
          </div>
          
          <div class="game-limit-countdown" id="countdown-display">--:--:--</div>
        </div>
        
        <div class="game-limit-buttons">
          <button class="game-limit-btn-ok" onclick="GameLimiter.redirectToDashboard()">
            <i class="fas fa-home"></i> BACK TO DASHBOARD
          </button>
          
          <button class="game-limit-btn-alternative" onclick="GameLimiter.showAlternativeGames('${gameType}')">
            <i class="fas fa-gamepad"></i> TRY ANOTHER GAME
          </button>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Start countdown
    this.startCountdown(modal);
    
    // Prevent closing by clicking outside
    modal.onclick = (e) => {
      if (e.target === modal) {
        this.redirectToDashboard();
      }
    };
  },
  
  startCountdown(modal) {
    const now = new Date();
    const midnight = new Date(now);
    midnight.setHours(23, 59, 59, 999);
    
    const updateTimer = () => {
      const now = new Date();
      const diff = midnight - now;
      
      if (diff <= 0) {
        // Reset time reached
        this.closeModal();
        window.location.reload();
        return;
      }
      
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      const countdownDisplay = modal.querySelector('#countdown-display');
      const timerText = modal.querySelector('#countdown-timer');
      
      if (countdownDisplay) {
        countdownDisplay.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      }
      
      if (timerText) {
        timerText.textContent = `${hours}h ${minutes}m`;
      }
    };
    
    updateTimer();
    this.countdownInterval = setInterval(updateTimer, 1000);
  },
  
  showAlternativeGames(currentGame) {
    this.closeModal();
    
    const alternativeGames = Object.keys(this.gameFriendlyNames).filter(game => game !== currentGame);
    
    if (alternativeGames.length === 0) {
      this.redirectToDashboard();
      return;
    }
    
    const modal = document.createElement('div');
    modal.id = 'alternative-games-modal';
    modal.className = 'alternative-games-modal';
    
    let gamesHTML = '';
    alternativeGames.forEach(gameType => {
      const gameName = this.gameFriendlyNames[gameType];
      const icon = this.gameIcons[gameType];
      let description = '';
      let onclick = '';
      
      switch(gameType) {
        case 'snake':
          description = 'Eat apples, earn ₦200 each';
          onclick = 'window.location.href="snake.html"';
          break;
        case 'coinflip':
          description = 'Bet & double your money';
          onclick = 'window.location.href="coinflip.html"';
          break;
        case 'plinko':
          description = 'Bet & multiply your earnings';
          onclick = 'window.location.href="plinko.html"';
          break;
        case 'spin':
          description = 'Spin & win up to ₦1000';
          onclick = 'customSpinEngine.openModal()';
          break;
        case 'tiktok':
          description = 'Follow & earn ₦150 daily';
          onclick = 'Games.openTikTok()';
          break;
      }
      
      gamesHTML += `
        <button class="alternative-game-btn" onclick="${onclick}">
          <div class="game-icon">${icon}</div>
          <div class="game-details">
            <div class="game-name">${gameName}</div>
            <div class="game-description">${description}</div>
          </div>
          <div class="game-arrow"><i class="fas fa-chevron-right"></i></div>
        </button>
      `;
    });
    
    modal.innerHTML = `
      <div class="alternative-games-content">
        <h3 class="alternative-games-title">
          <i class="fas fa-gamepad"></i> TRY THESE GAMES INSTEAD
        </h3>
        
        <div class="alternative-games-grid">
          ${gamesHTML}
        </div>
        
        <button class="btn-secondary" onclick="GameLimiter.closeAlternativeModal()" style="width: 100%; margin-top: 20px;">
          <i class="fas fa-times"></i> CLOSE
        </button>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Prevent closing by clicking outside
    modal.onclick = (e) => {
      if (e.target === modal) {
        this.closeAlternativeModal();
      }
    };
  },
  
  redirectToDashboard() {
    this.closeModal();
    window.location.href = 'index.html';
  },
  
  closeModal() {
    if (this.countdownInterval) {
      clearInterval(this.countdownInterval);
      this.countdownInterval = null;
    }
    
    const modal = document.getElementById('game-limit-modal');
    if (modal) modal.remove();
  },
  
  closeAlternativeModal() {
    const modal = document.getElementById('alternative-games-modal');
    if (modal) modal.remove();
  }
};

//========== GAME MANAGER ==========
const GameManager = {
  lastClaimTime: 0,
  pendingRequests: new Map(),
  
  async safeClaim(endpoint, data, gameType = 'unknown') {
    if (this.pendingRequests.has(gameType)) {
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
          message: "Request timed out" 
        };
      }
      
      return { 
        success: false, 
        message: error.message || "Connection error" 
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
      messageEl.textContent = error.message || 'Network error';
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
      messageEl.textContent = error.message || 'Network error';
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
                   style="width:100%;padding:10px;margin:10px 0;background:#151535;border:1px solid #8000FF;color:white;border-radius:8px;">
            <button class="btn-primary" onclick="Profile.setProfilePicture()" 
                    style="margin-top:15px;">
              <i class="fas fa-upload"></i> UPDATE PICTURE
            </button>
        `;
        
        if (data.user.profile_picture) {
          html += `
            <div style="margin-top:20px;text-align:center;">
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
        '<p class="error">Failed to load profile</p>';
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
      App.showMessage('Network error', 'error');
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
            <p><strong>Your Referral Code:</strong> <code>${data.user.referral_code}</code></p>
            <p>Share this code to earn <strong>₦${CONFIG.REFERRAL_BONUS.toLocaleString()}</strong> per friend!</p>
            <p><strong>Referred Users:</strong> ${data.referrals.count}</p>
            <p><strong>Unclaimed Bonus:</strong> ₦${unclaimed.toLocaleString()}</p>
            
            ${unclaimed > 0
              ? `<button class="btn-primary" onclick="Referral.claimBonuses()" style="margin-top:20px;">
                   <i class="fas fa-gift"></i> CLAIM ₦${unclaimed.toLocaleString()} BONUS
                 </button>`
              : '<p style="color:#00FF55;margin-top:20px;">All bonuses claimed! 🎉</p>'
            }
          </div>
          
          <div class="referral-section" style="margin-top:25px;">
            <h4><i class="fas fa-share-alt"></i> Share Your Link</h4>
            <div style="background:#151535;padding:12px;border-radius:8px;border:1px solid #8000FF;margin:15px 0;">
              ${window.location.origin}/?ref=${data.user.referral_code}
            </div>
            <button class="btn-secondary" onclick="Referral.copyReferralLink('${data.user.referral_code}')" 
                    style="margin-top:15px;">
              <i class="fas fa-copy"></i> COPY LINK
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
      App.showMessage('Referral link copied!', 'success');
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
      
      App.showMessage(`✅ ₦${result.claimed.toLocaleString()} referral bonus claimed!`, 'success');
      App.updateBalance(result.new_balance);
      Referral.open();
    } catch (error) {
      App.showMessage('Failed to claim bonus', 'error');
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
      App.showMessage('Session expired', 'error');
      return;
    }
    
    const user = userData.user;
    if (!user.withdrawal_pin) {
      App.showMessage('Set withdrawal PIN first', 'info');
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
      App.showMessage('Insufficient balance', 'error');
      return;
    }
    
    if (!bankCode || !accountNumber || accountNumber.length < 10 || isNaN(accountNumber)) {
      App.showMessage('Invalid bank details', 'error');
      return;
    }
    
    const pin = prompt('Enter your 4–6 digit withdrawal PIN:');
    if (!pin || !/^\d{4,6}$/.test(pin)) {
      App.showMessage('Valid PIN required', 'error');
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
        App.showMessage('✅ Withdrawal submitted!', 'success');
        setTimeout(() => App.closeModal('withdrawal-modal'), 2000);
      }
    } catch (error) {
      msgEl.textContent = 'Network error';
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
        App.showMessage(`✅ Achievement rewards claimed!`, 'success');
        App.updateBalance(result.new_balance);
      } else {
        App.showMessage(result.message || 'Failed to claim rewards', 'error');
      }
    } catch (error) {
      App.showMessage('Network error', 'error');
    }
  }
};

//========== GAMES & TIKTOK DAILY =========
const Games = {
  openSnake: () => GameLimiter.checkAndNavigate('snake', 'snake.html'),
  openCoinFlip: () => GameLimiter.checkAndNavigate('coinflip', 'coinflip.html'),
  openPlinko: () => GameLimiter.checkAndNavigate('plinko', 'plinko.html'),
  
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
  
  reportSpin: async function (reward) {
    return await GameManager.safeClaim(
      '/api/games/spin/report',
      { reward: reward },
      'spin'
    );
  },
  
  openTikTok: async function () {
    if (!App.currentUser) return;
    
    try {
      const response = await App.requestWithTimeout(`/api/games/access?game=tiktok`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      if (data.success && !data.can_play) {
        GameLimiter.showLimitModal('tiktok', data);
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
        <p style="color:#ff5252;">Failed to load TikTok task</p>
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
  
  openSpinWheel: async function() {
    if (!App.currentUser) return;
    
    try {
      const response = await App.requestWithTimeout(`/api/games/access?game=spin`, {
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      const data = await response.json();
      if (data.success && !data.can_play) {
        GameLimiter.showLimitModal('spin', data);
        return;
      }
    } catch (error) {
      console.error('Spin access check error:', error);
    }
    
    App.showModal('spin-modal');
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
              <i class="fas fa-key"></i> CHANGE PASSWORD
            </button>
          </div>
        `;
      }
      
      html += `
        <div class="settings-section">
          <h4><i class="fas fa-lock"></i> Security</h4>
          <button class="btn-primary" onclick="Settings.${hasPin ? 'changeWithdrawalPin' : 'setWithdrawalPin'}()" style="width:100%;">
            <i class="fas fa-key"></i> ${hasPin ? 'CHANGE' : 'SET'} WITHDRAWAL PIN
          </button>
        </div>
        
        <div class="settings-section">
          <h4><i class="fas fa-palette"></i> Appearance</h4>
          <button class="btn-primary" onclick="App.toggleTheme()" style="width:100%;">
            <i class="fas fa-moon"></i> ${document.body.classList.contains('dark-mode') ? 'SWITCH TO LIGHT MODE' : 'SWITCH TO DARK MODE'}
          </button>
        </div>
        
        <div class="settings-section">
          <h4><i class="fas fa-sign-out-alt"></i> Session</h4>
          <button class="btn-primary" style="background:#d32f2f;width:100%;" onclick="Settings.logout()">
            <i class="fas fa-sign-out-alt"></i> LOGOUT
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
        App.showMessage('Current PIN must be 4 to 6 digits', 'error');
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
          App.showMessage('Incorrect current PIN', 'error');
          return;
        }
      } catch (error) {
        App.showMessage('Verification failed', 'error');
        return;
      }
    }
    
    const newPin = prompt('Enter your NEW 4-6 digit Withdrawal PIN:');
    if (!newPin || !/^\d{4,6}$/.test(newPin)) {
      App.showMessage('New PIN must be 4 to 6 digits', 'error');
      return;
    }
    
    const confirmPin = prompt('Confirm your new PIN:');
    if (newPin !== confirmPin) {
      App.showMessage('PINs do not match', 'error');
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
      App.showMessage('Failed to set PIN', 'error');
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
      App.showMessage("Password must be at least 6 characters", "error");
      return;
    }
    
    const confirmPass = prompt("Confirm your new password:");
    if (newPass !== confirmPass) {
      App.showMessage("Passwords do not match", "error");
      return;
    }
    
    try {
      const result = await GameManager.safeClaim(
        '/api/user/change-password',
        { old_password: oldPass, new_password: newPass },
        'changepassword'
      );
      
      if (result.success) {
        App.showMessage("Password changed successfully!", "success");
        App.closeModal('settings-modal');
      } else {
        App.showMessage(result.message, "error");
      }
    } catch (error) {
      App.showMessage("Failed to change password", "error");
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

//========== CUSTOM SPIN ENGINE =========
const customSpinEngine = {
  isSpinning: false,
  
  async checkDailyStatus() {
    try {
      const res = await fetch('/api/spin/daily-status', { 
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' }
      });
      
      if (!res.ok) return true;
      
      const data = await res.json();
      return data.can_spin === true;
    } catch (e) {
      console.log('Spin status check failed:', e);
      return true;
    }
  },
  
  openModal() {
    if (!App.currentUser) return;
    
    // Check spin limit first
    Games.openSpinWheel();
  },
  
  setup() {
    console.log('Spin engine setup complete');
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
  
  Auth.initPasswordToggles();
  App.init();
  customSpinEngine.setup();
  
  // Initialize game limiter
  window.GameLimiter = GameLimiter;
  
  // Auto-refresh limits every minute
  setInterval(() => App.updateGameCards(), 60000);
  
  console.log('✅ FLEXIA v12.6 - Complete Game Limits System Loaded');
});

//========== GLOBAL FUNCTIONS =========
(function() {
  window.App = App;
  window.GameManager = GameManager;
  window.GameLimiter = GameLimiter;
  window.Games = Games;
  window.Auth = Auth;
  window.Profile = Profile;
  window.Referral = Referral;
  window.Banking = Banking;
  window.Achievements = Achievements;
  window.Settings = Settings;
  window.customSpinEngine = customSpinEngine;
  
  // Merchant chat function
  window.openMerchantChat = function() {
    window.open('https://chat-3zot.onrender.com', '_blank');
  };
  
  // Game navigation
  window.openSnakeGame = () => GameLimiter.checkAndNavigate('snake', 'snake.html');
  window.openCoinFlipGame = () => GameLimiter.checkAndNavigate('coinflip', 'coinflip.html');
  window.openPlinkoGame = () => GameLimiter.checkAndNavigate('plinko', 'plinko.html');
  window.openTikTokGame = Games.openTikTok;
  window.openSpinWheelGame = customSpinEngine.openModal;
  
  // API functions
  window.checkDailyLimit = GameManager.checkDailyLimit;
  window.updateBalance = App.updateBalance;
  window.showMessage = App.showMessage;
  window.goBackToDashboard = () => window.location.href = 'index.html';
  
  // Game claim functions
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
  
  console.log('✅ All functions loaded with COMPLETE GAME LIMITS');
})();

// Emergency fallback
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
