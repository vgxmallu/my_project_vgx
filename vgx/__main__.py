import asyncio
import logging
from datetime import datetime, timezone

from pyrogram import idle

from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job

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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("SchedulerBot")


async def restore_jobs():
    """Restore scheduled database jobs after bot restart."""
    logger.info("♻️ Restoring Database Jobs...")

    count = 0

    try:
        jobs = await db.get_all_jobs()

        async for job in jobs:
            try:
                if job.get("paused"):
                    continue

                run_at = job.get("next_run")
                now = datetime.now(timezone.utc)

                # Normalize DB datetime
                if run_at is None:
                    run_at = now

                elif run_at.tzinfo is None:
                    run_at = run_at.replace(tzinfo=timezone.utc)

                if run_at < now:
                    run_at = now

                job_id = str(job["_id"])

                scheduler.add_job(
                    run_job,
                    trigger="date",
                    run_date=run_at,
                    args=[job_id],
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=300,
                )

                count += 1

            except Exception:
                logger.exception(
                    "Failed to restore job: %s",
                    job.get("_id"),
                )

    except Exception:
        logger.exception("Failed to restore jobs from database.")

    logger.info("✅ Restored %s active jobs.", count)


async def start_background_tasks():
    """Start all background workers on the current asyncio loop."""

    # Night Mode
    logger.info("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    # Drip Feed
    logger.info("🤖 Drip-Feed System Online.")
    start_df_scheduler(app)

    # Analytics
    logger.info("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    # Quote Worker
    logger.info("🚀 Motivation Bot Online ⏰ Scheduler started")
    asyncio.create_task(
        quote_worker(app),
        name="quote_worker",
    )

    # Anime Worker
    logger.info("⛩️ Anime Bot Online! Interface & Commands ready.")
    asyncio.create_task(
        anime_worker(app),
        name="anime_worker",
    )

    # Birthday Worker
    logger.info("🎂 Birthday & Event Scheduler is Live....")
    asyncio.create_task(
        birthday_worker(app),
        name="birthday_worker",
    )

    # RSS Worker
    logger.info("📡 RSS Autopost Bot Online!")
    asyncio.create_task(
        autopost_worker(app),
        name="rss_autopost_worker",
    )

    # Pomodoro
    logger.info("🍅 Pomodoro Module Online!")
    asyncio.create_task(
        pomodoro_loop(app),
        name="pomodoro_worker",
    )

    # Health Monitor
    logger.info("💓 Health Monitor Online!")
    asyncio.create_task(
        heartbeat_loop(app),
        name="heartbeat_worker",
    )

    # Weather
    logger.info("🌤 Weather Morning Briefing System Online!")
    asyncio.create_task(
        morning_briefing_loop(app),
        name="weather_worker",
    )

    # Deezer
    logger.info("🚀 Deezer Music Scheduler Online!")
    asyncio.create_task(
        music_scheduler_loop(app),
        name="deezer_worker",
    )

    # Football
    logger.info("📢 Booting Football-Data.org Telegram Bot...")
    asyncio.create_task(
        fmatch_scheduler(app),
        name="football_worker",
    )

    # SportsDB
    logger.info("👀 SportsDB Telegram Bot...")
    asyncio.create_task(
        sportsdb_scheduler_loop(app),
        name="sportsdb_worker",
    )

    # Auto Mod
    logger.info("🛡 Auto-Mod System Online!")
    asyncio.create_task(
        weekly_audit_loop(app),
        name="automod_worker",
    )

    # Spotify
    logger.info("🎧 Spotify Pro System Online!")

    asyncio.create_task(
        drop_sender_loop(app),
        name="spotify_drop_worker",
    )

    asyncio.create_task(
        auto_delete_loop(app),
        name="spotify_delete_worker",
    )

    # Database scheduler jobs
    asyncio.create_task(
        restore_jobs(),
        name="restore_database_jobs",
    )


async def main():
    logger.info("🚀 Starting bot...")

    try:
        # Start APScheduler AFTER asyncio loop exists.
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ APScheduler started.")

        # Start Pyrogram.
        await app.start()
        logger.info("✅ Pyrogram client started.")

        # Start all background workers.
        await start_background_tasks()

        logger.info("🚀 Bot Started! Send /schedule")

        # Keep the Telegram client alive.
        await idle()

    except Exception:
        logger.exception("❌ Fatal error while running bot.")
        raise

    finally:
        logger.info("🛑 Shutting down bot...")

        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
                logger.info("✅ APScheduler stopped.")
        except Exception:
            logger.exception("Error stopping APScheduler.")

        try:
            await app.stop()
            logger.info("✅ Pyrogram client stopped.")
        except Exception:
            logger.exception("Error stopping Pyrogram.")


if __name__ == "__main__":
    asyncio.run(main())
