from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["DeezerBotDB"]
settings_col = db["group_settings"]

async def get_settings(chat_id: int) -> dict:
    s = await settings_col.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 60,       # Default: 60 minutes
            "pin": False,         # Default: No pinning
            "next_send_time": datetime.utcnow()
        }
        await settings_col.insert_one(s)
    return s

async def update_settings(chat_id: int, **kwargs):
    await settings_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_ready_groups(now: datetime):
    """Fetches groups that are enabled AND their scheduled time has arrived."""
    return await settings_col.find({
        "enabled": True, 
        "next_send_time": {"$lte": now}
    }).to_list(length=None)
