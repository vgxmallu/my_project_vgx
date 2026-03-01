
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URL)
db = client["random_quotes_bot"]

# one collection for per-chat scheduler settings
settings_col = db["chat_settings"]
