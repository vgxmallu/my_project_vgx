from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["ChannelManagerDB"]
users_col = db["users"]
channels_col = db["channels"]
posts_col = db["posts"]

# --- User Data ---
async def get_user(user_id: int) -> dict:
    user = await users_col.find_one({"user_id": user_id})
    return user or {"user_id": user_id, "timezone": "UTC", "is_plus": False}

async def update_user(user_id: int, **kwargs):
    await users_col.update_one({"user_id": user_id}, {"$set": kwargs}, upsert=True)

# --- Channel Data ---
async def get_channel(chat_id: int) -> dict:
    channel = await channels_col.find_one({"chat_id": chat_id})
    return channel or {
        "chat_id": chat_id,
        "signature": "",
        "default_reactions": ["👍", "👎"],
        "auto_complete_text": "",
        "del_service_msgs": False,
        "leave_ban_time": 0, # 0 = no ban
        "group_ban": False,
        "forward_targets": [] # Requires PLUS
    }

async def update_channel(chat_id: int, **kwargs):
    await channels_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)
    
async def get_user_channels(user_id: int, client) -> list:
    """Helper to find which channels a user is admin of (requires bot to be in them)"""
    # In a real bot, you'd save channels to the DB when the bot is added as admin.
    # For now, we query the DB for any channel linked to this user.
    cursor = channels_col.find({"owner_id": user_id})
    return await cursor.to_list(length=None)
