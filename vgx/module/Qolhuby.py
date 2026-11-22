import os
import time
from datetime import datetime, timezone
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from vgx import app

try:
    from config import Config
except ImportError:
    Config = None

MONGO_URI = (
    getattr(Config, "MONGO_URL", None)
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
MONGO_DB_NAME = (
    getattr(Config, "DB_NAME", None)
    or os.getenv("DB_NAME")
)

DEFAULT_HUB_CFG = {
    "report_enabled": True,
    "report_cooldown_sec": 60,
    "delete_reported_on_action": True,
    "mod_log_chat_id": None,
    "dm_hub_enabled": True,
    "warn_limit": 3,
}

MUTE_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

NORMAL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False
_report_cooldowns: dict[tuple[int, int, int], float] = {}


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "Unknown"
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _build_msg_link(chat_id: int, username: str | None, message_id: int) -> str | None:
    if not message_id:
        return None
    if username:
        return f"https://t.me/{username}/{message_id}"
    raw = str(chat_id)
    if raw.startswith("-100"):
        return f"https://t.me/c/{raw[4:]}/{message_id}"
    return None


def _truncate(text: str, limit: int = 3800) -> str:
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + "\n\n_...truncated_"


async def is_admin(client: Client, chat_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception:
        return False


async def get_db():
    global _mongo_client, _indexes_ready
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(MONGO_URI)
    db = _mongo_client[MONGO_DB_NAME]
    if not _indexes_ready:
        await db["qol_groups"].create_indexes([IndexModel([("chat_id", 1)], unique=True)])
        await db["qol_members"].create_indexes([
            IndexModel([("chat_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("chat_id", 1), ("msg_count", -1)]),
        ])
        await db["qol_incidents"].create_indexes([
            IndexModel([("incident_id", 1)], unique=True),
            IndexModel([("chat_id", 1), ("status", 1), ("created_at", -1)]),
        ])
        _indexes_ready = True
    return db


async def get_hub_cfg(chat_id: int, title: str | None = None, username: str | None = None) -> dict:
    db = await get_db()
    col = db["qol_groups"]
    doc = await col.find_one({"chat_id": chat_id})
    out = dict(DEFAULT_HUB_CFG)
    if doc:
        for k in DEFAULT_HUB_CFG:
            if k in doc and doc[k] is not None:
                out[k] = doc[k]
    out["chat_id"] = chat_id
    out["title"] = title or (doc.get("title") if doc else None) or str(chat_id)
    out["username"] = username if username is not None else (doc.get("username") if doc else None)

    if doc is None:
        await col.update_one(
            {"chat_id": chat_id},
            {"$set": {**out, "updated_at": time.time()}},
            upsert=True,
        )
    else:
        patch: dict = {}
        if title and doc.get("title") != title:
            patch["title"] = title
        if username and doc.get("username") != username:
            patch["username"] = username
        if patch:
            await col.update_one({"chat_id": chat_id}, {"$set": patch})
    return out


async def update_hub_cfg(chat_id: int, **kwargs) -> dict:
    db = await get_db()
    col = db["qol_groups"]
    current = await get_hub_cfg(chat_id)
    for k, v in kwargs.items():
        if k in DEFAULT_HUB_CFG:
            current[k] = v
    current["updated_at"] = time.time()
    await col.update_one({"chat_id": chat_id}, {"$set": current}, upsert=True)
    return current


async def list_managed_groups() -> list[dict]:
    db = await get_db()
    cursor = db["qol_groups"].find({}).sort("title", 1)
    return [doc async for doc in cursor]


# ==========================================
# --- MEMBER CONTEXT & STATS ---
# ==========================================

async def touch_member_join(chat_id: int, user_id: int, name: str, username: str | None = None) -> None:
    db = await get_db()
    col = db["qol_members"]
    now = time.time()
    existing = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not existing:
        await col.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "name": (name or str(user_id))[:64],
            "username": username,
            "joined_at": now,
            "last_seen_at": now,
            "msg_count": 0,
            "warns": 0,
            "verified": False,
            "verified_at": None,
        })
    else:
        patch: dict = {
            "name": (name or existing.get("name") or str(user_id))[:64],
            "last_seen_at": now,
        }
        if username:
            patch["username"] = username
        if not existing.get("joined_at"):
            patch["joined_at"] = now
        await col.update_one({"_id": existing["_id"]}, {"$set": patch})


async def touch_member_message(chat_id: int, user_id: int, name: str, username: str | None = None) -> None:
    db = await get_db()
    col = db["qol_members"]
    now = time.time()
    patch: dict = {
        "name": (name or str(user_id))[:64],
        "last_seen_at": now,
    }
    if username:
        patch["username"] = username
    await col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": patch,
            "$inc": {"msg_count": 1},
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
                "joined_at": now,
                "warns": 0,
                "verified": False,
                "verified_at": None,
            },
        },
        upsert=True,
    )


async def get_member_context(chat_id: int, user_id: int, name: str = "", username: str | None = None) -> dict:
    db = await get_db()
    doc = await db["qol_members"].find_one({"chat_id": chat_id, "user_id": user_id}) or {}
    smart_warn_doc = await db["smart_warns"].find_one({"chat_id": chat_id, "user_id": user_id})
    prob_doc = await db["smart_probation"].find_one({"chat_id": chat_id, "user_id": user_id})

    warns = int(doc.get("warns", 0))
    if smart_warn_doc and int(smart_warn_doc.get("points", 0)) > warns:
        warns = int(smart_warn_doc.get("points", 0))

    verified = bool(doc.get("verified", False))
    if not verified and prob_doc is None and doc.get("joined_at"):
        if int(doc.get("msg_count", 0)) >= 3:
            verified = True

    return {
        "chat_id": chat_id,
        "user_id": user_id,
        "name": doc.get("name") or name or str(user_id),
        "username": doc.get("username") or username,
        "joined_at": doc.get("joined_at"),
        "last_seen_at": doc.get("last_seen_at"),
        "msg_count": int(doc.get("msg_count", 0)),
        "warns": warns,
        "verified": verified,
    }


async def set_member_verified(chat_id: int, user_id: int, verified: bool = True) -> None:
    db = await get_db()
    now = time.time()
    await db["qol_members"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "verified": verified,
                "verified_at": now if verified else None,
                "last_seen_at": now,
            },
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
                "name": str(user_id),
                "joined_at": now,
                "msg_count": 0,
                "warns": 0,
            },
        },
        upsert=True,
    )
    if verified:
        await db["smart_probation"].delete_one({"chat_id": chat_id, "user_id": user_id})


async def add_member_warn(chat_id: int, user_id: int, delta: int = 1) -> int:
    db = await get_db()
    now = time.time()
    doc = await db["qol_members"].find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$inc": {"warns": delta},
            "$set": {"last_seen_at": now},
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
                "name": str(user_id),
                "joined_at": now,
                "msg_count": 0,
                "verified": False,
            },
        },
        upsert=True,
        return_document=True,
    )
    new_w = max(0, int((doc or {}).get("warns", 0)))
    if new_w != int((doc or {}).get("warns", 0)):
        await db["qol_members"].update_one({"chat_id": chat_id, "user_id": user_id}, {"$set": {"warns": new_w}})
    return new_w


# ==========================================
# --- UI BUILDERS (COLOR/STATUS CODED) ---
# ==========================================

async def build_whois_card(
    client: Client, chat_id: int, group_title: str, target_id: int, viewer_is_admin: bool
) -> tuple[str, InlineKeyboardMarkup]:
    cfg = await get_hub_cfg(chat_id, title=group_title)
    try:
        u = await client.get_users(target_id)
        display_name = u.first_name or str(target_id)
        uname = u.username
    except Exception:
        display_name = str(target_id)
        uname = None

    ctx = await get_member_context(chat_id, target_id, name=display_name, username=uname)
    ver_badge = "🟢 Verified ✅" if ctx["verified"] else "🟡 Unverified / New"
    handle_str = f"@{ctx['username']}" if ctx.get("username") else "None"
    warn_lim = int(cfg.get("warn_limit", 3))

    text = (
        f"🪪 **Member Context — {ctx['name']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **User ID:** `{target_id}` ({handle_str})\n"
        f"• **Group:** {group_title}\n"
        f"• **Joined:** `{_fmt_ts(ctx['joined_at'])}`\n"
        f"• **Last Active:** `{_fmt_ts(ctx['last_seen_at'])}`\n"
        f"• **Messages Logged:** `{ctx['msg_count']}`\n"
        f"• **Warnings:** `{ctx['warns']}/{warn_lim}`\n"
        f"• **Verification:** {ver_badge}"
    )

    rows: list[list[InlineKeyboardButton]] = []
    if viewer_is_admin:
        rows.append([
            InlineKeyboardButton("⚠️ Warn", callback_data=f"qol_act_warn_{chat_id}_{target_id}_0"),
            InlineKeyboardButton("🔇 Mute 1h", callback_data=f"qol_act_mute_{chat_id}_{target_id}_0"),
            InlineKeyboardButton("🔴 Ban", callback_data=f"qol_act_ban_{chat_id}_{target_id}_0"),
        ])
        rows.append([
            InlineKeyboardButton(
                "🟢 Mark Verified" if not ctx["verified"] else "🟡 Unverify",
                callback_data=f"qol_ver_{chat_id}_{target_id}_{0 if ctx['verified'] else 1}",
            ),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"qol_who_{chat_id}_{target_id}"),
        ])
    rows.append([InlineKeyboardButton("✖️ Close", callback_data="qol_close")])
    return text, InlineKeyboardMarkup(rows)


async def build_dm_group_picker(client: Client, admin_id: int) -> tuple[str, InlineKeyboardMarkup]:
    groups = await list_managed_groups()
    allowed: list[dict] = []
    for g in groups:
        gid = g.get("chat_id")
        if gid is not None and await is_admin(client, int(gid), admin_id):
            allowed.append(g)

    if not allowed:
        text = (
            "🎛️ **DM Control Center**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "No admin groups registered yet.\n\n"
            "Run `/hub` inside your group first to register it, then control switches here in DM."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="qol_dm_home"),
                InlineKeyboardButton("✖️ Close", callback_data="qol_close"),
            ]
        ])
        return text, kb

    db = await get_db()
    lines = [
        "🎛️ **DM Control Center — Select Group**\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        "Pick a group below to manage settings and open incidents:\n",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for g in allowed[:12]:
        gid = int(g["chat_id"])
        gtitle = g.get("title") or str(gid)
        open_inc = await db["qol_incidents"].count_documents({"chat_id": gid, "status": "open"})
        rep_dot = "🟢" if g.get("report_enabled", True) else "🔴"
        inc_tag = f" • 🚨 {open_inc} open" if open_inc else ""
        lines.append(f"• {rep_dot} **{gtitle}** (`{gid}`){inc_tag}")
        rows.append([
            InlineKeyboardButton(
                f"{rep_dot} {gtitle[:24]}{' 🚨' if open_inc else ''}",
                callback_data=f"qol_dm_grp_{gid}",
            )
        ])

    rows.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="qol_dm_home"),
        InlineKeyboardButton("✖️ Close", callback_data="qol_close"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def build_dm_group_dashboard(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    cfg = await get_hub_cfg(chat_id)
    db = await get_db()
    open_incidents = await db["qol_incidents"].count_documents({"chat_id": chat_id, "status": "open"})
    total_members = await db["qol_members"].count_documents({"chat_id": chat_id})

    rep_status = "🟢 Reports ON" if cfg.get("report_enabled", True) else "🔴 Reports OFF"
    del_status = "🟢 Auto-Del ON" if cfg.get("delete_reported_on_action", True) else "🟡 Keep Msg"
    dm_status = "🟢 DM Hub ON" if cfg.get("dm_hub_enabled", True) else "🔴 DM Hub OFF"
    log_chat = cfg.get("mod_log_chat_id")
    log_label = f"`{log_chat}`" if log_chat else "_Group Admins DM_"

    text = (
        f"🎛️ **Control Panel — {cfg['title']}** (`{chat_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Incident `/report`:** {rep_status}\n"
        f"• **Delete on Mod Action:** {del_status}\n"
        f"• **DM Control Hub:** {dm_status}\n"
        f"• **Report Destination:** {log_label}\n"
        f"• **Open Incidents:** `{open_incidents}` • **Tracked Members:** `{total_members}`"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 Reports: ON" if cfg.get("report_enabled", True) else "🔴 Reports: OFF",
                callback_data=f"qol_tog_{chat_id}_report",
            ),
            InlineKeyboardButton(
                "🟢 Auto-Del: ON" if cfg.get("delete_reported_on_action", True) else "🟡 Auto-Del: OFF",
                callback_data=f"qol_tog_{chat_id}_del",
            ),
        ],
        [
            InlineKeyboardButton(
                "🟢 DM Hub: ON" if cfg.get("dm_hub_enabled", True) else "🔴 DM Hub: OFF",
                callback_data=f"qol_tog_{chat_id}_dm",
            ),
            InlineKeyboardButton(
                "📍 Use This DM as Log" if log_chat != chat_id else "📍 Clear Log Chat",
                callback_data=f"qol_setlog_{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(f"🚨 Open ({open_incidents})", callback_data=f"qol_mlog_{chat_id}_open_0"),
            InlineKeyboardButton("📜 Mod Log", callback_data=f"qol_mlog_{chat_id}_all_0"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"qol_dm_grp_{chat_id}"),
        ],
        [
            InlineKeyboardButton("⬅️ All Groups", callback_data="qol_dm_home"),
            InlineKeyboardButton("✖️ Close", callback_data="qol_close"),
        ],
    ])
    return text, kb


async def build_incident_log_card(
    chat_id: int, filter_mode: str = "all", page: int = 0, page_size: int = 5
) -> tuple[str, InlineKeyboardMarkup]:
    mode = filter_mode if filter_mode in {"all", "open", "resolved"} else "all"
    cfg = await get_hub_cfg(chat_id)
    db = await get_db()
    col = db["qol_incidents"]

    query: dict = {"chat_id": chat_id}
    if mode in {"open", "resolved"}:
        query["status"] = mode

    open_cnt = await col.count_documents({"chat_id": chat_id, "status": "open"})
    res_cnt = await col.count_documents({"chat_id": chat_id, "status": "resolved"})
    total = await col.count_documents(query)
    max_page = max(0, (total - 1) // page_size) if total else 0
    page = max(0, min(page, max_page))

    cursor = col.find(query).sort("created_at", -1).skip(page * page_size).limit(page_size)
    docs = [d async for d in cursor]

    mode_label = {"all": "All Incidents", "open": "Open Incidents", "resolved": "Resolved Incidents"}[mode]
    lines = [
        f"📜 **Incident Mod Log — {cfg['title']}**",
        f"Filter: **{mode_label}** • Page `{page + 1}/{max_page + 1}` (`🚨 {open_cnt} open` | `✅ {res_cnt} resolved`)",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not docs:
        lines.append(f"_No {mode if mode != 'all' else ''} incidents found._")
    else:
        for item in docs:
            iid = item.get("incident_id", "inc")
            st = item.get("status", "open")
            badge = "🚨 OPEN" if st == "open" else "✅ RESOLVED"
            tid = item.get("target_id")
            tname = item.get("target_name") or str(tid)
            reason = item.get("reason") or "no reason"
            ts_str = _fmt_ts(item.get("created_at"))
            res_note = f" — _{item.get('resolution')}_" if st == "resolved" and item.get("resolution") else ""
            lines.append(f"• {badge} `{iid}` | **{tname}** (`{tid}`){res_note}")
            lines.append(f"  Reason: _{reason}_ • `{ts_str}`")

    filter_row = [
        InlineKeyboardButton(
            f"{'• ' if mode == 'all' else ''}📜 All",
            callback_data=f"qol_mlog_{chat_id}_all_0",
        ),
        InlineKeyboardButton(
            f"{'• ' if mode == 'open' else ''}🚨 Open ({open_cnt})",
            callback_data=f"qol_mlog_{chat_id}_open_0",
        ),
        InlineKeyboardButton(
            f"{'• ' if mode == 'resolved' else ''}✅ Resolved ({res_cnt})",
            callback_data=f"qol_mlog_{chat_id}_resolved_0",
        ),
    ]

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"qol_mlog_{chat_id}_{mode}_{page - 1}"))
    nav_row.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"qol_mlog_{chat_id}_{mode}_{page}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"qol_mlog_{chat_id}_{mode}_{page + 1}"))

    kb = InlineKeyboardMarkup([
        filter_row,
        nav_row,
        [
            InlineKeyboardButton("⚙️ Control Panel", callback_data=f"qol_dm_grp_{chat_id}"),
            InlineKeyboardButton("✖️ Close", callback_data="qol_close"),
        ],
    ])
    return "\n".join(lines), kb


def build_incident_keyboard(
    incident_id: str, chat_id: int, target_id: int, msg_id: int, link: str | None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("🗑️ Del Msg", callback_data=f"qol_inc_act_{incident_id}_del"),
            InlineKeyboardButton("⚠️ Warn", callback_data=f"qol_inc_act_{incident_id}_warn"),
            InlineKeyboardButton("🔇 Mute 1h", callback_data=f"qol_inc_act_{incident_id}_mute"),
            InlineKeyboardButton("🔴 Ban", callback_data=f"qol_inc_act_{incident_id}_ban"),
        ],
        [
            InlineKeyboardButton("🪪 Whois", callback_data=f"qol_who_{chat_id}_{target_id}"),
            InlineKeyboardButton("✅ Dismiss", callback_data=f"qol_inc_act_{incident_id}_dismiss"),
        ],
    ]
    if link:
        rows.insert(1, [InlineKeyboardButton("🔗 Jump to Message", url=link)])
    return InlineKeyboardMarkup(rows)


# ==========================================
# --- ACTIVITY TRACKER HOOK ---
# ==========================================

@app.on_message(filters.new_chat_members)
async def on_new_members_context(client: Client, message: Message):
    chat_id = message.chat.id
    await get_hub_cfg(chat_id, title=message.chat.title, username=message.chat.username)
    for m in message.new_chat_members:
        if m.is_bot:
            continue
        await touch_member_join(chat_id, m.id, m.first_name or str(m.id), username=m.username)


@app.on_message(filters.group & ~filters.service, group=4)
async def on_group_msg_context(client: Client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    await touch_member_message(
        message.chat.id,
        message.from_user.id,
        message.from_user.first_name or str(message.from_user.id),
        username=message.from_user.username,
    )


# ==========================================
# --- COMMANDS: DM HUB, /MODLOG, /REPORT, /WHOIS ---
# ==========================================

@app.on_message(filters.command(["hub", "dmhub"]) & filters.private)
async def cmd_dm_hub(client: Client, message: Message):
    if not message.from_user:
        return
    text, kb = await build_dm_group_picker(client, message.from_user.id)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["hub"]) & filters.group)
async def cmd_group_hub_shortcut(client: Client, message: Message):
    chat_id = message.chat.id
    cfg = await get_hub_cfg(chat_id, title=message.chat.title, username=message.chat.username)
    me = await client.get_me()
    bot_user = me.username or ""
    deep_url = f"https://t.me/{bot_user}" if bot_user else None

    rows: list[list[InlineKeyboardButton]] = []
    if deep_url:
        rows.append([InlineKeyboardButton("🎛️ Open DM Control Center", url=deep_url)])
    rows.append([InlineKeyboardButton("✖️ Close", callback_data="qol_close")])

    await message.reply_text(
        f"🎛️ **{cfg['title']}** settings are managed in Private DM to keep the chat clean.\n"
        f"Send `/hub` in DM with the bot to toggle switches and review reports.",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command(["modlog"]) & filters.group)
async def cmd_group_modlog(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)
    await get_hub_cfg(chat_id, title=message.chat.title, username=message.chat.username)
    text, kb = await build_incident_log_card(chat_id, filter_mode="all", page=0)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["modlog"]) & filters.private)
async def cmd_pm_modlog(client: Client, message: Message):
    actor_id = message.from_user.id if message.from_user else None
    if not actor_id:
        return

    args = message.command[1:]
    if not args:
        text, kb = await build_dm_group_picker(client, actor_id)
        return await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    raw = args[0].strip()
    try:
        lookup: int | str = int(raw) if raw.lstrip("-").isdigit() else raw
        chat_obj = await client.get_chat(lookup)
        gid = chat_obj.id
    except Exception as exc:
        return await message.reply_text(f"❌ Could not resolve group `{raw}`: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    if not await is_admin(client, gid, actor_id):
        return await message.reply_text("⛔ You are not an admin in that group.", parse_mode=ParseMode.MARKDOWN)

    mode = args[1].lower() if len(args) > 1 and args[1].lower() in {"all", "open", "resolved"} else "all"
    text, kb = await build_incident_log_card(gid, filter_mode=mode, page=0)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["report"]) & filters.group)
async def cmd_incident_report(client: Client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    chat_id = message.chat.id
    cfg = await get_hub_cfg(chat_id, title=message.chat.title, username=message.chat.username)
    if not cfg.get("report_enabled", True):
        return await message.reply_text("🔴 `/report` is currently disabled in this group.", parse_mode=ParseMode.MARKDOWN)

    replied = message.reply_to_message
    if not replied or not replied.from_user:
        return await message.reply_text(
            "💡 Reply to the rule-breaking message with `/report [reason]`.",
            parse_mode=ParseMode.MARKDOWN,
        )

    reporter = message.from_user
    target = replied.from_user
    if target.id == reporter.id:
        return await message.reply_text("⚠️ You cannot report your own message.", parse_mode=ParseMode.MARKDOWN)

    now = time.time()
    cd_sec = int(cfg.get("report_cooldown_sec", 60))
    cd_key = (chat_id, reporter.id, target.id)
    last_rep = _report_cooldowns.get(cd_key, 0.0)
    if (now - last_rep) < cd_sec:
        rem = int(cd_sec - (now - last_rep)) + 1
        return await message.reply_text(f"⏳ Please wait `{rem}s` before reporting this user again.", parse_mode=ParseMode.MARKDOWN)
    _report_cooldowns[cd_key] = now

    reason = ""
    if message.text and len(message.text.split(None, 1)) > 1:
        reason = message.text.split(None, 1)[1].strip()[:240]

    snippet = (replied.text or replied.caption or "[Non-text / Media message]").strip()
    if len(snippet) > 350:
        snippet = snippet[:350] + "..."

    link = _build_msg_link(chat_id, message.chat.username, replied.id)
    incident_id = f"inc_{int(now * 1000)}"

    db = await get_db()
    await db["qol_incidents"].insert_one({
        "incident_id": incident_id,
        "chat_id": chat_id,
        "chat_title": cfg["title"],
        "reporter_id": reporter.id,
        "target_id": target.id,
        "target_name": target.first_name or str(target.id),
        "message_id": replied.id,
        "snippet": snippet,
        "link": link,
        "reason": reason,
        "status": "open",
        "created_at": now,
    })

    report_body = (
        f"🚨 **Incident Report `{incident_id}`**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Group:** {cfg['title']} (`{chat_id}`)\n"
        f"• **Reporter:** {reporter.mention} (`{reporter.id}`)\n"
        f"• **Reported User:** {target.mention} (`{target.id}`)\n"
        f"• **Reason:** {reason or '_No reason provided_'}\n\n"
        f"**Message Preview:**\n`{snippet}`"
    )
    kb = build_incident_keyboard(incident_id, chat_id, target.id, replied.id, link)

    delivered = 0
    log_dest = cfg.get("mod_log_chat_id")
    if log_dest:
        try:
            await client.send_message(int(log_dest), _truncate(report_body), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            delivered += 1
        except Exception:
            pass

    if delivered == 0:
        try:
            async for member in client.get_chat_members(chat_id):
                if member.user and not member.user.is_bot and member.status in {
                    ChatMemberStatus.OWNER,
                    ChatMemberStatus.ADMINISTRATOR,
                }:
                    try:
                        await client.send_message(
                            member.user.id,
                            _truncate(report_body),
                            reply_markup=kb,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        delivered += 1
                    except Exception:
                        continue
        except Exception:
            pass

    try:
        await message.delete()
    except Exception:
        pass

    confirm_txt = (
        f"✅ Report `{incident_id}` sent silently to mods."
        if delivered > 0
        else f"📌 Report `{incident_id}` logged (open `/hub` in DM to review)."
    )
    try:
        await client.send_message(reporter.id, confirm_txt, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_message(filters.command(["info", "whois"]) & filters.group)
async def cmd_member_whois(client: Client, message: Message):
    chat_id = message.chat.id
    group_title = message.chat.title or str(chat_id)
    await get_hub_cfg(chat_id, title=group_title, username=message.chat.username)

    target_user = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        token = message.command[1].strip()
        try:
            lookup: int | str = int(token) if token.lstrip("-").isdigit() else token
            target_user = await client.get_users(lookup)
        except Exception:
            target_user = None
    else:
        target_user = message.from_user

    if not target_user:
        return await message.reply_text("⚠️ Could not resolve that user.", parse_mode=ParseMode.MARKDOWN)

    viewer_id = message.from_user.id if message.from_user else None
    viewer_admin = await is_admin(client, chat_id, viewer_id)
    text, kb = await build_whois_card(client, chat_id, group_title, target_user.id, viewer_admin)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^qol_dm_home$"))
async def cb_qol_dm_home(client: Client, query: CallbackQuery):
    text, kb = await build_dm_group_picker(client, query.from_user.id)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_dm_grp_(?P<chatid>-?\d+)$"))
async def cb_qol_dm_grp(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    text, kb = await build_dm_group_dashboard(chat_id)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_mlog_(?P<chatid>-?\d+)_(?P<mode>all|open|resolved)_(?P<page>\d+)$"))
async def cb_qol_modlog(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    mode = query.matches[0].group("mode")
    page = int(query.matches[0].group("page"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    text, kb = await build_incident_log_card(chat_id, filter_mode=mode, page=page)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_tog_(?P<chatid>-?\d+)_(?P<key>report|del|dm)$"))
async def cb_qol_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    key = query.matches[0].group("key")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_hub_cfg(chat_id)
    mapping = {
        "report": "report_enabled",
        "del": "delete_reported_on_action",
        "dm": "dm_hub_enabled",
    }
    field = mapping[key]
    nxt = not bool(cfg.get(field, True))
    await update_hub_cfg(chat_id, **{field: nxt})
    await query.answer("🟢 Enabled" if nxt else "🔴 Disabled", show_alert=True)
    text, kb = await build_dm_group_dashboard(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_setlog_(?P<chatid>-?\d+)$"))
async def cb_qol_set_log(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_hub_cfg(chat_id)
    msg_chat_id = query.message.chat.id if query.message and query.message.chat else None
    is_pm = bool(query.message and query.message.chat and query.message.chat.type == ChatType.PRIVATE)

    if cfg.get("mod_log_chat_id") == msg_chat_id:
        await update_hub_cfg(chat_id, mod_log_chat_id=None)
        await query.answer("Log chat cleared -> using admins DM", show_alert=True)
    elif is_pm and msg_chat_id:
        await update_hub_cfg(chat_id, mod_log_chat_id=msg_chat_id)
        await query.answer("📍 This DM set as Mod Log chat", show_alert=True)
    else:
        await query.answer("Open /hub in DM to set a log destination", show_alert=True)

    text, kb = await build_dm_group_dashboard(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_inc_act_(?P<incid>inc_\d+)_(?P<act>del|warn|mute|ban|dismiss)$"))
async def cb_qol_incident_action(client: Client, query: CallbackQuery):
    inc_id = query.matches[0].group("incid")
    act = query.matches[0].group("act")
    db = await get_db()
    inc = await db["qol_incidents"].find_one({"incident_id": inc_id})
    if not inc:
        return await query.answer("Incident not found.", show_alert=True)

    chat_id = int(inc["chat_id"])
    target_id = int(inc["target_id"])
    msg_id = inc.get("message_id")

    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_hub_cfg(chat_id)
    outcome = act

    if act == "del":
        try:
            if msg_id:
                await client.delete_messages(chat_id, int(msg_id))
            outcome = "🗑️ Deleted"
        except Exception as exc:
            return await query.answer(f"Delete failed: {str(exc)[:120]}", show_alert=True)

    elif act == "warn":
        w_cnt = await add_member_warn(chat_id, target_id, delta=1)
        if cfg.get("delete_reported_on_action", True) and msg_id:
            try:
                await client.delete_messages(chat_id, int(msg_id))
            except Exception:
                pass
        outcome = f"⚠️ Warned ({w_cnt}/{cfg.get('warn_limit', 3)})"

    elif act == "mute":
        try:
            await client.restrict_chat_member(chat_id, target_id, MUTE_PERMS)
            if cfg.get("delete_reported_on_action", True) and msg_id:
                try:
                    await client.delete_messages(chat_id, int(msg_id))
                except Exception:
                    pass
            outcome = "🔇 Muted"
        except Exception as exc:
            return await query.answer(f"Mute failed: {str(exc)[:120]}", show_alert=True)

    elif act == "ban":
        try:
            await client.ban_chat_member(chat_id, target_id)
            if cfg.get("delete_reported_on_action", True) and msg_id:
                try:
                    await client.delete_messages(chat_id, int(msg_id))
                except Exception:
                    pass
            outcome = "🔴 Banned"
        except Exception as exc:
            return await query.answer(f"Ban failed: {str(exc)[:120]}", show_alert=True)

    elif act == "dismiss":
        outcome = "✅ Dismissed"

    await db["qol_incidents"].update_one(
        {"incident_id": inc_id},
        {"$set": {"status": "resolved", "resolution": outcome, "resolved_by": query.from_user.id, "resolved_at": time.time()}},
    )
    await query.answer(f"{inc_id}: {outcome}", show_alert=True)

    updated_text = (
        f"{query.message.text or f'Incident `{inc_id}`'}\n\n"
        f"**Resolution:** {outcome} by `{query.from_user.id}`"
    )
    try:
        await query.message.edit_text(_truncate(updated_text), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^qol_who_(?P<chatid>-?\d+)_(?P<userid>\d+)$"))
async def cb_qol_whois(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    target_id = int(query.matches[0].group("userid"))
    viewer_admin = await is_admin(client, chat_id, query.from_user.id)
    cfg = await get_hub_cfg(chat_id)
    text, kb = await build_whois_card(client, chat_id, cfg["title"], target_id, viewer_admin)
    await query.answer()
    try:
        await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_ver_(?P<chatid>-?\d+)_(?P<userid>\d+)_(?P<val>0|1)$"))
async def cb_qol_verify(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    target_id = int(query.matches[0].group("userid"))
    val = query.matches[0].group("val") == "1"
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    await set_member_verified(chat_id, target_id, verified=val)
    if val:
        try:
            await client.restrict_chat_member(chat_id, target_id, NORMAL_PERMS)
        except Exception:
            pass
    await query.answer("🟢 Marked Verified ✅" if val else "🟡 Marked Unverified", show_alert=True)
    cfg = await get_hub_cfg(chat_id)
    text, kb = await build_whois_card(client, chat_id, cfg["title"], target_id, viewer_is_admin=True)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^qol_act_(?P<act>warn|mute|ban)_(?P<chatid>-?\d+)_(?P<userid>\d+)_(?P<msgid>\d+)$"))
async def cb_qol_direct_mod_action(client: Client, query: CallbackQuery):
    act = query.matches[0].group("act")
    chat_id = int(query.matches[0].group("chatid"))
    target_id = int(query.matches[0].group("userid"))
    msg_id = int(query.matches[0].group("msgid"))

    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_hub_cfg(chat_id)
    if act == "warn":
        w_cnt = await add_member_warn(chat_id, target_id, delta=1)
        await query.answer(f"⚠️ Warned ({w_cnt}/{cfg.get('warn_limit', 3)})", show_alert=True)
    elif act == "mute":
        try:
            await client.restrict_chat_member(chat_id, target_id, MUTE_PERMS)
            await query.answer("🔇 Muted", show_alert=True)
        except Exception as exc:
            return await query.answer(f"Mute failed: {str(exc)[:120]}", show_alert=True)
    elif act == "ban":
        try:
            await client.ban_chat_member(chat_id, target_id)
            await query.answer("🔴 Banned", show_alert=True)
        except Exception as exc:
            return await query.answer(f"Ban failed: {str(exc)[:120]}", show_alert=True)

    if cfg.get("delete_reported_on_action", True) and msg_id > 0:
        try:
            await client.delete_messages(chat_id, msg_id)
        except Exception:
            pass

    text, kb = await build_whois_card(client, chat_id, cfg["title"], target_id, viewer_is_admin=True)
    try:
        await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^qol_close$"))
async def cb_qol_close(client: Client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass
