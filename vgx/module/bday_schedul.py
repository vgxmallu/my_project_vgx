import pytz
from datetime import datetime
from vgx.database.bday_db import users, chats
from pyrogram.types import ChatPermissions

async def check_celebrations(app):
    async for user in users.find():
        tz = pytz.timezone(user.get("tz", "UTC"))
        now = datetime.now(tz)
        current_date = now.strftime("%m-%d") # MM-DD format
        
        if user["dob"][5:] == current_date: # Match month and day
            chat_id = user["chat_id"]
            settings = await chats.find_one({"chat_id": chat_id})
            
            # Check Trusted System
            if settings.get("trusted_users") and user["user_id"] not in settings["trusted_users"]:
                continue

            # 1. Custom Title (Simulated Role)
            try:
                await app.set_administrator_custom_title(chat_id, user["user_id"], settings["bday_role"])
            except: pass # Bot might not be admin

            # 2. Send Message
            mention = f"[(link to user)](tg://user?id={user['user_id']})" # Simplified mention logic
            msg = settings["bday_msg"].replace("{mention}", mention).replace("{role}", settings["bday_role"])
            await app.send_message(chat_id, msg)
