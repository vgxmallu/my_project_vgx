from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client["rss_feed_db"]
        self.feeds = self.db.feeds

    async def add_feed(self, chat_id, feed_url):
        feed_data = {
            "chat_id": chat_id,
            "feed_url": feed_url,
            "is_active": True,
            "template": "<b>{{title}}</b>\n{{content}}\n<a href='{{link}}'>Read more...</a>",
            "parse_mode": "html",
            "preview_enabled": True,
            "images_enabled": True,
            "notifications_enabled": True,
            "posted_entries": [] # Cache of posted guids
        }
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$set": feed_data},
            upsert=True
        )

    async def get_all_active_feeds(self):
        cursor = self.feeds.find({"is_active": True})
        return await cursor.to_list(length=None)

    async def get_chat_feeds(self, chat_id):
        cursor = self.feeds.find({"chat_id": chat_id})
        return await cursor.to_list(length=None)

    async def update_feed_setting(self, chat_id, feed_url, setting_key, setting_value):
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$set": {setting_key: setting_value}}
        )

    async def add_to_cache(self, chat_id, feed_url, entry_id):
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$push": {"posted_entries": entry_id}}
        )

    async def clear_cache(self, chat_id, feed_url):
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$set": {"posted_entries": []}}
        )

db = Database()
