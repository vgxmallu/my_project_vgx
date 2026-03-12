from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["WeatherBotDB"]
weather_col = db["weather_settings"]

async def get_weather_settings(chat_id: int) -> dict:
    s = await weather_col.find_one({"chat_id": chat_id})
    if not s:
        s = {
            "chat_id": chat_id,
            "enabled": False,
            "city": "Thalassery",   # Default city!
            "hour": 7,              # Default time: 07:00 (7 AM)
            "pin": False,           # Auto-Pin Disabled by default
            "last_sent_date": ""    # Format: "YYYY-MM-DD"
        }
        await weather_col.insert_one(s)
    return s

async def update_weather_settings(chat_id: int, **kwargs):
    await weather_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)

async def get_groups_due_for_weather(current_hour: int, today_str: str):
    """Fetches groups where it is the correct hour, and they haven't received it today."""
    return await weather_col.find({
        "enabled": True,
        "hour": current_hour,
        "last_sent_date": {"$ne": today_str}
    }).to_list(length=None)
