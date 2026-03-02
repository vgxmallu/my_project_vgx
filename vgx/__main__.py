import asyncio
import logging
from datetime import datetime
from pyrogram import idle
from vgx import app, scheduler
from vgx.database.db_advanc import db
from vgx.module.adv_engine import run_job

from vgx.module.night_schedul import start_nm_scheduler
from vgx.module.dfeed_scheduler import start_df_scheduler
from vgx.module.anylz_schedul import start_anlyz_scheduler
from vgx.module.bday_schedul import start_bday_scheduler
from vgx.module.quotes_schedul import load_jobs_on_start


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
    scheduler.start()
    await app.start()

    print("💫 Night Mode System Online.")
    start_nm_scheduler(app)

    print("🤖 Drip-Feed System Online..")
    start_df_scheduler(app)

    print("🤖 Golden Hour Analytics Online...")
    start_anlyz_scheduler()

    print("🚀 Motivation Bot is Online ⏰ Scheduler started")

    # ✅ FIXED HERE (await added)
    await load_jobs_on_start(app)

    print("🎂 Birthday & Event Scheduler is Live....")
    start_bday_scheduler(app)

    # restore DB jobs
    asyncio.create_task(restore_jobs())

    print("🚀 Bot Started! Send /schedule")
    await idle()

    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
