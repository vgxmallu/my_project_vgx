from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["SpotifyProDB"]

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
            "last_sent": datetime.utcnow() - timedelta(days=1) # Forces immediate send when enabled
        }
        await spoti_settings.insert_one(s)
    return s

async def update_settings(chat_id: int, **kwargs):
    await spoti_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_active_groups():
    """Fetches all groups where the module is turned ON."""
    return await spoti_settings.find({"enabled": True}).to_list(length=None)

# --- Crash-Proof Delete Queue ---
async def add_to_delete_queue(chat_id: int, message_id: int, delay_seconds: int):
    delete_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    await delete_queue.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "delete_at": delete_at
    })

async def get_expired_deletes(now: datetime):
    """Finds messages whose delete timers have popped."""
    return await delete_queue.find({"delete_at": {"$lte": now}}).to_list(length=None)

async def remove_from_queue(doc_id):
    await delete_queue.delete_one({"_id": doc_id})
