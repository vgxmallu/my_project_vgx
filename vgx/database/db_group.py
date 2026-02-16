from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from bson.objectid import ObjectId

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client[Config.DB_NAME]
        self.jobs = self.db.jobs

    async def add_job(self, data):
        return await self.jobs.insert_one(data)

    async def get_job(self, job_id):
        return await self.jobs.find_one({"_id": ObjectId(job_id)})

    async def get_all_jobs(self):
        return self.jobs.find({})

    async def delete_job(self, job_id):
        await self.jobs.delete_one({"_id": ObjectId(job_id)})

    async def update_job(self, job_id, update_data):
        await self.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": update_data})

db = Database()
