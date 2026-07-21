from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta

# Initialize MongoDB connection
client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

async def save_user(user_id: int, username: str):
    """Registers or updates a user in the database."""
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "last_active": datetime.utcnow()}},
        upsert=True
    )

async def get_cache(key: str):
    """Retrieves cached data if it hasn't expired."""
    record = await db.cache.find_one({"_id": key})
    if record and record['expires_at'] > datetime.utcnow():
        return record['data']
    return None

async def set_cache(key: str, data: str, ttl_hours: int = 12):
    """Stores data in the cache with a time-to-live (TTL)."""
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    await db.cache.update_one(
        {"_id": key},
        {"$set": {"data": data, "expires_at": expires_at}},
        upsert=True
    )
