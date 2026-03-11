from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["SpotifyBotDB"]
spoti_settings = db["spoti_settings"]

async def get_spoti_settings(chat_id: int) -> dict:
    s = await spoti_settings.find_one({"chat_id": chat_id})
    return s or {"chat_id": chat_id, "enabled": False}

async def update_spoti_settings(chat_id: int, **kwargs):
    await spoti_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_all_enabled_groups():
    return await spoti_settings.find({"enabled": True}).to_list(length=None)
