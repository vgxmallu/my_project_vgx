import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from vgx.database.quets_db2 import settings_col
from utils.job_utils import get_random_quote

scheduler = AsyncIOScheduler()

async def send_quote(app, chat_id: int):
    """Send one random quote to chat_id according to its settings."""
    # fetch latest settings
    settings = await settings_col.find_one({"chat_id": chat_id})
    if not settings or not settings.get("enabled"):
        return

    target = settings.get("target_chat") or chat_id

    # Delete last message if configured
    if settings.get("delete_last") and settings.get("last_msg_id"):
        try:
            await app.delete_messages(target, settings["last_msg_id"])
        except Exception:
            pass

    # send message
    try:
        msg = await app.send_message(target, get_random_quote())
    except Exception:
        # if sending fails (e.g. bot not in target chat), skip
        return

    # pin if requested and chat is group/channel
    if settings.get("pin"):
        try:
            # only attempt pin if chat is group-like (starts with -)
            # pyrogram will raise if pinning not allowed — catch and ignore
            await msg.pin(disable_notification=True)
        except Exception:
            pass

    # schedule auto delete locally using asyncio to preserve message id
    auto_delete = settings.get("auto_delete", 0)
    if auto_delete and auto_delete > 0:
        # schedule coroutine to delete after `auto_delete` seconds
        asyncio.create_task(_auto_delete_task(app, target, msg.id, auto_delete))

    # update last_msg_id
    await settings_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_msg_id": msg.id}}
    )

async def _auto_delete_task(app, chat_id: int, msg_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await app.delete_messages(chat_id, msg_id)
    except Exception:
        pass

def schedule_job_for_chat(chat_id: int, interval_seconds: int):
    job_id = f"quotes::{chat_id}"
    # replace existing
    scheduler.add_job(send_quote, "interval", seconds=interval_seconds,
                      args=[app, chat_id], id=job_id, replace_existing=True)

def remove_job_for_chat(chat_id: int):
    job_id = f"quotes::{chat_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

async def load_jobs_on_start(app):
    """Load jobs from DB on startup (for enabled chats with interval)."""
    cursor = settings_col.find({"enabled": True, "interval": {"$exists": True}})
    async for s in cursor:
        interval = s.get("interval")
        if interval and int(interval) > 0:
            schedule_job_for_chat(s["chat_id"], int(interval))
