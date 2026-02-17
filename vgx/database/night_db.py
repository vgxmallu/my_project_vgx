from motor.motor_asyncio import AsyncIOMotorClient
from config import Config


client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["NightModeBot"]
chats = db["settings"]

async def get_settings(chat_id):
    doc = await chats.find_one({"chat_id": chat_id})
    if not doc:
        return {
            "chat_id": chat_id,
            "enabled": False,
            "night_start": "22:00",
            "night_end": "07:00",
            "timezone": "UTC",
            "night_msg": "🌙 Group is closed for the night.",
            "night_photo": None,
            "morning_msg": "☀️ Good morning! Group is now open.",
            "morning_photo": None,
            "current_state": "morning"
        }
    return doc

async def update_settings(chat_id, data):
    await chats.update_one({"chat_id": chat_id}, {"$set": data}, upsert=True)
