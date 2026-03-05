import datetime
from pyrogram import Client, filters
from vgx.module import sessions
from vgx.database.db_advanc import db
from vgx import scheduler
from utils2 import get_wizard_kb
from vgx.module.adv_engine import run_job
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# --- STARTER ---
@Client.on_message(filters.private & filters.command("schedule"))
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

"""
# ✅ MERGED DECORATOR: Listens for Text, Photos, Videos, AND Stickers in Private Chat
@Client.on_message(filters.private & (filters.text | filters.photo | filters.video | filters.sticker))
async def input_handler(c, m):
    # 1. Safety Check: Ignore messages without a sender (Channels/Service msgs)
    if not m.from_user:
        return

    uid = m.from_user.id
    
    # 2. Safety Check: Ignore if the user isn't currently in a session
    if uid not in sessions:
        return

    s = sessions[uid]
    step = s.get('step') # Using .get() prevents crashes if 'step' is missing
    
    # ==================================================================
    # BLOCK A: EDITING AN EXISTING JOB (Direct DB Update)
    # ==================================================================
    if step == "editing_existing_job":
        job_id = s.get('job_id')
        update_data = {}

        # Detect Media Type
        if m.sticker:
            update_data = {"media_type": "sticker", "file_id": m.sticker.file_id, "text": ""}
        elif m.photo:
            update_data = {"media_type": "photo", "file_id": m.photo.file_id, "text": m.caption or ""}
        elif m.video:
            update_data = {"media_type": "video", "file_id": m.video.file_id, "text": m.caption or ""}
        elif m.text:
            update_data = {"media_type": "text", "text": m.text, "file_id": None}
        else:
             return await m.reply("⚠️ Unsupported media type.")

        # Update MongoDB immediately
        await db.update_job(job_id, update_data)
        
        # Cleanup session (Interaction finished)
        del sessions[uid]
        
        await m.reply(
            f"✅ **Job Updated!**\nNext time this job runs, it will use the new content.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to My Jobs", callback_data="myjobs_refresh")]])
        )
        return

    # ==================================================================
    # BLOCK B: CREATING A NEW JOB (Wizard Steps)
    # ==================================================================
    
    # --- Step: Waiting for Target Chat ID ---
    elif step == "waiting_target":
        try:
            # We strip whitespace in case user copied a space
            chat_id_str = m.text.strip()
            # Basic validation to ensure it's a number
            target_id = int(chat_id_str)
            
            s['data']['target_chat'] = target_id
            s['step'] = "menu" # Return to main wizard menu
            
            await m.reply("✅ Target Set.", reply_markup=get_wizard_kb(s['data']))
        except (ValueError, AttributeError):
            await m.reply("❌ **Invalid ID.** Please send a numeric ID (e.g., `-100123456789`).")

    # --- Step: Waiting for Content (Initial Setup) ---
    elif step == "waiting_content":
        if m.sticker:
            s['data']['media_type'] = 'sticker'
            s['data']['file_id'] = m.sticker.file_id
            s['data']['text'] = "" 
        elif m.photo:
            s['data']['media_type'] = 'photo'
            s['data']['file_id'] = m.photo.file_id
            s['data']['text'] = m.caption or ""
        elif m.video:
            s['data']['media_type'] = 'video'
            s['data']['file_id'] = m.video.file_id
            s['data']['text'] = m.caption or ""
        elif m.text:
            s['data']['media_type'] = 'text'
            s['data']['text'] = m.text
        else:
            return await m.reply("⚠️ Please send only Text, Photo, Video, or Sticker.")
        
        s['step'] = "menu" # Return to main wizard menu
        await m.reply("✅ Content Updated.", reply_markup=get_wizard_kb(s['data']))
"""


# ==================================================================
# 1. COMMAND: /setcontent or /settext (Must reply to media/text)
# ==================================================================
@Client.on_message(filters.command(["settext", "setcontent"]) & filters.private)
async def set_content_command(c, m):
    if not m.from_user:
        return

    uid = m.from_user.id
    
    # Safety Check: Ignore if the user isn't currently in a session
    if uid not in sessions:
        return await m.reply("⚠️ You don't have an active setup session right now.")

    # REQUIREMENT: They must reply to the message they want to save
    if not m.reply_to_message:
        return await m.reply("❌ **Error:** You must **reply** to a text, photo, video, or sticker with this command!")

    s = sessions[uid]
    step = s.get('step')
    target_msg = m.reply_to_message

    # --- Detect Media Type from the Replied Message ---
    media_type = None
    file_id = None
    text_content = ""

    if target_msg.sticker:
        media_type = "sticker"
        file_id = target_msg.sticker.file_id
    elif target_msg.photo:
        media_type = "photo"
        file_id = target_msg.photo.file_id
        text_content = target_msg.caption or ""
    elif target_msg.video:
        media_type = "video"
        file_id = target_msg.video.file_id
        text_content = target_msg.caption or ""
    elif target_msg.text:
        media_type = "text"
        text_content = target_msg.text
    else:
        return await m.reply("⚠️ Unsupported media type. Please reply to Text, Photo, Video, or Sticker.")

    # --- BLOCK A: EDITING AN EXISTING JOB ---
    if step == "editing_existing_job":
        job_id = s.get('job_id')
        update_data = {
            "media_type": media_type,
            "file_id": file_id,
            "text": text_content
        }

        # Update MongoDB immediately
        await db.update_job(job_id, update_data)
        
        # Cleanup session (Interaction finished)
        del sessions[uid]
        
        await m.reply(
            f"✅ **Job Updated!**\nNext time this job runs, it will use the new content.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to My Jobs", callback_data="myjobs_refresh")]])
        )

    # --- BLOCK B: CREATING A NEW JOB (Wizard Steps) ---
    elif step == "waiting_content":
        s['data']['media_type'] = media_type
        s['data']['file_id'] = file_id
        s['data']['text'] = text_content
        
        s['step'] = "menu" # Return to main wizard menu
        await m.reply("✅ Content Updated.", reply_markup=get_wizard_kb(s['data']))
        
    else:
        await m.reply("⚠️ Please click the 'Set Content' button in the menu first before using this command.")


# ==================================================================
# 2. COMMAND: /settarget (To set the Chat ID)
# ==================================================================
@Client.on_message(filters.command("settarget") & filters.private)
async def set_target_command(c, m):
    if not m.from_user:
        return

    uid = m.from_user.id
    if uid not in sessions:
        return

    s = sessions[uid]
    step = s.get('step')

    if step == "waiting_target":
        if len(m.command) < 2:
            return await m.reply("❌ **Usage:** `/settarget -100123456789`")

        try:
            chat_id_str = m.command[1].strip()
            target_id = int(chat_id_str)
            
            s['data']['target_chat'] = target_id
            s['step'] = "menu" # Return to main wizard menu
            
            await m.reply("✅ Target Set.", reply_markup=get_wizard_kb(s['data']))
        except ValueError:
            await m.reply("❌ **Invalid ID.** Please send a numeric ID (e.g., `/settarget -100123456789`).")

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
        opts = [0, 5, 10, 30, 40, 50, 60]
        curr = s['data'].get('interval', 0)
        try: idx = (opts.index(curr) + 1) % len(opts)
        except: idx = 0
        s['data']['interval'] = opts[idx]
        
    elif "set_autodel" in data:
        # 0 -> 30s -> 5m -> 1h -> 0
        opts = [0, 30, 300, 2400, 3000, 3600]
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
