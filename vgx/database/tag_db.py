from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["NotifyDB"]
users = db.users

async def get_user_settings(user_id):
    user = await users.find_one({"user_id": user_id})
    if not user:
        # Default settings
        return {"mode": "complete", "muted": False}
    return user

async def update_setting(user_id, key, value):
    await users.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)
