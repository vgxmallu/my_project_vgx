import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import db
from main import scheduler, app
from scheduler_eng import perform_job_task

# In-memory session to store data while user is creating a post
# Structure: {user_id: { "text": "...", "pin": False ... } }
sessions = {} 

def get_dashboard_markup(uid):
    s = sessions.get(uid, {})
    
    # State Indicators
    pin_state = "✅ On" if s.get('pin') else "❌ Off"
    preview_state = "✅ On" if s.get('preview') else "❌ Off"
    repeat_state = f"{s.get('repeat')}m" if s.get('repeat') else "❌ Off"
    target_chat = s.get('target_chat', 'Not Set ❌')

    buttons = [
        [
            InlineKeyboardButton(f"🎯 Target: {str(target_chat)[:12]}", callback_data="set_target"),
            InlineKeyboardButton("📝 Edit Content", callback_data="set_content")
        ],
        [
            InlineKeyboardButton(f"📌 Pin: {pin_state}", callback_data="toggle_pin"),
            InlineKeyboardButton(f"🔗 Preview: {preview_state}", callback_data="toggle_preview")
        ],
        [
            InlineKeyboardButton(f"🔄 Repeat: {repeat_state}", callback_data="set_repeat"),
            InlineKeyboardButton("⏳ Set Time", callback_data="set_time")
        ],
        [
            InlineKeyboardButton("✅ SAVE & SCHEDULE", callback_data="save_job"),
            InlineKeyboardButton("🗑 Cancel", callback_data="cancel_wizard")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("schedule") & filters.private)
async def start_wizard(client, message):
    uid = message.from_user.id
    if uid != Config.ADMIN_ID:
        return await message.reply("🔒 You are not authorized.")

    # Initialize Session
    sessions[uid] = {
        "text": "Default Text",
        "media_type": "text",
        "pin": False,
        "preview": True,
        "repeat": 0,
        "target_chat": None,
        "time": None
    }
    
    await message.reply(
        "⚙️ **Scheduler Dashboard**\n\n"
        "Configure your auto-message using the buttons below. "
        "This mimics the app UI functionality.",
        reply_markup=get_dashboard_markup(uid)
    )
  
# --- Middleware-like Check ---
# Since many handlers need the session, we check it here
async def check_session(query):
    uid = query.from_user.id
    if uid not in sessions:
        await query.answer("⚠️ Session expired. /schedule again.", show_alert=True)
        return False
    return True

# --- Toggle Handlers ---

@Client.on_callback_query(filters.regex(r"^toggle_(pin|preview)$"))
async def toggle_handler(client, query):
    if not await check_session(query): return
    uid = query.from_user.id
    field = query.data.split("_")[1] # 'pin' or 'preview'
    
    sessions[uid][field] = not sessions[uid][field]
    await query.message.edit_reply_markup(get_dashboard_markup(uid))

# --- Input Initiation Handlers ---

@Client.on_callback_query(filters.regex(r"^set_(target|content|repeat|time)$"))
async def set_handler(client, query):
    if not await check_session(query): return
    uid = query.from_user.id
    data = query.data
    s = sessions[uid]

    if data == "set_target":
        await query.answer("⚠️ Send the Group ID now", show_alert=True)
        s['awaiting'] = 'chat_id'
    elif data == "set_content":
        await query.answer("⚠️ Send the Text or Photo now", show_alert=True)
        s['awaiting'] = 'content'
    elif data == "set_repeat":
        curr = s.get('repeat', 0)
        s['repeat'] = 10 if curr == 0 else (60 if curr == 10 else 0)
        await query.message.edit_reply_markup(get_dashboard_markup(uid))
    elif data == "set_time":
        s['time'] = datetime.datetime.now() + datetime.timedelta(minutes=1)
        await query.answer("✅ Time set to 1 minute from now", show_alert=True)

# --- Save Handler ---

@Client.on_callback_query(filters.regex("^save_job$"))
async def save_handler(client, query):
    if not await check_session(query): return
    uid = query.from_user.id
    s = sessions[uid]

    if not s.get('target_chat'):
        return await query.answer("❌ You must set a Target Chat ID!", show_alert=True)
    
    job_data = {
        "chat_id": int(s['target_chat']),
        "text": s['text'],
        "media_type": s['media_type'],
        "file_id": s.get('file_id'),
        "pin_msg": s['pin'],
        "link_preview": s['preview'],
        "repeat_interval": s['repeat'],
        "next_run": s.get('time') or datetime.datetime.now()
    }
    
    res = await db.add_job(job_data)
    job_id = str(res.inserted_id)

    scheduler.add_job(
        perform_job_task, "date", 
        run_date=job_data['next_run'], 
        args=[app, job_id], id=job_id
    )

    await query.message.edit_text(f"✅ **Scheduled!**\nJob ID: `{job_id}`")
    del sessions[uid]

# --- Cancel Handler ---

@Client.on_callback_query(filters.regex("^cancel_wizard$"))
async def cancel_handler(client, query):
    uid = query.from_user.id
    if uid in sessions:
        del sessions[uid]
        await query.message.edit_text("❌ Scheduled creation cancelled.")
    else:
        await query.message.delete()


@Client.on_message(filters.private & ~filters.command("schedule"))
async def input_listener(client, message):
    uid = message.from_user.id
    if uid not in sessions or 'awaiting' not in sessions[uid]:
        return
    
    s = sessions[uid]
    action = s['awaiting']
    
    if action == 'chat_id':
        s['target_chat'] = message.text
        s['awaiting'] = None
        await message.reply("✅ Target set.", reply_markup=get_dashboard_markup(uid))
        
    elif action == 'content':
        if message.photo:
            s['media_type'] = 'photo'
            s['file_id'] = message.photo.file_id
            s['text'] = message.caption or ""
        else:
            s['media_type'] = 'text'
            s['text'] = message.text
            
        s['awaiting'] = None
        await message.reply("✅ Content updated.", reply_markup=get_dashboard_markup(uid))
