from vgx.database.anlys_db import traffic, get_hourly_avg
import time

async def get_golden_hour(chat_id):
    # Find the hour with highest historical activity
    cursor = traffic.find({"chat_id": chat_id}).sort("count", -1).limit(1)
    result = await cursor.to_list(length=1)
    return result[0]["hour"] if result else 9 # Default to 9 AM if no data

async def is_viral_moment(chat_id, current_msgs_last_5_min):
    # 1. Get average for this current hour
    hour = time.localtime().tm_hour
    historical_total = await get_hourly_avg(chat_id, hour)
    
    # Assume historical_total is total over 7 days.
    # Avg per 5 mins = (Total / 7 days) / (60/5 slots)
    # Simplified Logic:
    expected_rate = (historical_total / 7) / 12 
    
    # Avoid div by zero or low data noise
    if expected_rate < 5: return False 

    # 2. Compare
    if current_msgs_last_5_min > (expected_rate * 1.5):
        return True
    return False
