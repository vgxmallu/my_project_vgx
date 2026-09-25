import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

class SafeDatabase:
    def __init__(self):
        self._client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
        self._db = self._client["FilterBotDB"]
        self.filters = self._db.filters  # Unlimited filters collection

    def __getattr__(self, name):
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)

db = SafeDatabase()
