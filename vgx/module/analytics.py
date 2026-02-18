from vgx.database.msg_anlyz_db import traffic, db
import time

async def get_golden_hour(chat_id):
    # Finds the hour with the highest aggregate message count
    cursor = traffic.find({"chat_id": chat_id}).sort("count", -1).limit(1)
    result = await cursor.to_list(length=1)
    return result[0]["hour"] if result else 0

async def detect_viral_spike(chat_id, current_count_last_min):
    # Logic: If current activity > 50% of the average activity for this hour
    stats = await traffic.find_one({"chat_id": chat_id, "hour": time.localtime().tm_hour})
    if not stats: return False
    
    # Simple average calculation (assuming 7 days of data)
    hourly_avg_per_min = (stats["count"] / 7) / 60 
    if current_count_last_min > (hourly_avg_per_min * 1.5):
        return True
    return False
