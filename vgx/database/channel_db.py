from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from bson.objectid import ObjectId

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["ChannelManagerDB"]

users_col = db["users"]
channels_col = db["channels"]
posts_col = db["live_posts"]

# --- User Data ---
async def get_user(user_id: int):
    user = await users_col.find_one({"user_id": user_id})
    return user or {"user_id": user_id, "timezone": "UTC", "is_plus": False}

async def update_user(user_id: int, **kwargs):
    await users_col.update_one({"user_id": user_id}, {"$set": kwargs}, upsert=True)

# --- Channel Data ---
async def save_channel(chat_id: int, title: str, owner_id: int):
    await channels_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"title": title, "owner_id": owner_id},
         "$setOnInsert": {
             "signature": "",
             "default_reactions": ["👍", "❤️"],
             "auto_complete": "",
             "welcome_enabled": False,
             "leave_ban": False
         }},
        upsert=True
    )

async def get_channel(chat_id: int):
    return await channels_col.find_one({"chat_id": chat_id})

async def get_user_channels(user_id: int):
    return await channels_col.find({"owner_id": user_id}).to_list(length=None)

async def update_channel(chat_id: int, **kwargs):
    await channels_col.update_one({"chat_id": chat_id}, {"$set": kwargs})

# --- Live Post Tracking ---
async def create_live_post(chat_id: int, message_id: int, emojis: list) -> str:
    reaction_dict = {emoji: [] for emoji in emojis}
    post = await posts_col.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "reactions": reaction_dict
    })
    return str(post.inserted_id)

async def update_reaction(post_id: str, emoji: str, user_id: int):
    post = await posts_col.find_one({"_id": ObjectId(post_id)})
    if not post: return None
    
    current_users = post["reactions"].get(emoji, [])
    if user_id in current_users:
        current_users.remove(user_id) # Toggle OFF
    else:
        current_users.append(user_id) # Toggle ON
        
    await posts_col.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {f"reactions.{emoji}": current_users}}
    )
    return await posts_col.find_one({"_id": ObjectId(post_id)})
