from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["NightwatchDB"]

nw_settings = db["nightwatch_settings"]

async def get_nw_settings(chat_id: int) -> dict:
    s = await nw_settings.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "current_mode": "lenient" # "lenient" or "strict"
        }
        await nw_settings.insert_one(s)
    return s

async def update_nw_settings(chat_id: int, **kwargs):
    await nw_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_all_enabled_groups():
    return await nw_settings.find({"enabled": True}).to_list(length=None)

async def set_global_mode(mode: str):
    """Updates the mode for ALL enabled groups at once when the time shifts."""
    await nw_settings.update_many({"enabled": True}, {"$set": {"current_mode": mode}})
