import pytz
from pyrogram import Client, filters
from vgx.database.bday_db import set_user_bday

@Client.on_message(filters.command(["setbirthday", "bdayset"]))
async def set_bdfirthday(client, message):
    # Expected: /birthday set DD/MM Timezone
    args = message.command
    if len(args) < 4:
        return await message.reply(
            "📝 **Set your Birthday!**\n\n"
            "**Usage:** `/bday set DD/MM Timezone`\n"
            "**Example:** `/bday set 25/12 Europe/London`\n"
            "*(If you don't know your timezone, use 'UTC')*"
        )
    
    try:
        date_parts = args[2].split("/")
        day, month = int(date_parts[0]), int(date_parts[1])
        timezone = args[3]
        
        # Validation
        if timezone != "UTC" and timezone not in pytz.all_timezones:
            return await message.reply("❌ Invalid Timezone. Please use a valid IANA timezone (e.g., America/New_York).")
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError
            
    except Exception:
        return await message.reply("❌ Invalid date format. Please use DD/MM.")

    await set_user_bday(message.from_user.id, month, day, timezone)
    await message.reply(f"✅ **Saved!** Your birthday is set to **{day:02d}/{month:02d}** ({timezone}). We'll remember it!")
