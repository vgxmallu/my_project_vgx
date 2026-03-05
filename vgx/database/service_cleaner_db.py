from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["ServiceCleanerDB"]
cleaner_col = db["cleaner_settings"]

async def get_cleaner_settings(chat_id: int) -> dict:
    """Fetch group cleaner settings or return default template."""
    settings = await cleaner_col.find_one({"chat_id": chat_id})
    if not settings:
        return {
            "chat_id": chat_id,
            "del_joins": False,   # Delete "User joined"
            "del_leaves": False,  # Delete "User left"
            "del_vc": False,      # Delete "Voice chat started/ended"
            "del_pins": False,    # Delete "Message pinned"
            "del_info": False     # Delete "Group photo/title changed"
        }
    return settings

async def update_cleaner_settings(chat_id: int, **kwargs):
    """Update specific cleaner settings for a group."""
    await cleaner_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)
