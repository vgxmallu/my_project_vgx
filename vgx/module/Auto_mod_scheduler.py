import asyncio
from datetime import datetime
from vgx.database.automod_db import get_all_enabled_groups, pop_weekly_stats

async def weekly_audit_loop(app):
    while True:
        try:
            now = datetime.utcnow()
            
            # Run exactly on Sunday (6) at 20:00 UTC
            if now.weekday() == 6 and now.hour == 20 and now.minute == 0:
                groups = await get_all_enabled_groups()
                
                for group in groups:
                    chat_id = group["chat_id"]
                    
                    # Fetch stats and instantly wipe them from DB
                    stats = await pop_weekly_stats(chat_id)
                    
                    if any(val > 0 for val in stats.values()):
                        report = (
                            "📊 **Weekly Auto-Mod Report**\n\n"
                            f"🔹 **Auto-Warns Issued:** {stats['warns_issued']}\n"
                            f"🔹 **Messages Deleted:** {stats['msgs_deleted']}\n"
                            f"🔹 **Users Muted:** {stats['users_muted']}\n"
                            f"🔹 **Users Banned:** {stats['users_banned']}\n"
                            f"🔹 **Warnings Decayed:** {stats['warns_decayed']}\n\n"
                            "🛡 *Your group is 100% secure!*"
                        )
                        
                        try:
                            await app.send_message(chat_id, report)
                        except Exception as e:
                            print(f"Failed to send report to {chat_id}: {e}")
                
                # Sleep 60 seconds so it doesn't trigger twice in the same minute
                await asyncio.sleep(60) 
                
        except Exception as e:
            print(f"Audit Loop Error: {e}")
            
        await asyncio.sleep(20) # Normal check interval
