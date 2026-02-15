from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from bson.objectid import ObjectId

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client[Config.DB_NAME]
        self.jobs = self.db.jobs

    async def add_job(self, job_data):
        result = await self.jobs.insert_one(job_data)
        return str(result.inserted_id)

    async def get_job(self, job_id):
        return await self.jobs.find_one({"_id": ObjectId(job_id)})

    async def update_job_time(self, job_id, next_run):
        await self.jobs.update_one(
            {"_id": ObjectId(job_id)}, 
            {"$set": {"next_run": next_run}}
        )

    async def delete_job(self, job_id):
        await self.jobs.delete_one({"_id": ObjectId(job_id)})

    async def get_active_jobs(self):
        return self.jobs.find({})

db = Database()

