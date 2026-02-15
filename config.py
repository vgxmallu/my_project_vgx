import os

class Config:
    API_ID = int(os.environ.get("API_ID", "12345"))
    API_HASH = os.environ.get("API_HASH", "your_hash_here")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://...")
    DB_NAME = "scheduler_bot"

