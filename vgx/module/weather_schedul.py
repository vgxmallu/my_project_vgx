from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from vgx.database.weather_db import get_weather_settings, get_groups_due_for_weather, update_weather_settings

def build_weather_kb(chat_id: int, s: dict):
    en_txt = "🟢 Module: ON" if s["enabled"] else "🔴 Module: OFF"
    pin_txt = "📌 Auto-Pin: ON" if s["pin"] else "📌 Auto-Pin: OFF"
    time_txt = f"⏱ Drop Time: {s['hour']:02d}:00" # Formats 7 as 07:00

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(en_txt, callback_data=f"wth_tgl_{chat_id}")],
        [
            InlineKeyboardButton(time_txt, callback_data=f"wth_time_{chat_id}"),
            InlineKeyboardButton(pin_txt, callback_data=f"wth_pin_{chat_id}")
        ]
    ])

@Client.on_message(filters.command("weathertarget") & filters.private)
async def target_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/weathertarget -100123456789`")
    try:
        chat_id = int(message.command[1])
        s = await get_weather_settings(chat_id)
        
        text = (
            f"🌤 **Morning Briefing Dashboard**\n"
            f"🎯 **Target Group:** `{chat_id}`\n"
            f"🌍 **Target City:** `{s['city'].title()}`\n\n"
            f"*(To change the city, type: `/setcity {chat_id} NewCityName`)*\n\n"
            f"Customize your schedule below:"
        )
        await message.reply(text, reply_markup=build_weather_kb(chat_id, s))
    except ValueError:
        await message.reply("❌ Invalid Group ID.")

@Client.on_message(filters.command("setcity") & filters.private)
async def set_city_cmd(client, message):
    # Usage: /setcity -100123456789 London
    if len(message.command) < 3:
        return await message.reply("❌ **Usage:** `/setcity <chat_id> <CityName>`")
        
    try:
        chat_id = int(message.command[1])
        new_city = " ".join(message.command[2:])
        
        await update_weather_settings(chat_id, city=new_city)
        await message.reply(f"✅ Target city for `{chat_id}` updated to **{new_city.title()}**!")
    except ValueError:
        await message.reply("❌ Invalid Group ID.")

@Client.on_callback_query(filters.regex(r"^wth_(?P<action>tgl|time|pin)_(?P<chat_id>-?\d+)$"))
async def weather_ui_router(client, query):
    action = query.matches[0].group("action")
    chat_id = int(query.matches[0].group("chat_id"))
    s = await get_weather_settings(chat_id)
    
    if action == "tgl":
        await update_weather_settings(chat_id, enabled=not s["enabled"])
    elif action == "pin":
        await update_weather_settings(chat_id, pin=not s["pin"])
    elif action == "time":
        # Cycle the hour from 0 to 23
        next_hour = (s["hour"] + 1) % 24
        await update_weather_settings(chat_id, hour=next_hour)

    s = await get_weather_settings(chat_id)
    text = (
        f"🌤 **Morning Briefing Dashboard**\n"
        f"🎯 **Target Group:** `{chat_id}`\n"
        f"🌍 **Target City:** `{s['city'].title()}`\n\n"
        f"*(To change the city, type: `/setcity {chat_id} NewCityName`)*\n\n"
        f"Customize your schedule below:"
    )
    await query.message.edit_text(text, reply_markup=build_weather_kb(chat_id, s))


import asyncio
import aiohttp
from datetime import datetime
WEATHER_API_KEY = "a564a913f3e791f99d8748a12420596c"
async def fetch_weather(city: str) -> dict:
    """Fetches live weather data from OpenWeatherMap API."""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Determine a fun emoji based on the weather condition
                    condition = data['weather'][0]['main'].lower()
                    emoji = "☀️"
                    if "rain" in condition or "drizzle" in condition: emoji = "🌧"
                    elif "cloud" in condition: emoji = "☁️"
                    elif "snow" in condition: emoji = "❄️"
                    elif "thunderstorm" in condition: emoji = "⛈"

                    return {
                        "temp": round(data['main']['temp']),
                        "feels_like": round(data['main']['feels_like']),
                        "humidity": data['main']['humidity'],
                        "desc": data['weather'][0]['description'].title(),
                        "wind": round(data['wind']['speed'] * 3.6, 1), # Convert m/s to km/h
                        "emoji": emoji,
                        "success": True
                    }
                return {"success": False}
    except Exception as e:
        print(f"Weather API Error: {e}")
        return {"success": False}

async def morning_briefing_loop(app):
    while True:
        try:
            # We use local server time. If your server is in India, this matches IST.
            now = datetime.now()
            current_hour = now.hour
            today_str = now.strftime("%Y-%m-%d")
            
            # Fetch groups waiting for a drop exactly at this hour
            groups = await get_groups_due_for_weather(current_hour, today_str)
            
            for group in groups:
                chat_id = group["chat_id"]
                city = group["city"]
                
                weather = await fetch_weather(city)
                
                if weather["success"]:
                    caption = (
                        f"🌅 **Good Morning, {city.title()}!**\n"
                        "━━━━━━━━━━━━━━\n"
                        f"{weather['emoji']} **Forecast:** {weather['desc']}\n"
                        f"🌡 **Temperature:** {weather['temp']}°C *(Feels like {weather['feels_like']}°C)*\n"
                        f"💧 **Humidity:** {weather['humidity']}%\n"
                        f"💨 **Wind:** {weather['wind']} km/h\n"
                        "━━━━━━━━━━━━━━\n"
                        "Have a great day ahead! ✨"
                    )
                    
                    try:
                        # 1. Send the Message
                        msg = await app.send_message(chat_id, caption)
                        
                        # 2. Pin the Message
                        if group.get("pin"):
                            try:
                                await msg.pin(disable_notification=False)
                            except Exception:
                                pass # Bot lacks pinning permissions
                                
                        # 3. Mark Today as Complete in Database
                        await update_weather_settings(chat_id, last_sent_date=today_str)
                        
                    except Exception as e:
                        print(f"Failed to send weather to {chat_id}: {e}")
                        
        except Exception as e:
            print(f"Weather Scheduler Error: {e}")
            
        await asyncio.sleep(60) # Check the clock every 60 seconds
