from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["RandomIMDB_DB"]

settings_col = db["group_settings"]
deletions_col = db["pending_deletions"]

DEFAULT_TEMPLATE = """
🎬 **{{title}}** ({{year}})
⭐️ **Rating:** {{rating}}/10 | 🗳 **Votes:** {{votes}}
⏱ **Runtime:** {{runtime}} | 🎭 **Genres:** {{genres}}
🗂 **Kind:** {{kind}} | 🌐 **Languages:** {{languages}}
🍿 **Seasons:** {{seasons}}

👤 **Director:** {{director}}
🌟 **Cast:** {{cast}}
💰 **Box Office:** {{box_office}}

📖 **Plot:** {{plot}}

🔗 [IMDb Link]({{url}})
"""

async def get_target(chat_id: int) -> dict:
    target = await settings_col.find_one({"chat_id": chat_id})
    if not target:
        target = {
            "chat_id": chat_id,
            "enabled": False,
            "interval": 60,       # Minutes
            "auto_delete": 0,     # Seconds (0 = Off)
            "pin": False,
            "template": DEFAULT_TEMPLATE,
            "next_run": datetime.utcnow()
        }
        await settings_col.insert_one(target)
    return target

async def update_target(chat_id: int, **kwargs):
    await settings_col.update_one({"chat_id": chat_id}, {"$set": kwargs})

async def get_due_posts(now: datetime):
    return await settings_col.find({"enabled": True, "next_run": {"$lte": now}}).to_list(length=None)

async def set_next_run(chat_id: int, interval_minutes: int):
    next_time = datetime.utcnow() + timedelta(minutes=interval_minutes)
    await update_target(chat_id, next_run=next_time)

async def queue_deletion(chat_id: int, message_id: int, delay_seconds: int):
    delete_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    await deletions_col.insert_one({"chat_id": chat_id, "message_id": message_id, "delete_at": delete_at})

async def get_due_deletions(now: datetime):
    return await deletions_col.find({"delete_at": {"$lte": now}}).to_list(length=None)

async def remove_deletion(doc_id):
    await deletions_col.delete_one({"_id": doc_id})
