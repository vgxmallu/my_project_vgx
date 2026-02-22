import asyncio
import logging
from datetime import datetime
from pyrogram import idle
from vgx import app, scheduler  # Ensure these are already instances
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

async def start_services():
    """Main entry point to start the bot and all background workers"""
    # 1. Start the Pyrogram client instance
    await app.start()
    
    # 2. Start the main scheduler
    if not scheduler.running:
        scheduler.start()
    
    # 3. Initialize background systems
    print("📡 Initializing background RSS worker...")
    asyncio.create_task(check_rss_feeds(app))

    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)
    
    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    # 4. Set up the Birthday/Event scheduler
    # Using a secondary scheduler as per your original logic
    bday_scheduler = AsyncIOScheduler()
    bday_scheduler.add_job(check_celebrations, "interval", hours=1, args=[app])
    bday_scheduler.start()
    print("🎂 Birthday & Event Scheduler is Live....")
    
    # 5. Restore DB Jobs
    await restore_jobs()
    
    print("🚀 Bot Started! Send /schedule")
    
    # 6. Wait for shutdown signal
    await idle()
    
    # 7. Cleanup
    await app.stop()
    bday_scheduler.shutdown()

if __name__ == "__main__":
    # This block correctly initializes the event loop for Python 3.10+
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
