import asyncio
from datetime import datetime
from pyrogram.types import ChatPermissions
from vgx.database.pomodoro_db import get_expired_sprints, remove_sprint

async def pomodoro_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            expired_sprints = await get_expired_sprints(now)
            
            for sprint in expired_sprints:
                chat_id = sprint["chat_id"]
                
                try:
                    # Restore standard chat permissions
                    await app.set_chat_permissions(
                        chat_id,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True
                        )
                    )
                    
                    # Announce the break
                    await app.send_message(
                        chat_id, 
                        "🔔 **Sprint over!**\nThe chat is now unlocked. You have a well-deserved break! ☕️"
                    )
                except Exception as e:
                    print(f"Failed to unlock chat {chat_id}: {e}")
                
                # Remove from database so it doesn't trigger again
                await remove_sprint(chat_id)
                
        except Exception as e:
            print(f"Pomodoro Scheduler Error: {e}")
            
        await asyncio.sleep(10) # Check every 10 seconds
