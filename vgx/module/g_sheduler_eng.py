import datetime
from pyrogram import Client
from database import db
from bson.objectid import ObjectId

# We receive the 'app' instance from main.py later
async def perform_job_task(app: Client, job_id: str):
    """
    The core function that runs when the timer hits.
    """
    job = await db.get_job(job_id)
    if not job:
        return

    chat_id = job['chat_id']
    
    try:
        # 1. Send the Message
        sent_msg = None
        if job.get('media_type') == 'photo':
            sent_msg = await app.send_photo(chat_id, job['file_id'], caption=job.get('text', ''))
        else:
            sent_msg = await app.send_message(
                chat_id, 
                job.get('text', ''), 
                disable_web_page_preview=not job.get('link_preview', True)
            )

        # 2. Handle Pinning
        if job.get('pin_msg') and sent_msg:
            try:
                await sent_msg.pin(disable_notification=False)
            except Exception as e:
                print(f"Failed to pin: {e}")

        # 3. Handle Auto-Delete
        # Note: In a real production bot, you'd schedule a DELETE job separately.
        # For simplicity, we just print here.
        if job.get('auto_delete'):
            print(f"⚠️ Message sent. Should delete in {job['auto_delete']} seconds.")

    except Exception as e:
        print(f"❌ Failed to send scheduled message: {e}")

    # 4. Handle Repeat Logic (Recursion)
    if job.get('repeat_interval') and job['repeat_interval'] > 0:
        from main import scheduler # Import here to avoid circular dependency
        
        # Calculate next run time
        next_run = datetime.datetime.now() + datetime.timedelta(minutes=job['repeat_interval'])
        
        # Update DB
        await db.update_job(job_id, {"next_run": next_run})
        
        # Reschedule
        scheduler.add_job(
            perform_job_task, 
            "date", 
            run_date=next_run, 
            args=[app, job_id],
            id=str(job_id),
            replace_existing=True
        )
    else:
        # If not repeating, clean up DB
        await db.delete_job(job_id)
