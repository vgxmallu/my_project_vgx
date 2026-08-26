import logging
import asyncio
from datetime import datetime
from pyrogram import idle

from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
from vgx.module.Automod import weekly_audit_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchedulerBot")


async def restore_jobs():
    """Reschedules jobs from DB on restart"""
    logger.info("♻️  Restoring Database Jobs...")
    count = 0
    jobs = await db.get_all_jobs()

    async for job in jobs:
        if job.get('paused'):
            continue

        # Check if missed timing
        run_at = job.get('next_run')
        if not run_at or run_at < datetime.now():
            run_at = datetime.now()  # Run immediately if missed

        scheduler.add_job(
            run_job,
            "date",
            run_date=run_at,
            args=[str(job['_id'])],
            id=str(job['_id']),
            replace_existing=True,
        )
        count += 1
    logger.info(f"✅ Restored {count} active jobs.")


async def main():
    # 1. Start APScheduler and Pyrogram Client asynchronously
    scheduler.start()
    await app.start()

    # 2. Boot synchronous module setups
    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)

    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    # 3. Schedule async background tasks directly on the active loop
    print("🚀 Motivation Bot is Online ⏰ Scheduler started")
    asyncio.create_task(quote_worker(app))

    print("⛩️ Anime Bot Online! Interface & Commands ready.")
    asyncio.create_task(anime_worker(app))

    print("🎂 Birthday & Event Scheduler is Live....")
    asyncio.create_task(birthday_worker(app))

    print("📡 RSS Autopost Bot Online!")
    asyncio.create_task(autopost_worker(app))

    print("🍅 Pomodoro Module Online!")
    asyncio.create_task(pomodoro_loop(app))

    print("💓 Health Monitor Online!")
    asyncio.create_task(heartbeat_loop(app))

    print("🌤 Weather Morning Briefing System Online!")
    asyncio.create_task(morning_briefing_loop(app))

    print("🚀 Deezer Music Scheduler Online!")
    asyncio.create_task(music_scheduler_loop(app))

    print("📢 Booting Football-Data.org Telegram Bot...")
    asyncio.create_task(fmatch_scheduler(app))

    print("👀 SoprtsDB Telegram Bot...")
    asyncio.create_task(sportsdb_scheduler_loop(app))

    print("🛡 Auto-Mod System Online!")
    asyncio.create_task(weekly_audit_loop(app))

    print("🎧 Spotify Pro System Online!")
    asyncio.create_task(drop_sender_loop(app))
    asyncio.create_task(auto_delete_loop(app))

    # 4. Restore DB Jobs
    asyncio.create_task(restore_jobs())

    print("🚀 Bot Started! Send /schedule")

    # 5. Keep client alive safely
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
