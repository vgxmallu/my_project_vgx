import uuid
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["UltimateEventsDB"]

settings_col = db["group_settings"]
users_col = db["users"]
events_col = db["events"]

# --- Group Settings ---
async def get_event_settings(chat_id: int) -> dict:
    s = await settings_col.find_one({"chat_id": chat_id})
    return s or {"chat_id": chat_id, "enabled": False}

async def update_event_settings(chat_id: int, enabled: bool):
    await settings_col.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)

# --- Users (Economy & Strikes) ---
async def get_user(user_id: int) -> dict:
    u = await users_col.find_one({"user_id": user_id})
    if not u:
        # Default: 1000 coins, 0 strikes, UTC timezone
        u = {"user_id": user_id, "coins": 1000, "strikes": 0, "tz_offset": 0.0}
        await users_col.insert_one(u)
    return u

async def alter_coins(user_id: int, amount: int) -> bool:
    u = await get_user(user_id)
    if u["coins"] + amount < 0:
        return False
    await users_col.update_one({"user_id": user_id}, {"$inc": {"coins": amount}})
    return True

async def add_strike(user_id: int):
    await users_col.update_one({"user_id": user_id}, {"$inc": {"strikes": 1}}, upsert=True)

# --- Event Management ---
async def create_event(chat_id: int, title: str, start_time: datetime, capacity: int, cost: int, event_type: str, metadata: dict = None) -> str:
    event_id = str(uuid.uuid4())[:8]
    doc = {
        "event_id": event_id,
        "chat_id": chat_id,
        "title": title,
        "start_time": start_time,
        "capacity": capacity,
        "cost": cost,
        "event_type": event_type, 
        "metadata": metadata or {}, 
        "attendees": {}, # format: {"user_id_str": {"checked_in": False, "username": "..."}}
        "status": "pending" # pending, active, finished
    }
    await events_col.insert_one(doc)
    return event_id

async def get_event(event_id: str) -> dict:
    return await events_col.find_one({"event_id": event_id})

async def update_event(event_id: str, **kwargs):
    await events_col.update_one({"event_id": event_id}, {"$set": kwargs})
