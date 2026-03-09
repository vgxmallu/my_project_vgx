from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["HealthPingDB"]

system_settings = db["system_settings"]

async def get_log_channel() -> dict:
    """Fetches the current log settings."""
    s = await system_settings.find_one({"_id": "health_config"})
    if not s:
        s = {
            "_id": "health_config",
            "log_channel_id": None,
            "ping_enabled": False
        }
        await system_settings.insert_one(s)
    return s

async def update_log_channel(log_channel_id: int = None, ping_enabled: bool = None):
    """Updates the target channel or toggles the ping on/off."""
    update_data = {}
    if log_channel_id is not None:
        update_data["log_channel_id"] = log_channel_id
    if ping_enabled is not None:
        update_data["ping_enabled"] = ping_enabled
        
    if update_data:
        await system_settings.update_one(
            {"_id": "health_config"}, 
            {"$set": update_data}, 
            upsert=True
        )
