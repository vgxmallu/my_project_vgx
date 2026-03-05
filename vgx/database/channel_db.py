from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from bson.objectid import ObjectId

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["ChannelManagerDB"]

channels_col = db["channels"]
posts_col = db["live_posts"]

# --- Channel Management ---
async def save_channel(chat_id: int, title: str, owner_id: int):
    await channels_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"title": title, "owner_id": owner_id, "default_reactions": ["👍", "❤️", "😂"]}},
        upsert=True
    )

async def get_user_channels(user_id: int):
    return await channels_col.find({"owner_id": user_id}).to_list(length=None)

# --- Live Post Reactions ---
async def create_live_post(chat_id: int, message_id: int, reactions: list) -> str:
    """Creates a database entry to track who clicks which emoji."""
    reaction_dict = {emoji: [] for emoji in reactions} # Example: {"👍": [], "❤️": []}
    post = await posts_col.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "reactions": reaction_dict
    })
    return str(post.inserted_id)

async def get_live_post(post_id: str):
    return await posts_col.find_one({"_id": ObjectId(post_id)})

async def update_reaction(post_id: str, emoji: str, user_id: int):
    post = await get_live_post(post_id)
    if not post: return None
    
    current_users = post["reactions"].get(emoji, [])
    
    # Toggle logic: If user already clicked it, remove them. If not, add them.
    if user_id in current_users:
        current_users.remove(user_id)
    else:
        current_users.append(user_id)
        
    await posts_col.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {f"reactions.{emoji}": current_users}}
    )
    return await get_live_post(post_id) # Return updated post
