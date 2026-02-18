from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["AnalyticsBot"]

traffic = db.traffic_stats
profiles = db.profiles
scheduled_jobs = db.scheduled_jobs

async def update_traffic(chat_id, hour):
    # Increments the message count for a specific hour (0-23)
    await traffic.update_one(
        {"chat_id": chat_id, "hour": hour},
        {"$inc": {"count": 1}},
        upsert=True
    )

async def increment_member_stats(chat_id, user_id, name):
    await profiles.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"messages": 1}, "$set": {"name": name}},
        upsert=True
    )
