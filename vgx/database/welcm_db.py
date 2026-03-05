from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["WelcomeBotDB"]
greetings_col = db["greetings_settings"]

async def get_group_greetings(chat_id: int) -> dict:
    """Fetch group settings or return default template."""
    settings = await greetings_col.find_one({"chat_id": chat_id})
    if not settings:
        return {
            "chat_id": chat_id,
            "welcome_enabled": False,
            "leave_enabled": False,
            "welcome_text": "Hey {{first_name}}❤️, welcome to {{group}} 🥳\nYou are member #{{count}}!",
            "leave_text": "Goodbye {{first_name}}, we will miss you! 😢"
        }
    return settings

async def update_group_greetings(chat_id: int, **kwargs):
    """Update specific greeting settings for a group."""
    await greetings_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)
