from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["BirthdayBot_DB"]
users_col = db["users"]
groups_col = db["groups"]

# --- User Database ---
async def set_user_bday(user_id: int, month: int, day: int, timezone: str):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"month": month, "day": day, "timezone": timezone}},
        upsert=True
    )

async def get_users_by_bday_and_tz(month: int, day: int, timezone: str):
    """Finds all users born on a specific day in a specific timezone."""
    cursor = users_col.find({"month": month, "day": day, "timezone": timezone})
    return await cursor.to_list(length=None)

# --- Group Database ---
async def get_group(chat_id: int) -> dict:
    group = await groups_col.find_one({"chat_id": chat_id})
    return group or {
        "chat_id": chat_id,
        "enabled": False,
        "custom_msg": "🎉 Happy Birthday {mention}! We hope you have a fantastic day! 🎂",
        "media_id": None,      # Stores Telegram file_id for GIFs/Photos
        "trusted_only": False, # Simulates Discord's "Trusted Role"
        "trusted_users": []    # List of user_ids allowed to be celebrated
    }

async def update_group(chat_id: int, **kwargs):
    await groups_col.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)
    
async def add_trusted_user(chat_id: int, user_id: int):
    await groups_col.update_one({"chat_id": chat_id}, {"$addToSet": {"trusted_users": user_id}}, upsert=True)
