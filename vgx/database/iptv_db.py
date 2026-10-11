
from config import Config


import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Explicitly load environment variables
load_dotenv()

MONGO_URI = os.getenv("Config.MONGO_URI")

if not MONGO_URI:
    raise ValueError("❌ CRITICAL: MONGO_URI is missing from your environment variables or .env file!")

class SafeDatabase:
    def __init__(self):
        self._client = AsyncIOMotorClient(MONGO_URI)
        self._db = self._client["BotDatabase"]
        
        # Common collections
        self.filters = self._db.filters
        self.users = self._db.users
        self.history = self._db.history

    def __getattr__(self, name):
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)

db = SafeDatabase()
