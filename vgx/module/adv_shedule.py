import datetime
from vgx import app, scheduler

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vgx.database.db_advanc import _db as db

from utils2 import get_job_controls
from vgx.module import sessions



async def run_job(job_id):
    # 1. Fetch Job Data
    job = await db.get_job(job_id)
    if not job: 
        return
    
    # 2. Check Pause Status
    if job.get('paused'):
        return 

    chat_id = job['target_chat']
    
    # 3. Extract Content Variables Safely (From Top Snippet)
    # This prevents KeyErrors if fields are missing
    txt = job.get('text', "")
    m_type = job.get('media_type')
    fid = job.get('file_id')

    try:
        # --- A. DELETE LAST MESSAGE FEATURE ---
        if job.get('del_last') and job.get('last_msg_id'):
            try: 
                await app.delete_messages(chat_id, job['last_msg_id'])
            except: 
                pass # Message might be too old or already deleted

        # --- B. SEND CONTENT (Merged Logic) ---
        sent = None
        
        if m_type == 'photo':
            sent = await app.send_photo(chat_id, fid, caption=txt)
        elif m_type == 'video':
            sent = await app.send_video(chat_id, fid, caption=txt)
        elif m_type == 'sticker':
            # Stickers do not support captions
            sent = await app.send_sticker(chat_id, fid)
        else:
            # Default to Text
            sent = await app.send_message(chat_id, txt, disable_web_page_preview=True)

        # --- C. SAVE MESSAGE ID (For 'Delete Last' feature) ---
        if sent:
            await db.update_job(job_id, {"last_msg_id": sent.id})

        # --- D. PIN MESSAGE FEATURE ---
        if job.get('pin') and sent:
            try: 
                await sent.pin(disable_notification=False)
            except: 
                pass

        # --- E. AUTO-DELETE FEATURE ---
        # If auto_del is set (e.g., 60 seconds), schedule a deletion task
        if job.get('auto_del', 0) > 0 and sent:
            scheduler.add_job(
                app.delete_messages, "date",
                run_date=datetime.datetime.now() + datetime.timedelta(seconds=job['auto_del']),
                args=[chat_id, sent.id]
            )

    except Exception as e:
        print(f"❌ Job Error: {e}")

    # 4. RECURSION (Schedule Next Run)
    interval = job.get('interval', 0)
    
    if interval > 0:
        # Calculate next run time
        next_run = datetime.datetime.now() + datetime.timedelta(minutes=interval)
        
        # Update DB
        await db.update_job(job_id, {"next_run": next_run})
        
        # Reschedule in APScheduler
        scheduler.add_job(
            run_job, "date",
            run_date=next_run,
            args=[job_id], id=job_id,
            replace_existing=True
        )
    else:
        # One-time job finished: Clean up from DB
        await db.delete_job(job_id)

#====================================================

@Client.on_message(filters.private & filters.command("myjobs"))
async def list_jobs(c, m):
    jobs = await db.get_user_jobs(m.from_user.id)
    btn_list = []
    async for j in jobs:
        status = "⏸" if j.get('paused') else "▶️"
        chat = str(j.get('target_chat'))[:10]
        btn_list.append([
            InlineKeyboardButton(
                f"{status} {chat} | {j.get('interval', 0)}m", 
                callback_data=f"mngr_view_{j['_id']}"
            )
        ])
    
    if not btn_list:
        return await m.reply("📭 No active schedules found.")
        
    await m.reply("📋 **Your Scheduled Jobs:**", reply_markup=InlineKeyboardMarkup(btn_list))

#====================================================


@Client.on_callback_query(filters.regex("^close$"))
async def col_callback(client, query):
    await query.answer("❌ Closed ❌")
    await asyncio.sleep(1)
    await query.message.delete()
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
