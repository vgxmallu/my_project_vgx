# To implement this cleanly, we usually attach a listener in main.py 
# or use a global counter that resets every minute.
# For simplicity, we assume 'watcher' in leaderboard.py increments a RAM counter.

# (Conceptual implementation for Main loop)
from vgx.database.anlys_db import promos
from vgx.module.anylz_Analytics import is_viral_moment

# Global RAM counter: {chat_id: count}
msg_buffer = {} 

async def check_viral_spikes(app):
    for chat_id, count in msg_buffer.items():
        if await is_viral_moment(chat_id, count):
            promo = await promos.find_one({"chat_id": chat_id})
            if promo:
                await app.send_message(chat_id, f"🔥 **TRENDING NOW:**\n\n{promo['text']}")
                # Cooldown logic needed here to prevent spam
    
    msg_buffer.clear() # Reset every 5 mins
