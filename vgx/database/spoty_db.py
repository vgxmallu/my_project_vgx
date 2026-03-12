from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["SpotifyAdvancedDB"]

spoti_settings = db["settings"]
delete_queue = db["delete_queue"]

# --- Group Settings ---
async def get_settings(chat_id: int) -> dict:
    s = await spoti_settings.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 60,       # Custom timer: 1, 5, 20, 30, 60 (minutes)
            "auto_delete": 0,     # 0 = Off. Options: 30, 300, 400, 2400 (seconds)
            "pin": False,         # Enable/Disable Pinning
            "next_send_time": datetime.utcnow() # Ready to send immediately when enabled
        }
        await spoti_settings.insert_one(s)
    return s

async def update_settings(chat_id: int, **kwargs):
    await spoti_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_ready_groups(now: datetime):
    """Fetches groups that are enabled AND whose timer has popped."""
    return await spoti_settings.find({
        "enabled": True, 
        "next_send_time": {"$lte": now}
    }).to_list(length=None)

# --- Crash-Proof Delete Queue ---
async def add_to_delete_queue(chat_id: int, message_id: int, delay_seconds: int):
    delete_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    await delete_queue.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "delete_at": delete_at
    })

async def get_expired_deletes(now: datetime):
    return await delete_queue.find({"delete_at": {"$lte": now}}).to_list(length=None)

async def remove_from_queue(doc_id):
    await delete_queue.delete_one({"_id": doc_id})
