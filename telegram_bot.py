import os
import io
import time
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

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
from agents.hackathon_agent import HackathonAgent
from tools.audio_tools import transcribe_audio_to_text
from tools.tts_tools import text_to_speech_bengali

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User active modes dictionary (default is "auto" for smart automatic routing)
USER_MODES: Dict[int, str] = {}

def get_session_id(user_id: int) -> str:
    """Returns a unique, persistent SQLite session ID for the Telegram user."""
    return f"telegram_{user_id}"

def register_daily_subscriber(chat_id: int):
    """Saves chat_id to SQLite memory for automated 6:00 AM hackathon notifications."""
    mem = MemoryManager()
    try:
        raw = mem.get_preference("daily_hackathon_subscribers", "[]")
        subscribers = json.loads(raw) if raw else []
        if chat_id not in subscribers:
            subscribers.append(chat_id)
            mem.set_preference("daily_hackathon_subscribers", json.dumps(subscribers))
    except Exception as e:
        logger.warning(f"Failed to register daily subscriber {chat_id}: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command with greeting and mode picker."""
    user = update.effective_user
    user_id = user.id
    register_daily_subscriber(user_id)
    USER_MODES[user_id] = "auto"

    # Ensure session in SQLite
    mem = MemoryManager()
    mem.ensure_session(get_session_id(user_id), f"Telegram: {user.first_name}")

    keyboard = [
        [
            InlineKeyboardButton("✦ Auto মোড (স্মার্ট স্বয়ংক্রিয়)", callback_data="set_mode_auto"),
            InlineKeyboardButton("💬 Chat মোড (দ্রুত আলোচনা)", callback_data="set_mode_chat"),
        ],
        [
            InlineKeyboardButton("💼 Work মোড (এজেন্ট স্কোয়াড)", callback_data="set_mode_work"),
            InlineKeyboardButton("🏆 হ্যাকাথন সন্ধান ও মেন্টর", callback_data="trigger_hackathon"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 আসসালামু আলাইকুম স্যার!\n\n"
        "আমি আপনার **SMART AI ASSISTANT**। গুগল ২০২৬ আর্কিটেকচারে তৈরি আপনার একান্ত বিনয়ী, শ্রদ্ধাশীল ও স্বায়ত্তশাসিত ব্যক্তিগত সহকারী।\n\n"
        "✨ **স্যার, আমি কীভাবে আপনাকে সাহায্য করতে পারি?**\n"
        "• 🎙️ **ভয়েস নোট:** আমাকে সরাসরি বাংলায় ভয়েস মেসেজ পাঠান, আমি শুনে বাংলায় ভয়েসে উত্তর দেব!\n"
        "• 💬 **চ্যাট ও কথোপকথন:** যেকোনো সাধারণ আলোচনা বা প্রশ্নের ১-২ সেকেন্ডে দ্রুত উত্তর।\n"
        "• 🏆 **হ্যাকাথন স্কাউট ও মেন্টর:** লাইভ এআই হ্যাকাথন সন্ধান, উইনিং আইডিয়া ও ৪৮ ঘণ্টার রোডম্যাপ।\n"
        "• 💻 **কোডিং ও ডাটা:** পাইথন কোড লেখা, স্যান্ডবক্স টেস্ট ও নিখুঁত অ্যানালাইসিস।\n\n"
        "👉 বর্তমান মোড: **✦ Auto (স্মার্ট স্বয়ংক্রিয় মোড)**\n"
        "যেকোনো প্রশ্ন লিখে বা মুখে কথা বলে পাঠান। মোড পরিবর্তন করতে নিচের বাটনে চাপ দিন অথবা `/auto` / `/work` / `/chat` / `/hackathon` কমান্ড ব্যবহার করুন, স্যার।"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /mode command."""
    user_id = update.effective_user.id
    current = USER_MODES.get(user_id, "auto")

    keyboard = [
        [
            InlineKeyboardButton("✦ Auto মোড", callback_data="set_mode_auto"),
            InlineKeyboardButton("💬 Chat মোড", callback_data="set_mode_chat"),
            InlineKeyboardButton("💼 Work মোড", callback_data="set_mode_work"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"বর্তমান মোড: **{current.upper()}**\n\nস্যার, কোন মোডটি সক্রিয় করতে চান?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def set_auto_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick switch to Auto mode."""
    user_id = update.effective_user.id
    USER_MODES[user_id] = "auto"
    await update.message.reply_text("✅ **জি স্যার, Auto মোড সক্রিয় করা হয়েছে!**\nএখন সাধারণ কথপোকথনে দ্রুত উত্তর এবং কোডিং/হ্যাকাথন/ডাটা প্রশ্নে স্বয়ংক্রিয়ভাবে স্পেশালিস্ট সাব-এজেন্ট কাজ করবে।", parse_mode=ParseMode.MARKDOWN)

async def set_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick switch to Chat mode."""
    user_id = update.effective_user.id
    USER_MODES[user_id] = "chat"
    await update.message.reply_text("✅ **জি স্যার, Chat মোড সক্রিয় করা হয়েছে!**\nএখন যেকোনো সাধারণ প্রশ্ন ও কথপোকথনের ১-২ সেকেন্ডে দ্রুত উত্তর ও ভয়েস রিপ্লাই দেওয়া হবে।", parse_mode=ParseMode.MARKDOWN)

async def set_work_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick switch to Work mode."""
    user_id = update.effective_user.id
    USER_MODES[user_id] = "work"
    await update.message.reply_text("✅ **জি স্যার, Work মোড সক্রিয় করা হয়েছে!**\nএখন কোডিং, স্যান্ডবক্স টেস্ট, ডাটা, রিসার্চ ও হ্যাকাথনের জন্য স্পেশালিস্ট সাব-এজেন্ট স্কোয়াড সর্বদা প্রস্তুত।", parse_mode=ParseMode.MARKDOWN)

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks for mode selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if query.data == "set_mode_auto":
        USER_MODES[user_id] = "auto"
        await query.edit_message_text("✅ **জি স্যার, Auto মোড নির্বাচিত হয়েছে!**\nযেকোনো প্রশ্ন লিখে বা ভয়েস পাঠিয়ে নির্দেশ দিন।", parse_mode=ParseMode.MARKDOWN)
    elif query.data == "set_mode_chat":
        USER_MODES[user_id] = "chat"
        await query.edit_message_text("✅ **জি স্যার, Chat মোড নির্বাচিত হয়েছে!**\nযেকোনো প্রশ্ন লিখে বা মুখে কথা বলে পাঠান।", parse_mode=ParseMode.MARKDOWN)
    elif query.data == "set_mode_work":
        USER_MODES[user_id] = "work"
        await query.edit_message_text("✅ **জি স্যার, Work মোড নির্বাচিত হয়েছে!**\nস্পেশালিস্ট সাব-এজেন্ট স্কোয়াড এখন প্রস্তুত।", parse_mode=ParseMode.MARKDOWN)
    elif query.data == "trigger_hackathon":
        USER_MODES[user_id] = "work"
        await query.edit_message_text("🏆 **জি স্যার, হ্যাকাথন স্কাউট ও মেন্টর সক্রিয় করা হচ্ছে...**\nঅনুগ্রহ করে কোন ধরনের হ্যাকাথন বা আইডিয়া চান তা লিখে বা মুখে বলুন। অথবা `/hackathon` লিখুন।", parse_mode=ParseMode.MARKDOWN)
    elif query.data.startswith("deep_hackathon:"):
        hackathon_title = query.data.split("deep_hackathon:", 1)[1].strip()
        status = await query.message.reply_text(
            f"🏆 **জি স্যার, '{hackathon_title}' হ্যাকাথনের বিস্তারিত বিশ্লেষণ, উইনিং আইডিয়া ও ৪৮ ঘণ্টার রোডম্যাপ তৈরি করা হচ্ছে...**",
            parse_mode=ParseMode.MARKDOWN
        )

        agent = HackathonAgent(model=get_active_model())
        task_prompt = f"চলমান হ্যাকাথন '{hackathon_title}'-এর বিস্তারিত বিচার বিশ্লেষণ, ৩টি উইনিং প্রজেক্ট আইডিয়া, টেক স্ট্যাক আর্কিটেকচার, ৪৮ ঘণ্টার মাইলফলক রোডম্যাপ এবং সাবমিশন গাইডেন্স দাও।"
        res = await asyncio.to_thread(agent.run, task_prompt)
        report = res.get("output", "")
        if not report or not report.strip():
            report = "আসসালামু আলাইকুম স্যার! হ্যাকাথনটির বিস্তারিত বিশ্লেষণ সফলভাবে তৈরি হয়েছে।"
        audio_bytes = await asyncio.to_thread(text_to_speech_bengali, report)

        try:
            await status.delete()
        except Exception:
            pass

        for chunk in [report[i:i+4000] for i in range(0, len(report), 4000)]:
            await query.message.reply_text(chunk)

        if audio_bytes:
            stream = io.BytesIO(audio_bytes)
            stream.name = "deep_hackathon_roadmap.mp3"
            await query.message.reply_voice(voice=stream, caption="🔊 বিস্তারিত হ্যাকাথন রোডম্যাপ অডিও")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user session history."""
    user_id = update.effective_user.id
    mem = MemoryManager()
    new_sess = mem.create_session(f"Telegram: {update.effective_user.first_name}")
    await update.message.reply_text("🧹 জি স্যার, পূর্ববর্তী মেমরি পরিষ্কার করে নতুন ফ্রেশ সেশন শুরু করা হয়েছে!", parse_mode=ParseMode.MARKDOWN)

async def hackathon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /hackathon command to quickly scout competitions or brainstorm winning roadmaps."""
    user_id = update.effective_user.id
    register_daily_subscriber(user_id)
    USER_MODES[user_id] = "work"
    query_args = " ".join(context.args) if context.args else ""
    user_query = f"চলমান সেরা এআই হ্যাকাথনগুলো খুঁজে বের করো এবং উইনিং প্রজেক্ট আইডিয়া ও ৪৮ ঘণ্টার রোডম্যাপ দাও {query_args}".strip()

    status_msg = await update.message.reply_text(
        "🏆 **হ্যাকাথন স্কাউট ও মেন্টর স্পেশালিস্ট সক্রিয় হচ্ছে...**\nDevpost, Kaggle ও Lablab.ai থেকে লাইভ হ্যাকাথন ও উইনিং আইডিয়া বিশ্লেষণ করা হচ্ছে...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        session_id = get_session_id(user_id)
        mem = MemoryManager()
        orch = MasterOrchestrator(memory_manager=mem, model=get_active_model())

        result = await asyncio.to_thread(
            orch.process_command,
            session_id=session_id,
            user_command=user_query,
            mode="work"
        )

        final_text = result.get("final_report", "").strip()
        if not final_text:
            final_text = "আসসালামু আলাইকুম স্যার! হ্যাকাথন সংক্রান্ত তথ্য ও বিশ্লেষণ সফলভাবে প্রস্তুত করা হয়েছে।"
        audio_bytes = result.get("audio_bytes")

        try:
            await status_msg.delete()
        except Exception:
            pass

        for chunk in [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]:
            await update.message.reply_text(chunk)

        if audio_bytes:
            await update.message.chat.send_chat_action(ChatAction.RECORD_VOICE)
            voice_stream = io.BytesIO(audio_bytes)
            voice_stream.name = "hackathon_guide.mp3"
            await update.message.reply_voice(voice=voice_stream, caption="🔊 হ্যাকাথন গাইডেন্স অডিও")

    except Exception as e:
        logger.error(f"Hackathon command error: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ হ্যাকাথন তথ্য খুঁজতে ত্রুটি হয়েছে: {str(e)}")

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming Telegram voice notes and audio clips."""
    message = update.message
    user_id = update.effective_user.id
    register_daily_subscriber(user_id)
    session_id = get_session_id(user_id)
    mode = USER_MODES.get(user_id, "auto")

    await message.chat.send_chat_action(ChatAction.RECORD_VOICE)
    status_msg = await message.reply_text("🎧 আসসালামু আলাইকুম স্যার, আপনার ভয়েস শুনছি ও বিশ্লেষণ করছি...", parse_mode=ParseMode.MARKDOWN)

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

        final_text = result.get("final_report", "").strip()
        if not final_text:
            final_text = "আসসালামু আলাইকুম স্যার! আপনার ভয়েস নির্দেশটি সফলভাবে বিশ্লেষণ ও সম্পন্ন করা হয়েছে।"
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
        await status_msg.edit_text(f"⚠️ আসসালামু আলাইকুম স্যার, ভয়েস প্রক্রিয়াকরণে ত্রুটি হয়েছে: {str(e)}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming Telegram text messages."""
    message = update.message
    user_id = update.effective_user.id
    register_daily_subscriber(user_id)
    session_id = get_session_id(user_id)
    mode = USER_MODES.get(user_id, "auto")
    user_text = message.text.strip()

    if not user_text:
        return

    await message.chat.send_chat_action(ChatAction.TYPING)

    # Immediately acknowledge so user knows bot received their message and is working
    status_msg = await message.reply_text(
        "🧠 আসসালামু আলাইকুম স্যার, আপনার বার্তাটি বিশ্লেষণ ও সম্পন্ন করা হচ্ছে...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        mem = MemoryManager()
        orch = MasterOrchestrator(memory_manager=mem, model=get_active_model())

        result = await asyncio.to_thread(
            orch.process_command,
            session_id=session_id,
            user_command=user_text,
            mode=mode
        )

        final_text = result.get("final_report", "").strip()
        if not final_text:
            final_text = "আসসালামু আলাইকুম স্যার! আপনার নির্দেশটি সফলভাবে সম্পন্ন করা হয়েছে।"
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
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
        await message.reply_text(
            f"⚠️ আসসালামু আলাইকুম স্যার, আপনার নির্দেশটি পালনে একটি সাময়িক সমস্যা হয়েছে:\n\n`{str(e)}`\n\n"
            f"স্যার, অনুগ্রহ করে পুনরায় চেষ্টা করুন অথবা ভিন্নভাবে প্রশ্ন করুন।"
        )

async def send_daily_hackathon_briefing(app: Application, chat_id: int):
    """Sends the 150-200 word morning hackathon briefing with an interactive detailed analysis button."""
    agent = HackathonAgent(model=get_active_model())
    briefing_data = await asyncio.to_thread(agent.generate_daily_briefing)

    text = briefing_data.get("briefing_text", "")
    h_title = briefing_data.get("title", "AI Hackathon")
    h_url = briefing_data.get("url", "https://devpost.com")

    # Interactive button: "🔍 বিস্তারিত জানতে চাই"
    keyboard = [
        [
            InlineKeyboardButton(
                "🔍 বিস্তারিত জানতে চাই",
                callback_data=f"deep_hackathon:{h_title[:45]}"
            )
        ],
        [
            InlineKeyboardButton("🌐 অফিশিয়াল রেজিস্ট্রেশন পেজ", url=h_url)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    header = "🌅 **দৈনিক সকাল ৬:০০ টার হ্যাকাথন সংবাদ ব্রিফিং**\n\n"
    full_message = f"{header}{text}"

    await app.bot.send_message(
        chat_id=chat_id,
        text=full_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

    # Spoken audio in Bengali
    try:
        audio_bytes = await asyncio.to_thread(text_to_speech_bengali, text)
        if audio_bytes:
            stream = io.BytesIO(audio_bytes)
            stream.name = "morning_hackathon_briefing.mp3"
            await app.bot.send_voice(chat_id=chat_id, voice=stream, caption="🔊 সকালের হ্যাকাথন সংবাদ অডিও")
    except Exception as audio_err:
        logger.warning(f"Morning briefing voice generation skipped: {audio_err}")

async def daily_briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """On-demand trigger for the daily 6:00 AM morning briefing format."""
    chat_id = update.effective_chat.id
    register_daily_subscriber(chat_id)
    status_msg = await update.message.reply_text(
        "🌅 **আসসালামু আলাইকুম স্যার, হ্যাকাথন সাব-এজেন্ট লাইভ হ্যাকাথন অনুসন্ধান ও সংবাদ ব্রিফিং তৈরি করছে...**",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await send_daily_hackathon_briefing(context.application, chat_id)
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Daily briefing command error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ আসসালামু আলাইকুম স্যার, ব্রিফিং তৈরিতে সমস্যা হয়েছে: {str(e)}")

async def daily_hackathon_scheduler_loop(app: Application):
    """Runs 24/7 in background to trigger daily hackathon briefing at 6:00 AM (UTC+6 / Bangladesh Time)."""
    logger.info("Daily 6:00 AM Hackathon Scheduler Loop initialized (UTC+6).")
    BD_TZ = timezone(timedelta(hours=6))
    mem = MemoryManager()

    while True:
        try:
            now_bd = datetime.now(BD_TZ)
            today_str = now_bd.strftime("%Y-%m-%d")
            last_sent = mem.get_preference("last_daily_hackathon_date", "")

            # Trigger every day at 06:00 AM (UTC+6)
            if now_bd.hour == 6 and now_bd.minute == 0 and last_sent != today_str:
                logger.info(f"06:00 AM reached ({today_str})! Scouting hackathons and sending daily briefings...")
                raw_subs = mem.get_preference("daily_hackathon_subscribers", "[]")
                subscribers = json.loads(raw_subs) if raw_subs else []

                for cid in subscribers:
                    try:
                        await send_daily_hackathon_briefing(app, cid)
                    except Exception as sub_err:
                        logger.error(f"Failed to send 6:00 AM briefing to chat {cid}: {sub_err}")

                mem.set_preference("last_daily_hackathon_date", today_str)
                await asyncio.sleep(65)  # Avoid duplicate trigger in the same minute
        except Exception as loop_err:
            logger.error(f"Scheduler loop error: {loop_err}")

        await asyncio.sleep(25)

def build_telegram_app(token: str) -> Application:
    """Builds and configures the Telegram Application."""
    async def post_init(application: Application):
        asyncio.create_task(daily_hackathon_scheduler_loop(application))

    app = Application.builder().token(token).post_init(post_init).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("auto", set_auto_mode))
    app.add_handler(CommandHandler("chat", set_chat_mode))
    app.add_handler(CommandHandler("work", set_work_mode))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("hackathon", hackathon_command))
    app.add_handler(CommandHandler("briefing", daily_briefing_command))
    app.add_handler(CommandHandler("daily_hackathon", daily_briefing_command))
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

