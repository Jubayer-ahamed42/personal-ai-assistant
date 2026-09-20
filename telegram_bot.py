import os
import io
import time
import asyncio
import logging
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import get_active_model
from database.memory import MemoryManager
from agents.orchestrator import MasterOrchestrator
from tools.audio_tools import transcribe_audio_to_text

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User active modes dictionary (default is "chat" for snappy response)
USER_MODES: Dict[int, str] = {}

def get_session_id(user_id: int) -> str:
    """Returns a unique, persistent SQLite session ID for the Telegram user."""
    return f"telegram_{user_id}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command with greeting and mode picker."""
    user = update.effective_user
    user_id = user.id
    USER_MODES[user_id] = "chat"

    # Ensure session in SQLite
    mem = MemoryManager()
    mem.ensure_session(get_session_id(user_id), f"Telegram: {user.first_name}")

    keyboard = [
        [
            InlineKeyboardButton("💬 Chat মোড (দ্রুত উত্তর)", callback_data="set_mode_chat"),
            InlineKeyboardButton("✦ Work মোড (এজেন্ট স্কোয়াড)", callback_data="set_mode_work"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 হ্যালো {user.first_name}!\n\n"
        "আমি আপনার **SMART AI ASSISTANT**। গুগল ২০২৬ আর্কিটেকচারে তৈরি একটি পূর্ণাঙ্গ স্বায়ত্তশাসিত এজেন্ট।\n\n"

        "✨ **আমি কী করতে পারি?**\n"
        "• 🎙️ **ভয়েস নোট:** আমাকে সরাসরি বাংলায় ভয়েস মেসেজ পাঠান, আমি শুনে বাংলায় ভয়েসে উত্তর দেব!\n"
        "• 💬 **চ্যাট:** যেকোনো প্রশ্ন বা আলোচনার ১-২ সেকেন্ডে দ্রুত উত্তর।\n"
        "• 💻 **কোডিং ও রিসার্চ:** পাইথন কোড লেখা, স্যান্ডবক্স টেস্ট ও গভীর ডাটা অনুসন্ধান।\n\n"
        "👉 বর্তমান মোড: **💬 Chat (দ্রুততম উত্তর)**\n"
        "মোড পরিবর্তন করতে নিচের বাটনে চাপ দিন অথবা `/work` / `/chat` কমান্ড ব্যবহার করুন।"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /mode command."""
    user_id = update.effective_user.id
    current = USER_MODES.get(user_id, "chat")

    keyboard = [
        [
            InlineKeyboardButton("💬 Chat মোড", callback_data="set_mode_chat"),
            InlineKeyboardButton("✦ Work মোড", callback_data="set_mode_work"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"বর্তমান মোড: **{current.upper()}**\n\nকোন মোডটি ব্যবহার করতে চান?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def set_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick switch to Chat mode."""
    user_id = update.effective_user.id
    USER_MODES[user_id] = "chat"
    await update.message.reply_text("✅ **Chat মোড সক্রিয়!**\nএখন সাধারণ প্রশ্ন ও কথপোকথনের ১-২ সেকেন্ডে দ্রুততম উত্তর ও ভয়েস রিপ্লাই দেওয়া হবে।", parse_mode=ParseMode.MARKDOWN)

async def set_work_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick switch to Work mode."""
    user_id = update.effective_user.id
    USER_MODES[user_id] = "work"
    await update.message.reply_text("✅ **Work মোড সক্রিয়!**\nএখন কোডিং, স্যান্ডবক্স টেস্ট, ডাটা ও রিসার্চের জন্য স্পেশালিস্ট সাব-এজেন্ট স্কোয়াড কাজ করবে।", parse_mode=ParseMode.MARKDOWN)

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks for mode selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if query.data == "set_mode_chat":
        USER_MODES[user_id] = "chat"
        await query.edit_message_text("✅ **Chat মোড নির্বাচিত হয়েছে!**\nযেকোনো প্রশ্ন লিখে বা মুখে কথা বলে পাঠান।", parse_mode=ParseMode.MARKDOWN)
    elif query.data == "set_mode_work":
        USER_MODES[user_id] = "work"
        await query.edit_message_text("✅ **Work মোড নির্বাচিত হয়েছে!**\nস্পেশালিস্ট সাব-এজেন্ট স্কোয়াড এখন প্রস্তুত।", parse_mode=ParseMode.MARKDOWN)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user session history."""
    user_id = update.effective_user.id
    mem = MemoryManager()
    new_sess = mem.create_session(f"Telegram: {update.effective_user.first_name}")
    await update.message.reply_text("🧹 নতুন ফ্রেশ সেশন শুরু করা হয়েছে!", parse_mode=ParseMode.MARKDOWN)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming Telegram voice notes and audio clips."""
    message = update.message
    user_id = update.effective_user.id
    session_id = get_session_id(user_id)
    mode = USER_MODES.get(user_id, "chat")

    await message.chat.send_chat_action(ChatAction.RECORD_VOICE)
    status_msg = await message.reply_text("🎧 আপনার ভয়েস মেসেজ শুনছি ও বিশ্লেষণ করছি...", parse_mode=ParseMode.MARKDOWN)

    try:
        # Download voice file
        voice = message.voice or message.audio
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()

        # Transcribe native audio
        transcribed_text = transcribe_audio_to_text(bytes(voice_bytes), mime_type="audio/ogg")
        if not transcribed_text or not transcribed_text.strip():
            await status_msg.edit_text("⚠️ কণ্ঠস্বর পরিষ্কার বোঝা যায়নি। দয়া করে আবার স্পষ্ট করে বলুন।")
            return

        await status_msg.edit_text(f"🗣️ **শনাক্তকৃত কথা:** \"_{transcribed_text}_\"\n\n🧠 উত্তর তৈরি হচ্ছে...", parse_mode=ParseMode.MARKDOWN)
        await message.chat.send_chat_action(ChatAction.TYPING)

        # Run multi-agent orchestrator in thread pool to avoid blocking asyncio event loop
        mem = MemoryManager()
        orch = MasterOrchestrator(memory_manager=mem, model=get_active_model())

        result = await asyncio.to_thread(
            orch.process_command,
            session_id=session_id,
            user_command=transcribed_text,
            mode=mode
        )

        final_text = result.get("final_report", "")
        audio_bytes = result.get("audio_bytes")

        # Delete waiting status
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send text response (split if exceeds Telegram 4096 char limit)
        for chunk in [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]:
            await message.reply_text(chunk)

        # Send spoken Bengali voice reply
        if audio_bytes:
            await message.chat.send_chat_action(ChatAction.RECORD_VOICE)
            voice_stream = io.BytesIO(audio_bytes)
            voice_stream.name = "response_voice.mp3"
            await message.reply_voice(voice=voice_stream, caption="🔊 বাংলা ভয়েস উত্তর")

    except Exception as e:
        logger.error(f"Telegram voice handling error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ একটি ত্রুটি ঘটেছে: {str(e)}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming Telegram text messages."""
    message = update.message
    user_id = update.effective_user.id
    session_id = get_session_id(user_id)
    mode = USER_MODES.get(user_id, "chat")
    user_text = message.text.strip()

    if not user_text:
        return

    await message.chat.send_chat_action(ChatAction.TYPING)

    # Indicate status for long-running Work tasks
    status_msg = None
    if mode == "work":
        status_msg = await message.reply_text("🧠 ওয়ার্ক মোড: স্পেশালিস্ট এজেন্ট স্কোয়াড কাজ করছে...", parse_mode=ParseMode.MARKDOWN)

    try:
        mem = MemoryManager()
        orch = MasterOrchestrator(memory_manager=mem, model=get_active_model())

        result = await asyncio.to_thread(
            orch.process_command,
            session_id=session_id,
            user_command=user_text,
            mode=mode
        )

        final_text = result.get("final_report", "")
        audio_bytes = result.get("audio_bytes")

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        # Send text response
        for chunk in [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]:
            await message.reply_text(chunk)

        # Send spoken voice note
        if audio_bytes:
            await message.chat.send_chat_action(ChatAction.RECORD_VOICE)
            voice_stream = io.BytesIO(audio_bytes)
            voice_stream.name = "response_voice.mp3"
            await message.reply_voice(voice=voice_stream, caption="🔊 বাংলা ভয়েস উত্তর")

    except Exception as e:
        logger.error(f"Telegram text handling error: {e}", exc_info=True)
        await message.reply_text(f"⚠️ একটি ত্রুটি ঘটেছে: {str(e)}")

def build_telegram_app(token: str) -> Application:
    """Builds and configures the Telegram Application."""
    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("chat", set_chat_mode))
    app.add_handler(CommandHandler("work", set_work_mode))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(mode_callback))

    # Voice & Audio
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))

    # General Text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app

def run_telegram_bot():
    """Starts the bot via long-polling with resilient auto-reconnect."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        logger.warning("TELEGRAM_BOT_TOKEN is not configured in .env. Bot worker will stay idle.")
        return

    logger.info("Starting Telegram Bot long-polling worker...")
    while True:
        try:
            app = build_telegram_app(token)
            app.run_polling(drop_pending_updates=False)
            break
        except Exception as e:
            logger.warning(f"Telegram polling transient error: {e}. Reconnecting in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    run_telegram_bot()

