import asyncio
import logging
from datetime import datetime
from pyrogram import idle
from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import your modules
from vgx.module.night_schedul import start_nm_scheduler
from vgx.module.dfeed_scheduler import start_df_scheduler
from vgx.module.anylz_schedul import start_anlyz_scheduler
from vgx.module.bday_schedul import check_celebrations
from vgx.module.rss_worker import check_rss_feeds 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchedulerBot")

async def restore_jobs():
    """Reschedules jobs from DB on restart"""
    logger.info("♻️  Restoring Database Jobs...")
    count = 0
    jobs = await db.get_all_jobs()
    
    async for job in jobs:
        if job.get('paused'): continue
        
        run_at = job.get('next_run')
        if not run_at or run_at < datetime.now():
            run_at = datetime.now()
            
        scheduler.add_job(
            run_job, "date",
            run_date=run_at,
            args=[str(job['_id'])],
            id=str(job['_id']),
            replace_existing=True
        )
        count += 1
    logger.info(f"✅ Restored {count} active jobs.")

async def start_bot():
    """Main async entry point to handle the event loop correctly"""
    # 1. Start the Pyrogram Client
    await app.start()
    
    # 2. Start the main scheduler (assumed to be the one from vgx)
    if not scheduler.running:
        scheduler.start()

    # 3. Start background RSS worker
    print("📡 Initializing background RSS worker...")
    asyncio.create_task(check_rss_feeds(app))

    # 4. Initialize other systems
    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)
    
    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    # 5. Setup Birthday Scheduler
    # Note: Using the vgx scheduler instead of creating a new one to avoid conflicts
    scheduler.add_job(check_celebrations, "interval", hours=1, args=[app])
    print("🎂 Birthday & Event Scheduler is Live....")
    
    # 6. Restore DB Jobs
    await restore_jobs()
    
    print("🚀 Bot Started! Send /schedule")
    
    # 7. Keep the bot running
    await idle()
    
    # 8. Graceful Stop
    await app.stop()

if __name__ == "__main__":
    # This creates the event loop and runs the start_bot coroutine
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
