import time
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["GoldenQuotesDB"]
chats_col = db["chat_settings"]

async def get_chat(chat_id: int) -> dict:
    """Fetch settings for a chat, or return defaults."""
    chat = await chats_col.find_one({"chat_id": chat_id})
    if not chat:
        return {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 60,      # Default 60 minutes
            "delete_after": 0,   # Default 0 (Disabled)
            "pin": False,
            "last_msg_id": None,
            "last_sent": 0
        }
    return chat

async def update_chat(chat_id: int, **kwargs):
    """Update specific settings for a chat."""
    await chats_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_due_chats() -> list:
    """Finds all active chats where the time interval has passed."""
    now = int(time.time())
    active_chats = chats_col.find({"enabled": True})
    due_chats = []
    
    async for chat in active_chats:
        interval_seconds = chat.get("interval", 60) * 60
        if now - chat.get("last_sent", 0) >= interval_seconds:
            due_chats.append(chat)
            
    return due_chats
