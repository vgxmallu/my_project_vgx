import datetime
from pyrogram import Client, filters
from vgx.module import sessions
from vgx.database.db_advanc import db
from vgx import scheduler
from utils2 import get_wizard_kb
from vgx.module.adv_engine import run_job

# --- STARTER ---
@Client.on_message(filters.command("schedule"))
async def start_wizard(c, m):
    uid = m.from_user.id
    sessions[uid] = {
        "step": "menu",
        "data": {
            "user_id": uid,
            "pin": False,
            "del_last": False,
            "interval": 0,
            "auto_del": 0,
            "target_chat": None,
            "text": "Default Text",
            "media_type": "text"
        }
    }
    await m.reply("⚙️ **Scheduler Dashboard**", reply_markup=get_wizard_kb(sessions[uid]['data']))

# --- TEXT/MEDIA INPUT LISTENER ---
@Client.on_message(filters.text | filters.photo | filters.video)
async def input_handler(c, m):
    uid = m.from_user.id
    if uid not in sessions: return

    s = sessions[uid]
    step = s['step']
    
    if step == "waiting_target":
        try:
            s['data']['target_chat'] = int(m.text)
            s['step'] = "menu"
            await m.reply("✅ Target Set.", reply_markup=get_wizard_kb(s['data']))
        except:
            await m.reply("❌ Invalid ID. Send a number like -100123456.")

    elif step == "waiting_content":
        if m.photo:
            s['data']['media_type'] = 'photo'
            s['data']['file_id'] = m.photo.file_id
            s['data']['text'] = m.caption or ""
        elif m.video:
            s['data']['media_type'] = 'video'
            s['data']['file_id'] = m.video.file_id
            s['data']['text'] = m.caption or ""
        else:
            s['data']['media_type'] = 'text'
            s['data']['text'] = m.text
        
        s['step'] = "menu"
        await m.reply("✅ Content Updated.", reply_markup=get_wizard_kb(s['data']))

# --- REGEX CALLBACKS ---

@Client.on_callback_query(filters.regex(r"^wiz_"))
async def wizard_callbacks(c, q):
    uid = q.from_user.id
    data = q.data
    
    if uid not in sessions:
        return await q.answer("⚠️ Session Expired. /schedule again", show_alert=True)
        
    s = sessions[uid]
    
    # 1. Toggles
    if "toggle_pin" in data:
        s['data']['pin'] = not s['data']['pin']
    elif "toggle_dellast" in data:
        s['data']['del_last'] = not s['data']['del_last']
        
    # 2. Settings (Cycles)
    elif "set_interval" in data:
        # 0 -> 5 -> 10 -> 30 -> 60 -> 0
        opts = [0, 5, 10, 30, 60]
        curr = s['data'].get('interval', 0)
        try: idx = (opts.index(curr) + 1) % len(opts)
        except: idx = 0
        s['data']['interval'] = opts[idx]
        
    elif "set_autodel" in data:
        # 0 -> 30s -> 5m -> 1h -> 0
        opts = [0, 30, 300, 3600]
        curr = s['data'].get('auto_del', 0)
        try: idx = (opts.index(curr) + 1) % len(opts)
        except: idx = 0
        s['data']['auto_del'] = opts[idx]

    # 3. Input Triggers
    elif "set_target" in data:
        s['step'] = "waiting_target"
        return await q.message.reply("🆔 **Send Target Chat ID:**\n(Make sure I am admin there)")
        
    elif "set_content" in data:
        s['step'] = "waiting_content"
        return await q.message.reply("📝 **Send Text, Photo or Video:**")

    # 4. Save / Cancel
    elif "wiz_cancel" in data:
        del sessions[uid]
        return await q.message.edit_text("❌ Cancelled.")
        
    elif "wiz_save" in data:
        if not s['data'].get('target_chat'):
            return await q.answer("❌ Target Chat Required!", show_alert=True)
            
        # Set first run time (+10 seconds from now)
        s['data']['next_run'] = datetime.datetime.now() + datetime.timedelta(seconds=10)
        s['data']['paused'] = False
        
        # Save DB
        res = await db.add_job(s['data'])
        job_id = str(res.inserted_id)
        
        # Start Job
        scheduler.add_job(
            run_job, "date", 
            run_date=s['data']['next_run'],
            args=[job_id], id=job_id
        )
        
        del sessions[uid]
        return await q.message.edit_text(f"✅ **Job Started!**\nID: `{job_id}`")

    # Refresh keyboard
    await q.message.edit_reply_markup(get_wizard_kb(s['data']))
