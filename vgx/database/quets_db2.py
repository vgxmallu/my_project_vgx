from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import time


client = AsyncIOMotorClient(Config.MONGO_URI)
db = client["QuotesBot_db"]
collection = db["chat_settings"]

async def get_chat(chat_id: int):
    data = await collection.find_one({"chat_id": chat_id})
    if not data:
        data = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 3600, # Default 1h
            "auto_delete": 0, # Default Off
            "pin": False,
            "last_msg_id": None,
            "last_sent_time": 0
        }
        await collection.insert_one(data)
    return data

async def update_chat(chat_id: int, **kwargs):
    await collection.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_all_active_chats():
    return await collection.find({"enabled": True}).to_list(length=None)
    
