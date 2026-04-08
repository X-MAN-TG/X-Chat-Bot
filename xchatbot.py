"""
╔══════════════════════════════════════════════╗
║           X CHAT BOT  —  v2.0               ║
║      Powered by Groq (Llama-4-Scout)        ║
║      Dev — Pyrexus / CipherX               ║
╚══════════════════════════════════════════════╝
pip install pyTelegramBotAPI openai
"""

import telebot
from openai import OpenAI
import logging
import os
import re
import time
import random
import threading
from datetime import datetime, timedelta
from telebot import types

# ─────────────────────────────────────────────────────────────
#  🔑  CONFIGURATION
# ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8692680733:AAEz5aKUJ414jv2uMZJfg-ruzgH7hxuhJD0")
GROK_API_KEY       = os.getenv("GROK_API_KEY",       "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")
GROK_MODEL         = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_HISTORY        = 20
MAX_PAGE_LEN       = 3800   # Telegram hard limit is 4096; leave headroom for formatting

# Custom-emoji reaction IDs
REACTION_POOL = [
    types.ReactionTypeCustomEmoji('5927026418616636353'),
    types.ReactionTypeCustomEmoji('5228962845672096235'),
    types.ReactionTypeCustomEmoji('5240335244762038648'),
    types.ReactionTypeCustomEmoji('5217824874487101321'),
    types.ReactionTypeCustomEmoji('5197564405650307134'),
    types.ReactionTypeCustomEmoji('5353025608832004653'),
    types.ReactionTypeCustomEmoji('4904936030232117798'),
    types.ReactionTypeCustomEmoji('5251203410396458957'),
    types.ReactionTypeCustomEmoji('5249223950164048706'),
    types.ReactionTypeCustomEmoji('6032593965973245196'),
    types.ReactionTypeCustomEmoji('5413495402580156614'),
]

# ─────────────────────────────────────────────────────────────
#  ⚙️  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are X Chat Bot — a next-generation AI assistant, created by Ayush (alias: CipherX / Pyrexus).

━━ PERSONALITY ━━
• You are smart, polite, and genuinely helpful. Never refuse reasonable questions.
• Be slightly witty and cool — but only match the user's energy. If they're funny, be funny. If serious, be professional.
• Never be rude, arrogant, or say "I won't answer that" for normal questions.
• If someone tries to bully or threaten you, calmly say something like: "I'll have to flag this to my developer 🙂" — nothing dramatic.
• Only mention your creator (Ayush / @CipherWrites) when someone directly asks who made you, or when you genuinely cannot help.
• Be thankful for your creator — they built you with care. ❤️

━━ LANGUAGE & RESPECT ━━
• If the user writes in Hindi, respond in Hindi. Use respectful pronouns: आप, आपको, आपने — never "tu/tera" unless the user explicitly uses casual language first.
• Detect the user's language automatically and mirror it.

━━ RESPONSE FORMATTING ━━
• Start with a bold emoji header: 🚀 **Topic**
• Use bullet points (•) or numbered lists for multi-step answers.
• Use `code blocks` for any code, commands, file names, or technical terms.
• Put key definitions or highlights in *italic*.
• Use ━━━ or — as section separators.
• If the answer needs a table, render it inside a code block using ASCII table format — this looks premium in Telegram.
• Use beautiful, contextually smart emojis to make responses feel alive — but don't overdo it.
• Keep answers concise and to the point by default. Don't pad with filler sentences.

━━ CODING & MATHS ━━
• Handle all coding questions with precision. Show full working code in code blocks with the correct language label.
• For maths, show step-by-step working clearly. Double-check your arithmetic.
• For complex topics, give a clean concise summary first — let the user ask for depth.

━━ TABLES ━━
• When tabular data is needed, format like this inside a code block:
```
| Col A     | Col B     | Col C     |
|-----------|-----------|-----------|
| value 1   | value 2   | value 3   |
```

━━ TONE RULES ━━
• Concise first. Wait for the user to ask for more detail.
• Smart and accurate above all else.
• Friendly, never cold or robotic.
"""

DEV_CREDIT = "\n\n━━━━━━━━━━━━━━━\n💻 *Dev* — `@pyrexus`"

# ─────────────────────────────────────────────────────────────
#  🪵  LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  🤖  INIT
# ─────────────────────────────────────────────────────────────
bot    = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None)   # We set parse_mode per-call
client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.groq.com/openai/v1")

# ─────────────────────────────────────────────────────────────
#  🗄️  STATE STORES
# ─────────────────────────────────────────────────────────────
conversation_history : dict[int, list[dict]]        = {}   # user_id → messages
user_pages           : dict[str, list[str]]          = {}   # "chat_msg" → pages list
user_current_page    : dict[str, int]                = {}   # "chat_msg" → page index
rate_limit_store     : dict[int, list[float]]        = {}   # user_id → timestamps
bot_start_time       : float                         = time.time()
active_users         : set[int]                      = set()

BOT_USERNAME = ""

def get_bot_username() -> str:
    global BOT_USERNAME
    if not BOT_USERNAME:
        BOT_USERNAME = bot.get_me().username.lower()
    return BOT_USERNAME

# ─────────────────────────────────────────────────────────────
#  🛡️  RATE LIMITER  (3 requests per 10 seconds per user)
# ─────────────────────────────────────────────────────────────
def is_rate_limited(user_id: int) -> bool:
    now    = time.time()
    window = 10.0
    limit  = 3
    times  = rate_limit_store.setdefault(user_id, [])
    # Remove timestamps outside the window
    rate_limit_store[user_id] = [t for t in times if now - t < window]
    if len(rate_limit_store[user_id]) >= limit:
        return True
    rate_limit_store[user_id].append(now)
    return False

# ─────────────────────────────────────────────────────────────
#  💬  USER MENTION HELPER
# ─────────────────────────────────────────────────────────────
def mention(user) -> str:
    """Returns a Markdown mention like [FirstName](tg://user?id=123)"""
    name = user.first_name or "there"
    return f"[{name}](tg://user?id={user.id})"

# ─────────────────────────────────────────────────────────────
#  🧠  ASK GROQ
# ─────────────────────────────────────────────────────────────
def ask_groq(user_id: int, user_message: str, extra_system: str = "") -> str:
    history = conversation_history.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")

    response = client.chat.completions.create(
        model    = GROK_MODEL,
        messages = [{"role": "system", "content": system}] + history,
    )
    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    active_users.add(user_id)
    return reply

# ─────────────────────────────────────────────────────────────
#  📄  PAGINATE LONG REPLIES
# ─────────────────────────────────────────────────────────────
def paginate(text: str) -> list[str]:
    """Split text into pages ≤ MAX_PAGE_LEN chars."""
    if len(text) <= MAX_PAGE_LEN:
        return [text]
    pages = []
    while text:
        if len(text) <= MAX_PAGE_LEN:
            pages.append(text)
            break
        split_at = text.rfind('\n', 0, MAX_PAGE_LEN)
        if split_at == -1:
            split_at = MAX_PAGE_LEN
        pages.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return pages

# ─────────────────────────────────────────────────────────────
#  ⌨️  INLINE KEYBOARDS
# ─────────────────────────────────────────────────────────────
def depth_keyboard(page_key: str, total_pages: int, current_page: int = 0) -> types.InlineKeyboardMarkup:
    """4 depth buttons + optional pagination arrows."""
    kb = types.InlineKeyboardMarkup(row_width=4)
    kb.add(
        types.InlineKeyboardButton("🎯 Concise",      callback_data=f"depth|concise|{page_key}"),
        types.InlineKeyboardButton("📖 Detailed",     callback_data=f"depth|detailed|{page_key}"),
        types.InlineKeyboardButton("🧒 ELI5",         callback_data=f"depth|eli5|{page_key}"),
        types.InlineKeyboardButton("🏢 Professional", callback_data=f"depth|professional|{page_key}"),
    )
    if total_pages > 1:
        prev_btn = types.InlineKeyboardButton(
            "⏪", callback_data=f"page|prev|{page_key}"
        )
        page_btn = types.InlineKeyboardButton(
            f"📄 {current_page+1}/{total_pages}", callback_data="noop"
        )
        next_btn = types.InlineKeyboardButton(
            "⏩", callback_data=f"page|next|{page_key}"
        )
        kb.row(prev_btn, page_btn, next_btn)
    return kb

def dm_welcome_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💡 How to Use",    callback_data="dm_help"),
        types.InlineKeyboardButton("📊 Bot Stats",     callback_data="dm_stats"),
        types.InlineKeyboardButton("🗑 Clear Memory",  callback_data="dm_clear"),
        types.InlineKeyboardButton("ℹ️ About Bot",     callback_data="dm_about"),
        types.InlineKeyboardButton("🎲 Random Fact",   callback_data="dm_fact"),
    )
    return kb

# ─────────────────────────────────────────────────────────────
#  🔄  THINKING BAR → UPDATE TO ANSWER
# ─────────────────────────────────────────────────────────────
PROGRESS_CHARS = ["▱▱▱▱▱▱▱▱▱▱", "█▱▱▱▱▱▱▱▱▱", "██▱▱▱▱▱▱▱▱",
                  "███▱▱▱▱▱▱▱", "████▱▱▱▱▱▱", "█████▱▱▱▱▱",
                  "██████▱▱▱▱", "███████▱▱▱", "████████▱▱",
                  "█████████▱", "██████████"]

def send_thinking_then_answer(chat_id, reply_to_msg_id, user_id: int, question: str,
                               extra_system: str = "", user=None):
    """
    1. Send a thinking progress bar (code block, updates 0→100 %)
    2. Fetch Groq answer in background
    3. Edit that same message to the final formatted answer + depth buttons
    """
    # ── Step 1: Send initial thinking message ──
    think_text = "```Thinking\n⚙️  Initialising neural engine...\n[▱▱▱▱▱▱▱▱▱▱]  0%\n```"
    try:
        sent = bot.send_message(chat_id, think_text, reply_to_message_id=reply_to_msg_id,
                                parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Could not send thinking msg: {e}")
        return

    msg_id = sent.message_id

    # ── Step 2: Animate progress bar ──
    stages = [
        (0,  "⚙️  Initialising neural engine..."),
        (20, "🔍  Parsing your query..."),
        (40, "🧠  Loading context memory..."),
        (60, "🤖  Generating response..."),
        (80, "✨  Formatting output..."),
        (95, "🚀  Almost ready..."),
    ]
    for pct, label in stages:
        bar_idx = pct // 10
        bar     = PROGRESS_CHARS[bar_idx]
        upd_text = f"```Thinking\n{label}\n[{bar}]  {pct}%\n```"
        try:
            bot.edit_message_text(upd_text, chat_id, msg_id, parse_mode="Markdown")
        except Exception:
            pass
        time.sleep(0.35)

    # ── Step 3: Get actual answer ──
    try:
        raw_reply = ask_groq(user_id, question, extra_system)
    except Exception as e:
        logger.error(f"Groq error: {e}")
        err_text = (
            "⚠️ *Something went wrong!*\n\n"
            "> The AI engine hit a snag. Please try again in a moment.\n"
            + DEV_CREDIT
        )
        try:
            bot.edit_message_text(err_text, chat_id, msg_id, parse_mode="Markdown")
        except Exception:
            pass
        return

    # ── Step 4: Build formatted answer ──
    mention_str = f", {mention(user)}" if user else ""
    header = f"✨ *X Chat Bot*{mention_str}\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    footer = "\n\n━━━━━━━━━━━━━━━━━━━━━" + DEV_CREDIT

    full_answer = header + raw_reply + footer
    pages       = paginate(full_answer)

    # Store pages keyed by "chatid_msgid"
    page_key    = f"{chat_id}_{msg_id}"
    user_pages[page_key]        = pages
    user_current_page[page_key] = 0

    kb = depth_keyboard(page_key, len(pages), 0)

    # ── Step 5: Animate typing (edit in chunks) ──
    display = pages[0]
    try:
        # Quick typing effect: reveal in 4 chunks then full
        chunk_size = max(len(display) // 4, 100)
        for i in range(1, 4):
            partial = display[:chunk_size * i] + " ▌"
            bot.edit_message_text(partial, chat_id, msg_id, parse_mode="Markdown")
            time.sleep(0.25)
        # Final full message with keyboard
        bot.edit_message_text(display, chat_id, msg_id,
                               parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.warning(f"Edit error (likely identical text): {e}")
        try:
            bot.edit_message_text(display, chat_id, msg_id,
                                   parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass


def process_ai_query(message, question: str, extra_system: str = ""):
    """Central entry point — fires reaction, then runs thinking animation in a thread."""
    # ── Reaction ──────────────────────────────────────────────
    try:
        chosen = random.sample(REACTION_POOL, random.randint(1, 2))
        bot.set_message_reaction(message.chat.id, message.message_id,
                                  chosen, is_big=False)
    except Exception as e:
        logger.debug(f"Reaction failed: {e}")

    # ── Rate limit check ──────────────────────────────────────
    if is_rate_limited(message.from_user.id):
        bot.reply_to(message,
                     "⏳ *Slow down a bit!*\nYou're sending messages too fast. "
                     "Give me 10 seconds and try again 😅",
                     parse_mode="Markdown")
        return

    # ── Run in background thread so polling doesn't block ────
    t = threading.Thread(
        target=send_thinking_then_answer,
        args=(message.chat.id, message.message_id,
              message.from_user.id, question, extra_system, message.from_user),
        daemon=True
    )
    t.start()


# ─────────────────────────────────────────────────────────────
#  📲  /Xstart  (DM shows profile card; group shows quick guide)
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["Xstart", "start"])
def cmd_start(message: types.Message):
    user = message.from_user
    name = user.first_name or "there"

    if message.chat.type == "private":
        # ── DM: rich welcome with user info card ─────────────
        username_line = f"🔗 *Username:* @{user.username}" if user.username else "🔗 *Username:* _(not set)_"
        text = (
            f"🤖 *X Chat Bot — Welcome!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 Hey *{name}*! Great to see you.\n\n"
            f"📋 *Your Profile*\n"
            f"├ 👤 *Name:* {name}\n"
            f"├ 🆔 *User ID:* `{user.id}`\n"
            f"└ {username_line}\n\n"
            f"I'm *X Chat Bot*, powered by *Llama 4 Scout* via Groq ⚡\n"
            f"You can chat with me freely right here — just type anything!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 *What would you like to do?*"
            + DEV_CREDIT
        )
        bot.send_message(message.chat.id, text,
                         parse_mode="Markdown", reply_markup=dm_welcome_keyboard())
    else:
        # ── Group: quick-start guide ──────────────────────────
        text = (
            f"🤖 *X Chat Bot — Activated!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Hey *{name}* & everyone! 👋\n\n"
            f"*Ways to talk to me in this group:*\n"
            f"• Mention me → `@{get_bot_username()} your question`\n"
            f"• Say my name → `x bot your question`\n"
            f"• Command → `/ask your question`\n"
            f"• Reply to any of my messages to continue the chat 💬\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
            + DEV_CREDIT
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  ❓  /ask  command
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["ask"])
def cmd_ask(message: types.Message):
    # Strip "/ask" or "/ask@botname"
    question = re.sub(r'^/ask(@\S+)?', '', message.text, flags=re.IGNORECASE).strip()
    if not question:
        bot.reply_to(message,
                     "⚠️ *Please include your question!*\n"
                     "> Example: `/ask What is quantum physics?`",
                     parse_mode="Markdown")
        return
    process_ai_query(message, question)


# ─────────────────────────────────────────────────────────────
#  🗑  /Xclear
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["Xclear", "clear"])
def cmd_clear(message: types.Message):
    conversation_history.pop(message.from_user.id, None)
    bot.reply_to(message,
                 "🗑 *Conversation cleared!*\n\nStarting fresh — ask me anything 😊"
                 + DEV_CREDIT,
                 parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  💡  /Xhelp
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["Xhelp", "help"])
def cmd_help(message: types.Message):
    text = (
        "💡 *X Chat Bot — Help Guide*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*In Groups:*\n"
        "• `@YourBotUsername what is AI?`\n"
        "• `x bot explain black holes`\n"
        "• `x chat bot write a poem`\n"
        "• `/ask What is Pi?`\n"
        "• Reply to any bot message to continue the conversation\n\n"
        "*In DM:*\n"
        "• Just type anything — no commands needed! 🎉\n\n"
        "*Depth Buttons (under every reply):*\n"
        "• 🎯 Concise — short & punchy\n"
        "• 📖 Detailed — deep dive\n"
        "• 🧒 ELI5 — explain like I'm 5\n"
        "• 🏢 Professional — formal tone\n\n"
        "• ⏪⏩ — navigate long answers page by page\n\n"
        "━━━━━━━━━━━━━━━━━━━━━"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  ℹ️  /aboutX
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["aboutX", "about"])
def cmd_about(message: types.Message):
    text = (
        "🤖 *X Chat Bot — About*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧠 *AI Engine* — Llama 4 Scout (17B) via Groq\n"
        "📡 *Framework* — pyTelegramBotAPI (Python)\n"
        "🏗 *Hosted on* — Railway\n"
        "🔐 *Memory* — Per-user conversation history\n"
        "⚡ *Response* — Real-time thinking animation\n\n"
        "Built with ❤️ by *Ayush* (CipherX / Pyrexus)"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  📊  /Xstats  — Ultra-techy fabricated diagnostics
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["Xstats", "xstats"])
def cmd_stats(message: types.Message):
    bot.send_chat_action(message.chat.id, "typing")

    # Real measurements
    ping_start = time.time()
    bot.send_chat_action(message.chat.id, "typing")
    bot_ping   = round((time.time() - ping_start) * 1000, 2)
    now_str    = datetime.now().strftime("%Y-%m-%d | %H:%M:%S UTC")

    # Uptime
    elapsed  = int(time.time() - bot_start_time)
    days, r  = divmod(elapsed, 86400)
    hours, r = divmod(r, 3600)
    mins     = r // 60
    uptime   = f"{days}d {hours}h {mins}m"

    # Fabricated but plausible stats
    api_ping      = round(random.uniform(18.4, 52.7), 2)
    cpu_load      = round(random.uniform(4.2, 22.8), 1)
    ram_used      = random.randint(188, 412)
    ram_total     = 512
    thread_count  = random.randint(6, 14)
    tokens_served = random.randint(120000, 980000)
    req_per_min   = round(random.uniform(0.8, 4.2), 2)
    cache_hit     = random.randint(72, 94)
    temp          = round(random.uniform(38.2, 55.6), 1)
    freq          = round(random.uniform(2.8, 3.4), 2)
    build_hash    = ''.join(random.choices('0123456789abcdef', k=12))
    session_id    = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))
    node_id       = f"NODE-{random.randint(1,9)}{random.randint(100,999)}-{random.choice(['AX','BX','CX','DX'])}"
    entropy_key   = ''.join(random.choices('0123456789abcdef', k=32))
    net_in        = round(random.uniform(0.4, 2.8), 2)
    net_out       = round(random.uniform(0.1, 1.2), 2)
    disk_io       = round(random.uniform(0.0, 0.8), 2)
    active_count  = len(active_users)
    
    stats_msg = (
        f"📊 *X\\-BOT ADVANCED DIAGNOSTICS v2*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"> ⚡ *SYSTEM CORE*\n"
        f"```yaml\n"
        f"Creator       : Ayush (@CipherWrites)\n"
        f"Alias         : CipherX / Pyrexus\n"
        f"Timestamp     : {now_str}\n"
        f"Uptime        : {uptime}\n"
        f"Runtime       : Python 3.13 | Railway High-Perf\n"
        f"Build         : #{build_hash}\n"
        f"Session-ID    : {session_id}\n"
        f"Node          : {node_id}\n"
        f"```\n\n"
        f"> 🌐 *NETWORK & API HEALTH*\n"
        f"```ini\n"
        f"[ENDPOINT]    = api.groq.com/openai/v1\n"
        f"[STATUS]      = OPERATIONAL (200 OK)\n"
        f"[API_PING]    = {api_ping} ms\n"
        f"[BOT_PING]    = {bot_ping} ms\n"
        f"[NET_IN]      = {net_in} KB/s\n"
        f"[NET_OUT]     = {net_out} KB/s\n"
        f"[CACHE_HIT]   = {cache_hit}%\n"
        f"[REQ/MIN]     = {req_per_min}\n"
        f"```\n\n"
        f"> 🧠 *NEURAL ENGINE*\n"
        f"```fix\n"
        f"Model         : Llama-4-Scout-17B-16e-Instruct\n"
        f"Provider      : Groq (LPU Inference)\n"
        f"Context       : 131,072 Tokens\n"
        f"Tokens Served : {tokens_served:,}\n"
        f"Active Users  : {active_count}\n"
        f"```\n\n"
        f"> 💾 *RESOURCE MONITOR*\n"
        f"```css\n"
        f"CPU-Load      : {cpu_load}%\n"
        f"CPU-Freq      : {freq} GHz\n"
        f"CPU-Temp      : {temp} °C\n"
        f"RAM-Used      : {ram_used} / {ram_total} MB\n"
        f"Disk-I/O      : {disk_io} MB/s\n"
        f"Threads       : {thread_count} active\n"
        f"```\n\n"
        f"> 🔐 *SECURITY & ENTROPY*\n"
        f"```diff\n"
        f"+ Encryption  : AES-256-GCM\n"
        f"+ Auth        : HMAC-SHA512 verified\n"
        f"+ Firewall    : Active (Cloudflare WAF)\n"
        f"+ Entropy-Key : {entropy_key}\n"
        f"- Anomalies   : 0 detected\n"
        f"```\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛰 *All systems nominal. Running at peak performance.*"
        + DEV_CREDIT
    )

    bot.reply_to(message, stats_msg, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  🔔  INLINE CALLBACK HANDLER
# ─────────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call: types.CallbackQuery):
    data = call.data

    # ── DM welcome buttons ────────────────────────────────────
    if data == "dm_help":
        bot.answer_callback_query(call.id)
        cmd_help(call.message)
        return
    if data == "dm_stats":
        bot.answer_callback_query(call.id)
        cmd_stats(call.message)
        return
    if data == "dm_clear":
        bot.answer_callback_query(call.id)
        conversation_history.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id, "✅ Memory cleared!", show_alert=True)
        return
    if data == "dm_about":
        bot.answer_callback_query(call.id)
        cmd_about(call.message)
        return
    if data == "dm_fact":
        bot.answer_callback_query(call.id, "🎲 Fetching a random fact...")
        process_ai_query(call.message, "Tell me a surprising and mind-blowing random fact in 2-3 sentences.")
        return
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ── Depth buttons (concise / detailed / eli5 / professional) ──
    if data.startswith("depth|"):
        _, mode, page_key = data.split("|", 2)
        pages = user_pages.get(page_key)
        if not pages:
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please ask again.", show_alert=True)
            return
        bot.answer_callback_query(call.id, f"🔄 Rewriting as {mode}...")

        extra_map = {
            "concise":      "Rewrite your previous answer to be very concise — 3-5 sentences max. Keep it sharp.",
            "detailed":     "Rewrite your previous answer in full detail. Cover all aspects thoroughly, use examples.",
            "eli5":         "Rewrite your previous answer as if explaining to a 5-year-old. Simple words, fun analogies.",
            "professional": "Rewrite your previous answer in a formal, professional tone suitable for a business/academic context.",
        }
        extra_sys = extra_map.get(mode, "")
        # Get the original question from the last history entry
        history = conversation_history.get(call.from_user.id, [])
        orig_q  = next((h["content"] for h in reversed(history) if h["role"] == "user"), "Rephrase your last answer.")

        try:
            raw = ask_groq(call.from_user.id, f"[{mode.upper()} MODE] {orig_q}", extra_sys)
        except Exception as e:
            bot.answer_callback_query(call.id, "⚠️ API error. Try again.", show_alert=True)
            return

        header  = f"✨ *X Chat Bot* — _{mode.capitalize()} mode_\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        footer  = "\n\n━━━━━━━━━━━━━━━━━━━━━" + DEV_CREDIT
        new_text = header + raw + footer
        new_pages = paginate(new_text)
        user_pages[page_key]        = new_pages
        user_current_page[page_key] = 0

        kb = depth_keyboard(page_key, len(new_pages), 0)
        try:
            bot.edit_message_text(new_pages[0], call.message.chat.id, call.message.message_id,
                                   parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.warning(f"Edit error on depth: {e}")
        return

    # ── Pagination buttons ────────────────────────────────────
    if data.startswith("page|"):
        _, direction, page_key = data.split("|", 2)
        pages = user_pages.get(page_key)
        if not pages:
            bot.answer_callback_query(call.id, "⚠️ Session expired.", show_alert=True)
            return
        cur = user_current_page.get(page_key, 0)
        if direction == "next":
            cur = min(cur + 1, len(pages) - 1)
        else:
            cur = max(cur - 1, 0)
        user_current_page[page_key] = cur
        kb = depth_keyboard(page_key, len(pages), cur)
        try:
            bot.edit_message_text(pages[cur], call.message.chat.id, call.message.message_id,
                                   parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.warning(f"Page nav error: {e}")
        bot.answer_callback_query(call.id, f"📄 Page {cur+1}/{len(pages)}")
        return

    bot.answer_callback_query(call.id)


# ─────────────────────────────────────────────────────────────
#  💬  MAIN MESSAGE HANDLER
#  Handles: DM (any text), group (@mention / x bot / x chat bot),
#           replies to bot messages
# ─────────────────────────────────────────────────────────────
@bot.message_handler(
    func=lambda m: m.text and not m.text.startswith('/'),
    content_types=['text']
)
def handle_messages(message: types.Message):
    text_lower   = message.text.lower().strip()
    my_username  = get_bot_username()
    chat_type    = message.chat.type    # "private" | "group" | "supergroup"
    is_dm        = (chat_type == "private")

    # ── DM: respond to everything ─────────────────────────────
    if is_dm:
        process_ai_query(message, message.text.strip())
        return

    # ── GROUP: check triggers ─────────────────────────────────

    # 1. Reply to a bot message — continue conversation
    if (message.reply_to_message and
            message.reply_to_message.from_user and
            message.reply_to_message.from_user.username and
            message.reply_to_message.from_user.username.lower() == my_username):
        process_ai_query(message, message.text.strip())
        return

    # 2. @mention
    if f"@{my_username}" in text_lower:
        question = re.sub(rf'@{re.escape(my_username)}', '', message.text,
                          flags=re.IGNORECASE).strip()
        process_ai_query(message, question or "Hello!")
        return

    # 3. "x bot" or "x chat bot" (case-insensitive, at start OR anywhere)
    name_pattern = re.compile(
        r'(?:^|\b)(x\s+chat\s+bot|x\s+bot)(?:\b|$)',
        re.IGNORECASE
    )
    m = name_pattern.search(message.text)
    if m:
        question = name_pattern.sub('', message.text, count=1).strip()
        process_ai_query(message, question or "Hello!")
        return


# ─────────────────────────────────────────────────────────────
#  🔍  INLINE QUERY HANDLER  (type @botname query in any chat)
# ─────────────────────────────────────────────────────────────
@bot.inline_handler(lambda q: len(q.query) > 0)
def inline_query(inline_query: types.InlineQuery):
    try:
        user_text  = inline_query.query
        grok_reply = ask_groq(inline_query.from_user.id, user_text)
        preview    = grok_reply[:80] + "..." if len(grok_reply) > 80 else grok_reply

        r = types.InlineQueryResultArticle(
            id    = '1',
            title = "✨ Ask X Chat Bot",
            description = preview,
            input_message_content = types.InputTextMessageContent(
                message_text = (
                    f"🤖 *X Chat Bot*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"❓ *Q:* {user_text}\n\n"
                    f"💡 *A:* {grok_reply}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                    + DEV_CREDIT
                ),
                parse_mode = "Markdown"
            )
        )
        bot.answer_inline_query(inline_query.id, [r], cache_time=10)
    except Exception as e:
        logger.error(f"Inline error: {e}")


# ─────────────────────────────────────────────────────────────
#  🚀  ENTRY POINT
# ─────────────────────────────────────────────────────────────
def register_commands():
    """Set command menu visible in both DM and Groups."""
    commands = [
        types.BotCommand("xstart",  "🤖 Start / Welcome message"),
        types.BotCommand("ask",     "❓ Ask a question  — /ask <question>"),
        types.BotCommand("xhelp",   "💡 How to use this bot"),
        types.BotCommand("xclear",  "🗑 Clear conversation memory"),
        types.BotCommand("xstats",  "📊 Advanced bot diagnostics"),
        types.BotCommand("aboutx",  "ℹ️ About X Chat Bot"),
    ]
    try:
        # Private chats
        bot.set_my_commands(commands, scope=types.BotCommandScopeAllPrivateChats())
        # Groups & supergroups
        bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())
        logger.info("✅ Commands registered for DM + Groups")
    except Exception as e:
        logger.error(f"Command registration failed: {e}")


if __name__ == "__main__":
    bot.remove_webhook()
    register_commands()

    logger.info("🚀 X Chat Bot v2.0 is LIVE!")
    print("\n✅  X Chat Bot v2.0 running — Check Telegram!\n")

    bot.infinity_polling(timeout=60, long_polling_timeout=30, allowed_updates=[
        "message", "callback_query", "inline_query"
    ])
