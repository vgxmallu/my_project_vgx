from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["RSSBot_DB"]
feeds_col = db["feeds"]

async def add_feed(chat_id: int, url: str):
    feed_doc = {
        "chat_id": chat_id,
        "url": url,
        "enabled": True,
        "format": "Markdown", # "Markdown" or "HTML"
        "template": "**{{title}}**\n\n{{content}}\n\n[Read more...]({{link}})",
        "link_preview": True,
        "send_images": True,
        "silent_notification": False,
        "posted_guids": [] # Cache
    }
    await feeds_col.insert_one(feed_doc)

async def get_feeds(chat_id: int = None):
    if chat_id:
        return await feeds_col.find({"chat_id": chat_id}).to_list(length=None)
    return await feeds_col.find({"enabled": True}).to_list(length=None)

async def update_feed(feed_id, **kwargs):
    await feeds_col.update_one({"_id": feed_id}, {"$set": kwargs})

async def add_to_cache(feed_id, guid: str):
    # Add to cache and keep only the last 100 entries to save database space
    await feeds_col.update_one(
        {"_id": feed_id},
        {"$push": {"posted_guids": {"$each": [guid], "$slice": -100}}}
    )

async def clear_cache(feed_id):
    await feeds_col.update_one({"_id": feed_id}, {"$set": {"posted_guids": []}})
