from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime

db_client = AsyncIOMotorClient(Config.MONGO_URL)
db = db_client["IMDB_Bot"]

imdb_settings = db["imdb_settings"]
imdb_queue = db["imdb_queue"]
imdb_deletions = db["imdb_deletions"]

# Default customizable template
DEFAULT_TEMPLATE = """
🎬 **{{title}}** ({{year}})
⭐️ **Rating:** {{rating}}/10 | 🗳 **Votes:** {{votes}}
⏱ **Runtime:** {{runtime}} | 🎭 **Genres:** {{genres}}
🗂 **Kind:** {{kind}} | 🌐 **Languages:** {{languages}}

👤 **Director:** {{director}}
🌟 **Cast:** {{cast}}

📖 **Plot:** {{plot}}

🔗 [IMDb Link]({{url}})
"""

async def get_settings(chat_id: int) -> dict:
    s = await imdb_settings.find_one({"chat_id": chat_id})
    return s or {
        "chat_id": chat_id,
        "enabled": False,
        "interval": 60, # Minutes (default 1h)
        "auto_delete": 0, # Seconds (0 = Off)
        "pin_message": False,
        "template": DEFAULT_TEMPLATE
    }

async def update_settings(chat_id: int, **kwargs):
    await imdb_settings.update_one({"chat_id": chat_id}, {"$set": kwargs}, upsert=True)
    
async def add_to_queue(chat_id: int, query: str, next_run: datetime):
    await imdb_queue.insert_one({"chat_id": chat_id, "query": query, "next_run": next_run})

async def add_to_deletion(chat_id: int, message_id: int, delete_at: datetime):
    await imdb_deletions.insert_one({"chat_id": chat_id, "message_id": message_id, "delete_at": delete_at})
