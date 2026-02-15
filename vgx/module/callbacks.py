import datetime
from pyrogram import Client
from pyrogram.types import CallbackQuery
from client import scheduler
from database import db
from utils import get_settings_keyboard
from plugins.commands import user_sessions
from plugins.jobs import send_scheduled_message

@Client.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    chat_id = query.message.chat.id
    data = query.data
    
    if data == "cancel":
        if chat_id in user_sessions: del user_sessions[chat_id]
        await query.message.edit_text("❌ Cancelled.")
        return

    if chat_id not in user_sessions:
        await query.answer("⚠️ Session expired.", show_alert=True)
        return

    session = user_sessions[chat_id]

    if data == "toggle_pin":
        session["pin"] = not session["pin"]
    
    elif data == "toggle_preview":
        session["preview"] = not session["preview"]

    elif data == "toggle_night":
        session["night_mode"] = not session["night_mode"]
        await query.answer("🌙 Night Mode Toggled", show_alert=True)

    elif data == "set_time":
        session["schedule_time"] = datetime.datetime.now() + datetime.timedelta(minutes=1)
        await query.answer("⏰ Set to +1 Minute")

    elif data == "set_repeat":
        current = session["repeat"]
        session["repeat"] = 10 if current == 0 else (60 if current == 10 else 0)
        await query.answer(f"🔄 Repeat: {session['repeat']} mins")

    elif data == "save_job":
        run_time = session["schedule_time"] or datetime.datetime.now()
        
        job_data = {
            "chat_id": chat_id,
            "text": session["text"],
            "media": session["media"],
            "media_type": session["media_type"],
            "pin": session["pin"],
            "disable_preview": not session["preview"],
            "night_mode": session["night_mode"],
            "next_run": run_time,
            "repeat_interval": session["repeat"]
        }
        
        job_id = await db.add_job(job_data)
        
        scheduler.add_job(
            send_scheduled_message, 
            "date", 
            run_date=run_time, 
            args=[job_id],
            id=job_id
        )

        await query.message.edit_text("✅ **Scheduled Successfully!**")
        del user_sessions[chat_id]
        return

    await query.message.edit_reply_markup(reply_markup=get_settings_keyboard(session))
