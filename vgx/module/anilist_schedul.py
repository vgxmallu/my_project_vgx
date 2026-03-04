import asyncio
import time
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.anilist_db import get_due_chats, update_chat


from vgx.utils.anilist import fetch_random_anime

async def auto_delete_task(app, chat_id: int, msg_id: int, delay: int):
    await asyncio.sleep(delay)
    try: await app.delete_messages(chat_id, msg_id)
    except Exception: pass

async def anime_worker(app):
    while True:
        try:
            due_chats = await get_due_chats()
            if due_chats:
                # Fetch ONE anime to send to all due chats to save API limits
                anime = await fetch_random_anime()
                now = int(time.time())
                
                caption = (
                    f"📺 **{anime['title']}**\n\n"
                    f"**⭐ Score:** {anime['score']}/100\n"
                    f"**🎬 Episodes:** {anime['episodes']}\n"
                    f"**🎭 Genres:** {anime['genres']}\n\n"
                    f"📝 *{anime['description']}*"
                )
                
                buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View on AniList", url=anime["url"])]])
                
                for chat in due_chats:
                    chat_id = chat["chat_id"]
                    try:
                        # Send Photo with Caption
                        msg = await app.send_photo(
                            chat_id, 
                            photo=anime["image"], 
                            caption=caption,
                            reply_markup=buttons
                        )
                        
                        await update_chat(chat_id, last_sent=now, last_msg_id=msg.id)
                        
                        if chat.get("pin", False):
                            await msg.pin(both_sides=True)
                            
                        del_time = chat.get("delete_after", 0)
                        if del_time > 0:
                            asyncio.create_task(auto_delete_task(app, chat_id, msg.id, del_time))
                            
                        await asyncio.sleep(1) # Anti-flood pacing
                        
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        print(f"Skipping {chat_id}: {e}")
                        
            await asyncio.sleep(20) # 20 second precise polling
            
        except Exception as e:
            print(f"Scheduler Engine Error: {e}")
            await asyncio.sleep(10)
