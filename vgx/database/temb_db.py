
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

class SafeDatabase:
    """Wraps the Motor client to prevent Pyrogram handler collisions."""
    def __init__(self):
        self._client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
        self._db = self._client["TempMailDB"]
        
        # Collections
        self.users = self._db.users
        self.history = self._db.history  # Stores all total generated emails

    def __getattr__(self, name):
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)

db = SafeDatabase()
