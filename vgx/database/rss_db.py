from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client["rssfeed_db"]
        self.feeds = self.db.feeds

    async def add_feed(self, chat_id: int, feed_url: str):
        feed_data = {
            "chat_id": chat_id,
            "feed_url": feed_url,
            "is_active": True,
            "template": "<b>{{title}}</b>\n\n{{content}}\n\n<a href='{{link}}'>Read more...</a>",
            "parse_mode": "html",
            "preview_enabled": True,
            "images_enabled": True,
            "notifications_enabled": True,
            "posted_entries": [] # Cache
        }
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$setOnInsert": feed_data},
            upsert=True
        )

    async def get_all_active_feeds(self):
        cursor = self.feeds.find({"is_active": True})
        return await cursor.to_list(length=None)

    async def get_chat_feeds(self, chat_id: int):
        cursor = self.feeds.find({"chat_id": chat_id})
        return await cursor.to_list(length=None)

    async def get_feed(self, feed_id: str):
        from bson.objectid import ObjectId
        return await self.feeds.find_one({"_id": ObjectId(feed_id)})

    async def update_setting(self, feed_id: str, key: str, value):
        from bson.objectid import ObjectId
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$set": {key: value}})

    async def add_to_cache(self, feed_id: str, entry_id: str):
        from bson.objectid import ObjectId
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$push": {"posted_entries": entry_id}})

    async def clear_cache(self, feed_id: str):
        from bson.objectid import ObjectId
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$set": {"posted_entries": []}})

    async def delete_feed(self, feed_id: str):
        from bson.objectid import ObjectId
        await self.feeds.delete_one({"_id": ObjectId(feed_id)})

db = Database()
