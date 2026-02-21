import asyncio
import feedparser
from pyrogram.enums import ParseMode
from database.db import db
from utils.formatter import format_message

async def rss_worker(app):
    await asyncio.sleep(5) # Give the bot time to start
    print("📡 RSS Worker Started.")
    
    while True:
        try:
            active_feeds = await db.get_all_active_feeds()
            
            for feed_data in active_feeds:
                feed_id = str(feed_data["_id"])
                chat_id = feed_data["chat_id"]
                url = feed_data["feed_url"]
                cache = feed_data.get("posted_entries", [])
                
                parsed = feedparser.parse(url)
                
                # Setup mock info objects (In a full bot, fetch real chat info via app.get_chat)
                chat_info = {"title": "Target Chat", "type": "Channel", "description": ""}
                feed_info = {
                    "title": parsed.feed.get("title", "Feed"),
                    "description": parsed.feed.get("description", ""),
                    "link": parsed.feed.get("link", "")
                }

                # Reverse to post oldest unread first
                for entry in reversed(parsed.entries):
                    entry_id = entry.get("id", entry.get("link", ""))
                    
                    if entry_id not in cache:
                        text = format_message(feed_data["template"], entry, chat_info, feed_info)
                        
                        p_mode = ParseMode.HTML if feed_data["parse_mode"] == "html" else ParseMode.MARKDOWN
                        
                        try:
                            await app.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode=p_mode,
                                disable_web_page_preview=not feed_data["preview_enabled"],
                                disable_notification=not feed_data["notifications_enabled"]
                            )
                            # Update DB Cache
                            await db.add_to_cache(feed_id, entry_id)
                            await asyncio.sleep(2) # Flood wait protection
                        except Exception as e:
                            print(f"Failed to post to {chat_id}: {e}")
                            
        except Exception as e:
            print(f"Worker Error: {e}")
            
        await asyncio.sleep(300) # Wait 5 minutes
