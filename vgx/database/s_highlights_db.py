from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client[Config.DB_NAME]

groups_col = db.group_settings
targets_col = db.target_groups
cache_col = db.api_cache

# --- GROUP SETTINGS ---
async def get_group_settings(chat_id: int) -> dict:
    default_settings = {
        "chat_id": chat_id,
        "auto_delete": 0,         # 0, 30, 300, 400, 2400
        "pin_messages": False,
        "live_schedule": 0,       # 0, 60, 300, 1200, 1800, 3600
        "last_live_run": datetime.utcnow() - timedelta(days=1),
        "modules": {sport: True for sport in Config.SPORTS}
    }
    default_settings["modules"].update({"highlights": True, "odds": True, "h2h": True})
    
    data = await groups_col.find_one({"chat_id": chat_id})
    if not data:
        await groups_col.insert_one(default_settings)
        return default_settings
    return data

async def update_group_setting(chat_id: int, key: str, value):
    await groups_col.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)

async def toggle_group_module(chat_id: int, module_name: str) -> bool:
    settings = await get_group_settings(chat_id)
    new_state = not settings["modules"].get(module_name, True)
    await groups_col.update_one(
        {"chat_id": chat_id}, {"$set": {f"modules.{module_name}": new_state}}, upsert=True
    )
    return new_state

# --- TARGET MANAGEMENT ---
async def set_user_target(user_id: int, target_chat_id: int):
    await targets_col.update_one({"user_id": user_id}, {"$set": {"active_target": target_chat_id}}, upsert=True)

async def get_user_target(user_id: int):
    doc = await targets_col.find_one({"user_id": user_id})
    return doc.get("active_target") if doc else None

async def clear_user_target(user_id: int):
    await targets_col.update_one({"user_id": user_id}, {"$unset": {"active_target": ""}})

# --- API CACHING ---
async def get_cached_api(cache_key: str):
    record = await cache_col.find_one({"_id": cache_key})
    if record and record['expires_at'] > datetime.utcnow():
        return record['data']
    return None

async def set_cached_api(cache_key: str, data: dict, ttl_seconds: int = 300):
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    await cache_col.update_one({"_id": cache_key}, {"$set": {"data": data, "expires_at": expires_at}}, upsert=True)
