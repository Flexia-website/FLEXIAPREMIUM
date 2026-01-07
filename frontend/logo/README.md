# FLEXIA Platform

A referral banking platform where users can earn money through games, referrals, and social media tasks.

## Features

### 🎮 Games
- **Snake Mine**: Eat apples to earn ₦10 per apple (unlimited earnings)
- **Coin Flip**: 50/50 chance to double your money
- **Plinko 3D**: Bet and multiply your earnings
- **Daily Spin Wheel**: Spin once daily for prizes up to ₦1000

### 💰 Earnings
- **TikTok Follow**: Earn ₦150 for following accounts
- **Referral Program**: Earn ₦7,500 for each friend you refer
- **Daily Bonuses**: Regular bonuses and rewards

### 🏦 Banking
- Secure withdrawals to Nigerian banks
- Minimum withdrawal: ₦100,000
- Professional receipt system
- Multiple bank support

## Logo Implementation

The platform now includes a custom logo system with:

### Logo Assets
Located in `frontend/logo/`:
- `flexia-logo.svg` - Vector logo
- `flexia-logo.png` - 192x192 PNG
- `flexia-logo-512.png` - 512x512 PNG
- `favicon.ico` - Browser favicon
- `apple-touch-icon.png` - iOS icon

### Logo Features
1. **Gradient Design**: Purple (#8000FF) to blue (#00CCFF) gradient
2. **Responsive**: Scales properly on all devices
3. **PWA Ready**: Properly sized icons for PWA installation
4. **Favicon Support**: Appears in browser tabs
5. **iOS Support**: Apple touch icon for home screens

### Regenerating Logos
If you need to regenerate logos:
```bash
cd backend
python generate_logos.py