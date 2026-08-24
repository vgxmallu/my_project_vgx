import logging
import asyncio
from datetime import datetime
from pyrogram import idle
from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Imports
from vgx.module.Night_Mod import start_nm_scheduler
from vgx.module.dfeed_scheduler import start_df_scheduler
from vgx.module.anlyz_adm_cmd import start_anlyz_scheduler
from vgx.module.bday_schedul import birthday_worker
from vgx.module.quotes_schedul import quote_worker
from vgx.module.anilist_schedul import anime_worker
from vgx.module.rssfeed_scheduler import autopost_worker
from vgx.module.pomodoro_scheduler import pomodoro_loop
from vgx.module.bot_health import heartbeat_loop
from vgx.module.weather_schedul import morning_briefing_loop
from vgx.module.spoty import drop_sender_loop, auto_delete_loop
from vgx.module.deezer_scheduler import music_scheduler_loop
from vgx.module.f_boll_schedul import fmatch_scheduler
from vgx.module.fsport_schedul import sportsdb_scheduler_loop

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

async def main():
    """Main async entry point for the bot."""
    
    # 1. Start standard schedulers
    scheduler.start()
    
    # 2. Start Pyrogram asynchronously
    await app.start()
    
    # 3. Boot Synchronous Modules
    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)
    
    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)
    
    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    # 4. Boot Asynchronous Background Workers
    print("🚀 Booting Background Workers...")
    
    # asyncio.create_task automatically attaches to the running loop
    asyncio.create_task(quote_worker(app))
    asyncio.create_task(anime_worker(app))
    asyncio.create_task(birthday_worker(app))
    asyncio.create_task(autopost_worker(app))
    asyncio.create_task(pomodoro_loop(app))
    asyncio.create_task(heartbeat_loop(app))
    asyncio.create_task(morning_briefing_loop(app))
    asyncio.create_task(music_scheduler_loop(app))
    asyncio.create_task(fmatch_scheduler(app))
    asyncio.create_task(sportsdb_scheduler_loop(app))
    asyncio.create_task(drop_sender_loop(app))
    asyncio.create_task(auto_delete_loop(app))
    
    # 5. Restore database jobs
    asyncio.create_task(restore_jobs())

    print("🚀 Bot Started! Send /schedule")
    
    # 6. Keep the script alive
    await idle()
    
    # 7. Clean shutdown when interrupted
    await app.stop()

if __name__ == "__main__":
    # This safely creates the event loop and executes everything inside main()
    asyncio.run(main())
