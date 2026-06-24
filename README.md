# 🎮 ask_me_Gray_bot

A 2-player question game bot for Telegram. Players join privately, flip a coin, and take turns answering, daring, or skipping questions from a curated deck of 400.

---

## Files

```
ask_me_gray_bot/
├── bot.py              ← main bot code
├── questions.json      ← 400 questions (all levels)
├── requirements.txt    ← Python dependencies
├── Procfile            ← Railway deployment config
└── README.md
```

---

## Step 1 — Create your Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Name it: `Ask Me Gray`
4. Username: `ask_me_Gray_bot`
5. BotFather gives you a **token** that looks like: `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx`
6. Copy it — you'll need it in Step 3

---

## Step 2 — Push to GitHub

1. Create a free account at https://github.com
2. Create a new repository called `ask-me-gray-bot` (private is fine)
3. Upload all files from this folder into the repo

---

## Step 3 — Deploy on Railway (free)

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `ask-me-gray-bot` repo
4. Railway detects the Procfile automatically
5. Go to **Variables** tab and add:
   ```
   BOT_TOKEN = 7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx
   ```
   (paste your token from Step 1)
6. Click **Deploy** — done!

The bot goes live in ~1 minute. Railway free tier is enough for personal use.

---

## How to play

1. You open a private chat with `@ask_me_Gray_bot` and send `/start`
2. The bot gives you a unique invite link
3. You paste that link into your Telegram chat with your partner
4. They tap the link → bot connects you both
5. You choose the spice mode (Mixed or Spicy only)
6. A coin flip decides who goes first
7. Each round: Answer 💬 / Dare 🎯 / Skip ⏭️
8. Roles swap every 3 questions
9. Skip twice in a row = automatic dare!

---

## Commands

| Command | What it does |
|---|---|
| `/start` | Create a new game |
| `/score` | See live scores |
| `/endgame` | End current game (admin only) |
| `/help` | Show help |

---

## Spice levels

| Level | Emoji | Type |
|---|---|---|
| 1 | 🌸 | Innocent / Icebreaker |
| 2 | 💭 | Deep / Thoughtful |
| 3 | 😏 | Flirty / Playful |
| 4 | 🔥 | Spicy / Intimate |
