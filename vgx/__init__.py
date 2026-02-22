import asyncio
import feedparser
import os
from pyrogram import Client
from pyrogram.enums import ParseMode
from vgx.database.rss_db import Database
from vgx.module.rssf_formatter import format_post

from config import Config

class app(Client):
    def __init__(self):
        super().__init__(
            "rss_bot_session",
            api_id=int(os.getenv("API_ID")),
            api_hash=os.getenv("API_HASH"),
            bot_token=os.getenv("BOT_TOKEN"),
            plugins=dict(root="vgx")
        )
        self.db = Database(os.getenv(Config.MONGO_URL), os.getenv("rss_fdb"))
        self.worker_task = None
        # In-memory dictionary to track user states (e.g. waiting for new template)
        self.user_states = {} 

    async def start(self):
        await super().start()
        print("🚀 Bot initialized.")
        self.worker_task = asyncio.create_task(self._rss_worker())

    async def stop(self, *args):
        if self.worker_task:
            self.worker_task.cancel()
        print("🛑 Shutting down...")
        await super().stop(*args)

    async def _rss_worker(self):
        print("📡 Background RSS Worker started.")
        await asyncio.sleep(5)
        
        while True:
            try:
                feeds = await self.db.get_active_feeds()
                for feed in feeds:
                    feed_id = str(feed["_id"])
                    chat_id = feed["chat_id"]
                    
                    parsed = feedparser.parse(feed["feed_url"])
                    cache = feed.get("posted_entries", [])
                    
                    # Premium features: Fetch chat info natively
                    try:
                        chat_info = await self.get_chat(chat_id)
                    except Exception:
                        chat_info = None

                    feed_info = {"title": parsed.feed.get("title", "Feed"), "link": parsed.feed.get("link", "")}

                    for entry in reversed(parsed.entries):
                        entry_id = entry.get("id", entry.get("link", ""))
                        
                        if entry_id not in cache:
                            text, image_url = format_post(feed["template"], entry, chat_info, feed_info)
                            p_mode = ParseMode.HTML if feed["parse_mode"] == "html" else ParseMode.MARKDOWN
                            
                            try:
                                # If images enabled and image exists, send as photo
                                if feed["images_enabled"] and image_url:
                                    await self.send_photo(
                                        chat_id=chat_id,
                                        photo=image_url,
                                        caption=text[:1024], # Captions have a strict 1024 char limit
                                        parse_mode=p_mode,
                                        disable_notification=not feed["notifications_enabled"]
                                    )
                                else:
                                    # Send as text message
                                    await self.send_message(
                                        chat_id=chat_id,
                                        text=text,
                                        parse_mode=p_mode,
                                        disable_web_page_preview=not feed["preview_enabled"],
                                        disable_notification=not feed["notifications_enabled"]
                                    )
                                await self.db.cache_entry(feed_id, entry_id)
                                await asyncio.sleep(3) # Anti-flood
                            except Exception as e:
                                print(f"Post failed for {chat_id}: {e}")
            except Exception as e:
                print(f"Worker Error: {e}")
                
            await asyncio.sleep(300) # Check every 5 mins
