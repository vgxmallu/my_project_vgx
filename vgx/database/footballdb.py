from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

# Collections
users_col = db.users
groups_col = db.group_settings
targets_col = db.target_groups
cache_col = db.api_cache

# --- USER MANAGEMENT ---
async def save_user(user_id: int, username: str):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "last_active": datetime.utcnow()}},
        upsert=True
    )

# --- TARGET GROUPS & SETTINGS ---
async def get_group_settings(chat_id: int) -> dict:
    default_settings = {
        "chat_id": chat_id,
        "auto_delete": 0,          # 0 = Off, 30, 300, 400, 2400 seconds
        "pin_messages": False,     # True / False
        "live_schedule": 0,        # 0 = Off, 60 (1m), 300 (5m), 1200 (20m), 1800 (30m), 3600 (1h)
        "last_live_run": datetime.utcnow() - timedelta(days=1),
        "modules": {
            "live": True,
            "standings": True,
            "topscorers": True,
            "predict": True,
            "lineup": True,
            "injuries": True,
            "h2h": True
        }
    }
    data = await groups_col.find_one({"chat_id": chat_id})
    if not data:
        await groups_col.insert_one(default_settings)
        return default_settings
    return data

async def update_group_setting(chat_id: int, key: str, value):
    await groups_col.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)

async def toggle_group_module(chat_id: int, module_name: str) -> bool:
    settings = await get_group_settings(chat_id)
    current = settings["modules"].get(module_name, True)
    new_state = not current
    await groups_col.update_one(
        {"chat_id": chat_id},
        {"$set": {f"modules.{module_name}": new_state}},
        upsert=True
    )
    return new_state

async def set_user_active_target(user_id: int, target_chat_id: int, chat_title: str = "Group"):
    await targets_col.update_one(
        {"user_id": user_id},
        {"$set": {"active_target": target_chat_id, "title": chat_title}},
        upsert=True
    )

async def get_user_active_target(user_id: int):
    doc = await targets_col.find_one({"user_id": user_id})
    return doc.get("active_target") if doc else None

# --- API RESPONSE CACHING ---
async def get_cached_api(cache_key: str):
    record = await cache_col.find_one({"_id": cache_key})
    if record and record['expires_at'] > datetime.utcnow():
        return record['data']
    return None

async def set_cached_api(cache_key: str, data: dict, ttl_seconds: int = 1800):
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    await cache_col.update_one(
        {"_id": cache_key},
        {"$set": {"data": data, "expires_at": expires_at}},
        upsert=True
    )
