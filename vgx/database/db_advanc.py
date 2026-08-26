from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from bson.objectid import ObjectId

class Database:
    self.handlers = None
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client[Config.DB_NAME]
        self.jobs = self.db.jobs

    async def add_job(self, data):
        return await self.jobs.insert_one(data)

    async def get_job(self, job_id):
        try:
            return await self.jobs.find_one({"_id": ObjectId(job_id)})
        except:
            return None

    async def get_user_jobs(self, user_id):
        # Returns jobs created by specific user
        return self.jobs.find({"user_id": user_id})

    async def get_all_jobs(self):
        return self.jobs.find({})

    async def __getattr__(self, name):
        # Raising AttributeError forces Pyrogram's scanner to completely ignore this object
        if name == "handlers":
            raise AttributeError("'SafeDatabase' object has no attribute 'handlers'")
        return getattr(self._db, name)
        
    async def update_job(self, job_id, data):
        await self.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": data})

    async def delete_job(self, job_id):
        await self.jobs.delete_one({"_id": ObjectId(job_id)})

    # Toggles Pause/Resume
    async def toggle_pause(self, job_id, is_paused):
        await self.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {"paused": is_paused}})

db = Database()

from motor.motor_asyncio import AsyncIOMotorClient

# 1. Your existing connection
_client = AsyncIOMotorClient("YOUR_MONGODB_URI")
_raw_db = _client["YOUR_DATABASE_NAME"]

# 2. Corrected wrapper
class SafeDatabase:
    def __init__(self, db_instance):
        self._db = db_instance

    

    def __getitem__(self, name):
        return self._db[name]

# 3. Export
db = SafeDatabase(_raw_db)
