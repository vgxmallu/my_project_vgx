from pyrogram import Client, filters
from vgx.database.db_advanc import db
from utils2 import get_job_controls
from vgx import scheduler
from vgx.module import sessions




# In plugins/manager.py
@Client.on_callback_query(filters.regex(r"^mngr_edit_"))
async def trigger_edit_msg(c, q):
    job_id = q.data.split("_")[2]
    uid = q.from_user.id
    
    # Store in session that we are editing an EXISTING job
    sessions[uid] = {
        "step": "editing_existing_job",
        "job_id": job_id
    }
    
    await q.answer("📝 Send the NEW text/media for this job.")
    await q.message.reply("📤 **Please send the new Content (Text/Photo/Video/Sticker).\n\nThis will replace the current message of the scheduled job.")
    


@Client.on_callback_query(filters.regex(r"^mngr_"))
async def manager_callbacks(c, q):
    action, job_id = q.data.split("_")[1], q.data.split("_")[2]
    
    # 1. VIEW JOB
    if action == "view":
        job = await db.get_job(job_id)
        if not job: return await q.answer("Job not found", show_alert=True)
        
        txt = (
            f"🆔 `{job_id}`\n"
            f"🎯 Target: `{job['target_chat']}`\n"
            f"⏲ Interval: {job.get('interval')}m\n"
            f"📌 Pin: {job.get('pin')}\n"
            f"📂 Type: {job.get('media_type')}"
        )
        await q.message.edit_text(txt, reply_markup=get_job_controls(job_id, job.get('paused')))

    # 2. PAUSE / RESUME
    elif action in ["pause", "resume"]:
        is_paused = (action == "pause")
        await db.toggle_pause(job_id, is_paused)
        
        # Update UI
        job = await db.get_job(job_id)
        await q.message.edit_reply_markup(get_job_controls(job_id, job.get('paused')))
        await q.answer(f"Job {action}d!")

    # 3. DELETE
    elif action == "delete":
        await db.delete_job(job_id)
        try: scheduler.remove_job(job_id)
        except: pass
        await q.message.edit_text("🗑 **Job Deleted.**")

@Client.on_callback_query(filters.regex("^myjobs_refresh$"))
async def refresh_list(c, q):
    # Triggers the /myjobs list again
    # We can just delete and ask user to run command, or re-run logic.
    # Simple way:
    await q.message.delete()
    await q.message.reply("🔄 Please run /myjobs again to refresh.")
