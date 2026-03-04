from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["GoldenQuotes_db"]
chats = db.chats

async def get_chat_config(chat_id):
    chat = await chats.find_one({"chat_id": chat_id})
    return chat or {
        "chat_id": chat_id,
        "enabled": False,
        "interval": 60,      # In minutes (default 1h)
        "del_str": 0,   # In seconds (0 = off)
        "pin": False,        # Auto-pin state
        "last_msg_id": None, # For the "Delete Last Sent" button
        "last_sent": 0       # Unix timestamp for schedule calculation
    }

async def update_config(chat_id, **kwargs):
    await chats.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_due_chats(current_time):
    all_active = chats.find({"enabled": True})
    due = []
    async for chat in all_active:
        # Check if current time has passed the required interval (converted to seconds)
        if current_time - chat.get("last_sent", 0) >= (chat.get("interval", 60) * 60):
            due.append(chat)
    return due
