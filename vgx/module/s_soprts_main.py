from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from vgx.database.s_highlights_db import get_group_settings, update_group_setting, toggle_group_module, set_user_target, get_user_target, clear_user_target
from vgx.module.s_highlightly_api import format_live_scores, format_highlights, fetch_hl_api
from vgx.module.s_scheduler import send_managed_message






def main_sports_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚽ Football", callback_data="hl_sport_football"), InlineKeyboardButton("🏀 Basketball", callback_data="hl_sport_basketball")],
        [InlineKeyboardButton("🏈 Am. Football", callback_data="hl_sport_american-football"), InlineKeyboardButton("🏒 Hockey", callback_data="hl_sport_hockey")],
        [InlineKeyboardButton("⚾ Baseball", callback_data="hl_sport_baseball"), InlineKeyboardButton("🏏 Cricket", callback_data="hl_sport_cricket")],
        [InlineKeyboardButton("🏉 Rugby", callback_data="hl_sport_rugby"), InlineKeyboardButton("🏐 Volleyball", callback_data="hl_sport_volleyball")],
        [InlineKeyboardButton("🤾‍♂️ Handball", callback_data="hl_sport_handball")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="cfg_menu")]
    ])

def sport_actions_menu(sport: str):
    kb = [
        [InlineKeyboardButton("🔴 Live Scores", callback_data=f"hl_live_{sport}"), InlineKeyboardButton("🎬 Highlights", callback_data=f"hl_high_{sport}")],
        [InlineKeyboardButton("🏆 Standings", callback_data=f"hl_leagues_{sport}")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="hl_main")]
    ]
    return InlineKeyboardMarkup(kb)

def football_leagues_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", callback_data="hl_stand_football_39"), InlineKeyboardButton("🇪🇸 La Liga", callback_data="hl_stand_football_140")],
        [InlineKeyboardButton("🇮🇹 Serie A", callback_data="hl_stand_football_135"), InlineKeyboardButton("🇩🇪 Bundesliga", callback_data="hl_stand_football_78")],
        [InlineKeyboardButton("🇫🇷 Ligue 1", callback_data="hl_stand_football_61"), InlineKeyboardButton("🇪🇺 UCL", callback_data="hl_stand_football_2")],
        [InlineKeyboardButton("⬅️ Back", callback_data="hl_sport_football")]
    ])

def settings_menu(settings: dict, active_target: int = None):
    auto_del = f"{settings.get('auto_delete', 0)}s" if settings.get("auto_delete", 0) > 0 else "OFF"
    pin = "ON ✅" if settings.get("pin_messages", False) else "OFF ❌"
    sched_str = {0: "OFF", 60: "1m", 300: "5m", 1200: "20m", 1800: "30m", 3600: "1h"}.get(settings.get("live_schedule", 0), "OFF")
    
    target_row = [InlineKeyboardButton(f"🎯 Target: {active_target or 'Current'}", callback_data="cfg_target_info")]
    if active_target: target_row.append(InlineKeyboardButton("❌ Clear Target", callback_data="cfg_clear_target"))

    return InlineKeyboardMarkup([
        target_row,
        [InlineKeyboardButton(f"⏱ Auto-Del: {auto_del}", callback_data="cfg_cycle_autodel"), InlineKeyboardButton(f"📌 Pin: {pin}", callback_data="cfg_toggle_pin")],
        [InlineKeyboardButton(f"📡 Schedule: {sched_str}", callback_data="cfg_cycle_sched")],
        [InlineKeyboardButton("🧩 Toggle Modules", callback_data="cfg_modules")],
        [InlineKeyboardButton("⬅️ Back", callback_data="hl_main")]
    ])

def modules_menu(modules: dict):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚽ Football {'✅' if modules.get('football', True) else '❌'}", callback_data="cfg_mod_football"),
         InlineKeyboardButton(f"🏀 Basket {'✅' if modules.get('basketball', True) else '❌'}", callback_data="cfg_mod_basketball")],
        [InlineKeyboardButton(f"🎬 Highlights {'✅' if modules.get('highlights', True) else '❌'}", callback_data="cfg_mod_highlights"),
         InlineKeyboardButton(f"📊 Odds {'✅' if modules.get('odds', True) else '❌'}", callback_data="cfg_mod_odds")],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="cfg_menu")]
    ])

#====================================================



@Client.on_message(filters.command("sports"))
async def starhyt_sports(client: Client, message: Message):
    await send_managed_message(
        client, message.chat.id, 
        "⚡ **Highlightly Unified Sports Engine**\nSelect a sport to explore live data, odds, tracking, and videos:",
        reply_markup=main_sports_menu()
    )

# Direct commands for power users
@Client.on_message(filters.command("live"))
async def cmd_live(client: Client, message: Message):
    sport = message.command[1] if len(message.command) > 1 else "football"
    await send_managed_message(client, message.chat.id, await format_live_scores(sport))

@Client.on_message(filters.command("player"))
async def cmd_player(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply("Usage: `/player <sport> <player_id>` (e.g. `/player football 123`)")
    
    # Example Highlightly Player tracking endpoint
    sport, pid = message.command[1], message.command[2]
    data = await fetch_hl_api(f"{sport}/players/{pid}")
    if "data" in data:
        p = data["data"]
        txt = f"👤 **{p['name']}** ({p['team']})\nStats: {p.get('season_stats', 'N/A')}\nInjury status: {p.get('injuries', 'Fit')}"
        await send_managed_message(client, message.chat.id, txt)

# Regex Callbacks for Highlightly Data
@Client.on_callback_query(filters.regex(r"^hl_(main|sport_.*|live_.*|high_.*|leagues_.*|stand_.*_.*)$"))
async def sports_callbacks(client: Client, query: CallbackQuery):
    await query.answer()
    data = query.matches[0].group(1)
    chat_id = query.message.chat.id
    settings = await get_group_settings(chat_id)
    modules = settings.get("modules", {})

    try:
        if data == "main":
            await query.message.edit_text("⚡ **Highlightly Unified Sports Engine**", reply_markup=main_sports_menu())
            
        elif data.startswith("sport_"):
            sport = data.replace("sport_", "")
            if not modules.get(sport, True): return await query.answer("🚫 Module Disabled", show_alert=True)
            await query.message.edit_text(f"🏅 **{sport.upper()} HUB**", reply_markup=sport_actions_menu(sport))

        elif data.startswith("live_"):
            sport = data.replace("live_", "")
            await query.message.edit_text("⏳ Fetching real-time data...")
            await query.message.edit_text(await format_live_scores(sport), reply_markup=sport_actions_menu(sport))

        elif data.startswith("high_"):
            if not modules.get("highlights", True): return await query.answer("🚫 Highlights Disabled", show_alert=True)
            sport = data.replace("high_", "")
            await query.message.edit_text("⏳ Searching video library...")
            await query.message.edit_text(await format_highlights(sport), disable_web_page_preview=False, reply_markup=sport_actions_menu(sport))

        elif data.startswith("leagues_football"):
            await query.message.edit_text("🏆 Select a Football League:", reply_markup=football_leagues_menu())

        elif data.startswith("stand_"):
            _, sport, lg_id = data.split("_")
            await query.message.edit_text(f"⏳ Fetching {sport} standings for league {lg_id}...")
            # Implement your specific standings endpoint wrapper here
            await query.message.edit_text(f"🏆 Data fetched for League {lg_id} via Highlightly", reply_markup=football_leagues_menu())

    except Exception as e:
        await query.message.edit_text(f"⚠️ API Error: {str(e)}")

#====================================================

@Client.on_message(filters.command("s_settarget"))
async def set_tarvhget_command(client: Client, message: Message):
    try:
        target_id = int(message.command[1])
        await set_user_target(message.from_user.id, target_id)
        await message.reply_text(f"✅ **Target Group set:** `{target_id}`\nSettings changed here will apply to the group.")
    except (IndexError, ValueError):
        await message.reply_text("⚠️ **Usage:** `/settarget <group_id>`")

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
        await query.message.edit_text(f"⚙️ **Settings for:** `{chat_id}`", reply_markup=settings_menu(settings, active_target))

    elif action == "target_info":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="cfg_menu")]])
        await query.message.edit_text("🎯 **Target Group Setup**\nAdd bot to group, then PM me `/settarget <group_id>`.", reply_markup=kb)

    elif action == "clear_target":
        await clear_user_target(uid)
        settings = await get_group_settings(query.message.chat.id)
        await query.message.edit_text("✅ **Target Cleared!** Managing PM settings.", reply_markup=settings_menu(settings, None))

    elif action == "cycle_autodel":
        curr = (await get_group_settings(chat_id)).get("auto_delete", 0)
        cycle = [0, 30, 300, 400, 2400]
        nxt = cycle[(cycle.index(curr) + 1) % len(cycle)] if curr in cycle else 0
        await update_group_setting(chat_id, "auto_delete", nxt)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "toggle_pin":
        new_pin = not (await get_group_settings(chat_id)).get("pin_messages", False)
        await update_group_setting(chat_id, "pin_messages", new_pin)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "cycle_sched":
        curr = (await get_group_settings(chat_id)).get("live_schedule", 0)
        cycle = [0, 60, 300, 1200, 1800, 3600]
        nxt = cycle[(cycle.index(curr) + 1) % len(cycle)] if curr in cycle else 0
        await update_group_setting(chat_id, "live_schedule", nxt)
        await query.message.edit_reply_markup(reply_markup=settings_menu(await get_group_settings(chat_id), active_target))

    elif action == "modules":
        settings = await get_group_settings(chat_id)
        await query.message.edit_text(f"🧩 **Modules Configuration**\nID: `{chat_id}`", reply_markup=modules_menu(settings.get("modules", {})))

    elif action.startswith("mod_"):
        mod_name = action.replace("mod_", "")
        await toggle_group_module(chat_id, mod_name)
        settings = await get_group_settings(chat_id)
        await query.message.edit_reply_markup(reply_markup=modules_menu(settings.get("modules", {})))
