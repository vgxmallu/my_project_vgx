import datetime
from client import app, scheduler
from database import db
from bson.objectid import ObjectId

async def send_scheduled_message(job_id):
    """The function executed by APScheduler"""
    job = await db.get_job(job_id)
    if not job:
        return

    chat_id = job["chat_id"]
    
    # --- NIGHT MODE LOGIC ---
    if job.get("night_mode"):
        current_hour = datetime.datetime.now().hour
        # If between 12 AM and 6 AM, reschedule for 6:01 AM
        if 0 <= current_hour < 6:
            new_time = datetime.datetime.now().replace(hour=6, minute=1, second=0)
            scheduler.add_job(send_scheduled_message, "date", run_date=new_time, args=[job_id])
            return

    # --- SEND MESSAGE ---
    try:
        sent_msg = None
        if job["media_type"] == "photo":
            sent_msg = await app.send_photo(chat_id, job["media"], caption=job["text"])
        elif job["media_type"] == "text":
            sent_msg = await app.send_message(
                chat_id, 
                job["text"], 
                disable_web_page_preview=job["disable_preview"]
            )
        
        if job["pin"] and sent_msg:
            await sent_msg.pin()
            
    except Exception as e:
        print(f"❌ Failed to send job {job_id}: {e}")

    # --- REPEAT LOGIC ---
    if job.get("repeat_interval", 0) > 0:
        next_run = datetime.datetime.now() + datetime.timedelta(minutes=job["repeat_interval"])
        await db.update_job_time(job_id, next_run)
        
        scheduler.add_job(
            send_scheduled_message, 
            "date", 
            run_date=next_run, 
            args=[job_id],
            id=job_id
        )
    else:
        await db.delete_job(job_id)
