import asyncio
import logging
from datetime import datetime
from pyrogram import idle
from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job

from vgx.module.night_schedul import start_nm_scheduler
from vgx.module.dfeed_scheduler import start_df_scheduler


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchedulerBot")



async def restore_jobs():
    """Reschedules jobs from DB on restart"""
    logger.info("♻️  Restoring Database Jobs...")
    count = 0
    jobs = await db.get_all_jobs()
    
    async for job in jobs:
        if job.get('paused'): continue
        
        # Check if missed timing
        run_at = job.get('next_run')
        if not run_at or run_at < datetime.now():
            run_at = datetime.now() # Run immediately if missed
            
        scheduler.add_job(
            run_job, "date",
            run_date=run_at,
            args=[str(job['_id'])],
            id=str(job['_id']),
            replace_existing=True
        )
        count += 1
    logger.info(f"✅ Restored {count} active jobs.")

if __name__ == "__main__":
    scheduler.start()
    app.start()

    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online...")
    start_df_scheduler(app)
    
    loop = asyncio.get_event_loop()
    loop.create_task(restore_jobs())
    
    print("🚀 Bot Started! Send /schedule")
    idle()
    app.stop()

