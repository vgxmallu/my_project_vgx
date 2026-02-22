from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["NotifyBot"]
users = db.users

async def get_user_config(user_id):
    user = await users.find_one({"user_id": user_id})
    if not user:
        # Default settings: Complete style, Unmuted
        return {"mode": "complete", "muted": False}
    return user

async def update_config(user_id, key, value):
    await users.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)
