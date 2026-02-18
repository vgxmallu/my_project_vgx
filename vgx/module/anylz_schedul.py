from apscheduler.schedulers.asyncio import AsyncIOScheduler
from vgx.module.analytics import get_golden_hour
from datetime import datetime, timedelta
import pytz

scheduler = AsyncIOScheduler()

async def schedule_for_peak(app, chat_id, text):
    peak_hour = await get_golden_hour(chat_id)
    now = datetime.now()
    
    # Calculate target time
    run_date = now.replace(hour=peak_hour, minute=0, second=0)
    if run_date < now:
        run_date += timedelta(days=1)
        
    scheduler.add_job(
        send_scheduled_msg,
        "date",
        run_date=run_date,
        args=[app, chat_id, text]
    )
    return run_date

async def send_scheduled_msg(app, chat_id, text):
    await app.send_message(chat_id, text)
