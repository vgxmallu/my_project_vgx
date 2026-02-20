import asyncio
import feedparser
from pyrogram.enums import ParseMode
from vgx.database.rss_db import db
from vgx.lotta.formatter import format_message

async def check_rss_feeds(app):
    while True:
        try:
            active_feeds = await db.get_all_active_feeds()
            for feed_data in active_feeds:
                chat_id = feed_data["chat_id"]
                url = feed_data["feed_url"]
                cache = feed_data.get("posted_entries", [])
                
                # Fetch RSS
                parsed = feedparser.parse(url)
                
                # Mock chat/feed info for premium placeholders
                chat_info = {"title": "My Telegram Chat", "type": "Channel"}
                feed_info = {"title": parsed.feed.get("title", "RSS Feed")}

                # Iterate entries (reversed so oldest unread is posted first)
                for entry in reversed(parsed.entries):
                    entry_id = entry.get("id", entry.get("link", ""))
                    
                    if entry_id not in cache:
                        # Format message
                        text = format_message(feed_data["template"], entry, chat_info, feed_info)
                        
                        parse_mode = ParseMode.HTML if feed_data["parse_mode"] == "html" else ParseMode.MARKDOWN
                        disable_preview = not feed_data["preview_enabled"]
                        disable_notif = not feed_data["notifications_enabled"]

                        try:
                            # Send message
                            await app.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode=parse_mode,
                                disable_web_page_preview=disable_preview,
                                disable_notification=disable_notif
                            )
                            # Update Cache
                            await db.add_to_cache(chat_id, url, entry_id)
                            await asyncio.sleep(2) # Flood wait protection
                        except Exception as e:
                            print(f"Failed to send message to {chat_id}: {e}")
                            
        except Exception as e:
            print(f"Error in RSS Worker loop: {e}")
            
        await asyncio.sleep(300) # Check every 5 minutes
