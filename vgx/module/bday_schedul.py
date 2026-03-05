import asyncio
from datetime import datetime
import pytz
from pyrogram.errors import FloodWait
from vgx.database.bday_db import get_users_by_bday_and_tz, groups_col
from vgx import app
async def birthday_worker(app):
    """Hourly background loop for precision timezone announcements."""
    while True:
        try:
            now_utc = datetime.now(pytz.utc)
            
            # Scan all timezones to see where it is currently 08:00 AM
            for tz_name in pytz.all_timezones:
                tz = pytz.timezone(tz_name)
                local_time = now_utc.astimezone(tz)
                
                if local_time.hour == 8: # Trigger celebrations at 8 AM local time
                    month, day = local_time.month, local_time.day
                    birthday_users = await get_users_by_bday_and_tz(month, day, tz_name)
                    
                    if birthday_users:
                        await announce_birthdays(app, birthday_users)

            # Sleep exactly 1 hour before the next global sweep
            await asyncio.sleep(3600)
            
        except Exception as e:
            print(f"Scheduler Error: {e}")
            await asyncio.sleep(60)

async def announce_birthdays(app, users: list):
    """Dispatches messages to groups."""
    cursor = groups_col.find({"enabled": True})
    active_groups = await cursor.to_list(length=None)
    
    for group in active_groups:
        chat_id = group["chat_id"]
        
        for user_data in users:
            user_id = user_data["user_id"]
            
            # 🛡 Trusted Role System Check
            if group.get("trusted_only", False):
                if user_id not in group.get("trusted_users", []):
                    continue # Skip if user isn't trusted
            
            try:
                # Get user to tag them
                member = await app.get_chat_member(chat_id, user_id)
                msg_text = group["custom_msg"].replace("{mention}", member.user.mention)
                media_id = group.get("media_id")
                
                # Send Media-Friendly Message
                if media_id:
                    # Pyrogram auto-detects if it's an animation or photo file_id via send_cached_media
                    await app.send_cached_media(chat_id, document=media_id, caption=msg_text)
                else:
                    await app.send_message(chat_id, text=msg_text)
                    
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass # Bot kicked, or user left the group
