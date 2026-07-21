from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

users_collection = db["users"]
cache_collection = db["stats_cache"]

async def save_user(user_id: int, username: str):
    """Saves user interactions to MongoDB."""
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "username": username}},
        upsert=True
    )

async def get_cached_data(cache_key: str):
    """Retrieves cached response string from MongoDB."""
    return await cache_collection.find_one({"key": cache_key})

async def set_cached_data(cache_key: str, formatted_data: str):
    """Stores generated response in MongoDB with timestamp."""
    await cache_collection.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": formatted_data}},
        upsert=True
    )
