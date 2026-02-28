
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["NotifierDB"]
users = db.users

async def register_user(user_id, username):
    # Default settings: mode=complete, muted=False
    await users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {"mode": "complete", "muted": False},
         "$set": {"username": username.lower() if username else None}},
        upsert=True
    )

async def get_user_settings(user_id):
    return await users.find_one({"user_id": user_id})

async def get_user_by_username(username):
    return await users.find_one({"username": username.lower()})

async def update_setting(user_id, key, value):
    await users.update_one({"user_id": user_id}, {"$set": {key: value}})
