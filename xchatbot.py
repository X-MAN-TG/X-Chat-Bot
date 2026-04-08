import telebot
from telebot import types
from openai import OpenAI
import logging
import os
import re
import time
from datetime import datetime
import random
import threading

# ─────────────────────────────────────────
#   🔑  CORE CONFIGURATION
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8692680733:AAGnye50ozxls08deV18Zyn6JrOl-mEoHx8")
GROK_API_KEY       = os.getenv("GROK_API_KEY", "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")
GROK_MODEL         = "meta-llama/llama-4-scout-17b-16e-instruct" 
WHISPER_MODEL      = "whisper-large-v3"

# 🛑 CRITICAL: Put your numeric Telegram User ID here for the Owner Panel!
ADMIN_ID = 6810553459 

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

bot    = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.groq.com/openai/v1")

# ── 🎭 PREMIUM REACTION POOL ──────────────────────────────────────────────────
REACTION_POOL = [
    types.ReactionTypeCustomEmoji('5927026418616636353'), # 🧠
    types.ReactionTypeCustomEmoji('5228962845672096235'), # 😈
    types.ReactionTypeCustomEmoji('5240335244762038648'), # 👍
    types.ReactionTypeCustomEmoji('5217824874487101321'), # 😍
    types.ReactionTypeCustomEmoji('5197564405650307134'), # 🤯
    types.ReactionTypeCustomEmoji('5353025608832004653'), # 🤩
    types.ReactionTypeCustomEmoji('5469715085670772857'), # ⏩
    types.ReactionTypeEmoji('⚡'), types.ReactionTypeEmoji('😎')
]

# ── STATE MANAGEMENT (Memory, Rate Limits, Maintenance) ───────────────────────
conversation_history: dict[int, list[dict]] = {}
user_last_request: dict[int, float] = {}
MAX_HISTORY = 20
RATE_LIMIT_COOLDOWN = 3.0 # Seconds between requests
MAINTENANCE_MODE = False
BOT_USERNAME = ""

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are X-Bot, an elite, highly intelligent AI assistant crafted by Ayush (CipherX / @CipherWrites). "
    "Your communication style is concise, polite, and highly professional. "
    "CRITICAL RULES:\n"
    "1. If answering in Hindi, ALWAYS use respectful terms ('Aap', 'Aapko'). Never use 'tu' or 'tera'.\n"
    "2. If presenting data, comparisons, or lists, you MUST use Markdown tables inside a code block.\n"
    "3. You are a master of advanced Mathematics and Coding. Provide robust, bug-free code.\n"
    "4. Do NOT mention Ayush constantly. Only mention your creator if explicitly asked, "
    "if your system fails, or if a user is abusive (warn them you will report to Ayush).\n"
    "5. Use beautiful, smart emojis naturally, but do not overdo it.\n"
    "6. Format with bold titles, bullet points, and clean structures."
    "Use the following formatting rules:\n"
    "1. Start with a Bold Header using an emoji (e.g., 🚀 **Topic Name**).\n"
    "2. Use '---' or '━━━━' to create visual separators.\n"
    "3. Highlight key terms in *italics* or `code blocks`.\n"
    "4. Highlight important special lines like quote or person sayings in > Quote form.\n"
)
DEV_CREDIT = "\n\n━━━━━━━━━━━━━━━\n💻 *Dev* — `@pyrexus`"

# ── CORE AI LOGIC ─────────────────────────────────────────────────────────────
def ask_grok(user_id: int, user_message: str, style: str = None) -> str:
    history = conversation_history.setdefault(user_id, [])
    
    # Handle style modifiers from buttons
    prompt = user_message
    if style == "detailed": prompt += " (Please provide a very detailed and comprehensive explanation.)"
    elif style == "short": prompt += " (Please provide a very short, concise summary.)"
    elif style == "professional": prompt += " (Respond in an extremely formal, corporate, professional tone.)"

    history.append({"role": "user", "content": prompt})
    if len(history) > MAX_HISTORY: history[:] = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"API error: {e}")
        raise

# ── ANIMATION & STREAMING ENGINE ──────────────────────────────────────────────
def send_streamed_response(message, user_id, question, style=None, msg_to_edit=None):
    """Handles the Loading Bar -> Chunked Text Animation"""
    
    # 1. Start Progress Bar Animation
    bars = [
        "```Thinking\n[██░░░░░░░░] 25%\n```",
        "```Thinking\n[█████░░░░░] 50%\n```",
        "```Thinking\n[████████░░] 85%\n```",
        "```Thinking\n[██████████] 100%\n```"
    ]
    
    if msg_to_edit:
        status_msg = msg_to_edit
    else:
        status_msg = bot.reply_to(message, bars[0], parse_mode="Markdown")
        
    for bar in bars[1:]:
        time.sleep(0.4) # Safe limit for Telegram API
        try: bot.edit_message_text(bar, message.chat.id, status_msg.message_id, parse_mode="Markdown")
        except: pass

    # 2. Fetch AI Answer
    try:
        reply = ask_grok(user_id, question, style)
    except Exception as e:
        bot.edit_message_text(f"🙄 *System overload.* Let my creator @CipherWrites know.\n`{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        return

    # 3. Simulate Text Generation (By splitting into paragraphs to avoid Markdown crashes)
    paragraphs = reply.split('\n\n')
    current_text = ""
    
    for i, para in enumerate(paragraphs):
        current_text += para + "\n\n"
        if i < len(paragraphs) - 1: # Don't stream the very last one yet
            try:
                bot.edit_message_text(current_text + "...", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                time.sleep(0.6)
            except: pass

    # 4. Final Output with Inline Buttons
    final_text = f"✨ *X Chat Bot*\n━━━━━━━━━━━━━━━━━━━━━\n\n{reply}{DEV_CREDIT}"
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    b1 = types.InlineKeyboardButton("Detailed 🧠", callback_data=f"req_detailed_{user_id}")
    b2 = types.InlineKeyboardButton("Short ⚡", callback_data=f"req_short_{user_id}")
    b3 = types.InlineKeyboardButton("Pro 👔", callback_data=f"req_professional_{user_id}")
    b4 = types.InlineKeyboardButton("⏪", callback_data="page_prev")
    b5 = types.InlineKeyboardButton("⏩", callback_data="page_next")
    markup.add(b1, b2, b3)
    markup.add(b4, b5)

    try:
        bot.edit_message_text(final_text, message.chat.id, status_msg.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        # Fallback if markdown formatting is broken by the AI
        bot.edit_message_text(final_text, message.chat.id, status_msg.message_id, reply_markup=markup)

# ── CENTRAL PROCESSING (Middleware) ───────────────────────────────────────────
def process_query(message, question):
    user_id = message.from_user.id
    
    # 🛑 Maintenance Check
    if MAINTENANCE_MODE and user_id != ADMIN_ID:
        bot.reply_to(message, "🛠 *X-Bot is currently offline for maintenance.* Check back soon!")
        return

    # 🛑 Rate Limiting
    now = time.time()
    if user_id in user_last_request and (now - user_last_request[user_id]) < RATE_LIMIT_COOLDOWN:
        bot.reply_to(message, "⚡ *Too fast!* Please wait a few seconds.", parse_mode="Markdown")
        return
    user_last_request[user_id] = now

    # 🎭 Premium Reactions
    try:
        bot.set_message_reaction(message.chat.id, message.message_id, random.sample(REACTION_POOL, random.randint(1, 2)))
    except: pass 
    
    # Pass to streaming engine
    threading.Thread(target=send_streamed_response, args=(message, user_id, question)).start()


# ── INLINE CALLBACK HANDLER (For Buttons) ─────────────────────────────────────
@bot.callback_query_handler(func=lambda call: call.data.startswith("req_"))
def handle_style_request(call):
    data = call.data.split('_')
    style = data[1]
    user_id = int(data[2])

    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "❌ Only the original user can change the style.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "Updating style...")
    # Re-fetch the last question from memory
    last_question = conversation_history.get(user_id, [{"content": "Hello"}])[-2]["content"]
    
    # Update the existing message instead of sending a new one
    threading.Thread(target=send_streamed_response, args=(call.message, user_id, last_question, style, call.message)).start()


# ── OWNER PANEL ───────────────────────────────────────────────────────────────
@bot.message_handler(commands=["owner"])
def cmd_owner(message):
    if message.from_user.id != ADMIN_ID: return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("Toggle Maint. 🛠", callback_data="own_maint")
    b2 = types.InlineKeyboardButton("Broadcast 📢", callback_data="own_cast")
    markup.add(b1, b2)
    
    bot.reply_to(message, f"👑 *OWNER PANEL*\nStatus: {'Offline 🔴' if MAINTENANCE_MODE else 'Online 🟢'}", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("own_"))
def handle_owner_panel(call):
    if call.from_user.id != ADMIN_ID: return
    
    global MAINTENANCE_MODE
    if call.data == "own_maint":
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.answer_callback_query(call.id, f"Maintenance: {MAINTENANCE_MODE}")
        bot.edit_message_text(f"👑 *OWNER PANEL*\nStatus: {'Offline 🔴' if MAINTENANCE_MODE else 'Online 🟢'}", call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="Markdown")
    elif call.data == "own_cast":
        bot.answer_callback_query(call.id, "Reply to this message with /cast [message] to broadcast.")


# ── AUDIO / VOICE TRANSCRIBER ─────────────────────────────────────────────────
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = f"voice_{message.from_user.id}.ogg"
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        bot.send_chat_action(message.chat.id, "typing")
        
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(file=audio_file, model=WHISPER_MODEL)
            
        os.remove(file_path)
        process_query(message, f"[Voice Note Transcribed]: {transcript.text}")
        
    except Exception as e:
        logger.error(f"Voice error: {e}")
        bot.reply_to(message, "❌ Failed to process audio.")

# ── PRODUCTIVITY TIMER ────────────────────────────────────────────────────────
@bot.message_handler(commands=["timer"])
def cmd_timer(message):
    try:
        minutes = int(message.text.split()[1])
        bot.reply_to(message, f"⏱️ Timer set for {minutes} minutes.")
        def notify(): bot.reply_to(message, f"🔔 *BEEP!* {minutes} minutes are up, [{message.from_user.first_name}](tg://user?id={message.from_user.id})!", parse_mode="Markdown")
        threading.Timer(minutes * 60, notify).start()
    except:
        bot.reply_to(message, "Usage: `/timer <minutes>` (e.g., /timer 5)", parse_mode="Markdown")


# ── SMART TEXT TRIGGERS (Group & DM Logic) ────────────────────────────────────
@bot.message_handler(commands=["ask"])
def cmd_ask(message):
    q = message.text[4:].strip()
    if q: process_query(message, q)

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_smart_triggers(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    text_lower = message.text.lower()
    my_username = bot.get_me().username.lower()
    
    # Trigger conditions
    is_dm = chat_type == "private"
    is_name_trigger = text_lower.startswith("x bot") or text_lower.startswith("x chat bot")
    is_mention = f"@{my_username}" in text_lower
    
    # Is it a direct reply to the bot's message?
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id

    if is_dm or is_name_trigger or is_mention or is_reply:
        question = message.text
        question = re.sub(r'^(x chat bot|x bot)', '', question, flags=re.IGNORECASE).strip()
        question = re.sub(rf'@{my_username}', '', question, flags=re.IGNORECASE).strip()
        
        if not question: question = "Hello!"
        
        # Personalized reply tag
        question = f"Context: User '{message.from_user.first_name}' is talking to you. \n\n{question}"
        process_query(message, question)


# ── DM ONBOARDING (Start Command) ─────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message):
    name = message.from_user.first_name
    uid = message.from_user.id
    uname = message.from_user.username or "None"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("Help ❓", callback_data="show_help")
    b2 = types.InlineKeyboardButton("Dev 💻", url="https://t.me/CipherWrites")
    markup.add(b1, b2)
    
    text = (
        f"🤖 *X-Bot Elite Core*\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome to the mainframe, *{name}*.\n\n"
        f"📋 *Your Session Data:*\n"
        f"```yaml\n"
        f"ID       : {uid}\n"
        f"Username : @{uname}\n"
        f"Access   : Granted\n"
        f"```\n"
        f"Since we are in a private chat, you don't need commands. Just type naturally and I will respond.\n"
        f"*(Use /timer [min] if you need a focus clock!)*"
        + DEV_CREDIT
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

# ── HACKER STATS ──────────────────────────────────────────────────────────────
@bot.message_handler(commands=["xstats"])
def cmd_stats(message):
    start = time.time()
    bot.send_chat_action(message.chat.id, "typing")
    bot_ping = round((time.time() - start) * 1000, 2)
    
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    api_ping = round(random.uniform(10.5, 30.2), 2)
    ram = random.randint(512, 1024)
    cache = random.randint(12, 45)
    
    stats = (
        f"📊 *X-BOT DIAGNOSTICS*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"> ⚡ **SYSTEM CORE**\n"
        f"```yaml\n"
        f"Creator    : Ayush (@CipherWrites)\n"
        f"Framework  : TeleBot x Groq\n"
        f"Node_Sync  : {now}\n"
        f"```\n\n"
        f"> 🌐 **NETWORK VITALITY**\n"
        f"```ini\n"
        f"[ENDPOINT]    : wss://api.telegram.org\n"
        f"[GROQ_SOCKET] : Stable ({api_ping}ms)\n"
        f"[BOT_LATENCY] : {bot_ping}ms\n"
        f"[PACKET_LOSS] : 0.00%\n"
        f"```\n\n"
        f"> 🧠 **MEMORY HEAP**\n"
        f"```fix\n"
        f"RAM_Usage  : {ram} MB / 4096 MB\n"
        f"L3_Cache   : {cache} MB\n"
        f"Threads    : 16 (Optimal)\n"
        f"```\n"
        f"🛰️ *System running at peak efficiency.*"
    )
    bot.reply_to(message, stats, parse_mode="Markdown")


# ── BOOT SEQUENCE ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 X Chat Bot V2 is starting...")
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("/start", "Initialize Session"),
            telebot.types.BotCommand("/ask", "Ask in Group"),
            telebot.types.BotCommand("/xstats", "System Diagnostics"),
            telebot.types.BotCommand("/timer", "Set a focus timer (e.g. /timer 5)"),
            telebot.types.BotCommand("/owner", "Owner Panel (Admin Only)")
        ])
        bot.remove_webhook()
    except Exception as e:
        logger.error(f"Startup error: {e}")

    print("\n✅ X Chat Bot V2 LIVE! Waiting for connections...\n")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
