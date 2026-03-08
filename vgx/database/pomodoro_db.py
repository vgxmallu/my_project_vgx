from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["PomodoroDB"]

settings_col = db["pomo_settings"]
sprints_col = db["active_sprints"]

# --- Settings Management ---
async def get_pomo_settings(chat_id: int) -> dict:
    settings = await settings_col.find_one({"chat_id": chat_id})
    return settings or {"chat_id": chat_id, "enabled": False}

async def update_pomo_settings(chat_id: int, enabled: bool):
    await settings_col.update_one(
        {"chat_id": chat_id}, 
        {"$set": {"enabled": enabled}}, 
        upsert=True
    )

# --- Sprint Management ---
async def start_sprint_db(chat_id: int, duration_minutes: int):
    unlock_time = datetime.utcnow() + timedelta(minutes=duration_minutes)
    await sprints_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"unlock_time": unlock_time}},
        upsert=True
    )

async def get_expired_sprints(now: datetime):
    return await sprints_col.find({"unlock_time": {"$lte": now}}).to_list(length=None)

async def remove_sprint(chat_id: int):
    await sprints_col.delete_one({"chat_id": chat_id})
