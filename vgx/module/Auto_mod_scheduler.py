import asyncio
from datetime import datetime
from vgx.database.automod_db import get_all_enabled_groups, pop_weekly_stats

async def weekly_audit_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # Check if it is Sunday (weekday 6) and 20:00 (8:00 PM) UTC
            if now.weekday() == 6 and now.hour == 20 and now.minute == 0:
                groups = await get_all_enabled_groups()
                
                for group in groups:
                    chat_id = group["chat_id"]
                    
                    # Fetch stats and instantly reset them in the DB
                    stats = await pop_weekly_stats(chat_id)
                    
                    # Only send report if there was actually activity
                    if any(val > 0 for val in stats.values()):
                        report = (
                            "📊 **Weekly Auto-Mod Report**\n\n"
                            f"🔹 **Auto-Warns Issued:** {stats['warns_issued']}\n"
                            f"🔹 **Messages Deleted:** {stats['msgs_deleted']}\n"
                            f"🔹 **Users Muted:** {stats['users_muted']}\n"
                            f"🔹 **Warnings Decayed:** {stats['warns_decayed']}\n\n"
                            "🛡 *Your group is 100% secure!*"
                        )
                        
                        try:
                            # Sends the report to the group. 
                            # (If you want it to send to a private admin channel, you'd save an admin_chat_id in settings!)
                            await app.send_message(chat_id, report)
                        except Exception as e:
                            print(f"Failed to send report to {chat_id}: {e}")
                
                # Sleep for 60 seconds to ensure we don't send the report twice in the same minute!
                await asyncio.sleep(60) 
                
        except Exception as e:
            print(f"Audit Loop Error: {e}")
            
        await asyncio.sleep(20) # Normal check interval
