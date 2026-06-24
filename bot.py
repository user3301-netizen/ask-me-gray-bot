import os
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_USERNAME = "user_5991"   # @user_5991 is always Player 1 / admin

# ── Load questions ───────────────────────────────────────────────────────────
with open("questions.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)

ALL_QUESTIONS = list(DATA["questions"].values())

SPICE_EMOJI = {1: "🌸", 2: "💭", 3: "😏", 4: "🔥"}
SPICE_LABEL = {1: "Innocent", 2: "Deep", 3: "Flirty", 4: "Spicy"}

DARES = [
    "🎤 Send a voice note answering this question instead of typing!",
    "🔄 Ask your partner the SAME question back before answering yourself.",
    "🎭 Answer using ONLY emojis — no words allowed!",
    "⏱️ You have 10 seconds to answer. Go!",
    "🤫 Answer the question in exactly 5 words. Not more, not less.",
    "🎲 Your partner gets to guess your answer first, then you reveal the truth.",
    "📸 Describe your current facial expression as you read this question.",
    "🌀 Answer this question from the perspective of your future self in 5 years.",
]

# ── In-memory game sessions ──────────────────────────────────────────────────
# sessions[session_id] = {
#   "admin_id": int, "admin_name": str,
#   "partner_id": int | None, "partner_name": str | None,
#   "mode": "mixed" | "spicy",
#   "questions": [...shuffled list...],
#   "q_index": int,
#   "current_player": "admin" | "partner",   # whose turn to act
#   "skips": {"admin": 0, "partner": 0},
#   "scores": {"admin": 0, "partner": 0},
#   "state": "waiting_partner" | "choosing_mode" | "playing" | "ended"
# }
sessions = {}

# user_id → session_id  (so we can look up session from any player)
user_session = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session_by_user(user_id):
    sid = user_session.get(user_id)
    return sessions.get(sid), sid


def filter_questions(mode):
    if mode == "spicy":
        pool = [q for q in ALL_QUESTIONS if q["spice_level"] >= 3]
    else:  # mixed — starts soft, gets hotter
        pool = ALL_QUESTIONS[:]
    random.shuffle(pool)
    return pool


def current_question(session):
    idx = session["q_index"]
    if idx >= len(session["questions"]):
        return None
    return session["questions"][idx]


def other_player(role):
    return "partner" if role == "admin" else "admin"


def player_id(session, role):
    return session["admin_id"] if role == "admin" else session["partner_id"]


def player_name(session, role):
    return session["admin_name"] if role == "admin" else session["partner_name"]


def whose_role(session, user_id):
    if user_id == session["admin_id"]:
        return "admin"
    if user_id == session["partner_id"]:
        return "partner"
    return None


def question_card(session, q, show_whose_turn=True):
    level = q["spice_level"]
    emoji = SPICE_EMOJI[level]
    label = SPICE_LABEL[level]
    total = len(session["questions"])
    idx = session["q_index"] + 1
    current = player_name(session, session["current_player"])
    text = (
        f"{emoji} *Question {idx}/{total}* — _{label}_\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*{q['question']}*\n"
        f"━━━━━━━━━━━━━━━"
    )
    if show_whose_turn:
        text += f"\n\n🎯 It's *{current}*'s turn to answer!"
    return text


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    # ── Partner joining via deep link: /start join_SESSIONID
    if args and args[0].startswith("join_"):
        sid = args[0][5:]
        session = sessions.get(sid)

        if not session:
            await update.message.reply_text("❌ This game session doesn't exist or has expired.")
            return

        if session["state"] != "waiting_partner":
            await update.message.reply_text("❌ This game already started or is full.")
            return

        if user.id == session["admin_id"]:
            await update.message.reply_text("😅 You can't join your own game! Share the link with someone else.")
            return

        # Register partner
        session["partner_id"] = user.id
        session["partner_name"] = user.first_name
        user_session[user.id] = sid
        session["state"] = "choosing_mode"

        # Notify partner
        await update.message.reply_text(
            f"🎉 You joined *{session['admin_name']}'s* game!\n\n"
            f"Waiting for them to choose the game mode...",
            parse_mode="Markdown"
        )

        # Ask admin to choose mode
        keyboard = [
            [InlineKeyboardButton("🌊 Mixed (all levels, starts soft)", callback_data=f"mode_mixed_{sid}")],
            [InlineKeyboardButton("🔥 Spicy only (levels 3 & 4)", callback_data=f"mode_spicy_{sid}")],
        ]
        await ctx.bot.send_message(
            chat_id=session["admin_id"],
            text=(
                f"🎮 *{user.first_name}* just joined your game!\n\n"
                f"Choose the spice mode:"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # ── Admin starting a new game
    # Check if already in a game
    existing, sid = get_session_by_user(user.id)
    if existing and existing["state"] not in ("ended",):
        await update.message.reply_text(
            "⚠️ You already have an active game. Use /endgame to stop it first."
        )
        return

    # Create new session
    sid = f"{user.id}_{random.randint(1000, 9999)}"
    sessions[sid] = {
        "admin_id": user.id,
        "admin_name": user.first_name,
        "partner_id": None,
        "partner_name": None,
        "mode": None,
        "questions": [],
        "q_index": 0,
        "current_player": "admin",
        "skips": {"admin": 0, "partner": 0},
        "scores": {"admin": 0, "partner": 0},
        "state": "waiting_partner",
    }
    user_session[user.id] = sid

    bot_username = (await ctx.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=join_{sid}"

    await update.message.reply_text(
        f"🎮 *Game created!*\n\n"
        f"Send this link to your partner so they can join:\n\n"
        f"👉 {invite_link}\n\n"
        f"Waiting for them to tap it...",
        parse_mode="Markdown"
    )


# ── Mode selection callback ───────────────────────────────────────────────────

async def mode_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # "mode_mixed_SID" or "mode_spicy_SID"
    parts = data.split("_", 2)
    mode = parts[1]
    sid = parts[2]

    session = sessions.get(sid)
    if not session or query.from_user.id != session["admin_id"]:
        await query.edit_message_text("❌ Not authorized.")
        return

    session["mode"] = mode
    session["questions"] = filter_questions(mode)
    session["state"] = "playing"

    mode_text = "🌊 Mixed (all levels)" if mode == "mixed" else "🔥 Spicy only"

    # Coin flip to decide who goes first
    first = random.choice(["admin", "partner"])
    session["current_player"] = first
    first_name = player_name(session, first)

    await query.edit_message_text(
        f"✅ Mode set: *{mode_text}*\n\n🪙 Flipping a coin...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(1)

    # Send coin flip result + first question to BOTH players
    q = current_question(session)
    card = question_card(session, q)

    action_keyboard = [
        [
            InlineKeyboardButton("💬 Answer", callback_data=f"act_answer_{sid}"),
            InlineKeyboardButton("🎯 Dare", callback_data=f"act_dare_{sid}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"act_skip_{sid}"),
        ]
    ]
    wait_keyboard = [
        [InlineKeyboardButton("👀 See question", callback_data=f"act_view_{sid}")]
    ]

    intro = f"🪙 *{first_name}* goes first!\n\n"

    for role in ["admin", "partner"]:
        pid = player_id(session, role)
        if role == session["current_player"]:
            kb = InlineKeyboardMarkup(action_keyboard)
            msg = intro + card + "\n\n👆 Your move!"
        else:
            kb = InlineKeyboardMarkup(wait_keyboard)
            msg = intro + card + f"\n\n⏳ Waiting for *{first_name}* to respond..."

        await ctx.bot.send_message(
            chat_id=pid,
            text=msg,
            reply_markup=kb,
            parse_mode="Markdown"
        )


# ── Game action callbacks ─────────────────────────────────────────────────────

async def game_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # "act_ACTION_SID"
    parts = data.split("_", 2)
    action = parts[1]
    sid = parts[2]

    session = sessions.get(sid)
    if not session:
        await query.edit_message_text("❌ Session not found.")
        return

    user_id = query.from_user.id
    role = whose_role(session, user_id)

    if action == "view":
        # Partner just wants to see the question clearly — already shown
        await query.answer("Question is shown above 👆", show_alert=False)
        return

    if role != session["current_player"]:
        await query.answer("⏳ It's not your turn yet!", show_alert=True)
        return

    current_role = session["current_player"]
    other_role = other_player(current_role)
    current_name = player_name(session, current_role)
    other_name = player_name(session, other_role)
    other_id = player_id(session, other_role)
    q = current_question(session)

    if action == "answer":
        session["scores"][current_role] += 1
        session["skips"][current_role] = 0  # reset skip streak

        await query.edit_message_text(
            f"💬 *{current_name}* chose to answer!\n\n"
            f"*Question:* {q['question']}\n\n"
            f"✍️ Type your answer below and I'll share it with your partner.",
            parse_mode="Markdown"
        )

        # Tell partner to wait
        await ctx.bot.send_message(
            chat_id=other_id,
            text=f"💬 *{current_name}* is answering...\n\n*Question:* _{q['question']}_\n\n⏳ Wait for their answer!",
            parse_mode="Markdown"
        )

        # Set state: waiting for text reply
        ctx.user_data["awaiting_answer"] = sid

    elif action == "dare":
        dare = random.choice(DARES)
        session["scores"][current_role] += 1
        session["skips"][current_role] = 0

        dare_msg = (
            f"🎯 *{current_name}* took a Dare!\n\n"
            f"*Question was:* _{q['question']}_\n\n"
            f"*Dare:* {dare}"
        )

        # Tell both players
        await query.edit_message_text(dare_msg, parse_mode="Markdown")
        await ctx.bot.send_message(chat_id=other_id, text=dare_msg, parse_mode="Markdown")

        # Advance
        await advance_question(ctx, sid, session)

    elif action == "skip":
        session["skips"][current_role] += 1
        skip_count = session["skips"][current_role]

        skip_msg = f"⏭️ *{current_name}* skipped this one."

        if skip_count >= 2:
            # Force dare after 2 consecutive skips
            dare = random.choice(DARES)
            skip_msg += (
                f"\n\n⚠️ *2 skips in a row — automatic dare!*\n\n"
                f"*Dare:* {dare}"
            )
            session["skips"][current_role] = 0

        await query.edit_message_text(skip_msg, parse_mode="Markdown")
        await ctx.bot.send_message(chat_id=other_id, text=skip_msg, parse_mode="Markdown")

        await advance_question(ctx, sid, session)


async def advance_question(ctx, sid, session):
    """Move to next question, swap roles every 3 questions."""
    session["q_index"] += 1

    # Swap roles every 3 questions
    if session["q_index"] % 3 == 0:
        session["current_player"] = other_player(session["current_player"])

    q = current_question(session)

    if q is None:
        await end_game(ctx, sid, session)
        return

    current_role = session["current_player"]
    other_role = other_player(current_role)
    current_name = player_name(session, current_role)

    card = question_card(session, q)

    action_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Answer", callback_data=f"act_answer_{sid}"),
            InlineKeyboardButton("🎯 Dare", callback_data=f"act_dare_{sid}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"act_skip_{sid}"),
        ]
    ])
    wait_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👀 See question", callback_data=f"act_view_{sid}")]
    ])

    for role in ["admin", "partner"]:
        pid = player_id(session, role)
        if role == current_role:
            await ctx.bot.send_message(
                chat_id=pid,
                text=card + "\n\n👆 Your turn!",
                reply_markup=action_keyboard,
                parse_mode="Markdown"
            )
        else:
            await ctx.bot.send_message(
                chat_id=pid,
                text=card + f"\n\n⏳ Waiting for *{current_name}*...",
                reply_markup=wait_keyboard,
                parse_mode="Markdown"
            )


async def end_game(ctx, sid, session):
    session["state"] = "ended"

    # If no partner joined yet, just cancel cleanly
    if not session["partner_id"]:
        await ctx.bot.send_message(
            chat_id=session["admin_id"],
            text="❌ Game cancelled. Send /start to create a new one!",
            parse_mode="Markdown"
        )
        user_session.pop(session["admin_id"], None)
        sessions.pop(sid, None)
        return

    admin_score = session["scores"]["admin"]
    partner_score = session["scores"]["partner"]
    admin_name = session["admin_name"]
    partner_name = session["partner_name"]

    if admin_score > partner_score:
        winner = f"🏆 *{admin_name}* wins with {admin_score} answers!"
    elif partner_score > admin_score:
        winner = f"🏆 *{partner_name}* wins with {partner_score} answers!"
    else:
        winner = f"🤝 It's a tie! You're both equally brave."

    msg = (
        f"🎮 *Game Over!*\n\n"
        f"📊 *Scoreboard:*\n"
        f"  {admin_name}: {admin_score} answered\n"
        f"  {partner_name}: {partner_score} answered\n\n"
        f"{winner}\n\n"
        f"Want to play again? Just tap /start 🔁"
    )

    for role in ["admin", "partner"]:
        pid = player_id(session, role)
        if pid:
            try:
                await ctx.bot.send_message(chat_id=pid, text=msg, parse_mode="Markdown")
            except Exception:
                pass

    # Clean up
    user_session.pop(session["admin_id"], None)
    user_session.pop(session["partner_id"], None)
    sessions.pop(sid, None)


# ── Receive text answers ──────────────────────────────────────────────────────

async def receive_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sid = ctx.user_data.get("awaiting_answer")

    if not sid:
        # Not in answer mode — ignore
        return

    session = sessions.get(sid)
    if not session:
        return

    role = whose_role(session, user.id)
    other_role = other_player(role)
    other_id = player_id(session, other_role)
    name = player_name(session, role)
    q = current_question(session)

    answer_text = update.message.text
    ctx.user_data.pop("awaiting_answer", None)

    # Confirm to answerer
    await update.message.reply_text(
        f"✅ Answer sent to your partner!",
    )

    # Send to partner
    await ctx.bot.send_message(
        chat_id=other_id,
        text=(
            f"💬 *{name}* answered:\n\n"
            f"_Q: {q['question']}_\n\n"
            f"*\"{answer_text}\"*"
        ),
        parse_mode="Markdown"
    )

    await advance_question(ctx, sid, session)


# ── /endgame ──────────────────────────────────────────────────────────────────

async def endgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session, sid = get_session_by_user(user.id)

    if not session:
        await update.message.reply_text("You don't have an active game.")
        return

    role = whose_role(session, user.id)
    if role != "admin":
        await update.message.reply_text("Only the game admin can end the game.")
        return

    await end_game(ctx, sid, session)


# ── /reset ────────────────────────────────────────────────────────────────────

async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session, sid = get_session_by_user(user.id)
    if session:
        user_session.pop(session.get("admin_id"), None)
        user_session.pop(session.get("partner_id"), None)
        sessions.pop(sid, None)
    ctx.user_data.clear()
    await update.message.reply_text("🔄 Session cleared! Send /start to create a fresh game.")


# ── /score ────────────────────────────────────────────────────────────────────

async def score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session, _ = get_session_by_user(user.id)

    if not session or session["state"] != "playing":
        await update.message.reply_text("No active game found.")
        return

    admin_score = session["scores"]["admin"]
    partner_score = session["scores"]["partner"]
    q_done = session["q_index"]
    total = len(session["questions"])

    await update.message.reply_text(
        f"📊 *Live Score*\n\n"
        f"  {session['admin_name']}: {admin_score} answered\n"
        f"  {session['partner_name']}: {partner_score} answered\n\n"
        f"Progress: {q_done}/{total} questions",
        parse_mode="Markdown"
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *@ask_me_Gray_bot — Help*\n\n"
        "*Commands:*\n"
        "/start — Create a new game & get an invite link\n"
        "/score — Check the current score\n"
        "/endgame — End the current game (admin only)\n"
        "/help — Show this message\n\n"
        "*How to play:*\n"
        "1️⃣ You tap /start → get an invite link\n"
        "2️⃣ Share the link with your partner\n"
        "3️⃣ Choose the spice mode\n"
        "4️⃣ A coin flip decides who goes first\n"
        "5️⃣ Each question: Answer 💬, Dare 🎯, or Skip ⏭️\n"
        "6️⃣ Roles swap every 3 questions\n"
        "7️⃣ Skip twice in a row = automatic dare!\n\n"
        "*Spice levels:*\n"
        "🌸 Innocent · 💭 Deep · 😏 Flirty · 🔥 Spicy",
        parse_mode="Markdown"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("endgame", endgame))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(mode_chosen, pattern=r"^mode_"))
    app.add_handler(CallbackQueryHandler(game_action, pattern=r"^act_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_answer))

    print("🤖 @ask_me_Gray_bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
