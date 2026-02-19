from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from vgx.module.anylz_Analytics import get_golden_hour

scheduler = AsyncIOScheduler()

async def schedule_golden_msg(app, chat_id, text):
    peak_hour = await get_golden_hour(chat_id)
    
    now = datetime.now()
    run_date = now.replace(hour=peak_hour, minute=0, second=0)
    
    # If peak hour passed today, schedule for tomorrow
    if run_date < now:
        run_date += timedelta(days=1)
    
    scheduler.add_job(
        send_msg, 
        "date", 
        run_date=run_date, 
        args=[app, chat_id, text]
    )
    return run_date.strftime("%Y-%m-%d %H:%M")

async def send_msg(app, chat_id, text):
    try:
        await app.send_message(chat_id, text)
    except Exception as e:
        print(f"Failed to send scheduled msg: {e}")

def start_anlyz_scheduler():
    if not scheduler.running:
        scheduler.start()
