from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import time

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["GoldenHour_DB"]
chats = db.chats

async def get_chat_data(chat_id):
    chat = await chats.find_one({"chat_id": chat_id})
    return chat or {
        "chat_id": chat_id,
        "enabled": False,
        "interval": 60,      # Default 1h (in minutes)
        "delete_after": 0,   # 0 means disabled
        "pin": False,
        "last_msg_id": None,
        "last_sent": 0
    }

async def update_chat(chat_id, **kwargs):
    await chats.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_all_active_chats():
    return chats.find({"enabled": True})

