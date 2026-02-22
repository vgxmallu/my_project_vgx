from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId

class Database:
    def __init__(self, uri, db_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.feeds = self.db.feeds

    async def add_source(self, chat_id: int, feed_url: str):
        default_data = {
            "chat_id": chat_id,
            "feed_url": feed_url,
            "is_active": True,
            "template": "<b>{{title}}</b>\n\n{{content}}\n\n<a href='{{link}}'>Read more...</a>",
            "parse_mode": "html",
            "preview_enabled": True,
            "images_enabled": True,
            "notifications_enabled": True,
            "posted_entries": []
        }
        await self.feeds.update_one(
            {"chat_id": chat_id, "feed_url": feed_url},
            {"$setOnInsert": default_data},
            upsert=True
        )

    async def get_active_feeds(self):
        return await self.feeds.find({"is_active": True}).to_list(length=None)

    async def get_chat_feeds(self, chat_id: int):
        return await self.feeds.find({"chat_id": chat_id}).to_list(length=None)

    async def get_feed(self, feed_id: str):
        return await self.feeds.find_one({"_id": ObjectId(feed_id)})

    async def update_setting(self, feed_id: str, key: str, value):
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$set": {key: value}})

    async def cache_entry(self, feed_id: str, entry_id: str):
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$push": {"posted_entries": entry_id}})
        
    async def clear_cache(self, feed_id: str):
        await self.feeds.update_one({"_id": ObjectId(feed_id)}, {"$set": {"posted_entries": []}})
