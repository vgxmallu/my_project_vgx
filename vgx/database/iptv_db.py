
from config import Config


import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Explicitly load environment variables
load_dotenv()

class SafeDatabase:
    def __init__(self):
        self._client = AsyncIOMotorClient(Config.MONGO_URL)
        self._db = self._client["iptvBotDatabase"]
        
        # Common collections
        self.filters = self._db.filters
        self.users = self._db.users
        self.history = self._db.history

    def __getattr__(self, name):
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)

db = SafeDatabase()
