from pymongo import MongoClient
from config import MONGO_URL
import datetime

client = MongoClient(config.MONGO_URL)
db = client["birthday_bot"]

# Collections
birthdays = db.birthdays
chats = db.chats
events = db.events
member_anniversaries = db.member_anniversaries


def save_birthday(user_id: int, chat_id: int, bday: str, tz: str = "UTC"):
    birthdays.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"birthday": bday, "timezone": tz, "last_celebrated": None}},
        upsert=True
    )

def get_birthday(user_id: int, chat_id: int):
    return birthdays.find_one({"user_id": user_id, "chat_id": chat_id})

def update_last_celebrated(user_id: int, chat_id: int):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    birthdays.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"last_celebrated": today}}
    )

def get_chat_settings(chat_id: int):
    settings = chats.find_one({"chat_id": chat_id}) or {}
    return {
        "birthday_message": settings.get("birthday_message", DEFAULT_BIRTHDAY_MESSAGE),
        "birthday_role": settings.get("birthday_role", DEFAULT_BIRTHDAY_ROLE),
        "trusted_users": settings.get("trusted_users", []),
        "server_anniversary": settings.get("server_anniversary"),
        "server_message": settings.get("server_message", "🎊 Happy Server Anniversary everyone! 🎉")
    }

def save_chat_setting(chat_id: int, key: str, value):
    chats.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)

def add_trusted_user(chat_id: int, user_id: int):
    chats.update_one(
        {"chat_id": chat_id},
        {"$addToSet": {"trusted_users": user_id}},
        upsert=True
    )

def remove_trusted_user(chat_id: int, user_id: int):
    chats.update_one({"chat_id": chat_id}, {"$pull": {"trusted_users": user_id}})

def save_event(chat_id: int, name: str, date: str, message: str):
    events.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": {"date": date, "message": message}},
        upsert=True
    )

def get_events_for_date(chat_id: int, date_str: str):
    return list(events.find({"chat_id": chat_id, "date": date_str}))

def save_member_anniversary(user_id: int, chat_id: int, join_mmdd: str):
    member_anniversaries.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"join_date": join_mmdd, "last_celebrated": None}},
        upsert=True
    )

def get_member_anniversaries_for_date(chat_id: int, date_str: str):
    return list(member_anniversaries.find({
        "chat_id": chat_id,
        "join_date": date_str,
        "last_celebrated": {"$ne": datetime.datetime.now().strftime("%Y-%m-%d")}
    }))
