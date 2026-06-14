
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from vgx.database.night_db import get_chat, update_chat, add_vip, remove_vip, chats

from timezonefinder import TimezoneFinder
import pytz

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler





def get_settings_kb(data):
    # Visual Toggles
    en = "✅" if data['enabled'] else "❌"
    warn = "✅" if data.get('warning') else "❌"
    clean = "✅" if data.get('auto_clean') else "❌"
    
    # Permission Toggles (What is ALLOWED at night?)
    p = data['perms']
    txt = "🟢" if p['text'] else "🔴"
    med = "🟢" if p['media'] else "🔴"
    stk = "🟢" if p['stickers'] else "🔴"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Night Mode: {en}", callback_data="nm_toggle_main", style=ButtonStyle.SUCCESS)],
        [
            InlineKeyboardButton(f"🕒 Start: {data['night_start']}", callback_data="nm_set_start", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"☀️ End: {data['night_end']}", callback_data="nm_set_end", style=ButtonStyle.PRIMARY)
        ],
        [InlineKeyboardButton(f"🌍 Timezone: {data['timezone']}", callback_data="nm_set_tz", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("--- 🛡 RESTRICTIONS ---", callback_data="ignore", style=ButtonStyle.SUCCESS)],
        [
            InlineKeyboardButton(f"📝Text {txt}", callback_data="nm_perm_text", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"📹 Media {med}", callback_data="nm_perm_media", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(f"🎭 Stickers {stk}", callback_data="nm_perm_stickers", style=ButtonStyle.PRIMARY)
        ],
        [InlineKeyboardButton("--- ⚙️ EXTRAS ---", callback_data="ignore", style=ButtonStyle.SUCCESS)],
        [
            InlineKeyboardButton(f"⚠️ Warning: {warn}", callback_data="nm_toggle_warn", style=ButtonStyle.PRIMARY)
        ],[
            InlineKeyboardButton(f"🧹 Auto-Clean: {clean}", callback_data="nm_toggle_clean", style=ButtonStyle.PRIMARY)
        ],[
            InlineKeyboardButton("🚨 Emergency Unlock", callback_data="nm_emergency", style=ButtonStyle.PRIMARY)
        ],
        [InlineKeyboardButton("❌ Close Menu", callback_data="close", style=ButtonStyle.DANGER)]
    ])

# --- MAIN DASHBOARD ---
@Client.on_message(filters.command("nightmode") & filters.group)
async def open_dashboard(c, m):
    # Only admins
    mem = await c.get_chat_member(m.chat.id, m.from_user.id)
    await m.reply("Only admin can use this.")
    if not mem.privileges: return
    
    data = await get_chat(m.chat.id)
    await m.reply("🌙 **Night Mode Settings**", reply_markup=get_settings_kb(data))

# --- CALLBACK HANDLER (The Button Logic) ---
@Client.on_callback_query(filters.regex(r"^nm_"))
async def nm_callbacks(c, q):
    cid = q.message.chat.id
    # Ensure Admin
    mem = await c.get_chat_member(cid, q.from_user.id)
    if not mem.privileges: return await q.answer("❌ Admins only.")

    data = await get_chat(cid)
    action = q.data
    
    if action == "nm_toggle_main":
        await update_chat(cid, {"enabled": not data['enabled']})
    
    elif action == "nm_toggle_warn":
        await update_chat(cid, {"warning": not data.get('warning')})

    elif action == "nm_toggle_clean":
        await update_chat(cid, {"auto_clean": not data.get('auto_clean')})
        
    elif action == "nm_emergency":
        # Toggle Emergency State
        new_state = not data.get('temp_unlock')
        await update_chat(cid, {"temp_unlock": new_state})
        if new_state:
            await set_day_permissions(c, cid)
            await q.answer("🚨 EMERGENCY UNLOCK ACTIVATED", show_alert=True)
        else:
            await q.answer("🚨 Emergency Unlock Disabled.")

    # Permission Toggles
    elif action.startswith("nm_perm_"):
        p_type = action.split("_")[2] # text, media, stickers
        new_perms = data['perms']
        new_perms[p_type] = not new_perms[p_type]
        await update_chat(cid, {"perms": new_perms})

    # Time Setting (Simple version: Prompt user)
    elif action in ["nm_set_start", "nm_set_end"]:
        await q.answer("✏️ Send the new time (HH:MM) to set.", show_alert=True)
        # You would implement a listener here or use a ForceReply
        # For this snippet, we assume the user knows to use commands like /setnight

    elif action == "nm_set_tz":
        await q.answer("📍 Send your location to auto-detect timezone.", show_alert=True)
    
    elif action == "nm_close":
        await q.message.delete()
        return

    # Refresh Menu
    new_data = await get_chat(cid)
    try: await q.message.edit_reply_markup(get_settings_kb(new_data))
    except: pass

# --- SMART TIMEZONE (Location Based) ---
@Client.on_message(filters.location & filters.group)
async def auto_timezone(c, m):
    # Only if an admin sent it (could be improved with state checks)
    mem = await c.get_chat_member(m.chat.id, m.from_user.id)
    if not mem.privileges: return
    
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=m.location.longitude, lat=m.location.latitude)
    
    if tz_name:
        await update_chat(m.chat.id, {"timezone": tz_name})
        await m.reply(f"✅ Timezone detected and set to: `{tz_name}`")
    else:
        await m.reply("❌ Could not detect timezone.")

# --- VIP COMMANDS ---
@Client.on_message(filters.command("addvip") & filters.group)
async def add_vip_user(c, m):
    if not m.reply_to_message: return await m.reply("Reply to a user to VIP them.")
    user_id = m.reply_to_message.from_user.id
    
    await add_vip(m.chat.id, user_id)
    
    # Apply VIP permission immediately (Allow sending messages even if blocked)
    await c.restrict_chat_member(
        m.chat.id, user_id, 
        ChatPermissions(
            can_send_messages=True, 
            can_send_media_messages=True,
            can_send_other_messages=True
        )
    )
    await m.reply(f"👑 User {m.reply_to_message.from_user.first_name} is now a VIP.")


async def check_schedules(app):
    async for chat in chats.find({"enabled": True}):
        try:
            cid = chat['chat_id']
            tz = pytz.timezone(chat.get('timezone', 'UTC'))
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")
            
            # Times
            start_str = chat['night_start']
            end_str = chat['night_end']
            
            # --- 1. WARNING SYSTEM (5 mins before) ---
            if chat.get('warning'):
                # Calculate 5 mins before start
                h, m = map(int, start_str.split(':'))
                warn_time = (now.replace(hour=h, minute=m, second=0) - timedelta(minutes=5)).strftime("%H:%M")
                
                if current_time == warn_time:
                    await app.send_message(cid, "⚠️ **Notice:**\n\n Night Mode will activate in 5 minutes!")

            # --- 2. NIGHT MODE LOGIC ---
            # Determine if we are in the "Night Window"
            is_night_now = False
            if start_str < end_str:
                is_night_now = start_str <= current_time < end_str
            else: # Cross-midnight (e.g. 23:00 to 06:00)
                is_night_now = current_time >= start_str or current_time < end_str

            # Emergency Override Check
            if chat.get('temp_unlock'):
                if is_night_now: 
                    continue # Skip locking logic if emergency unlocked
                else: 
                    # If morning comes, reset the emergency flag automatically
                    await update_chat(cid, {"temp_unlock": False})

            # State Transition
            prev_state = chat.get('is_night', False)
            
            if is_night_now and not prev_state:
                # -> LOCK GROUP
                await set_night_permissions(app, chat)
                msg = await app.send_message(cid, "🌙 **Night Mode Active. 🌌**\nChat is Closed/restricted. Wait for morning to Message again 😴😪🌝.")
                
                # Pin logic could go here
                
                await update_chat(cid, {"is_night": True, "last_alert_id": msg.id})
                
            elif not is_night_now and prev_state:
                # -> UNLOCK GROUP
                await set_day_permissions(app, cid)
                
                # Auto-Clean: Delete the "Night Mode Active" message
                if chat.get('auto_clean') and chat.get('last_alert_id'):
                    try: await app.delete_messages(cid, chat['last_alert_id'])
                    except: pass
                
                msg = await app.send_message(cid, "☀️ **Good Morning Members! 🍃**\nGroup Chat is opened! Now everyone can message here🙂‍↕️🤭.")
                
                # Schedule deletion of the Morning message (1 hour later)
                # (Simple version: just leave it or use a separate job. We'll skip complex job scheduling for now)
                
                await update_chat(cid, {"is_night": False})

        except Exception as e:
            print(f"Error in {chat.get('chat_id')}: {e}")

async def set_night_permissions(app, chat):
    """Applies the selective permissions defined in DB"""
    p = chat['perms']
    # If p['text'] is True, we ALLOW text. 
    # Telegram ChatPermissions logic: True = Allowed, False = Restricted
    
    perms = ChatPermissions(
        can_send_messages=p['text'],
        can_send_media_messages=p['media'],
        can_send_other_messages=p['stickers'], # GIF/Stickers
        can_add_web_page_previews=p['links'],
        can_send_polls=False,
        can_invite_users=True
    )
    await app.set_chat_permissions(chat['chat_id'], perms)

async def set_day_permissions(app, chat_id):
    """Restores full access"""
    perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_send_polls=True,
        can_invite_users=True
    )
    await app.set_chat_permissions(chat_id, perms)

def start_nm_scheduler(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_schedules, "interval", minutes=1, args=[app])
    scheduler.start()
