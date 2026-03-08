from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["AutoModDB"]

mod_settings = db["mod_settings"]
mod_stats = db["mod_stats"]

# --- Settings ---
async def get_mod_settings(chat_id: int) -> dict:
    s = await mod_settings.find_one({"chat_id": chat_id})
    return s or {"chat_id": chat_id, "enabled": False}

async def update_mod_settings(chat_id: int, **kwargs):
    await mod_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_all_enabled_groups():
    return await mod_settings.find({"enabled": True}).to_list(length=None)

# --- Stats Engine ---
async def increment_stat(chat_id: int, warns=0, deleted=0, muted=0, decayed=0):
    """Adds numbers to the weekly counters."""
    await mod_stats.update_one(
        {"chat_id": chat_id},
        {"$inc": {
            "warns_issued": warns,
            "msgs_deleted": deleted,
            "users_muted": muted,
            "warns_decayed": decayed
        }},
        upsert=True
    )

async def pop_weekly_stats(chat_id: int) -> dict:
    """Fetches the current stats and resets them to zero for the new week."""
    stats = await mod_stats.find_one_and_delete({"chat_id": chat_id})
    if not stats:
        return {"warns_issued": 0, "msgs_deleted": 0, "users_muted": 0, "warns_decayed": 0}
    return stats
