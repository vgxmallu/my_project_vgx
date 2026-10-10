import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
load_dotenv()

class SafeDatabase:
    def __init__(self):
        self._client = AsyncIOMotorClient(os.getenv("Config.MONGO_URL"))
        self._db = self._client["IPTVBotDB"]
        
        # Caching collections for iptv-org endpoints
        self.channels = self._db.channels
        self.streams = self._db.streams
        self.guides = self._db.guides
        self.health_logs = self._db.health_logs

    def __getattr__(self, name):
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)

db = SafeDatabase()
