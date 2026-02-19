from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import time

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["analysis_db"]

traffic = db.traffic_stats   # Stores hourly activity
profiles = db.profiles       # Stores user stats
promos = db.promos           # Stores the viral promo message

async def track_message(chat_id, user_id, name):
    # 1. Update User Profile
    await profiles.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$inc": {"messages": 1},
            "$set": {"name": name, "last_active": time.time()}
        },
        upsert=True
    )
    
    # 2. Update Hourly Traffic Stat (0-23)
    current_hour = time.localtime().tm_hour
    await traffic.update_one(
        {"chat_id": chat_id, "hour": current_hour},
        {"$inc": {"count": 1, "total_samples": 1}}, # total_samples tracks days
        upsert=True
    )

async def get_top_users(chat_id, limit=10):
    return await profiles.find({"chat_id": chat_id}).sort("messages", -1).limit(limit).to_list(length=limit)

async def get_hourly_avg(chat_id, hour):
    doc = await traffic.find_one({"chat_id": chat_id, "hour": hour})
    if not doc: return 0
    # Average = Total Messages in this hour slot / Total Days tracked
    # (Simplified: using raw count for now, but ideal is count / days)
    # Here we return raw count to compare against "average" baseline logic
    return doc.get("count", 0)
