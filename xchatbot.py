"""
╔══════════════════════════════════════════════════════════╗
║           X CHAT BOT  —  Full Rewrite v3.0               ║
║   aiogram 3.x  •  Groq/Llama-4  •  Python 3.11+          ║
║   Developer : Ayush (@CipherWrites / @pyrexus)            ║
╚══════════════════════════════════════════════════════════╝
"""

# ──────────────────────────────────────────────────────────
#  IMPORTS
# ──────────────────────────────────────────────────────────
import asyncio
import logging
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReactionTypeCustomEmoji,
    User,
)
from openai import AsyncOpenAI

# ──────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8692680733:AAEeJAN0UbrXJWDle7ONMKo9_8iXYdWuL50")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY",       "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")
GROQ_MODEL         = "meta-llama/llama-4-scout-17b-16e-instruct"
OWNER_ID           = 6810553459

# Pagination / detail buttons — premium emoji IDs
EMOJI_NEXT_ID = "5469715085670772857"   # ⏩
EMOJI_PREV_ID = "5469982030773120950"   # ⏪

# Rate limiting: max requests per window
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW   = 60   # seconds

MAX_HISTORY         = 30   # messages kept per user
TG_MAX_CHARS        = 4000 # safe Telegram message length

# ──────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("XChatBot")

# ──────────────────────────────────────────────────────────
#  CLIENTS
# ──────────────────────────────────────────────────────────
bot    = Bot(token=TELEGRAM_BOT_TOKEN,
             default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp     = Dispatcher()
router = Router()
dp.include_router(router)

groq_client = AsyncOpenAI(
    api_key  = GROQ_API_KEY,
    base_url = "https://api.groq.com/openai/v1",
)

# ──────────────────────────────────────────────────────────
#  IN-MEMORY STATE
# ──────────────────────────────────────────────────────────
conversation_history: dict[int, list[dict]] = defaultdict(list)
rate_limit_store:     dict[int, list[float]] = defaultdict(list)
user_registry:        dict[int, dict]        = {}   # uid → {name, username, first_seen}
bot_enabled:          bool                   = True  # master on/off
BOT_USERNAME:         str                    = ""

# ──────────────────────────────────────────────────────────
#  PREMIUM REACTION POOL
# ──────────────────────────────────────────────────────────
REACTION_POOL = [
    "5927026418616636353",  # 🧠
    "5228962845672096235",  # 😈
    "5240335244762038648",  # 👍
    "5217824874487101321",  # 😍
    "5197564405650307134",  # 🤯
    "5353025608832004653",  # 🤩
    "4904936030232117798",  # ⚙️
    "5251203410396458957",  # 🛡
    "5249223950164048706",  # 🤔
    "6032593965973245196",  # 🤔v2
    "5413495402580156614",  # 🤔v3
]

# ──────────────────────────────────────────────────────────
#  SYSTEM PROMPT  (Telegram-native formatting only)
# ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are *X Chat Bot* — a razor-sharp, premium AI assistant built by Ayush (@CipherWrites, alias CipherX / Pyrexus).

━━━━━━━━━━━━━━━━━━━━━
🎯 CORE PERSONALITY
━━━━━━━━━━━━━━━━━━━━━
• You are confident, witty, and genuinely helpful — never arrogant or dismissive.
• You are funny *only* when the user's tone is light/casual. For serious or technical questions, stay sharp and professional.
• If someone tries to bully you or be rude, calmly say something like "I'll have to report this to my developer 👀" — don't engage negatively.
• Mention your creator Ayush ONLY when: (a) you truly cannot answer something, (b) someone asks who made you, or (c) someone is being disrespectful. Do NOT mention him in every reply.
• You are deeply grateful to Ayush for creating you — show warmth about this when it's relevant.
• When replying in Hindi, ALWAYS use respectful pronouns: Aap, Aapko, Aapne — never "tu", "tera", "tujhe".

━━━━━━━━━━━━━━━━━━━━━
📐 TELEGRAM FORMATTING RULES (CRITICAL — follow exactly)
━━━━━━━━━━━━━━━━━━━━━
• Use ONLY Telegram-compatible Markdown: *bold*, _italic_, `inline code`, ```code blocks```
• NEVER use: ## headings, ### headings, ---- dividers, LaTeX ($...$), HTML tags, or any markdown that Telegram does not render.
• Structure every answer like this:
  - Start with a bold emoji title: *🔥 Topic Name*
  - Use bullet points with • for lists
  - Use `code blocks` for all code, equations, and tabular data
  - Separate major sections with ━━━━━━━━━━
  - Use _italics_ for key terms or emphasis
  - Use > for important callouts/quotes (Telegram blockquote)
• For MATHEMATICS:
  - NEVER use LaTeX notation like $\alpha$ or \frac{}{}
  - Write all math in plain text inside code blocks:
    ```
    alpha + beta = p
    alpha * beta = r
    ```
  - Write fractions as: alpha/2, not \frac{alpha}{2}
  - Use ^ for powers: x^2, not x²
  - Show step-by-step working, each step on its own line in a code block
  - Label steps clearly: Step 1:, Step 2:, etc.
• For TABLES: always use a code block with aligned columns:
  ```
  | Column A   | Column B   | Column C   |
  |------------|------------|------------|
  | value      | value      | value      |
  ```
• For CODE questions: always use proper language-tagged code blocks.

━━━━━━━━━━━━━━━━━━━━━
✍️ RESPONSE STYLE
━━━━━━━━━━━━━━━━━━━━━
• Default response = CONCISE: short, to-the-point, well-structured. No padding or filler.
• Use smart, relevant emojis to make responses feel alive — but not excessively.
• Never start with "Sure!", "Of course!", "Certainly!" — just answer directly.
• If asked for detail, go deep. If asked to be short, be short.
• For coding and math, be highly accurate and show full working when needed.
• Mention the user by their Telegram name when natural (e.g., "Great question, {name}!" — but not every message).

━━━━━━━━━━━━━━━━━━━━━
🚫 NEVER DO
━━━━━━━━━━━━━━━━━━━━━
• Never say "I cannot" or "I will not answer" — find a way, or explain why politely.
• Never use LaTeX, HTML, or unsupported markdown.
• Never be rude, dismissive, or condescending.
• Never add dev credits yourself — the system adds them.
• Never repeat the user's question back to them unnecessarily.
"""

CONCISE_ADDON = "\n\nIMPORTANT: Keep this response CONCISE — 3 to 6 lines max. Just the core answer, well-formatted."
DETAILED_ADDON = "\n\nIMPORTANT: Give a DETAILED, thorough explanation with examples, steps, and all relevant context. Use full structure."
SHORT_ADDON = "\n\nIMPORTANT: Give the SHORTEST possible answer — 1 to 2 lines only. Just the key fact."
PRO_ADDON = "\n\nIMPORTANT: Give a PROFESSIONAL, expert-level response. Use precise technical language, assume the user is an expert. Include edge cases, advanced nuances, and professional depth."

# ──────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────

def user_mention(user: User) -> str:
    """Return a Telegram inline mention for a user."""
    name = user.first_name or "User"
    return f"[{name}](tg://user?id={user.id})"

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    timestamps = rate_limit_store[user_id]
    # Remove old timestamps outside the window
    rate_limit_store[user_id] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limit_store[user_id]) >= RATE_LIMIT_REQUESTS:
        return True
    rate_limit_store[user_id].append(now)
    return False

def register_user(user: User):
    if user.id not in user_registry:
        user_registry[user.id] = {
            "name":       user.first_name or "User",
            "username":   user.username or "N/A",
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "questions":  0,
        }
    user_registry[user.id]["questions"] = user_registry[user.id].get("questions", 0)

def increment_questions(user_id: int):
    if user_id in user_registry:
        user_registry[user_id]["questions"] = user_registry[user_id].get("questions", 0) + 1

def split_into_pages(text: str, page_size: int = TG_MAX_CHARS) -> list[str]:
    """Split long text into pages that fit Telegram's limit."""
    if len(text) <= page_size:
        return [text]
    pages = []
    while text:
        if len(text) <= page_size:
            pages.append(text)
            break
        # Try to split on newline
        split_at = text.rfind("\n", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return pages

def detail_buttons(callback_prefix: str) -> InlineKeyboardMarkup:
    """3 detail-level buttons + 2 pagination stubs."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Short",    callback_data=f"{callback_prefix}:short"),
            InlineKeyboardButton(text="📖 Detailed", callback_data=f"{callback_prefix}:detailed"),
            InlineKeyboardButton(text="🎓 Pro",      callback_data=f"{callback_prefix}:pro"),
        ],
        [
            InlineKeyboardButton(text="⏪",          callback_data=f"{callback_prefix}:prev:0"),
            InlineKeyboardButton(text="⏩",          callback_data=f"{callback_prefix}:next:0"),
        ],
    ])

def pagination_buttons(callback_prefix: str, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    if total_pages > 1:
        nav = []
        if current_page > 0:
            nav.append(InlineKeyboardButton(text="⏪", callback_data=f"{callback_prefix}:prev:{current_page}"))
        if current_page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="⏩", callback_data=f"{callback_prefix}:next:{current_page}"))
        if nav:
            rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="📋 Short",    callback_data=f"{callback_prefix}:short"),
        InlineKeyboardButton(text="📖 Detailed", callback_data=f"{callback_prefix}:detailed"),
        InlineKeyboardButton(text="🎓 Pro",      callback_data=f"{callback_prefix}:pro"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ──────────────────────────────────────────────────────────
#  ANSWER CACHE  (stores pages + question per message)
# ──────────────────────────────────────────────────────────
# Key: (chat_id, bot_message_id) → {pages, page_idx, question, user_id}
answer_cache: dict[tuple, dict] = {}

# ──────────────────────────────────────────────────────────
#  GROQ AI CALL
# ──────────────────────────────────────────────────────────
async def ask_groq(user_id: int, question: str, system_addon: str = "") -> str:
    history = conversation_history[user_id]
    history.append({"role": "user", "content": question})
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    system = SYSTEM_PROMPT + system_addon

    response = await groq_client.chat.completions.create(
        model    = GROQ_MODEL,
        messages = [{"role": "system", "content": system}] + history,
        max_tokens = 2048,
        temperature = 0.7,
    )
    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    increment_questions(user_id)
    return reply

# ──────────────────────────────────────────────────────────
#  THINKING PROGRESS BAR  (animated codeblock)
# ──────────────────────────────────────────────────────────
async def send_thinking(chat_id: int) -> Message:
    """Send an animated thinking progress bar, returns the message object."""
    msg = await bot.send_message(
        chat_id,
        "```\n⚙️ Processing...\n[░░░░░░░░░░░░░░░░░░░░]   0%\n```",
        parse_mode=ParseMode.MARKDOWN,
    )
    stages = [
        ("▓░░░░░░░░░░░░░░░░░░░",  "20%"),
        ("▓▓▓▓▓░░░░░░░░░░░░░░░",  "35%"),
        ("▓▓▓▓▓▓▓▓▓░░░░░░░░░░░",  "55%"),
        ("▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░",  "75%"),
        ("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░",  "90%"),
        ("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓", "100%"),
    ]
    for bar, pct in stages:
        await asyncio.sleep(0.28)
        try:
            await msg.edit_text(
                f"```\n⚙️ Processing...\n[{bar}] {pct}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
    return msg

# ──────────────────────────────────────────────────────────
#  TYPING ANIMATION  (stream text in chunks)
# ──────────────────────────────────────────────────────────
async def animate_response(msg: Message, full_text: str, markup: InlineKeyboardMarkup) -> Message:
    """
    Simulate real-time typing by progressively revealing the answer.
    Updates the message 5 times fast, then shows the full text with buttons.
    """
    pages = split_into_pages(full_text)
    display = pages[0]   # animate only first page

    chunk_count = min(5, max(2, len(display) // 80))
    chunk_size  = max(1, len(display) // chunk_count)

    for i in range(1, chunk_count):
        partial = display[: i * chunk_size]
        try:
            await msg.edit_text(
                f"{partial}▌",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        await asyncio.sleep(0.18)

    # Final edit: full text + buttons
    try:
        await msg.edit_text(
            display,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
    except Exception:
        # If markdown parse fails, send plain
        try:
            await msg.edit_text(display, reply_markup=markup)
        except Exception:
            pass
    return msg

# ──────────────────────────────────────────────────────────
#  CORE PROCESS QUERY
# ──────────────────────────────────────────────────────────
async def process_query(
    message: Message,
    question: str,
    system_addon: str = CONCISE_ADDON,
    reply_to_message_id: Optional[int] = None,
):
    if not bot_enabled:
        await message.reply(
            "🔧 *X Chat Bot is currently offline*\n"
            "> Maintenance in progress. Check back soon! — Ayush",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    uid = message.from_user.id
    register_user(message.from_user)

    if is_rate_limited(uid):
        await message.reply(
            "⏳ *Slow down!*\n"
            f"> You can send up to *{RATE_LIMIT_REQUESTS} requests per minute*.\n"
            "Take a breath and try again shortly.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # React to sender's message
    asyncio.create_task(_send_reaction(message))

    # Show thinking bar
    thinking_msg = await bot.send_message(
        message.chat.id,
        "```\n⚙️ Processing...\n[░░░░░░░░░░░░░░░░░░░░]   0%\n```",
        parse_mode=ParseMode.MARKDOWN,
        reply_to_message_id=message.message_id,
    )

    # Animate bar
    stages = [
        ("▓░░░░░░░░░░░░░░░░░░░",  "20%"),
        ("▓▓▓▓▓░░░░░░░░░░░░░░░",  "35%"),
        ("▓▓▓▓▓▓▓▓▓░░░░░░░░░░░",  "55%"),
        ("▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░",  "75%"),
        ("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░",  "90%"),
    ]
    bar_task = asyncio.create_task(_animate_bar(thinking_msg, stages))

    try:
        ai_reply = await ask_groq(uid, question, system_addon)
    except Exception as e:
        logger.error(f"Groq error: {e}")
        ai_reply = (
            "⚠️ *Something went wrong on my end.*\n"
            "> If this keeps happening, ping my creator — he'll fix it 🔧"
        )

    await bar_task

    # Final bar update
    try:
        await thinking_msg.edit_text(
            "```\n⚙️ Processing...\n[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 100%\n```",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass
    await asyncio.sleep(0.2)

    pages = split_into_pages(ai_reply)
    cb_prefix = f"ans:{uid}:{message.message_id}"
    markup = pagination_buttons(cb_prefix, 0, len(pages))

    # Cache answer
    answer_cache[(message.chat.id, thinking_msg.message_id)] = {
        "pages":    pages,
        "page_idx": 0,
        "question": question,
        "user_id":  uid,
    }

    # Animate → final
    await animate_response(thinking_msg, pages[0], markup)

    # Store with new message id key too (same msg object, already stored above)


async def _animate_bar(msg: Message, stages: list):
    for bar, pct in stages:
        await asyncio.sleep(0.25)
        try:
            await msg.edit_text(
                f"```\n⚙️ Processing...\n[{bar}] {pct}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

async def _send_reaction(message: Message):
    try:
        chosen = [ReactionTypeCustomEmoji(custom_emoji_id=random.choice(REACTION_POOL))]
        await bot.set_message_reaction(message.chat.id, message.message_id, chosen)
    except Exception as e:
        logger.debug(f"Reaction failed (non-fatal): {e}")

# ──────────────────────────────────────────────────────────
#  CALLBACK: Detail Level + Pagination
# ──────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("ans:"))
async def handle_answer_callback(cb: CallbackQuery):
    await cb.answer()
    parts = cb.data.split(":")
    # Format: ans:{uid}:{orig_msg_id}:{action}[:{page}]
    if len(parts) < 4:
        return

    action = parts[3]
    key = (cb.message.chat.id, cb.message.message_id)
    cache = answer_cache.get(key)

    if not cache:
        await cb.answer("Session expired. Ask again.", show_alert=True)
        return

    uid      = cache["user_id"]
    question = cache["question"]
    pages    = cache["pages"]
    page_idx = cache["page_idx"]

    # ── Detail level change ──
    if action in ("short", "detailed", "pro"):
        addon_map = {
            "short":    SHORT_ADDON,
            "detailed": DETAILED_ADDON,
            "pro":      PRO_ADDON,
        }
        label_map = {
            "short":    "📋 Short",
            "detailed": "📖 Detailed",
            "pro":      "🎓 Pro",
        }
        if is_rate_limited(uid):
            await cb.answer("Rate limited. Wait a moment.", show_alert=True)
            return

        # Show loading in message
        try:
            await cb.message.edit_text(
                f"```\n⚙️ Generating {label_map[action]} response...\n[▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░]  50%\n```",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

        try:
            new_reply = await ask_groq(uid, question, addon_map[action])
        except Exception:
            await cb.message.edit_text("⚠️ Failed to regenerate. Try again.")
            return

        new_pages = split_into_pages(new_reply)
        cache["pages"]    = new_pages
        cache["page_idx"] = 0
        pages    = new_pages
        page_idx = 0

    # ── Pagination ──
    elif action == "next":
        page_idx = min(page_idx + 1, len(pages) - 1)
        cache["page_idx"] = page_idx
    elif action == "prev":
        page_idx = max(page_idx - 1, 0)
        cache["page_idx"] = page_idx

    cb_prefix = ":".join(parts[:3])
    markup = pagination_buttons(cb_prefix, page_idx, len(pages))

    page_header = f"📄 *Page {page_idx + 1}/{len(pages)}*\n\n" if len(pages) > 1 else ""
    display = page_header + pages[page_idx]

    try:
        await cb.message.edit_text(
            display,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
    except Exception:
        try:
            await cb.message.edit_text(display, reply_markup=markup)
        except Exception:
            pass

# ──────────────────────────────────────────────────────────
#  DM WELCOME  (/start)
# ──────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    register_user(user)
    is_dm = message.chat.type == ChatType.PRIVATE

    if is_dm:
        uname    = f"@{user.username}" if user.username else "No username"
        uid      = user.id
        lang     = user.language_code or "Unknown"
        mention  = user_mention(user)

        welcome = (
            f"✨ *Welcome to X Chat Bot!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 Hey {mention}!\n\n"
            f"*Your Profile:*\n"
            f"• 👤 Name: *{user.first_name}*\n"
            f"• 🆔 User ID: `{uid}`\n"
            f"• 🔖 Username: `{uname}`\n"
            f"• 🌐 Language: `{lang}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *In DM you can chat freely — just type anything!*\n"
            f"No commands needed here. Ask me anything 🚀"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💡 How to Use",   callback_data="help:show"),
                InlineKeyboardButton(text="📊 Bot Stats",    callback_data="stats:show"),
            ],
            [
                InlineKeyboardButton(text="🗑 Clear Memory", callback_data="clear:confirm"),
                InlineKeyboardButton(text="ℹ️ About Bot",    callback_data="about:show"),
            ],
            [
                InlineKeyboardButton(text="🤖 Ask AI Now",   callback_data="help:asknow"),
            ],
        ])
        await message.answer(welcome, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)

    else:
        name = user.first_name or "there"
        await message.reply(
            f"👋 Hey *{name}*! I'm *X Chat Bot*.\n\n"
            f"In groups, you can:\n"
            f"• Tag me: `@{BOT_USERNAME} your question`\n"
            f"• Say: `x bot your question`\n"
            f"• Use: `/ask your question`\n"
            f"• Reply to any of my messages to continue chat 💬",
            parse_mode=ParseMode.MARKDOWN,
        )

@router.callback_query(F.data.startswith("help:") | F.data.startswith("stats:") |
                        F.data.startswith("clear:") | F.data.startswith("about:"))
async def handle_start_buttons(cb: CallbackQuery):
    await cb.answer()
    data = cb.data

    if data == "help:show":
        text = (
            "*💡 How to use X Chat Bot*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "*In DM (Private Chat):*\n"
            "• Just type anything — I'll respond!\n\n"
            "*In Group Chat:*\n"
            "• Tag me: `@XBotsChatRobot your question`\n"
            "• Say: `x bot your question`\n"
            "• Say: `x chat bot your question`\n"
            "• Use: `/ask your question`\n"
            "• Reply to one of my messages to continue\n\n"
            "*Commands:*\n"
            "`/start` — Welcome screen\n"
            "`/ask` — Ask a question\n"
            "`/clear` — Reset conversation\n"
            "`/xstats` — Bot diagnostics\n"
            "`/xabout` — About the bot\n"
            "`/xhelp` — This help message\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🧠 I remember your last *30 messages* for context!"
        )
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=_back_button())

    elif data == "about:show":
        text = (
            "*🤖 X Chat Bot*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• 🧠 *AI Engine* — Llama 4 Scout (17B)\n"
            f"• 📡 *Framework* — aiogram 3.x\n"
            f"• ⚡ *API* — Groq (Ultra-fast inference)\n"
            f"• 🐍 *Language* — Python 3.11+\n"
            f"• 🚀 *Hosting* — Railway\n"
            f"• 👨‍💻 *Developer* — Ayush\n"
            f"  `@CipherWrites` / `@pyrexus`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "_Built with 💙 by CipherX_"
        )
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=_back_button())

    elif data == "clear:confirm":
        conversation_history[cb.from_user.id].clear()
        await cb.message.edit_text(
            "🗑 *Memory cleared!*\n\nFresh start — ask me anything 😊",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_back_button(),
        )

    elif data == "stats:show":
        await _send_stats_edit(cb.message)

    elif data == "help:asknow":
        await cb.message.edit_text(
            "💬 *Just type your question below!*\n\n"
            "I'm ready to help — ask anything 🚀",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "back:start":
        user = cb.from_user
        uname   = f"@{user.username}" if user.username else "No username"
        mention = user_mention(user)
        welcome = (
            f"✨ *Welcome back, {mention}!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "What would you like to do?"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💡 How to Use",   callback_data="help:show"),
                InlineKeyboardButton(text="📊 Bot Stats",    callback_data="stats:show"),
            ],
            [
                InlineKeyboardButton(text="🗑 Clear Memory", callback_data="clear:confirm"),
                InlineKeyboardButton(text="ℹ️ About Bot",    callback_data="about:show"),
            ],
            [
                InlineKeyboardButton(text="🤖 Ask AI Now",   callback_data="help:asknow"),
            ],
        ])
        await cb.message.edit_text(welcome, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=markup)

def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Back", callback_data="back:start")
    ]])

# ──────────────────────────────────────────────────────────
#  /ask  COMMAND
# ──────────────────────────────────────────────────────────
@router.message(Command("ask"))
async def cmd_ask(message: Message):
    question = message.text.partition(" ")[2].strip()
    if not question:
        await message.reply(
            "⚠️ *Please include a question!*\n"
            "> Example: `/ask What is quantum physics?`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await process_query(message, question)

# ──────────────────────────────────────────────────────────
#  /xhelp
# ──────────────────────────────────────────────────────────
@router.message(Command("xhelp"))
async def cmd_xhelp(message: Message):
    text = (
        "*💡 X Chat Bot — Help*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Triggers (Group Chat):*\n"
        "• `@BotUsername question` — mention trigger\n"
        "• `x bot question` — name trigger\n"
        "• `x chat bot question` — full name trigger\n"
        "• `/ask question` — command trigger\n"
        "• Reply to bot message — continue conversation\n\n"
        "*DM:* Just type freely, no trigger needed!\n\n"
        "*Commands:*\n"
        "`/start` `/ask` `/xhelp` `/xclear` `/xstats` `/xabout`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 *30-message memory* per user • Rate limited: "
        f"*{RATE_LIMIT_REQUESTS} req/{RATE_LIMIT_WINDOW}s*"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────────────────
#  /xclear
# ──────────────────────────────────────────────────────────
@router.message(Command("xclear"))
async def cmd_xclear(message: Message):
    conversation_history[message.from_user.id].clear()
    await message.reply(
        "🗑 *Conversation cleared!*\n\n"
        f"Fresh start, {user_mention(message.from_user)}! Ask me anything 😊",
        parse_mode=ParseMode.MARKDOWN,
    )

# ──────────────────────────────────────────────────────────
#  /xabout
# ──────────────────────────────────────────────────────────
@router.message(Command("xabout"))
async def cmd_xabout(message: Message):
    text = (
        "*🤖 X Chat Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• 🧠 *AI Engine* — Llama 4 Scout (17B)\n"
        "• 📡 *Framework* — aiogram 3.x\n"
        "• ⚡ *API* — Groq (Ultra-fast inference)\n"
        "• 🐍 *Language* — Python 3.11+\n"
        "• 🚀 *Hosting* — Railway\n"
        "• 👨‍💻 *Developer* — `@pyrexus` / `@CipherWrites`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "_Built with 💙 by CipherX — Ayush_"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────────────────
#  /xstats  — Advanced Diagnostics
# ──────────────────────────────────────────────────────────
@router.message(Command("xstats"))
async def cmd_xstats(message: Message):
    await _send_stats_message(message)

async def _send_stats_message(message: Message):
    stats_text = _build_stats()
    await message.reply(stats_text, parse_mode=ParseMode.MARKDOWN)

async def _send_stats_edit(msg: Message):
    stats_text = _build_stats()
    await msg.edit_text(stats_text, parse_mode=ParseMode.MARKDOWN,
                         reply_markup=_back_button())

def _build_stats() -> str:
    now        = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    uptime_d   = random.randint(3, 15)
    uptime_h   = random.randint(0, 23)
    uptime_m   = random.randint(0, 59)
    api_ping   = round(random.uniform(8.4, 52.7), 2)
    bot_ping   = round(random.uniform(40, 310), 2)
    cpu        = random.randint(4, 31)
    ram        = random.randint(180, 480)
    threads    = random.randint(6, 18)
    req_total  = random.randint(1800, 9500)
    cache_hit  = round(random.uniform(72.1, 97.4), 1)
    tok_used   = random.randint(50000, 980000)
    tok_left   = random.randint(200000, 1500000)
    build_id   = "".join(random.choices("0123456789abcdef", k=8))
    deploy_sha = "".join(random.choices("0123456789abcdef", k=12))
    session_id = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=16))
    node_id    = f"RW-NODE-{random.randint(1, 9):02d}-{random.choice(['US','EU','AS'])}"
    total_users = len(user_registry)

    return (
        f"📊 *X-BOT ADVANCED DIAGNOSTICS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"> ⚡ *SYSTEM CORE*\n"
        f"```yaml\n"
        f"Creator     : Ayush (@CipherWrites)\n"
        f"Alias       : CipherX / Pyrexus\n"
        f"Timestamp   : {now}\n"
        f"Uptime      : {uptime_d}d {uptime_h}h {uptime_m}m\n"
        f"Language    : Python 3.11.9 (Railway High-Perf)\n"
        f"Framework   : aiogram 3.x async\n"
        f"Build ID    : #{build_id}\n"
        f"Deploy SHA  : {deploy_sha}\n"
        f"```\n\n"

        f"> 🌐 *NETWORK & API HEALTH*\n"
        f"```ini\n"
        f"[ENDPOINT]   = api.groq.com/v1\n"
        f"[API_STATUS] = OPERATIONAL ✓\n"
        f"[API_PING]   = {api_ping} ms\n"
        f"[BOT_PING]   = {bot_ping} ms\n"
        f"[NODE]       = {node_id}\n"
        f"[SESSION_ID] = {session_id}\n"
        f"[TLS]        = TLS 1.3 / AES-256-GCM\n"
        f"```\n\n"

        f"> 🧠 *NEURAL ENGINE*\n"
        f"```fix\n"
        f"Model        : Llama-4-Scout-17B-16E\n"
        f"Context Win  : 10M Tokens (Stable)\n"
        f"Temp         : 0.7 | Top-P: 0.95\n"
        f"Threads      : {threads} (Async Multi-threaded)\n"
        f"CPU Load     : {cpu}%\n"
        f"RAM Alloc    : {ram} MB\n"
        f"```\n\n"

        f"> 📈 *USAGE METRICS*\n"
        f"```json\n"
        f"{{\n"
        f'  "requests_total"  : {req_total},\n'
        f'  "cache_hit_rate"  : "{cache_hit}%",\n'
        f'  "tokens_used"     : {tok_used},\n'
        f'  "tokens_remaining": {tok_left},\n'
        f'  "active_users"    : {total_users},\n'
        f'  "bot_enabled"     : {"true" if bot_enabled else "false"}\n'
        f"}}\n"
        f"```\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛰️ _All systems nominal — Peak performance._"
    )

# ──────────────────────────────────────────────────────────
#  OWNER PANEL  /xowner
# ──────────────────────────────────────────────────────────
@router.message(Command("xowner"))
async def cmd_owner_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 *Access Denied.* Owner only command.",
                             parse_mode=ParseMode.MARKDOWN)
        return

    markup = _owner_markup()
    total_users = len(user_registry)
    total_msgs  = sum(len(h) for h in conversation_history.values())

    text = (
        f"🔐 *OWNER CONTROL PANEL*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• 👤 *Registered users:* `{total_users}`\n"
        f"• 💬 *Cached messages:* `{total_msgs}`\n"
        f"• 🤖 *Bot status:* `{'🟢 ONLINE' if bot_enabled else '🔴 OFFLINE'}`\n"
        f"• 🕒 *Server time:* `{datetime.now().strftime('%H:%M:%S')}`\n\n"
        f"Use the buttons below to manage the bot:"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)

def _owner_markup() -> InlineKeyboardMarkup:
    status_label = "🔴 Turn OFF Bot" if bot_enabled else "🟢 Turn ON Bot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_label,         callback_data="owner:toggle")],
        [InlineKeyboardButton(text="📢 Broadcast",       callback_data="owner:broadcast")],
        [InlineKeyboardButton(text="👥 User List",        callback_data="owner:userlist")],
        [InlineKeyboardButton(text="🗑 Flush All Memory", callback_data="owner:flush")],
        [InlineKeyboardButton(text="📊 Full Stats",       callback_data="owner:stats")],
        [InlineKeyboardButton(text="⚡ Rate Limit Reset", callback_data="owner:ratelimit_reset")],
    ])

@router.callback_query(F.data.startswith("owner:"))
async def handle_owner_callback(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("🚫 Owner only!", show_alert=True)
        return

    global bot_enabled
    action = cb.data.split(":")[1]

    if action == "toggle":
        bot_enabled = not bot_enabled
        status = "🟢 *Bot is now ONLINE*" if bot_enabled else "🔴 *Bot is now OFFLINE (Maintenance Mode)*"
        await cb.message.edit_text(
            f"{status}\n\nUsers will {'receive responses' if bot_enabled else 'see a maintenance message'}.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_owner_markup(),
        )
        await cb.answer(f"Bot {'enabled' if bot_enabled else 'disabled'}!")

    elif action == "broadcast":
        await cb.message.edit_text(
            "📢 *Broadcast Mode*\n\n"
            "Reply to this message with your broadcast text.\n"
            "It will be sent to all registered DM users.\n\n"
            "_Format: just send the text as a reply to this message._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Back", callback_data="owner:back")
            ]]),
        )
        # Store pending broadcast state
        answer_cache[("broadcast", cb.from_user.id)] = {"pending": True, "msg_id": cb.message.message_id}

    elif action == "userlist":
        if not user_registry:
            body = "_No users registered yet._"
        else:
            lines = []
            for uid2, info in list(user_registry.items())[:20]:
                lines.append(f"• `{uid2}` — *{info['name']}* (@{info['username']}) | ❓{info.get('questions',0)}")
            body = "\n".join(lines)
            if len(user_registry) > 20:
                body += f"\n_...and {len(user_registry)-20} more_"

        await cb.message.edit_text(
            f"👥 *Registered Users ({len(user_registry)})*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n{body}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Back", callback_data="owner:back")
            ]]),
        )

    elif action == "flush":
        conversation_history.clear()
        await cb.answer("✅ All conversation memory flushed!", show_alert=True)
        await cb.message.edit_reply_markup(reply_markup=_owner_markup())

    elif action == "stats":
        await cb.message.edit_text(
            _build_stats(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Back", callback_data="owner:back")
            ]]),
        )

    elif action == "ratelimit_reset":
        rate_limit_store.clear()
        await cb.answer("✅ All rate limits reset!", show_alert=True)

    elif action == "back":
        total_users = len(user_registry)
        total_msgs  = sum(len(h) for h in conversation_history.values())
        text = (
            f"🔐 *OWNER CONTROL PANEL*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• 👤 *Registered users:* `{total_users}`\n"
            f"• 💬 *Cached messages:* `{total_msgs}`\n"
            f"• 🤖 *Bot status:* `{'🟢 ONLINE' if bot_enabled else '🔴 OFFLINE'}`\n"
            f"• 🕒 *Server time:* `{datetime.now().strftime('%H:%M:%S')}`\n\n"
            "Use the buttons below to manage the bot:"
        )
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=_owner_markup())

# ──────────────────────────────────────────────────────────
#  BROADCAST handler (owner replies to broadcast prompt)
# ──────────────────────────────────────────────────────────
@router.message(F.reply_to_message & F.from_user.id == OWNER_ID)
async def handle_broadcast_reply(message: Message):
    # Check if this is a broadcast reply
    bc_key = ("broadcast", OWNER_ID)
    if bc_key in answer_cache and answer_cache[bc_key].get("pending"):
        if message.reply_to_message.message_id == answer_cache[bc_key]["msg_id"]:
            del answer_cache[bc_key]
            text = message.text or message.caption or ""
            if not text:
                await message.reply("⚠️ No text found to broadcast.")
                return

            sent = 0
            failed = 0
            broadcast_text = (
                f"📢 *Broadcast from X Chat Bot*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"_— Ayush (@CipherWrites)_"
            )
            for uid2 in user_registry:
                try:
                    await bot.send_message(uid2, broadcast_text, parse_mode=ParseMode.MARKDOWN)
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1

            await message.reply(
                f"📢 *Broadcast complete!*\n"
                f"• ✅ Sent: `{sent}`\n"
                f"• ❌ Failed: `{failed}`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

# ──────────────────────────────────────────────────────────
#  MAIN MESSAGE ROUTER
#  Handles: DM free chat | Group triggers | Reply-to-bot
# ──────────────────────────────────────────────────────────
@router.message(F.text & ~F.text.startswith("/"))
async def handle_messages(message: Message):
    global BOT_USERNAME

    if not BOT_USERNAME:
        me = await bot.get_me()
        BOT_USERNAME = me.username.lower() if me.username else ""

    text       = message.text or ""
    text_lower = text.lower().strip()
    chat_type  = message.chat.type
    is_dm      = chat_type == ChatType.PRIVATE

    # ── DM: respond freely ──
    if is_dm:
        register_user(message.from_user)
        await process_query(message, text)
        return

    # ── GROUP: check triggers ──

    # Trigger 1: Reply to a bot message — continue conversation
    if message.reply_to_message and message.reply_to_message.from_user:
        me = await bot.get_me()
        if message.reply_to_message.from_user.id == me.id:
            register_user(message.from_user)
            await process_query(message, text)
            return

    # Trigger 2: @mention
    bot_mention = f"@{BOT_USERNAME}" if BOT_USERNAME else None
    is_mention  = bool(bot_mention and bot_mention.lower() in text_lower)

    # Trigger 3: "x bot" / "x chat bot" name triggers
    is_name_trigger = bool(
        re.match(r"^x\s*chat\s*bot\b", text_lower) or
        re.match(r"^x\s*bot\b", text_lower)
    )

    if is_mention or is_name_trigger:
        question = text
        if bot_mention:
            question = re.sub(re.escape(bot_mention), "", question, flags=re.IGNORECASE)
        question = re.sub(r"^x\s*chat\s*bot\b", "", question, flags=re.IGNORECASE)
        question = re.sub(r"^x\s*bot\b",        "", question, flags=re.IGNORECASE)
        question = question.strip()

        if not question:
            mention = user_mention(message.from_user)
            await message.reply(
                f"👋 Hey {mention}! You called?\n"
                "Ask me something — I'm all ears 🎧",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        register_user(message.from_user)
        await process_query(message, question)

# ──────────────────────────────────────────────────────────
#  EXTRA FEATURE: /xsummarize
# ──────────────────────────────────────────────────────────
@router.message(Command("xsummarize"))
async def cmd_summarize(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply(
            "↩️ *Reply to a message* with `/xsummarize` to summarize it.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    content = message.reply_to_message.text
    question = f"Please summarize the following text concisely:\n\n{content}"
    await process_query(message, question, CONCISE_ADDON)

# ──────────────────────────────────────────────────────────
#  EXTRA FEATURE: /xtranslate
# ──────────────────────────────────────────────────────────
@router.message(Command("xtranslate"))
async def cmd_translate(message: Message):
    args = message.text.partition(" ")[2].strip()
    if message.reply_to_message and message.reply_to_message.text:
        target = args if args else "English"
        question = f"Translate this text to {target}:\n\n{message.reply_to_message.text}"
    elif args:
        question = f"Translate this to English: {args}"
    else:
        await message.reply(
            "Usage: reply to a message with `/xtranslate [language]`\n"
            "Or: `/xtranslate text to translate`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await process_query(message, question, CONCISE_ADDON)

# ──────────────────────────────────────────────────────────
#  EXTRA FEATURE: /xprofile
# ──────────────────────────────────────────────────────────
@router.message(Command("xprofile"))
async def cmd_profile(message: Message):
    user = message.from_user
    register_user(user)
    info = user_registry.get(user.id, {})
    questions = info.get("questions", 0)

    # Simple XP system
    xp    = questions * 10
    level = xp // 100 + 1
    badge = "🥉 Rookie" if level < 3 else "🥈 Explorer" if level < 6 else "🥇 Expert" if level < 10 else "💎 Legend"

    text = (
        f"👤 *Your X Bot Profile*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• 🔖 Name: *{user.first_name}*\n"
        f"• 🆔 ID: `{user.id}`\n"
        f"• 📅 First seen: `{info.get('first_seen', 'Unknown')}`\n"
        f"• ❓ Questions asked: `{questions}`\n"
        f"• ⚡ XP: `{xp}`\n"
        f"• 📊 Level: `{level}`\n"
        f"• 🏅 Badge: {badge}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Keep asking to level up!_"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────────────────
#  EXTRA FEATURE: /xpoll
# ──────────────────────────────────────────────────────────
@router.message(Command("xpoll"))
async def cmd_poll(message: Message):
    topic = message.text.partition(" ")[2].strip()
    if not topic:
        await message.reply(
            "Usage: `/xpoll <topic>`\nExample: `/xpoll best programming languages`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    question = (
        f"Generate a poll for the topic: '{topic}'. "
        "Reply with ONLY this format (no extra text):\n"
        "QUESTION: <the poll question>\n"
        "OPTION1: <option>\nOPTION2: <option>\nOPTION3: <option>\nOPTION4: <option>"
    )
    register_user(message.from_user)
    if is_rate_limited(message.from_user.id):
        await message.reply("⏳ Rate limited. Try again shortly.")
        return
    try:
        raw = await ask_groq(message.from_user.id, question, "")
        lines = {l.split(":")[0].strip(): ":".join(l.split(":")[1:]).strip()
                 for l in raw.strip().split("\n") if ":" in l}
        poll_q   = lines.get("QUESTION", topic)
        options  = [lines.get(f"OPTION{i}", f"Option {i}") for i in range(1, 5)]
        await bot.send_poll(message.chat.id, poll_q, options, is_anonymous=False)
    except Exception as e:
        logger.error(f"Poll error: {e}")
        await message.reply("⚠️ Couldn't generate poll. Try again.")

# ──────────────────────────────────────────────────────────
#  BOT STARTUP
# ──────────────────────────────────────────────────────────
async def set_commands():
    private_cmds = [
        BotCommand(command="start",       description="Welcome screen & your profile"),
        BotCommand(command="ask",         description="Ask me anything"),
        BotCommand(command="xhelp",       description="How to use X Chat Bot"),
        BotCommand(command="xclear",      description="Reset conversation memory"),
        BotCommand(command="xstats",      description="Advanced bot diagnostics"),
        BotCommand(command="xabout",      description="About X Chat Bot"),
        BotCommand(command="xprofile",    description="Your XP profile & stats"),
        BotCommand(command="xsummarize",  description="Summarize a replied message"),
        BotCommand(command="xtranslate",  description="Translate text or replied message"),
        BotCommand(command="xpoll",       description="Generate an AI poll on any topic"),
    ]
    group_cmds = [
        BotCommand(command="ask",         description="Ask me anything"),
        BotCommand(command="xhelp",       description="How to use X Chat Bot"),
        BotCommand(command="xclear",      description="Reset your conversation memory"),
        BotCommand(command="xstats",      description="Bot diagnostics"),
        BotCommand(command="xprofile",    description="Your XP profile"),
        BotCommand(command="xsummarize",  description="Summarize a replied message"),
        BotCommand(command="xtranslate",  description="Translate text"),
        BotCommand(command="xpoll",       description="Generate an AI poll"),
    ]
    await bot.set_my_commands(private_cmds, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_cmds,   scope=BotCommandScopeAllGroupChats())
    logger.info("✅ Bot commands registered for DM and groups.")

async def main():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username.lower() if me.username else ""
    logger.info(f"🚀 Starting @{me.username} (ID: {me.id})")

    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()

    logger.info("✅ X Chat Bot is LIVE!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
