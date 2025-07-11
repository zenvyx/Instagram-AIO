# 🌟 IG AIO Automation Tool

A full-featured, multi-account Instagram automation tool powered by Python and `instagrapi`. Supports login via session ID or password, DM campaigns, scraping, interaction automation (like/follow/comment), with configurable limits, robust error handling, and proxy support.

---

## 🚀 Features

✅ Login via username/password or session ID  
🔀 Proxy and session management per account  
⚙️ Configurable delays and multi-threading  
📩 DM campaigns with spintax/message templates  
❤️ Mass like/comment/follow/unfollow  
📖 Story & highlight viewing, reacting, and liking  
🔍 Scraping: profile info, tagged posts, location posts  
📊 Engagement summaries and analytics  
📁 Export data to JSON/TXT  
📌 Works across multiple accounts simultaneously

---

## 🔧 Installation

### Requirements

- Python 3.8+
- Dependencies (install with pip)

```bash
pip install -r requirements.txt
```

### File Structure (auto-generated on first run)

```
assets/
├── accounts.txt
├── message.txt
├── comments.txt
├── users.txt
├── proxies.txt
├── completed_follows.txt
├── completed_unfollows.txt
scraped_data/
sessions/
```

### Account Format (`assets/accounts.txt`)

```
username:password
username:password:sessionid
```

- Session login is preferred to avoid frequent re-authentication.

---

## 🧪 Usage

```bash
python main.py
```

You’ll be greeted with a colorful menu to choose tasks like:
- Viewing stories
- Interacting with highlights
- Scraping profiles & locations
- DM campaigns
- Mass follow/unfollow
- Engagement analysis

All automated safely with rate limits and threading 💨

---

## ⚙️ Configuration

Edit `assets/config.json`:

```json
{
  "dm_daily_limit": 50,
  "like_limit": 300,
  "comment_limit": 100,
  "follow_limit": 200,
  "max_threads": 5,
  "delays": {
    "follow": 10,
    "unfollow": 10,
    "dm": 20,
    "like": 2,
    "comment": 3,
    "story_view": 1
  }
}
```

---

## 📬 Contact Me

If you like this tool or have suggestions, feel free to reach out!  
Let’s build cool stuff together. 😎💻

- 🐦 Telegram: [@yourhandle](https://t.me/smartmoneyreversal)
- 💬 Discord: smartmoneyreversal
- ☕ SOL: G39hKUBXLiXxiUjLSTXZG18nSGyTApysvEvRqSJgVGgx

> *Don't forget to ⭐ the repo if you find it helpful!*

---

## ⚠️ Disclaimer

> This tool is for **educational and personal use only**.  
> Use responsibly. Automation may violate [Instagram’s Terms](https://help.instagram.com/581066165581870).

---

## 📄 License

MIT License. Free to use, modify, and share with proper attribution.
