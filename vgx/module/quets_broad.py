import random
import asyncio
from pyrogram.errors import FloodWait, PeerIdInvalid, UserIsBlocked
from vgx.database.quets_db import get_all_enabled_chats, disable_quotes
from quotes_list import POWERFUL_QUOTES
from vgx.module.quets_broad import send_hourly_quotes

async def send_hourly_quotes(app):
    """This function is called by the APScheduler every hour."""
    enabled_chats = await get_all_enabled_chats()
    
    async for chat in enabled_chats:
        chat_id = chat["chat_id"]
        quote = random.choice(POWERFUL_QUOTES)
        
        try:
            await app.send_message(chat_id, quote)
            await asyncio.sleep(1) # Prevent hitting Telegram's broadcast limits
            
        except FloodWait as e:
            # If we send too fast, wait the required time
            await asyncio.sleep(e.value)
            await app.send_message(chat_id, quote)
            
        except (PeerIdInvalid, UserIsBlocked, Exception):
            # If the bot was kicked from the group or blocked by the user,
            # disable the module in the database to save future resources.
            await disable_quotes(chat_id)

def start_qet_scheduler(app):
    scheduler = AsyncIOScheduler()
    # Check every minute
    scheduler.add_job(send_hourly_quotes, "interval", hours=1, args=[app])
    scheduler.start()
