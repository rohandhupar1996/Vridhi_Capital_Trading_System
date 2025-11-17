# Automated Zerodha Login Guide

## 🎯 Problem
Zerodha login requires:
1. Browser login (Google auth - can't be automated)
2. Manual copy-paste of `request_token` from redirect URL

## ✅ Solution
Two automated approaches to eliminate manual copy-paste:

### Method 1: Clipboard Monitoring (Recommended) ⭐
**Script:** `scripts/zerodha_login_auto.py`

**How it works:**
1. Script opens browser with login URL
2. You complete login (Google auth - still manual)
3. After redirect, **copy the entire URL** from browser address bar
4. Script automatically detects `request_token` from clipboard
5. No manual typing needed!

**Usage:**
```bash
PYTHONPATH=. python scripts/zerodha_login_auto.py
```

**Steps:**
1. Run script
2. Browser opens automatically
3. Complete login in browser
4. After redirect, copy the URL (Ctrl+C / Cmd+C)
5. Script automatically detects token ✅

**Requirements:**
```bash
pip install pyperclip
```

---

### Method 2: OAuth Callback Server
**Script:** `scripts/zerodha_login.py` (updated)

**How it works:**
1. Starts local HTTP server on `localhost:8080`
2. You configure Zerodha API app to redirect to `http://localhost:8080`
3. Script automatically captures token from redirect

**Setup (One-time):**
1. Go to Zerodha API settings
2. Set redirect URL to: `http://localhost:8080`
3. Save settings

**Usage:**
```bash
PYTHONPATH=. python scripts/zerodha_login.py
```

**Note:** This requires changing Zerodha API app settings, which may not be desired.

---

## 📊 Comparison

| Method | Setup Required | Automation Level | Ease of Use |
|--------|---------------|------------------|-------------|
| **Clipboard Monitoring** | Install pyperclip | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Callback Server** | Change Zerodha settings | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Manual Entry** | None | ⭐ | ⭐⭐ |

---

## 🚀 Quick Start

### Recommended: Clipboard Monitoring

1. **Install dependency:**
   ```bash
   pip install pyperclip
   ```

2. **Run automated login:**
   ```bash
   PYTHONPATH=. python scripts/zerodha_login_auto.py
   ```

3. **Follow prompts:**
   - Browser opens automatically
   - Complete login (Google auth)
   - Copy the redirect URL (Ctrl+C)
   - Token detected automatically! ✅

---

## 🔧 Troubleshooting

### Clipboard monitoring not working?
- **macOS:** May need accessibility permissions
- **Linux:** May need `xclip` or `xsel` installed
- **Windows:** Should work out of the box

### Fallback to manual entry:
If clipboard monitoring fails, the script will prompt for manual entry.

---

## 💡 Tips

1. **After login redirect:**
   - The URL will look like: `https://...?request_token=XXXXX&action=login&status=success`
   - Just copy the entire URL (Ctrl+C / Cmd+C)
   - Script extracts token automatically

2. **Token saved:**
   - Token is saved to `configs/zerodha_tokens.json`
   - Next time, script will use saved token if valid

3. **Token expiry:**
   - Tokens typically valid for 1 day
   - Script will prompt for re-login when expired

---

## ✅ Summary

**Best approach:** Use `zerodha_login_auto.py` with clipboard monitoring
- ✅ No Zerodha settings changes needed
- ✅ Fully automated token capture
- ✅ Just copy URL after login
- ✅ Works on all platforms

**Result:** No more manual token typing! 🎉

