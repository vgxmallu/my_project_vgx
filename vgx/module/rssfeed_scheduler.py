import asyncio
from pyrogram.errors import FloodWait
from vgx.database.rssfeed_db import get_feeds, add_to_cache
from vgx.module.rssfeed_engine import parse_and_format

async def autopost_worker(app):
    while True:
        try:
            active_feeds = await get_feeds() # Fetch all globally enabled feeds
            
            for feed in active_feeds:
                try:
                    chat_id = feed["chat_id"]
                    # Fetch basic chat info for the placeholders
                    chat_info = await app.get_chat(chat_id)
                    chat_data = {"title": chat_info.title, "type": chat_info.type.name}
                    
                    # Parse feed and get formatted posts
                    posts = await parse_and_format(feed, chat_data)
                    
                    for post in posts:
                        text = post["text"]
                        parse_mode = None if feed.get("format") == "HTML" else "markdown"
                        
                        try:
                            if post["image"] and feed.get("send_images"):
                                await app.send_photo(
                                    chat_id, 
                                    photo=post["image"], 
                                    caption=text,
                                    disable_notification=feed.get("silent_notification")
                                )
                            else:
                                await app.send_message(
                                    chat_id, 
                                    text=text,
                                    disable_web_page_preview=not feed.get("link_preview"),
                                    disable_notification=feed.get("silent_notification")
                                )
                                
                            # Cache the GUID so we never post it again
                            await add_to_cache(feed["_id"], post["guid"])
                            await asyncio.sleep(2) # Anti-flood pacing
                            
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                            
                except Exception as e:
                    print(f"Failed processing feed {feed['url']}: {e}")
            
            # Check RSS feeds every 5 minutes
            await asyncio.sleep(300) 
            
        except Exception as e:
            print(f"RSS Scheduler Error: {e}")
            await asyncio.sleep(60)
