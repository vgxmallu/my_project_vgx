from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["night_mod"]
chats = db.chats

async def get_chat(chat_id):
    doc = await chats.find_one({"chat_id": chat_id})
    if not doc:
        default_doc = {
            "chat_id": chat_id,
            "enabled": False,
            "timezone": "UTC",
            "night_start": "23:45",
            "night_end": "06:00",
            # Permissions Config (True = Allowed during night, False = Blocked)
            "perms": {
                "text": False,      # Strict mode: No text
                "media": False,     # No photos/videos
                "stickers": False,  # No stickers/GIFs
                "links": False      # No embeds
            },
            "vips": [],             # List of User IDs
            "warning": True,        # 5-min warning
            "auto_clean": True,     # Delete open/close alerts
            "last_alert_id": None,  # To track message for deletion
            "temp_unlock": False,   # Emergency override
            "is_night": False       # Current State
        }
        await chats.insert_one(default_doc)
        return default_doc
    return doc

async def update_chat(chat_id, data):
    await chats.update_one({"chat_id": chat_id}, {"$set": data})

async def add_vip(chat_id, user_id):
    await chats.update_one({"chat_id": chat_id}, {"$addToSet": {"vips": user_id}})

async def remove_vip(chat_id, user_id):
    await chats.update_one({"chat_id": chat_id}, {"$pull": {"vips": user_id}})
