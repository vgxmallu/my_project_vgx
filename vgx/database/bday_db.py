from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["BirthdayBotDB"]

users = db.users
chats = db.chats

async def get_chat_settings(chat_id):
    doc = await chats.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "bday_msg": "🎂 Happy Bday {mention}!",
            "bday_role": "Birthday King/Queen",
            "trusted_users": [], # List of user IDs
            "events": [], # [{ "name": "NewYear", "date": "01-01", "msg": "..." }]
            "server_anniversary": None # { "date": "08-15", "msg": "..." }
        }
        await chats.insert_one(doc)
    return doc

async def set_user_birthday(user_id, chat_id, dob, timezone="UTC"):
    await users.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"dob": dob, "tz": timezone, "join_date": datetime.now().strftime("%m-%d")}},
        upsert=True
    )
