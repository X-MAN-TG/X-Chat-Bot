"""
╔══════════════════════════════════════╗
║         X Chat Bot - Telegram        ║
║         Powered by Grok AI (xAI)     ║
║         Dev - Pyrexus                ║
╚══════════════════════════════════════╝

Requirements:
    pip install pyTelegramBotAPI openai

Setup:
    1. Get your Telegram Bot Token from @BotFather
    2. Get your Grok API Key from https://console.x.ai/
    3. Replace the placeholder values below with your actual keys
"""

import telebot
from openai import OpenAI
import logging


# ─────────────────────────────────────────
#   🔑  CONFIGURATION — Updated for Groq
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8692680733:AAFXyLmRGdPVWV6M-yqJZpA8mnhkXDv90us"   # Keep your same token from @BotFather
GROK_API_KEY       = "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"    # 👈 Paste your Groq key (starts with gsk_)
GROK_MODEL         = "llama-4-scout-17b-16e-instruct" # 👈 Use the fast Scout model
# ─────────────────────────────────────────

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ── Bot & Groq client initialisation ──────────────────────────────────────────
bot    = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
client = OpenAI(
    api_key  = GROK_API_KEY,
    base_url = "https://api.groq.com/openai/v1",   # 👈 Change this to the Groq endpoint
)


# Per-user conversation history  {user_id: [{"role": ..., "content": ...}, ...]}
conversation_history: dict[int, list[dict]] = {}

SYSTEM_PROMPT = (
    "You are X Chat Bot, a smart and friendly AI assistant powered by Grok (xAI). "
    "You are helpful, concise, and love using clear formatting. "
    "Always respond in a conversational but informative tone."
)

DEV_CREDIT = "\n\n✦ *Dev* — `Pyrexus`"

MAX_HISTORY = 20   # Keep last N messages per user to stay within context limits


# ── Helper: call Grok ──────────────────────────────────────────────────────────
def ask_grok(user_id: int, user_message: str) -> str:
    """Send a message to Grok and return its reply."""
    history = conversation_history.setdefault(user_id, [])

    # Append the new user message
    history.append({"role": "user", "content": user_message})

    # Trim history to keep memory manageable
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model    = GROK_MODEL,
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        reply = response.choices[0].message.content.strip()

        # Save assistant reply to history
        history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        logger.error(f"Grok API error: {e}")
        raise


# ── /start ─────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    name = message.from_user.first_name or "there"
    text = (
        f"🤖 *X Chat Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Hey *{name}*\\! 👋 Welcome aboard\\!\n\n"
        f"I'm powered by *Grok AI* from xAI 🚀\n"
        f"Just send me any message and I'll do my best to help\\.\n\n"
        f"📌 *Quick Commands:*\n"
        f"`/start`  — Show this welcome message\n"
        f"`/help`   — Usage tips\n"
        f"`/clear`  — Reset our conversation\n"
        f"`/about`  — About this bot"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")


# ── /help ──────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
def cmd_help(message: telebot.types.Message):
    text = (
        "💡 *How to use X Chat Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Simply *type your message* and I'll reply using Grok AI\\.\n\n"
        "🗣 *Examples you can try:*\n"
        "> Explain quantum computing simply\n"
        "> Write a Python function to reverse a string\n"
        "> What's the latest in AI research?\n\n"
        "🧠 I remember the *last 20 messages* in our chat\\.\n"
        "Use `/clear` to start a fresh conversation\\."
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")


# ── /clear ─────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["clear"])
def cmd_clear(message: telebot.types.Message):
    conversation_history.pop(message.from_user.id, None)
    text = (
        "🗑 *Conversation cleared\\!*\n\n"
        "Starting fresh — ask me anything 😊"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")


# ── /about ─────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["about"])
def cmd_about(message: telebot.types.Message):
    text = (
        "🤖 *X Chat Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧠 *AI Engine* — Grok by xAI\n"
        "📡 *Framework* — pyTelegramBotAPI\n"
        "🐍 *Language* — Python\n"
        "👨‍💻 *Developer* — `Pyrexus`\n\n"
        "Built with ❤️ using the Grok free\\-tier API\\."
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")


# ── Main message handler ───────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text is not None)
def handle_message(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_text = message.text.strip()

    if not user_text:
        return

    # Show "typing…" indicator while waiting for Grok
    bot.send_chat_action(message.chat.id, "typing")

    try:
        grok_reply = ask_grok(user_id, user_text)

        # Append dev credit and send
        full_reply = grok_reply + DEV_CREDIT
        bot.reply_to(message, full_reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling message from {user_id}: {e}")
        error_text = (
            "⚠️ *Oops\\!* Something went wrong while contacting Grok\\.\n\n"
            "> Please try again in a moment\\."
            + DEV_CREDIT
        )
        bot.reply_to(message, error_text, parse_mode="MarkdownV2")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 X Chat Bot is starting...")
    logger.info(f"   Model  : {GROK_MODEL}")
    logger.info("   Status : Polling for messages...")
    print("\n✅  X Chat Bot is LIVE! Press Ctrl+C to stop.\n")

    bot.infinity_polling(timeout=60, long_polling_timeout=30)
