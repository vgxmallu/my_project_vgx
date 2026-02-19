import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

from vgx.database.bday_db import *
from config import *
from utils3 import get_mention

scheduler = AsyncIOScheduler(timezone="UTC")

async def celebrate_all(client):
    now_utc = datetime.now(pytz.utc)
    
    # Birthdays
    for doc in birthdays.find():
        try:
            user_tz = pytz.timezone(doc["timezone"])
            now_tz = now_utc.astimezone(user_tz)
            today_mmdd = now_tz.strftime("%m-%d")
            
            if doc.get("birthday") == today_mmdd:
                last = doc.get("last_celebrated")
                if last and last == now_tz.strftime("%Y-%m-%d"):
                    continue
                
                chat_settings = get_chat_settings(doc["chat_id"])
                trusted = chat_settings["trusted_users"]
                
                if trusted and doc["user_id"] not in trusted:
                    continue
                
                try:
                    user = await client.get_users(doc["user_id"])
                    mention = get_mention(user)
                    msg = chat_settings["birthday_message"].format(
                        mention=mention,
                        name=user.first_name,
                        role=chat_settings["birthday_role"]
                    )
                    await client.send_message(doc["chat_id"], msg, disable_web_page_preview=True)
                    update_last_celebrated(doc["user_id"], doc["chat_id"])
                except:
                    continue
        except:
            continue
    
    # Member Anniversaries
    for doc in member_anniversaries.find():
        try:
            chat_settings = get_chat_settings(doc["chat_id"])
            today_mmdd = datetime.now().strftime("%m-%d")
            if doc["join_date"] == today_mmdd:
                last = doc.get("last_celebrated")
                if last == datetime.now().strftime("%Y-%m-%d"):
                    continue
                user = await client.get_users(doc["user_id"])
                years = datetime.now().year - int(doc.get("join_year", datetime.now().year))  # optional
                msg = f"🎊 Happy {years if years > 0 else ''} Member Anniversary to {get_mention(user)}! You've been with us for another amazing year!"
                await client.send_message(doc["chat_id"], msg)
                member_anniversaries.update_one({"_id": doc["_id"]}, {"$set": {"last_celebrated": datetime.now().strftime("%Y-%m-%d")}})
        except:
            continue
    
    # Server Anniversaries & Custom Events
    for chat in chats.find({"server_anniversary": {"$exists": True}}):
        today = datetime.now().strftime("%m-%d")
        if chat["server_anniversary"] == today:
            await client.send_message(chat["chat_id"], chat.get("server_message", "🎉 Happy Server Anniversary!"))
    
    for event in events.find():
        today = datetime.now().strftime("%m-%d")
        if event["date"] == today:
            await client.send_message(event["chat_id"], event["message"])

def start_bday_scheduler(client):
    scheduler.add_job(celebrate_all, "interval", minutes=30, args=[client], id="celebrate")
    scheduler.start()
    print("🎉 Scheduler started - checking every 30 minutes")
