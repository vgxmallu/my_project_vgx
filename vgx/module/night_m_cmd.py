
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from vgx.database.night_db import get_chat, update_chat, add_vip, remove_vip
from vgx.module.night_m_keybord import get_settings_kb
from timezonefinder import TimezoneFinder
import pytz
from vgx.module.night_schedul import set_day_permissions
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

