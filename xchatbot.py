import telebot
from openai import OpenAI
import logging
import os

# ─────────────────────────────────────────
#   🔑  CONFIGURATION — Updated for Groq & Railway
# ─────────────────────────────────────────
# Using os.getenv for Railway security
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8692680733:AAFXyLmRGdPVWV6M-yqJZpA8mnhkXDv90us")
GROK_API_KEY       = os.getenv("GROK_API_KEY", "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")
GROK_MODEL         = "llama-4-scout-17b-16e-instruct" 
# ─────────────────────────────────────────

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ── Bot & Groq client initialisation ──────────────────────────────────────────
# Changed default parse_mode to Markdown for better stability
bot    = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
client = OpenAI(
    api_key  = GROK_API_KEY,
    base_url = "https://api.groq.com/openai/v1",
)

conversation_history: dict[int, list[dict]] = {}

SYSTEM_PROMPT = (
    "You are X Chat Bot, a smart and friendly AI assistant. "
    "You are helpful, concise, and love using clear formatting. "
    "Always respond in a conversational but informative tone."
)

# Standard Markdown formatting (no extra escaping needed)
DEV_CREDIT = "\n\n━━━━━━━━━━━━━━━\n💻 *Dev* — `Pyrexus`"

MAX_HISTORY = 20

def ask_grok(user_id: int, user_message: str) -> str:
    history = conversation_history.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model    = GROK_MODEL,
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise

# ── Handlers ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    name = message.from_user.first_name or "there"
    text = (
        f"🤖 *X Chat Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Hey *{name}*! 👋 Welcome aboard!\n\n"
        f"I'm powered by *Llama 4 Scout* via Groq 🚀\n"
        f"Just send me any message and I'll do my best to help.\n\n"
        f"📌 *Quick Commands:*\n"
        f"`/start`  — Show this welcome message\n"
        f"`/help`   — Usage tips\n"
        f"`/clear`  — Reset our conversation\n"
        f"`/about`  — About this bot"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["help"])
def cmd_help(message: telebot.types.Message):
    text = (
        "💡 *How to use X Chat Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Simply *type your message* and I'll reply instantly.\n\n"
        "🗣 *Examples you can try:*\n"
        "> Explain quantum computing simply\n"
        "> Write a Python function to reverse a string\n\n"
        "🧠 I remember the *last 20 messages* in our chat.\n"
        "Use `/clear` to start a fresh conversation."
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["clear"])
def cmd_clear(message: telebot.types.Message):
    conversation_history.pop(message.from_user.id, None)
    text = (
        "🗑 *Conversation cleared!*\n\n"
        "Starting fresh — ask me anything 😊"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["about"])
def cmd_about(message: telebot.types.Message):
    text = (
        "🤖 *X Chat Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧠 *AI Engine* — Llama 4 Scout\n"
        f"📡 *Framework* — pyTelegramBotAPI\n"
        f"🐍 *Language* — Python\n"
        f"👨‍💻 *Developer* — `Pyrexus`"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text is not None)
def handle_message(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_text = message.text.strip()

    bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = ask_grok(user_id, user_text)
        # We wrap the reply in a quote for a clean look
        full_reply = f"> {reply}" + DEV_CREDIT
        bot.reply_to(message, full_reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")
        error_text = "⚠️ *Oops!* Something went wrong. Please try again." + DEV_CREDIT
        bot.reply_to(message, error_text, parse_mode="Markdown")

if __name__ == "__main__":
    logger.info("🚀 X Chat Bot is starting...")
    
    # 🛡️ ADD THIS LINE: It clears old connections and stops the 409 error
    bot.remove_webhook() 
    
    print("\n✅ X Chat Bot is LIVE! Check Telegram.\n")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
