// Frontend Configuration - FLEXIA v17.0
window.APP_CONFIG = {
    // API Configuration
    API_BASE_URL: '/api',
    
    // App Information
    APP_NAME: 'FLEXIA',
    VERSION: '17.0.0',
    SUPPORT_EMAIL: 'support@flexia.com',
    
    // Financial Configuration
    CURRENCY: '₦',
    MIN_WITHDRAWAL: 100000,
    REFERRAL_BONUS: 7500,
    
    // Tax Rates
    TAX_RATES: {
        SNAKE_GAME: 0.05,
        PLINKO_WIN: 0.10,
        TIKTOK_FOLLOW: 0.02,
        REFERRAL_BONUS: 0.00
    },
    
    // Game Rewards
    REWARDS: {
        SNAKE_APPLE: 200,
        TIKTOK_BASE: 150
    },
    
    // Game Daily Limits
    GAME_DAILY_LIMITS: {
        'snake': 17,
        'coinflip': 12,
        'plinko': 12,
        'spin': 1,
        'tiktok': 3
    },
    
    // Paystack Configuration
    PAYSTACK: {
        PUBLIC_KEY: 'pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        MIN_AMOUNT: 500,
        MAX_AMOUNT: 1000000,
        CURRENCY: 'NGN'
    }
};
