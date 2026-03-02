import asyncio
import logging
from datetime import datetime
# Switch to Kurigram as requested previously
from pyrogram import idle 
from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job

# Import schedulers
from vgx.module.night_schedul import start_nm_scheduler
from vgx.module.dfeed_scheduler import start_df_scheduler
from vgx.module.anylz_schedul import start_anlyz_scheduler
from vgx.module.bday_schedul import start_bday_scheduler
from vgx.module.quotes_schedul import load_jobs_on_start

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchedulerBot")

async def restore_jobs():
    """Reschedules jobs from DB on restart"""
    logger.info("♻️ Restoring Database Jobs...")
    count = 0
    # Use await because this is an async operation
    jobs = await db.get_all_jobs() 

    async for job in jobs:
        if job.get('paused'):
            continue

        run_at = job.get('next_run')

        if not run_at or run_at < datetime.now():
            run_at = datetime.now()

        scheduler.add_job(
            run_job,
            "date",
            run_date=run_at,
            args=[str(job['_id'])],
            id=str(job['_id']),
            replace_existing=True
        )
        count += 1

    logger.info(f"✅ Restored {count} active jobs.")

async def main():
    # Start the Kurigram client first
    await app.start()
    # Start the scheduler after the app is live
    scheduler.start()

    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)

    # ✅ FIXED: Added 'app' argument here
    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler(app) 

    print("🚀 Motivation Bot is Online ⏰ Scheduler started")
    # This was already fixed in your snippet, keeping it here
    await load_jobs_on_start(app)

    print("🎂 Birthday & Event Scheduler is Live....")
    # Make sure this function is defined to accept 'app'
    start_bday_scheduler(app)

    # Restore DB jobs in background
    asyncio.create_task(restore_jobs())

    print("🚀 Bot Started! Ready for /schedule")
    
    # Keeps the bot running
    await idle()
    
    # Graceful shutdown
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped manually.")
