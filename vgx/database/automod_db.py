from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["AdvancedAutoMod"]

warn_settings = db["warn_settings"]
user_warns = db["user_warns"]
mod_stats = db["mod_stats"]

# --- Group Settings ---
async def get_warn_settings(chat_id: int) -> dict:
    s = await warn_settings.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "punishment": "ban", # off, kick, mute, ban
            "max_warns": 4
        }
        await warn_settings.insert_one(s)
    return s

async def update_warn_settings(chat_id: int, **kwargs):
    await warn_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

# --- User Warning Tracker ---
async def add_user_warn(chat_id: int, user_id: int) -> int:
    """Adds a warning and returns the new total warning count."""
    doc = await user_warns.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"warns": 1}},
        upsert=True,
        return_document=True
    )
    return doc["warns"]

async def reset_user_warns(chat_id: int, user_id: int):
    await user_warns.delete_one({"chat_id": chat_id, "user_id": user_id})

# --- Weekly Stats Engine ---
async def increment_stat(chat_id: int, warns=0, deleted=0, muted=0, banned=0, decayed=0):
    await mod_stats.update_one(
        {"chat_id": chat_id},
        {"$inc": {
            "warns_issued": warns,
            "msgs_deleted": deleted,
            "users_muted": muted,
            "users_banned": banned,
            "warns_decayed": decayed
        }},
        upsert=True
    )

async def pop_weekly_stats(chat_id: int) -> dict:
    stats = await mod_stats.find_one_and_delete({"chat_id": chat_id})
    if not stats:
        return {"warns_issued": 0, "msgs_deleted": 0, "users_muted": 0, "users_banned": 0, "warns_decayed": 0}
    return stats

async def get_all_enabled_groups():
    return await warn_settings.find({"enabled": True}).to_list(length=None)
