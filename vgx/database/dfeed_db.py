from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import time

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["drip_feed"]

# Collections
queue = db.queue
settings = db.settings

async def add_to_queue(chat_id, file_id, file_type, caption):
    await queue.insert_one({
        "chat_id": chat_id,
        "file_id": file_id,
        "file_type": file_type,
        "caption": caption,
        "created_at": time.time()
    })

async def get_next_item(chat_id):
    # Get the oldest item in the queue
    item = await queue.find_one_and_delete({"chat_id": chat_id}, sort=[("created_at", 1)])
    return item

async def get_chat_settings(chat_id):
    doc = await settings.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "interval": Config.DEFAULT_INTERVAL,
            "last_drip_time": 0,
            "last_msg_id": None,
            "is_active": False
        }
        await settings.insert_one(doc)
    return doc

async def update_settings(chat_id, data):
    await settings.update_one({"chat_id": chat_id}, {"$set": data}, upsert=True)
