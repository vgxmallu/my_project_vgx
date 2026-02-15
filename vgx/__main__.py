import asyncio
import datetime
from vgx import app, scheduler
from vgx.database.db import db
from vgx.module.jobs import send_scheduled_message

async def restore_jobs():
    print("♻️  Restoring schedules...")
    async for job in db.get_active_jobs():
        if job["next_run"] > datetime.datetime.now():
            scheduler.add_job(
                send_scheduled_message, 
                "date", 
                run_date=job["next_run"], 
                args=[str(job["_id"])],
                id=str(job["_id"])
            )

if __name__ == "__main__":
    scheduler.start()
    
    # Restore jobs on startup
    loop = asyncio.get_event_loop()
    loop.create_task(restore_jobs())
    
    print("🚀 Bot Started!")
    app.run()
  
