from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from config import Config
from pyrogram import Client, filters

from database import (
    get_group_settings, 
    update_group_setting, 
    toggle_group_module, 
    set_user_target, 
    get_user_target, 
    clear_user_target
)

from vgx.module.f_boll_api import format_standings, format_fixtures, format_recent_results_with_spoilers
from vgx.module.f_boll_schedul import send_managed_message
from vgx.database.fdb import get_group_settings, get_user_favorite_team, set_user_favorite_team







def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Standings", callback_data="fb_menu_standings"), InlineKeyboardButton("📅 Fixtures", callback_data="fb_menu_fixtures")],
        [InlineKeyboardButton("⚽ Results (Spoilers)", callback_data="fb_menu_results"), InlineKeyboardButton("⭐ My Team", callback_data="fb_myteam")],
        [InlineKeyboardButton("⚙️ Group Settings", callback_data="cfg_menu")]
    ])

def league_selector_menu(action_prefix: str):
    buttons = []
    row = []
    for code, name in Config.COMPETITIONS.items():
        row.append(InlineKeyboardButton(name, callback_data=f"fb_{action_prefix}_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="fb_main")])
    return InlineKeyboardMarkup(buttons)

def settings_menu(settings: dict, active_target: int = None):
    auto_del = f"{settings.get('auto_delete', 0)}s" if settings.get("auto_delete", 0) > 0 else "OFF"
    pin = "ON ✅" if settings.get("pin_messages", False) else "OFF ❌"
    
    sched_map = {0: "OFF", 60: "1m", 300: "5m", 1200: "20m", 1800: "30m", 3600: "1h"}
    sched_str = sched_map.get(settings.get("live_schedule", 0), "OFF")
    
    target_label = f"🎯 Target: {active_target}" if active_target else "🎯 Target: Current Chat"
    target_row = [InlineKeyboardButton(target_label, callback_data="cfg_target_info")]
    if active_target:
        target_row.append(InlineKeyboardButton("❌ Clear Target", callback_data="cfg_clear_target"))

    return InlineKeyboardMarkup([
        target_row,
        [InlineKeyboardButton(f"⏱ Auto-Del: {auto_del}", callback_data="cfg_cycle_autodel"), InlineKeyboardButton(f"📌 Pin: {pin}", callback_data="cfg_toggle_pin")],
        [InlineKeyboardButton(f"📡 Schedule: {sched_str}", callback_data="cfg_cycle_sched")],
        [InlineKeyboardButton("🧩 Toggle Modules", callback_data="cfg_modules")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="fb_main")]
    ])

def modules_menu(modules: dict):
    fb_status = "✅" if modules.get("football", True) else "❌"
    jumb_status = "✅" if modules.get("jumbotron", True) else "❌"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚽ Football Data: {fb_status}", callback_data="cfg_mod_football")],
        [InlineKeyboardButton(f"📺 Jumbotron / Updates: {jumb_status}", callback_data="cfg_mod_jumbotron")],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="cfg_menu")]
    ])

#====================================================


# --- COMMAND HANDLERS ---
@Client.on_message(filters.command("ftball"))
async def starhrhtt_command(client: Client, message: Message):
    await send_managed_message(
        client,
        message.chat.id,
        "⚽ **Football-Data.org Sports Bot**\nSelect an option below to view standings, fixtures, and results:",
        reply_markup=main_menu()
    )

@Client.on_message(filters.command("standings"))
async def stanfdings_command(client: Client, message: Message):
    code = message.command[1].upper() if len(message.command) > 1 else "PL"
    text = await format_standings(code)
    await send_managed_message(client, message.chat.id, text)

@Client.on_message(filters.command("fixtures"))
async def fixtures_command(client: Client, message: Message):
    code = message.command[1].upper() if len(message.command) > 1 else "PL"
    text = await format_fixtures(code)
    await send_managed_message(client, message.chat.id, text)

@Client.on_message(filters.command("myteam"))
async def myteam_command(client: Client, message: Message):
    fav = await get_user_favorite_team(message.from_user.id)
    if not fav:
        return await message.reply("⭐ You haven't set a favorite team yet! Usage: `/setmyteam <team_name>`")
    await send_managed_message(
        client, message.chat.id, f"⭐ **Your Watchlist Team:** {fav['team_name']}\nNext fixture update coming soon!"
    )

@Client.on_message(filters.command("setmyteam"))
async def set_myteam_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/setmyteam Arsenal`")
    team_name = " ".join(message.command[1:])
    await set_user_favorite_team(message.from_user.id, 57, team_name)
    await message.reply(f"✅ Saved **{team_name}** as your favorite team!")

# --- REGEX CALLBACK QUERY HANDLERS ---
@Client.on_callback_query(filters.regex(r"^fb_(main|menu_.*|stand_.*|fix_.*|res_.*|myteam)$"))
async def sports_callbacks(client: Client, query: CallbackQuery):
    await query.answer()
    data = query.matches[0].group(1)
    chat_id = query.message.chat.id
    
    settings = await get_group_settings(chat_id)
    if not settings.get("modules", {}).get("football", True):
        return await query.answer("🚫 Football module is disabled in this group.", show_alert=True)

    if data == "main":
        await query.message.edit_text("⚽ **Football-Data.org Sports Bot**", reply_markup=main_menu())
        
    elif data == "menu_standings":
        await query.message.edit_text("🏆 Select a Competition:", reply_markup=league_selector_menu("stand"))

    elif data == "menu_fixtures":
        await query.message.edit_text("📅 Select a Competition:", reply_markup=league_selector_menu("fix"))

    elif data == "menu_results":
        await query.message.edit_text("⚽ Select a Competition:", reply_markup=league_selector_menu("res"))

    elif data.startswith("stand_"):
        code = data.replace("stand_", "")
        await query.message.edit_text("⏳ Fetching table...")
        text = await format_standings(code)
        await query.message.edit_text(text, reply_markup=league_selector_menu("stand"))

    elif data.startswith("fix_"):
        code = data.replace("fix_", "")
        await query.message.edit_text("⏳ Fetching fixtures...")
        text = await format_fixtures(code)
        await query.message.edit_text(text, reply_markup=league_selector_menu("fix"))

    elif data.startswith("res_"):
        code = data.replace("res_", "")
        await query.message.edit_text("⏳ Fetching results...")
        text = await format_recent_results_with_spoilers(code)
        await query.message.edit_text(text, reply_markup=league_selector_menu("res"))

    elif data == "myteam":
        fav = await get_user_favorite_team(query.from_user.id)
        if not fav:
            await query.message.edit_text("⭐ No team set. Send `/setmyteam <team_name>` in PM.", reply_markup=main_menu())
        else:
            await query.message.edit_text(f"⭐ **Watchlist:** {fav['team_name']}", reply_markup=main_menu())

#====================================================


@Client.on_message(filters.command("ftarget"))
async def set_target_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/settarget -1001234567890`")
    try:
        target_id = int(message.command[1])
        await set_user_target(message.from_user.id, target_id)
        await message.reply(f"🎯 **Target Chat set to:** `{target_id}`\nSettings adjusted in PM will now apply to this group.")
    except ValueError:
        await message.reply("⚠️ Invalid Group ID. Make sure it is numeric.")

@Client.on_message(filters.command("cleartarget"))
async def clear_target_command(client: Client, message: Message):
    await clear_user_target(message.from_user.id)
    await message.reply("✅ **Target Chat Cleared.** Controls returned to PM.")

# --- REGEX CALLBACK QUERY HANDLERS ---
@Client.on_callback_query(filters.regex(r"^cfg_(menu|target_info|clear_target|cycle_autodel|toggle_pin|cycle_sched|modules|mod_.*)$"))
async def settings_callbacks(client: Client, query: CallbackQuery):
    await query.answer()
    uid = query.from_user.id
    is_pm = query.message.chat.type.name == "PRIVATE"
    
    active_target = await get_user_target(uid) if is_pm else None
    chat_id = active_target if active_target else query.message.chat.id
    action = query.matches[0].group(1)

    if action == "menu":
        settings = await get_group_settings(chat_id)
        await query.message.edit_text(f"⚙️ **Control Panel for:** `{chat_id}`", reply_markup=settings_menu(settings, active_target))

    elif action == "target_info":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="cfg_menu")]])
        await query.message.edit_text(
            "🎯 **Target Chat Controls**\n\nSend `/settarget <group_id>` in PM to manage group options remotely.",
            reply_markup=kb
        )

    elif action == "clear_target":
        await clear_user_target(uid)
        settings = await get_group_settings(query.message.chat.id)
        await query.message.edit_text("✅ Target cleared! Reverted to current chat settings.", reply_markup=settings_menu(settings, None))

    elif action == "cycle_autodel":
        curr = (await get_group_settings(chat_id)).get("auto_delete", 0)
        delays = [0, 30, 300, 400, 2400]
        nxt = delays[(delays.index(curr) + 1) % len(delays)] if curr in delays else 0
        await update_group_setting(chat_id, "auto_delete", nxt)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "toggle_pin":
        curr_pin = (await get_group_settings(chat_id)).get("pin_messages", False)
        await update_group_setting(chat_id, "pin_messages", not curr_pin)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "cycle_sched":
        curr = (await get_group_settings(chat_id)).get("live_schedule", 0)
        scheds = [0, 60, 300, 1200, 1800, 3600]
        nxt = scheds[(scheds.index(curr) + 1) % len(scheds)] if curr in scheds else 0
        await update_group_setting(chat_id, "live_schedule", nxt)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "modules":
        settings = await get_group_settings(chat_id)
        await query.message.edit_text(f"🧩 **Modules Manager**\nTarget ID: `{chat_id}`", reply_markup=modules_menu(settings.get("modules", {})))

    elif action.startswith("mod_"):
        mod_name = action.replace("mod_", "")
        await toggle_group_module(chat_id, mod_name)
        settings = await get_group_settings(chat_id)
        await query.message.edit_reply_markup(reply_markup=modules_menu(settings.get("modules", {})))
