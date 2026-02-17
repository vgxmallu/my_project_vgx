import pytz
from datetime import datetime, timedelta
from pyrogram.types import ChatPermissions
from vgx.database.night_db import chats, update_chat
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def check_schedules(app):
    async for chat in chats.find({"enabled": True}):
        try:
            cid = chat['chat_id']
            tz = pytz.timezone(chat.get('timezone', 'UTC'))
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")
            
            # Times
            start_str = chat['night_start']
            end_str = chat['night_end']
            
            # --- 1. WARNING SYSTEM (5 mins before) ---
            if chat.get('warning'):
                # Calculate 5 mins before start
                h, m = map(int, start_str.split(':'))
                warn_time = (now.replace(hour=h, minute=m, second=0) - timedelta(minutes=5)).strftime("%H:%M")
                
                if current_time == warn_time:
                    await app.send_message(cid, "⚠️ **Notice:** Night Mode will activate in 5 minutes!")

            # --- 2. NIGHT MODE LOGIC ---
            # Determine if we are in the "Night Window"
            is_night_now = False
            if start_str < end_str:
                is_night_now = start_str <= current_time < end_str
            else: # Cross-midnight (e.g. 23:00 to 06:00)
                is_night_now = current_time >= start_str or current_time < end_str

            # Emergency Override Check
            if chat.get('temp_unlock'):
                if is_night_now: 
                    continue # Skip locking logic if emergency unlocked
                else: 
                    # If morning comes, reset the emergency flag automatically
                    await update_chat(cid, {"temp_unlock": False})

            # State Transition
            prev_state = chat.get('is_night', False)
            
            if is_night_now and not prev_state:
                # -> LOCK GROUP
                await set_night_permissions(app, chat)
                msg = await app.send_message(cid, "🌙 **Night Mode Active.** Chat is restricted.")
                
                # Pin logic could go here
                
                await update_chat(cid, {"is_night": True, "last_alert_id": msg.id})
                
            elif not is_night_now and prev_state:
                # -> UNLOCK GROUP
                await set_day_permissions(app, cid)
                
                # Auto-Clean: Delete the "Night Mode Active" message
                if chat.get('auto_clean') and chat.get('last_alert_id'):
                    try: await app.delete_messages(cid, chat['last_alert_id'])
                    except: pass
                
                msg = await app.send_message(cid, "☀️ **Good Morning!** Chat is open.")
                
                # Schedule deletion of the Morning message (1 hour later)
                # (Simple version: just leave it or use a separate job. We'll skip complex job scheduling for now)
                
                await update_chat(cid, {"is_night": False})

        except Exception as e:
            print(f"Error in {chat.get('chat_id')}: {e}")

async def set_night_permissions(app, chat):
    """Applies the selective permissions defined in DB"""
    p = chat['perms']
    # If p['text'] is True, we ALLOW text. 
    # Telegram ChatPermissions logic: True = Allowed, False = Restricted
    
    perms = ChatPermissions(
        can_send_messages=p['text'],
        can_send_media_messages=p['media'],
        can_send_other_messages=p['stickers'], # GIF/Stickers
        can_add_web_page_previews=p['links'],
        can_send_polls=False,
        can_invite_users=True
    )
    await app.set_chat_permissions(chat['chat_id'], perms)

async def set_day_permissions(app, chat_id):
    """Restores full access"""
    perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_send_polls=True,
        can_invite_users=True
    )
    await app.set_chat_permissions(chat_id, perms)

def start_scheduler(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_schedules, "interval", minutes=1, args=[app])
    scheduler.start()
