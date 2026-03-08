import asyncio
from datetime import datetime
from vgx.database.sleepmod_db import get_all_enabled_groups, set_global_mode

async def nightwatch_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # NOTE: datetime.utcnow() is UTC time. 
            # If your server is in India (IST = UTC+5:30), you may want to adjust this math 
            # or rely on server local time via datetime.now() depending on where it's hosted!
            # For this example, we check the exact hour.
            
            current_hour = now.hour
            current_minute = now.minute
            
            # TRIGGER 1: NIGHTWATCH ACTIVATES AT 01:00
            if current_hour == 1 and current_minute == 0:
                groups = await get_all_enabled_groups()
                # Update DB for all groups
                await set_global_mode("strict")
                
                for group in groups:
                    chat_id = group["chat_id"]
                    # If it was previously lenient, announce the shift
                    if group.get("current_mode") != "strict":
                        msg = (
                            "🦉 **NIGHTWATCH ACTIVATED** 🦉\n\n"
                            "The moderation team is offline. Maximum Security Protocol is now active.\n"
                            "🚫 **Blocked:** All Links, Media, and Forwards.\n"
                            "🔇 **Spam:** Strict auto-muting is enabled."
                        )
                        try:
                            await app.send_message(chat_id, msg)
                        except Exception:
                            pass
                
                # Sleep to prevent triggering multiple times in the same minute
                await asyncio.sleep(60)
                
            # TRIGGER 2: NIGHTWATCH DEACTIVATES AT 07:00
            elif current_hour == 7 and current_minute == 0:
                groups = await get_all_enabled_groups()
                # Update DB for all groups
                await set_global_mode("lenient")
                
                for group in groups:
                    chat_id = group["chat_id"]
                    # If it was previously strict, announce the shift
                    if group.get("current_mode") != "lenient":
                        msg = (
                            "☀️ **GOOD MORNING!** ☀️\n\n"
                            "Nightwatch Mode deactivated. Standard lenient security is restored. "
                            "Media and safe links are now permitted. Have a great day!"
                        )
                        try:
                            await app.send_message(chat_id, msg)
                        except Exception:
                            pass
                            
                await asyncio.sleep(60)

        except Exception as e:
            print(f"Nightwatch Scheduler Error: {e}")
            
        await asyncio.sleep(20) # Normal check interval
