from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta



client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

async def save_user(user_id: int, username: str):
    """Registers or updates active users in MongoDB."""
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "last_active": datetime.utcnow()}},
        upsert=True
    )

async def get_cached_api(cache_key: str):
    """Retrieves cached API JSON data if not expired."""
    record = await db.api_cache.find_one({"_id": cache_key})
    if record and record['expires_at'] > datetime.utcnow():
        return record['data']
    return None

async def set_cached_api(cache_key: str, data: dict, ttl_seconds: int = 1800):
    """Caches API data with a Time-To-Live (TTL)."""
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    await db.api_cache.update_one(
        {"_id": cache_key},
        {"$set": {"data": data, "expires_at": expires_at}},
        upsert=True
    )
