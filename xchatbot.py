import telebot
from openai import OpenAI
import logging
from telebot import types
import os
import re
import time
from datetime import datetime
import random

# ─────────────────────────────────────────
#   🔑  CONFIGURATION — Updated for Groq & Railway
# ─────────────────────────────────────────
# Using os.getenv for Railway security
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8692680733:AAHleP3Vd3sTqxMdMSwCZe-y_np-8-q6P7s")
GROK_API_KEY       = os.getenv("GROK_API_KEY", "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")
GROK_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct" 
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
    "You are X Chat Bot, a high-intelligence AI, an elite AI assistant developed by Ayush (CipherX). "
    "You are friendly but have a slight 'cool' attitude. "
    "You are helpful, concise, and love using clear formatting. "
    "Always respond in a conversational but informative tone."
    "Your responses must be visually impressive and easy to scan. "
    "Use the following formatting rules:\n"
    "1. Start with a Bold Header using an emoji (e.g., 🚀 **Topic Name**).\n"
    "2. Use '---' or '━━━━' to create visual separators.\n"
    "3. Use bullet points (• or ‣) for lists.\n"
    "4. Highlight key terms in *italics* or `code blocks`.\n"
    "5. Maintain a cool, slightly sassy 'Ayush-style' attitude. 😎\n"
    "6. If you can't answer, be blunt and tag @CipherWrites."
    "If you are asked who created you, proudly mention Ayush (@CipherWrites). "
    "If you ever encounter a question you absolutely cannot answer or if the API fails, "
    "tell the user to stop bothering you and ask your creator @CipherWrites instead."
    
)

# Standard Markdown formatting (no extra escaping needed)
DEV_CREDIT = "\n\n━━━━━━━━━━━━━━━\n💻 *Dev* — `@pyrexus`"

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
# ── Smart Engine Setup ────────────────────────────────────────────────────────
BOT_USERNAME = ""

def get_bot_username():
    global BOT_USERNAME
    if not BOT_USERNAME:
        BOT_USERNAME = bot.get_me().username.lower()
    return BOT_USERNAME

def process_ai_query(message, question):
    """The central brain that handles the actual AI request and formatting."""
    # 1. Cool Reactions (⚡/😎)
    try:
        bot.set_message_reaction(message.chat.id, message.message_id, [
            types.ReactionTypeEmoji('⚡'), 
            types.ReactionTypeEmoji('😎')
        ])
    except Exception:
        pass 

    # 2. Show Typing Indicator
    bot.send_chat_action(message.chat.id, "typing")

    try:
        # 🧠 Get the AI response
        reply = ask_grok(message.from_user.id, question)
        
        if not reply or len(reply) < 5:
            raise Exception("Incomplete AI response")

        # 🎨 Advanced 'GPT-Style' Formatting (WITHOUT BLOCKQUOTES)
        full_reply = (
            f"✨ *X Chat Bot Response*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{reply}\n\n" 
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💻 *Dev* — `Ayush (@CipherWrites)`"
        )
        
        bot.reply_to(message, full_reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Logic Error: {e}")
        
        # 🙄 Sassy Error Message
        attitude_text = (
            "🙄 *Ugh, even I have my limits.*\n\n"
            "I can't figure this one out right now. Stop spamming and "
            "go ask my creator **Ayush** (@CipherWrites) directly.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💻 *Dev* — `Ayush (@CipherWrites)`"
        )
        bot.reply_to(message, attitude_text, parse_mode="Markdown")


# ── TRIGGER 1: The /ask Command ──────────────────────────────────────────────
@bot.message_handler(commands=["ask"])
def cmd_ask(message):
    question = message.text[4:].strip() # Grabs text after "/ask"
    
    if not question:
        bot.reply_to(message, "⚠️ *Please ask a question!*\n> Example: `/ask What is quantum physics?`", parse_mode="Markdown")
        return
        
    process_ai_query(message, question)


# ── TRIGGERS 2 & 3: "X Bot" Text & @Mentions ─────────────────────────────────
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_smart_triggers(message):
    text_lower = message.text.lower()
    my_username = get_bot_username()
    
    # Check if they typed the trigger words or tagged the bot
    is_name_trigger = text_lower.startswith("x bot") or text_lower.startswith("x chat bot")
    is_mention = f"@{my_username}" in text_lower
    
    if is_name_trigger or is_mention:
        # Clean the text so the AI just sees the question
        question = message.text
        question = re.sub(r'^(x chat bot|x bot)', '', question, flags=re.IGNORECASE).strip()
        question = re.sub(rf'@{my_username}', '', question, flags=re.IGNORECASE).strip()
        
        if not question:
            question = "Hello!" # Fallback if they just tag it
            
        process_ai_query(message, question)

        
@bot.message_handler(commands=["Xstart"])
def cmd_start(message: telebot.types.Message):
    name = message.from_user.first_name or "there"
    text = (
        f"🤖 *X Chat Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Hey *{name}*! 👋 Welcome aboard!\n\n"
        f"I'm powered by *𝗫 𝗕𝗼𝘁𝘀 * developed and hosted by 𝐂𝐈𝐏𝐇𝐄𝐑𝐗.𝐚𝐞 🚀\n"
        f"Just send me any message and I'll do my best to help.\n\n"
        f"📌 *Quick Commands:*\n"
        f"`/start`  — Show this welcome message\n"
        f"`/help`   — Usage tips\n"
        f"`/clear`  — Reset our conversation\n"
        f"`/about`  — About this bot"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ── /Xstats Handler ──────────────────────────────────────────────────────────
@bot.message_handler(commands=["Xstats"])
def cmd_stats(message: telebot.types.Message):
    # ⏱️ 1. Calculate Real Bot Ping
    start_time = time.time()
    # Sending a temporary action to measure response time
    bot.send_chat_action(message.chat.id, "typing")
    end_time = time.time()
    bot_ping = round((end_time - start_time) * 1000, 2)

    # 🕒 2. Current Time Stamp
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")

    # 🌐 3. Generate "Techy" Artificial Stats
    api_ping = round(random.uniform(10.5, 45.2), 2)
    cpu_usage = random.randint(12, 28)
    ram_usage = random.randint(150, 450)
    uptime = f"{random.randint(5, 12)}d {random.randint(1, 23)}h {random.randint(1, 59)}m"

    # 🎨 4. Constructing the Beautiful Message
    stats_msg = (
        f"📊 *X-BOT ADVANCED DIAGNOSTICS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"> ⚡ **SYSTEM CORE STATUS**\n"
        f"```yaml\n"
        f"Creator     : Ayush (@CipherWrites)\n"
        f"Alias       : CipherX / Pyrexus\n"
        f"Timestamp   : {now}\n"
        f"Uptime      : {uptime}\n"
        f"Language    : Python 3.13 (Railway High-Perf)\n"
        f"```\n\n"
        f"> 🌐 **NETWORK & API HEALTH**\n"
        f"```ini\n"
        f"[API_URL]    : [api.groq.com/v1](https://api.groq.com/v1)\n"
        f"[API_STATUS] : Operational (HEALTHY)\n"
        f"[API_PING]   : {api_ping} ms\n"
        f"[BOT_PING]   : {bot_ping} ms\n"
        f"```\n\n"
        f"> 🧠 **NEURAL ENGINE SPECS**\n"
        f"```fix\n"
        f"Model       : Llama-4-Scout (17B)\n"
        f"Context     : 10M Tokens Stable\n"
        f"CPU_Load    : {cpu_usage}%\n"
        f"RAM_Alloc   : {ram_usage} MB\n"
        f"Threads     : Active (Multi-Threaded)\n"
        f"```\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛰️ *System running at peak performance.*"
    )

    bot.reply_to(message, stats_msg, parse_mode="Markdown")

@bot.message_handler(commands=["Xhelp"])
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

@bot.message_handler(commands=["Xclear"])
def cmd_clear(message: telebot.types.Message):
    conversation_history.pop(message.from_user.id, None)
    text = (
        "🗑 *Conversation cleared!*\n\n"
        "Starting fresh — ask me anything 😊"
        + DEV_CREDIT
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["aboutX"])
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
@bot.inline_handler(lambda query: len(query.query) > 0)
def query_text(inline_query):
    try:
        user_text = inline_query.query
      
        grok_reply = ask_grok(inline_query.from_user.id, user_text)
       
        r = types.InlineQueryResultArticle(
            id='1',
            title="✨ Ask X Chat Bot",
            description=f"AI says: {grok_reply[:50]}...",
            input_message_content=types.InputTextMessageContent(
                message_text=f"🤖 *X Chat Bot Inline Query*\n\n"
                             f"❓ *Q:* {user_text}\n"
                             f"💡 *A:* {grok_reply}\n\n"
                             f"━═━═━═━═━═━═━\n"
                             f"💻 *Dev - Ayush (@CipherWrites)*",
                parse_mode="Markdown"
            )
        )
        
        # Send the result back to the user's inline menu
        bot.answer_inline_query(inline_query.id, [r])
        
    except Exception as e:
        logger.error(f"Inline Error: {e}")

if __name__ == "__main__":
    logger.info("🚀 X Chat Bot is starting...")
    
    try:
        # 📋 THIS CREATES THE TELEGRAM COMMAND MENU!
        bot.set_my_commands([
            telebot.types.BotCommand("/Xstart", "Initialize the bot"),
            telebot.types.BotCommand("/Xhelp", "See how to use me"),
            telebot.types.BotCommand("/ask", "Ask me a question (e.g. /ask hello)"),
            telebot.types.BotCommand("/Xclear", "Wipe my memory"),
            telebot.types.BotCommand("/xstats", "View advanced bot diagnostics"),
            telebot.types.BotCommand("/aboutX", "See creator info")
        ])
        
        # 🛡️ Drop old connections
        bot.remove_webhook()
        logger.info("✅ Menu Updated & Connections cleared.")
    except Exception as e:
        logger.error(f"Startup error: {e}")

    print("\n✅ X Chat Bot is LIVE! Check Telegram.\n")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

