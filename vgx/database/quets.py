from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["MotivationBot"]
chats = db.chats

async def enable_quotes(chat_id, chat_title, chat_type):
    await chats.update_one(
        {"chat_id": chat_id},
        {"$set": {"title": chat_title, "type": chat_type, "enabled": True}},
        upsert=True
    )

async def disable_quotes(chat_id):
    await chats.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": False}},
        upsert=True
    )

async def is_enabled(chat_id):
    chat = await chats.find_one({"chat_id": chat_id})
    return chat.get("enabled", False) if chat else False

async def get_all_enabled_chats():
    # Returns a cursor for all chats where enabled is True
    return chats.find({"enabled": True})
