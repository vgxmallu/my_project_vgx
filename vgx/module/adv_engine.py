import datetime
from vgx import app, scheduler
from vgx.database.db_advanc import db

async def run_job(job_id):
    job = await db.get_job(job_id)
    if not job: return
    
    # 0. Check Pause
    if job.get('paused'):
        # If paused, we don't send, but we reschedule check in 1 min
        # Or we just stop. Here we stop recursion until resumed manually.
        # But to be safe, let's just exit. The "Resume" button needs to restart the job.
        return 

    chat_id = job['target_chat']
    
    try:
        # 1. DELETE LAST MESSAGE
        if job.get('del_last') and job.get('last_msg_id'):
            try: await app.delete_messages(chat_id, job['last_msg_id'])
            except: pass

        # 2. SEND CONTENT
        sent = None
        txt = job.get('text', "")
        
        if job['media_type'] == 'photo':
            sent = await app.send_photo(chat_id, job['file_id'], caption=txt)
        elif job['media_type'] == 'sticker':
            sent = await app.send_sticker(chat_id, job['file_id'])
        elif job['media_type'] == 'video':
            sent = await app.send_video(chat_id, job['file_id'], caption=txt)
        else:
            sent = await app.send_message(chat_id, txt, disable_web_page_preview=True)

        # Update Last Message ID in DB
        if sent:
            await db.update_job(job_id, {"last_msg_id": sent.id})

        # 3. PIN
        if job.get('pin') and sent:
            try: await sent.pin(disable_notification=False)
            except: pass

        # 4. AUTO DELETE (Self-Destruct)
        if job.get('auto_del', 0) > 0 and sent:
            scheduler.add_job(
                app.delete_messages, "date",
                run_date=datetime.datetime.now() + datetime.timedelta(seconds=job['auto_del']),
                args=[chat_id, sent.id]
            )

    except Exception as e:
        print(f"❌ Job Error: {e}")

    # 5. RECURSION (Schedule Next Run)
    interval = job.get('interval', 0)
    if interval > 0:
        next_run = datetime.datetime.now() + datetime.timedelta(minutes=interval)
        
        # Update DB
        await db.update_job(job_id, {"next_run": next_run})
        
        # Add to Scheduler
        scheduler.add_job(
            run_job, "date",
            run_date=next_run,
            args=[job_id], id=job_id,
            replace_existing=True
        )
    else:
        # One-time job finished
        await db.delete_job(job_id)
