from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["AdvancedWordGuard"]

settings_col = db["guard_settings"]
warns_col = db["user_warns"]

# --- Group Settings & Custom Words ---
async def get_guard_settings(chat_id: int) -> dict:
    s = await settings_col.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "custom_words": [],
            "punishment": "Ban", # Options: "Off", "Kick", "Mute", "Ban"
            "max_warns": 4
        }
        await settings_col.insert_one(s)
    return s

async def update_guard_settings(chat_id: int, **kwargs):
    await settings_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def add_custom_word(chat_id: int, word: str):
    await settings_col.update_one({"chat_id": chat_id}, {"$addToSet": {"custom_words": word.lower()}})

async def remove_custom_word(chat_id: int, word: str):
    await settings_col.update_one({"chat_id": chat_id}, {"$pull": {"custom_words": word.lower()}})

# --- Warning Tracker ---
async def get_user_warns(chat_id: int, user_id: int) -> int:
    doc = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return doc["warns"] if doc else 0

async def add_user_warn(chat_id: int, user_id: int) -> int:
    doc = await warns_col.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"warns": 1}},
        upsert=True,
        return_document=True
    )
    return doc["warns"]

async def reset_user_warns(chat_id: int, user_id: int):
    await warns_col.delete_one({"chat_id": chat_id, "user_id": user_id})
