import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ParseMode
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
)

ALLOWED_SPIKE_JOINS = [3, 5, 6, 8]
ALLOWED_SPIKE_SECONDS = [5, 10, 15, 30, 60]
ALLOWED_SPIKE_ACTIONS = ["warn", "kick", "ban"]

ALLOWED_WARN_LIMITS = [2, 3, 5]
ALLOWED_WARN_ESCALATIONS = ["mute", "kick", "ban"]
ALLOWED_PUNISH_SCOPES = ["perm", "24h", "7d"]
ALLOWED_DECAY_DAYS = [3, 7, 14, 30]

PROBATION_MAX_MESSAGES = 3
PROBATION_DURATION_SECONDS = 24 * 3600
STICKER_BURST_LIMIT = 3
STICKER_BURST_WINDOW = 15

LINK_PATTERN = re.compile(r"(https?://|t\.me/|telegram\.me/|www\.)", re.IGNORECASE)

DEFAULT_SMART_CFG = {
    "raid_shield": True,
    "raid_active": False,
    "spike_joins": 5,
    "spike_seconds": 10,
    "spike_action": "kick",
    "probation_enabled": True,
    "decay_days": 7,
    "warn_limit": 3,
    "warn_action": "mute",
    "punish_scope": "perm",
}

PERMISSION_KEYS = (
    "can_send_messages",
    "can_send_audios",
    "can_send_documents",
    "can_send_photos",
    "can_send_videos",
    "can_send_video_notes",
    "can_send_voice_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
)

RAID_LOCK_PERMS = ChatPermissions(
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

NORMAL_CHAT_PERMS = ChatPermissions(
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

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False
_join_events: dict[int, deque[tuple[float, int]]] = defaultdict(deque)
_spike_processed: dict[int, dict[int, float]] = defaultdict(dict)
_sticker_timestamps: dict[tuple[int, int], deque[float]] = defaultdict(deque)


def _truncate(text: str, limit: int = 3800) -> str:
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + "\n\n_...truncated_"


def _scope_until_date(scope: str) -> datetime | None:
    s = (scope or "perm").lower()
    if s == "24h":
        return datetime.now(timezone.utc) + timedelta(hours=24)
    if s == "7d":
        return datetime.now(timezone.utc) + timedelta(days=7)
    return None


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
        await db["smart_mod_groups"].create_indexes([IndexModel([("chat_id", 1)], unique=True)])
        await db["smart_probation"].create_indexes([
            IndexModel([("chat_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("expires_at", 1)]),
        ])
        await db["smart_snapshots"].create_indexes([IndexModel([("chat_id", 1), ("created_at", -1)])])
        await db["smart_warns"].create_indexes([IndexModel([("chat_id", 1), ("user_id", 1)], unique=True)])
        await db["smart_mod_logs"].create_indexes([IndexModel([("chat_id", 1), ("created_at", -1)])])
        _indexes_ready = True
    return db


async def log_smart_action(
    chat_id: int, action: str, target_user_id: int | None = None, detail: str = ""
) -> None:
    db = await get_db()
    await db["smart_mod_logs"].insert_one({
        "chat_id": chat_id,
        "action": action,
        "target_user_id": target_user_id,
        "detail": detail,
        "created_at": time.time(),
    })


async def get_recent_mod_logs(chat_id: int, limit: int = 8) -> list[dict]:
    db = await get_db()
    cursor = db["smart_mod_logs"].find({"chat_id": chat_id}).sort("created_at", -1).limit(limit)
    return [doc async for doc in cursor]


def _perms_to_dict(perms: ChatPermissions | None) -> dict:
    if not perms:
        return {k: True for k in PERMISSION_KEYS}
    return {
        k: bool(getattr(perms, k, True))
        for k in PERMISSION_KEYS
    }


def _dict_to_perms(data: dict | None) -> ChatPermissions:
    d = data or {}
    # Backward compatibility if an older snapshot in MongoDB has `can_send_media_messages`
    legacy_media = d.get("can_send_media_messages")
    media_keys = {
        "can_send_audios",
        "can_send_documents",
        "can_send_photos",
        "can_send_videos",
        "can_send_video_notes",
        "can_send_voice_notes",
    }
    kwargs = {}
    for k in PERMISSION_KEYS:
        if k in d and d[k] is not None:
            kwargs[k] = bool(d[k])
        elif k in media_keys and legacy_media is not None:
            kwargs[k] = bool(legacy_media)
        else:
            kwargs[k] = True
    return ChatPermissions(**kwargs)


async def get_smart_cfg(chat_id: int, title: str | None = None) -> dict:
    db = await get_db()
    col = db["smart_mod_groups"]
    doc = await col.find_one({"chat_id": chat_id})
    out = dict(DEFAULT_SMART_CFG)
    if doc:
        for k in DEFAULT_SMART_CFG:
            if k in doc and doc[k] is not None:
                out[k] = doc[k]

    if out["spike_joins"] not in ALLOWED_SPIKE_JOINS:
        out["spike_joins"] = 5
    if out["spike_seconds"] not in ALLOWED_SPIKE_SECONDS:
        out["spike_seconds"] = 10
    if out["spike_action"] not in ALLOWED_SPIKE_ACTIONS:
        out["spike_action"] = "kick"
    if out["decay_days"] not in ALLOWED_DECAY_DAYS:
        out["decay_days"] = 7
    if out["warn_limit"] not in ALLOWED_WARN_LIMITS:
        out["warn_limit"] = 3
    if out["warn_action"] not in ALLOWED_WARN_ESCALATIONS:
        out["warn_action"] = "mute"
    if out["punish_scope"] not in ALLOWED_PUNISH_SCOPES:
        out["punish_scope"] = "perm"

    out["chat_id"] = chat_id
    out["title"] = title or (doc.get("title") if doc else None) or str(chat_id)

    if doc is None:
        await col.update_one(
            {"chat_id": chat_id},
            {"$set": {**out, "updated_at": time.time()}},
            upsert=True,
        )
    elif title and doc.get("title") != title:
        await col.update_one({"chat_id": chat_id}, {"$set": {"title": title}})
    return out


async def update_smart_cfg(chat_id: int, title: str | None = None, **kwargs) -> dict:
    db = await get_db()
    col = db["smart_mod_groups"]
    current = await get_smart_cfg(chat_id, title=title)
    for k, v in kwargs.items():
        if k in DEFAULT_SMART_CFG:
            current[k] = v
    if title:
        current["title"] = title
    current["updated_at"] = time.time()
    await col.update_one({"chat_id": chat_id}, {"$set": current}, upsert=True)
    return current


async def list_registered_groups() -> list[dict]:
    db = await get_db()
    cursor = db["smart_mod_groups"].find({}).sort("title", 1)
    return [doc async for doc in cursor]


# ==========================================
# --- CUSTOM KICK / WARN / BAN ENGINE ---
# ==========================================

async def apply_custom_punishment(
    client: Client, chat_id: int, user_id: int, action: str, scope: str = "perm"
) -> str:
    """Executes kick, ban, or mute with optional 24h/7d duration."""
    act = (action or "mute").lower()
    until_dt = _scope_until_date(scope)

    if act == "kick":
        await client.ban_chat_member(chat_id, user_id)
        await client.unban_chat_member(chat_id, user_id)
        return "kicked"

    if act == "ban":
        if until_dt:
            await client.ban_chat_member(chat_id, user_id, until_date=until_dt)
            return f"banned ({scope})"
        await client.ban_chat_member(chat_id, user_id)
        return "banned (perm)"

    # Default: mute
    if until_dt:
        await client.restrict_chat_member(chat_id, user_id, MUTE_PERMS, until_date=until_dt)
        return f"muted ({scope})"
    await client.restrict_chat_member(chat_id, user_id, MUTE_PERMS)
    return "muted (perm)"


# ==========================================
# --- SNAPSHOTS & UNDO ENGINE ---
# ==========================================

async def save_snapshot(
    chat_id: int,
    actor_id: int | None,
    snap_type: str,
    summary: str,
    payload: dict,
) -> str:
    db = await get_db()
    col = db["smart_snapshots"]
    snap_id = f"snap_{int(time.time() * 1000)}"
    await col.insert_one({
        "snap_id": snap_id,
        "chat_id": chat_id,
        "actor_id": actor_id,
        "type": snap_type,
        "summary": summary,
        "payload": payload,
        "undone": False,
        "created_at": time.time(),
    })
    return snap_id


async def get_recent_snapshots(chat_id: int, limit: int = 5) -> list[dict]:
    db = await get_db()
    col = db["smart_snapshots"]
    cursor = col.find({"chat_id": chat_id}).sort("created_at", -1).limit(limit)
    return [doc async for doc in cursor]


async def undo_snapshot(client: Client, chat_id: int, snap_id: str | None = None) -> tuple[bool, str]:
    db = await get_db()
    col = db["smart_snapshots"]
    query = {"chat_id": chat_id, "snap_id": snap_id} if snap_id else {"chat_id": chat_id, "undone": False}
    snap = await col.find_one(query, sort=[("created_at", -1)])
    if not snap:
        return False, "No undoable snapshot found."

    ptype = snap.get("type")
    payload = snap.get("payload") or {}

    if ptype == "permissions":
        restored = _dict_to_perms(payload.get("permissions"))
        try:
            await client.set_chat_permissions(chat_id, restored)
        except Exception as exc:
            return False, f"Failed to restore permissions: {exc}"
        if payload.get("raid_active") is not None:
            await update_smart_cfg(chat_id, raid_active=bool(payload["raid_active"]))
        await col.update_one({"_id": snap["_id"]}, {"$set": {"undone": True, "undone_at": time.time()}})
        return True, f"Restored chat permissions ({snap.get('summary', ptype)})."

    if ptype == "purge":
        msg_ids = payload.get("message_ids") or []
        restored_count = 0
        for mid in msg_ids:
            try:
                await client.forward_messages(chat_id, chat_id, mid)
                restored_count += 1
            except Exception:
                continue
        await col.update_one({"_id": snap["_id"]}, {"$set": {"undone": True, "undone_at": time.time()}})
        return True, f"Re-posted `{restored_count}/{len(msg_ids)}` recoverable purged messages."

    return False, "Unknown snapshot type."


# ==========================================
# --- REPEAT-OFFENDER DECAY ENGINE ---
# ==========================================

async def _load_and_decay_user_warns(chat_id: int, user_id: int, decay_days: int) -> dict:
    db = await get_db()
    col = db["smart_warns"]
    doc = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    now = time.time()
    decay_secs = max(1, decay_days) * 86400

    if not doc:
        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "points": 0,
            "last_activity": now,
            "reasons": [],
        }

    points = int(doc.get("points", 0))
    last_ts = float(doc.get("last_activity", now))
    reasons = list(doc.get("reasons") or [])

    if points > 0 and (now - last_ts) >= decay_secs:
        decayed = int((now - last_ts) // decay_secs)
        points = max(0, points - decayed)
        last_ts = now
        if reasons and decayed > 0:
            reasons = reasons[min(len(reasons), decayed):]
        await col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"points": points, "last_activity": last_ts, "reasons": reasons}},
        )

    return {
        "chat_id": chat_id,
        "user_id": user_id,
        "points": points,
        "last_activity": last_ts,
        "reasons": reasons,
    }


async def add_decay_warn_point(
    chat_id: int, user_id: int, decay_days: int, reason: str = "", add_pts: int = 1
) -> dict:
    db = await get_db()
    col = db["smart_warns"]
    state = await _load_and_decay_user_warns(chat_id, user_id, decay_days)
    now = time.time()
    new_points = state["points"] + max(1, add_pts)
    reasons = list(state["reasons"])
    if reason:
        reasons.append(reason[:120])
    reasons = reasons[-5:]

    await col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "chat_id": chat_id,
                "user_id": user_id,
                "points": new_points,
                "last_activity": now,
                "reasons": reasons,
            }
        },
        upsert=True,
    )
    state["points"] = new_points
    state["last_activity"] = now
    state["reasons"] = reasons
    return state


async def reset_user_warns(chat_id: int, user_id: int) -> None:
    db = await get_db()
    await db["smart_warns"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"points": 0, "last_activity": time.time(), "reasons": []}},
        upsert=True,
    )


async def apply_spike_member_action(client: Client, chat_id: int, user_id: int, cfg: dict) -> str:
    """Applies warn, kick, or ban to a user joining during a join spike."""
    action = (cfg.get("spike_action") or "kick").lower()
    scope = str(cfg.get("punish_scope") or "perm")
    if await is_admin(client, chat_id, user_id):
        return "skipped_admin"

    if action == "ban":
        try:
            res = await apply_custom_punishment(client, chat_id, user_id, "ban", scope=scope)
            await log_smart_action(chat_id, "spike_ban", target_user_id=user_id, detail=res)
            return res
        except Exception:
            return "failed_ban"

    if action == "kick":
        try:
            res = await apply_custom_punishment(client, chat_id, user_id, "kick", scope=scope)
            await log_smart_action(chat_id, "spike_kick", target_user_id=user_id, detail=res)
            return res
        except Exception:
            return "failed_kick"

    warn_limit = int(cfg.get("warn_limit", 3))
    warn_action = str(cfg.get("warn_action", "mute"))
    state = await add_decay_warn_point(
        chat_id=chat_id,
        user_id=user_id,
        decay_days=int(cfg.get("decay_days", 7)),
        reason="rapid join spike",
        add_pts=1,
    )
    await log_smart_action(chat_id, "spike_warn", target_user_id=user_id, detail=f"pts={state['points']}")
    if state["points"] >= warn_limit:
        try:
            res = await apply_custom_punishment(client, chat_id, user_id, warn_action, scope=scope)
            await reset_user_warns(chat_id, user_id)
            return f"warn->{res}"
        except Exception:
            return "warned"
    return f"warned ({state['points']}/{warn_limit})"


# ==========================================
# --- PROBATION HELPERS ---
# ==========================================

async def start_probation(chat_id: int, user_id: int) -> None:
    db = await get_db()
    now = time.time()
    await db["smart_probation"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "chat_id": chat_id,
                "user_id": user_id,
                "msgs_seen": 0,
                "max_msgs": PROBATION_MAX_MESSAGES,
                "started_at": now,
                "expires_at": now + PROBATION_DURATION_SECONDS,
            }
        },
        upsert=True,
    )


async def check_and_advance_probation(client: Client, message: Message) -> bool:
    """Enforces probation rules on new members for first 3 msgs or 24h. Returns True if message was deleted."""
    if not message.from_user or message.from_user.is_bot:
        return False
    chat_id = message.chat.id
    user_id = message.from_user.id

    cfg = await get_smart_cfg(chat_id, title=message.chat.title)
    if not cfg.get("probation_enabled", True):
        return False

    db = await get_db()
    col = db["smart_probation"]
    rec = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not rec:
        return False

    now = time.time()
    if now > float(rec.get("expires_at", 0)) or int(rec.get("msgs_seen", 0)) >= int(rec.get("max_msgs", PROBATION_MAX_MESSAGES)):
        await col.delete_one({"_id": rec["_id"]})
        return False

    if await is_admin(client, chat_id, user_id):
        await col.delete_one({"_id": rec["_id"]})
        return False

    violation: str | None = None
    text_body = f"{message.text or ''} {message.caption or ''}".strip()

    if message.forward_date or message.forward_from or message.forward_from_chat:
        violation = "forwarded messages during probation"
    elif text_body and LINK_PATTERN.search(text_body):
        violation = "links during probation"
    elif message.sticker:
        dq = _sticker_timestamps[(chat_id, user_id)]
        dq.append(now)
        while dq and (now - dq[0]) > STICKER_BURST_WINDOW:
            dq.popleft()
        if len(dq) >= STICKER_BURST_LIMIT:
            violation = "sticker spam during probation"

    if violation:
        try:
            await client.delete_messages(chat_id, message.id)
        except Exception:
            pass
        await message.reply_text(
            f"🛡️ {message.from_user.mention} is on **First-Message Probation** (first `{PROBATION_MAX_MESSAGES}` msgs / `24h`): removed **{violation}**.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return True

    new_count = int(rec.get("msgs_seen", 0)) + 1
    if new_count >= int(rec.get("max_msgs", PROBATION_MAX_MESSAGES)):
        await col.delete_one({"_id": rec["_id"]})
    else:
        await col.update_one({"_id": rec["_id"]}, {"$set": {"msgs_seen": new_count}})
    return False


# ==========================================
# --- UI BUILDERS (GROUP & PRIVATE DM) ---
# ==========================================

async def build_smart_dashboard(
    client: Client, chat_id: int, title: str | None = None, from_pm: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
    cfg = await get_smart_cfg(chat_id, title=title)
    db = await get_db()
    prob_count = await db["smart_probation"].count_documents(
        {"chat_id": chat_id, "expires_at": {"$gt": time.time()}}
    )
    snaps = await get_recent_snapshots(chat_id, limit=3)

    raid_badge = "🚨 ACTIVE" if cfg["raid_active"] else "🟢 Standby"
    shield_badge = "On ✅" if cfg["raid_shield"] else "Off ❌"
    prob_badge = "On ✅" if cfg["probation_enabled"] else "Off ❌"
    spike_joins = int(cfg["spike_joins"])
    spike_secs = int(cfg["spike_seconds"])
    spike_act = str(cfg["spike_action"]).upper()
    warn_lim = int(cfg["warn_limit"])
    warn_act = str(cfg["warn_action"]).upper()
    scope_lbl = str(cfg["punish_scope"]).upper()

    snap_lines = []
    for s in snaps:
        mark = "↩️ Undone" if s.get("undone") else "📸 Ready"
        snap_lines.append(f"• `{s['snap_id'][-6:]}` — {s.get('summary', s.get('type'))} ({mark})")
    snap_block = "\n".join(snap_lines) if snap_lines else "_No recent snapshots._"

    text = (
        f"🎛️ **Custom Mod Control — {cfg['title']}** (`{chat_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 **Raid Mode:** {raid_badge} | **Scope:** `{scope_lbl}`\n"
        f"⚡ **Join-Spike:** `{spike_joins}+` joins / `{spike_secs}s` -> **`{spike_act}`** ({shield_badge})\n"
        f"⚠️ **Warn System:** Limit **`{warn_lim}` pts** -> **`{warn_act}`** | Decay: `1` pt / `{cfg['decay_days']}d`\n"
        f"🌱 **Probation (`{PROBATION_MAX_MESSAGES}` msgs / `24h`):** {prob_badge} (`{prob_count}` active)\n\n"
        f"**Recent Snapshots:**\n{snap_block}"
    )

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🟢 Disable Raid" if cfg["raid_active"] else "🚨 Enable Raid",
                callback_data=f"smod_raid_toggle_{chat_id}",
            ),
            InlineKeyboardButton(
                f"⚡ Spike Shield: {'On' if cfg['raid_shield'] else 'Off'}",
                callback_data=f"smod_shield_{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if a == cfg['spike_action'] else ''}Spike {a.capitalize()}",
                callback_data=f"smod_spact_{chat_id}_{a}",
            )
            for a in ALLOWED_SPIKE_ACTIONS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if j == cfg['spike_joins'] else ''}{j} Joins",
                callback_data=f"smod_spjoin_{chat_id}_{j}",
            )
            for j in ALLOWED_SPIKE_JOINS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if s == cfg['spike_seconds'] else ''}{s}s",
                callback_data=f"smod_spsec_{chat_id}_{s}",
            )
            for s in ALLOWED_SPIKE_SECONDS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if wl == cfg['warn_limit'] else ''}Warn @{wl}pts",
                callback_data=f"smod_wlim_{chat_id}_{wl}",
            )
            for wl in ALLOWED_WARN_LIMITS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if wa == cfg['warn_action'] else ''}Limit {wa.capitalize()}",
                callback_data=f"smod_wact_{chat_id}_{wa}",
            )
            for wa in ALLOWED_WARN_ESCALATIONS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if sc == cfg['punish_scope'] else ''}Scope {sc.upper()}",
                callback_data=f"smod_scope_{chat_id}_{sc}",
            )
            for sc in ALLOWED_PUNISH_SCOPES
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if d == cfg['decay_days'] else ''}Decay {d}d",
                callback_data=f"smod_decay_{chat_id}_{d}",
            )
            for d in ALLOWED_DECAY_DAYS
        ],
        [
            InlineKeyboardButton(
                f"🌱 Probation: {'On' if cfg['probation_enabled'] else 'Off'}",
                callback_data=f"smod_prob_{chat_id}",
            ),
            InlineKeyboardButton("↩️ Undo Last", callback_data=f"smod_undo_{chat_id}"),
        ],
        [
            InlineKeyboardButton("📸 Snapshots", callback_data=f"smod_snaps_{chat_id}"),
            InlineKeyboardButton("📜 Mod Logs", callback_data=f"smod_logs_{chat_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"smod_dash_{chat_id}"),
        ],
    ]

    if from_pm:
        rows.append([
            InlineKeyboardButton("📋 My Groups", callback_data="smod_pm_groups"),
            InlineKeyboardButton("❌ Close", callback_data="smod_close"),
        ])
    else:
        rows.append([InlineKeyboardButton("❌ Close", callback_data="smod_close")])

    return text, InlineKeyboardMarkup(rows)


async def build_pm_groups_menu(client: Client, admin_user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Builds the private DM group selector for groups where the user is an admin."""
    groups = await list_registered_groups()
    accessible: list[dict] = []
    for g in groups:
        gid = g["chat_id"]
        if await is_admin(client, gid, admin_user_id):
            accessible.append(g)

    if not accessible:
        text = (
            "🎛️ **Private Group Controller**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "No managed groups found for your admin account yet.\n\n"
            "• Run `/cmod` inside a group first to register it.\n"
            "• Or use `/cmod <chat_id>` in this DM to open a group directly."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="smod_pm_groups"),
                InlineKeyboardButton("❌ Close", callback_data="smod_close"),
            ]
        ])
        return text, kb

    lines = [
        "🎛️ **Private Group Controller**\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Select a group to control (`{len(accessible)}` available):\n",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for g in accessible[:12]:
        gid = g["chat_id"]
        title = g.get("title") or str(gid)
        raid_icon = "🚨" if g.get("raid_active") else "🟢"
        act_lbl = str(g.get("spike_action", "kick")).upper()
        lines.append(f"• {raid_icon} **{title}** (`{gid}`) — Spike: `{act_lbl}` | Warn: `{g.get('warn_limit', 3)}pts`")
        rows.append([
            InlineKeyboardButton(
                f"{raid_icon} {title[:22]}",
                callback_data=f"smod_pm_open_{gid}",
            )
        ])

    rows.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="smod_pm_groups"),
        InlineKeyboardButton("❌ Close", callback_data="smod_close"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_target_mod_card(
    chat_id: int, target_id: int, target_name: str, warn_pts: int, warn_limit: int, reason: str
) -> tuple[str, InlineKeyboardMarkup]:
    r_line = f"\n📝 **Reason:** _{reason}_" if reason else ""
    text = (
        f"⚖️ **Target Mod Action**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** {target_name} (`{target_id}`)\n"
        f"⚠️ **Decay Warns:** **`{warn_pts}/{warn_limit}`** pts{r_line}\n\n"
        f"Choose an action below:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ +1 Warn", callback_data=f"smod_t_warn_{chat_id}_{target_id}"),
            InlineKeyboardButton("👢 Kick", callback_data=f"smod_t_kick_{chat_id}_{target_id}"),
            InlineKeyboardButton("🔨 Ban", callback_data=f"smod_t_ban_{chat_id}_{target_id}"),
        ],
        [
            InlineKeyboardButton("🔊 Unmute", callback_data=f"smod_t_unmute_{chat_id}_{target_id}"),
            InlineKeyboardButton("♻️ Reset Warns", callback_data=f"smod_t_clrwarn_{chat_id}_{target_id}"),
        ],
        [
            InlineKeyboardButton("⚙️ Group Settings", callback_data=f"smod_dash_{chat_id}"),
            InlineKeyboardButton("❌ Close", callback_data="smod_close"),
        ],
    ])
    return text, kb


# ==========================================
# --- COMMANDS (GROUP & PRIVATE DM) ---
# ==========================================

@app.on_message(filters.command(["cmod", "smartmod"]) & filters.group)
async def cmd_group_cmod(client: Client, message: Message):
    chat_id = message.chat.id
    actor_id = message.from_user.id if message.from_user else None
    if not await is_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    cfg = await get_smart_cfg(chat_id, title=message.chat.title)

    # Check if replying to a user or passing a user token for target mod card
    target_user = None
    args = message.command[1:]
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    elif args and not args[0].lstrip("-").isdigit() or (args and args[0].isdigit() and len(args[0]) >= 6):
        token = args[0].strip()
        try:
            lookup: int | str = int(token) if token.isdigit() else token
            target_user = await client.get_users(lookup)
            args = args[1:]
        except Exception:
            target_user = None

    if target_user:
        reason = " ".join(args).strip()
        w_state = await _load_and_decay_user_warns(chat_id, target_user.id, cfg["decay_days"])
        t_text, t_kb = build_target_mod_card(
            chat_id=chat_id,
            target_id=target_user.id,
            target_name=target_user.first_name or str(target_user.id),
            warn_pts=w_state["points"],
            warn_limit=cfg["warn_limit"],
            reason=reason,
        )
        return await message.reply_text(_truncate(t_text), reply_markup=t_kb, parse_mode=ParseMode.MARKDOWN)

    text, kb = await build_smart_dashboard(client, chat_id, title=message.chat.title, from_pm=False)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["cmod", "groups"]) & filters.private)
async def cmd_pm_cmod(client: Client, message: Message):
    actor_id = message.from_user.id if message.from_user else None
    if not actor_id:
        return

    args = message.command[1:]
    if args:
        raw = args[0].strip()
        try:
            target_chat: int | str = int(raw) if raw.lstrip("-").isdigit() else raw
            chat_obj = await client.get_chat(target_chat)
            gid = chat_obj.id
            gtitle = chat_obj.title or str(gid)
        except Exception as exc:
            return await message.reply_text(f"❌ Could not find group `{raw}`: `{exc}`", parse_mode=ParseMode.MARKDOWN)

        if not await is_admin(client, gid, actor_id):
            return await message.reply_text(f"⛔ You are not an admin in **{gtitle}** (`{gid}`).", parse_mode=ParseMode.MARKDOWN)

        text, kb = await build_smart_dashboard(client, gid, title=gtitle, from_pm=True)
        return await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    text, kb = await build_pm_groups_menu(client, actor_id)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["raidmode"]) & filters.group)
async def cmd_raidmode(client: Client, message: Message):
    chat_id = message.chat.id
    uid = message.from_user.id if message.from_user else None
    if not await is_admin(client, chat_id, uid):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)

    cfg = await get_smart_cfg(chat_id, title=message.chat.title)
    target_state = not cfg["raid_active"]
    if len(message.command) > 1:
        arg = message.command[1].lower()
        if arg in {"on", "1", "true"}:
            target_state = True
        elif arg in {"off", "0", "false"}:
            target_state = False

    snap_id = await save_snapshot(
        chat_id=chat_id,
        actor_id=uid,
        snap_type="permissions",
        summary=f"Raid mode -> {'ON' if target_state else 'OFF'}",
        payload={
            "permissions": _perms_to_dict(getattr(message.chat, "permissions", None)),
            "raid_active": cfg["raid_active"],
        },
    )

    try:
        await client.set_chat_permissions(chat_id, RAID_LOCK_PERMS if target_state else NORMAL_CHAT_PERMS)
    except Exception as exc:
        return await message.reply_text(f"❌ Failed to update chat permissions: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    await update_smart_cfg(chat_id, raid_active=target_state)
    await log_smart_action(chat_id, "raid_on" if target_state else "raid_off", target_user_id=uid)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 Turn Raid Mode OFF" if target_state else "🚨 Turn Raid Mode ON",
                callback_data=f"smod_raid_toggle_{chat_id}",
            ),
            InlineKeyboardButton("↩️ Undo", callback_data=f"smod_undo_id_{chat_id}_{snap_id}"),
        ]
    ])
    await message.reply_text(
        f"{'🚨 **Raid Mode ENABLED** — group chat tightened.' if target_state else '🟢 **Raid Mode DISABLED** — normal permissions restored.'}\nSnapshot: `{snap_id}`",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command(["purge"]) & filters.group)
async def cmd_purge_with_snapshot(client: Client, message: Message):
    """Deletes replied message through current message and saves a snapshot for undo."""
    chat_id = message.chat.id
    uid = message.from_user.id if message.from_user else None
    if not await is_admin(client, chat_id, uid):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)
    if not message.reply_to_message:
        return await message.reply_text("⚠️ Reply to the starting message with `/purge`.", parse_mode=ParseMode.MARKDOWN)

    start_id = message.reply_to_message.id
    end_id = message.id
    ids = list(range(start_id, end_id + 1))

    snap_id = await save_snapshot(
        chat_id=chat_id,
        actor_id=uid,
        snap_type="purge",
        summary=f"Purged {len(ids)} msgs ({start_id}..{end_id})",
        payload={"message_ids": ids},
    )

    try:
        await client.delete_messages(chat_id, ids)
    except Exception as exc:
        return await message.reply_text(f"❌ Purge failed: `{exc}`", parse_mode=ParseMode.MARKDOWN)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Undo Purge", callback_data=f"smod_undo_id_{chat_id}_{snap_id}")]
    ])
    await client.send_message(
        chat_id,
        f"🧹 Purged `{len(ids)}` messages. Snapshot `{snap_id}` saved.",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


# ==========================================
# --- JOIN & MESSAGE GUARDS ---
# ==========================================

@app.on_message(filters.new_chat_members)
async def guard_on_member_join(client: Client, message: Message):
    chat_id = message.chat.id
    cfg = await get_smart_cfg(chat_id, title=message.chat.title)
    me = await client.get_me()
    now = time.time()

    spike_joins = int(cfg.get("spike_joins", 5))
    spike_seconds = int(cfg.get("spike_seconds", 10))
    spike_action = str(cfg.get("spike_action", "kick")).lower()

    dq = _join_events[chat_id]
    processed_map = _spike_processed[chat_id]

    expired_uids = [uid for uid, ts in processed_map.items() if (now - ts) > spike_seconds]
    for uid in expired_uids:
        processed_map.pop(uid, None)

    for m in message.new_chat_members:
        if m.id == me.id:
            continue
        dq.append((now, m.id))
        if cfg.get("probation_enabled", True):
            await start_probation(chat_id, m.id)

    while dq and (now - dq[0][0]) > spike_seconds:
        dq.popleft()

    if cfg.get("raid_shield", True) and len(dq) >= spike_joins:
        snap_id = ""
        if not cfg.get("raid_active"):
            snap_id = await save_snapshot(
                chat_id=chat_id,
                actor_id=None,
                snap_type="permissions",
                summary=f"Auto-Raid Shield ({len(dq)} joins/{spike_seconds}s -> {spike_action})",
                payload={
                    "permissions": _perms_to_dict(getattr(message.chat, "permissions", None)),
                    "raid_active": False,
                },
            )
            try:
                await client.set_chat_permissions(chat_id, RAID_LOCK_PERMS)
            except Exception:
                pass
            await update_smart_cfg(chat_id, raid_active=True)

        window_uids = list(dict.fromkeys(uid for _, uid in dq))
        results: list[str] = []
        for uid in window_uids:
            if uid in processed_map:
                continue
            processed_map[uid] = now
            outcome = await apply_spike_member_action(client, chat_id, uid, cfg)
            results.append(f"`{uid}`: {outcome}")

        if results:
            undo_btn = [InlineKeyboardButton("↩️ Undo", callback_data=f"smod_undo_id_{chat_id}_{snap_id}")] if snap_id else []
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Turn Raid Mode OFF", callback_data=f"smod_raid_toggle_{chat_id}"),
                    *undo_btn,
                ]
            ])
            res_line = "\n".join(results[:12])
            if len(results) > 12:
                res_line += f"\n_...and {len(results) - 12} more_"
            await message.reply_text(
                f"🚨 **Join-Spike Detected!** `{len(dq)}` joins within `{spike_seconds}s` (threshold: `{spike_joins}`).\n"
                f"**Action:** `{spike_action.upper()}` | **Raid Mode:** `ACTIVE`\n"
                f"{res_line}",
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
            )


@app.on_message(filters.group & ~filters.service, group=2)
async def guard_on_group_message(client: Client, message: Message):
    await check_and_advance_probation(client, message)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

def _is_pm_query(query: CallbackQuery) -> bool:
    return bool(query.message and query.message.chat and query.message.chat.type.name == "PRIVATE")


@app.on_callback_query(filters.regex(r"^smod_pm_groups$"))
async def cb_smod_pm_groups(client: Client, query: CallbackQuery):
    text, kb = await build_pm_groups_menu(client, query.from_user.id)
    await query.answer("Refreshing groups...")
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_pm_open_(?P<chatid>-?\d+)$"))
async def cb_smod_pm_open(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=True)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_dash_(?P<chatid>-?\d+)$"))
async def cb_smod_dash(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.answer("Refreshed")
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_raid_toggle_(?P<chatid>-?\d+)$"))
async def cb_smod_raid_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_smart_cfg(chat_id)
    next_state = not bool(cfg.get("raid_active"))

    await save_snapshot(
        chat_id=chat_id,
        actor_id=query.from_user.id,
        snap_type="permissions",
        summary=f"Button Raid Mode -> {'ON' if next_state else 'OFF'}",
        payload={
            "permissions": _perms_to_dict(getattr(query.message.chat, "permissions", None)),
            "raid_active": cfg.get("raid_active", False),
        },
    )

    try:
        await client.set_chat_permissions(chat_id, RAID_LOCK_PERMS if next_state else NORMAL_CHAT_PERMS)
    except Exception as exc:
        return await query.answer(f"Error: {str(exc)[:140]}", show_alert=True)

    await update_smart_cfg(chat_id, raid_active=next_state)
    await log_smart_action(chat_id, "raid_on" if next_state else "raid_off", target_user_id=query.from_user.id)
    await query.answer("🚨 Raid Mode ON" if next_state else "🟢 Raid Mode OFF", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_shield_(?P<chatid>-?\d+)$"))
async def cb_smod_shield_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    cfg = await get_smart_cfg(chat_id)
    val = not bool(cfg.get("raid_shield", True))
    await update_smart_cfg(chat_id, raid_shield=val)
    await query.answer(f"Spike Shield: {'On' if val else 'Off'}", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_spact_(?P<chatid>-?\d+)_(?P<act>warn|kick|ban)$"))
async def cb_smod_spike_action(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    act = query.matches[0].group("act")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, spike_action=act)
    await query.answer(f"Spike action -> {act.upper()}", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_spjoin_(?P<chatid>-?\d+)_(?P<joins>\d+)$"))
async def cb_smod_spike_joins(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    joins = int(query.matches[0].group("joins"))
    if joins not in ALLOWED_SPIKE_JOINS:
        return await query.answer("Invalid join count.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, spike_joins=joins)
    await query.answer(f"Spike threshold -> {joins} joins", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_spsec_(?P<chatid>-?\d+)_(?P<secs>\d+)$"))
async def cb_smod_spike_seconds(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    secs = int(query.matches[0].group("secs"))
    if secs not in ALLOWED_SPIKE_SECONDS:
        return await query.answer("Invalid window.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, spike_seconds=secs)
    await query.answer(f"Spike window -> {secs}s", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_wlim_(?P<chatid>-?\d+)_(?P<lim>\d+)$"))
async def cb_smod_warn_limit(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    lim = int(query.matches[0].group("lim"))
    if lim not in ALLOWED_WARN_LIMITS:
        return await query.answer("Invalid warn limit.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, warn_limit=lim)
    await query.answer(f"Warn limit -> {lim} pts", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_wact_(?P<chatid>-?\d+)_(?P<wact>mute|kick|ban)$"))
async def cb_smod_warn_action(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    wact = query.matches[0].group("wact")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, warn_action=wact)
    await query.answer(f"Warn limit action -> {wact.upper()}", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_scope_(?P<chatid>-?\d+)_(?P<scope>perm|24h|7d)$"))
async def cb_smod_punish_scope(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    scope = query.matches[0].group("scope")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, punish_scope=scope)
    await query.answer(f"Punishment scope -> {scope.upper()}", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_prob_(?P<chatid>-?\d+)$"))
async def cb_smod_prob_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    cfg = await get_smart_cfg(chat_id)
    val = not bool(cfg.get("probation_enabled", True))
    await update_smart_cfg(chat_id, probation_enabled=val)
    await query.answer(f"Probation: {'On' if val else 'Off'}", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_decay_(?P<chatid>-?\d+)_(?P<days>\d+)$"))
async def cb_smod_decay_set(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    days = int(query.matches[0].group("days"))
    if days not in ALLOWED_DECAY_DAYS:
        return await query.answer("Invalid decay interval.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_smart_cfg(chat_id, decay_days=days)
    await query.answer(f"Warn decay -> {days} days", show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_snaps_(?P<chatid>-?\d+)$"))
async def cb_smod_snaps(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    snaps = await get_recent_snapshots(chat_id, limit=5)
    lines = [f"📸 **Snapshots** (`{chat_id}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    rows: list[list[InlineKeyboardButton]] = []

    if not snaps:
        lines.append("_No snapshots recorded yet._")
    else:
        for s in snaps:
            sid = s["snap_id"]
            mark = "Undone" if s.get("undone") else "Active"
            lines.append(f"• `{sid}` — {s.get('summary')} [{mark}]")
            if not s.get("undone"):
                rows.append([
                    InlineKeyboardButton(f"↩️ Undo {sid[-6:]}", callback_data=f"smod_undo_id_{chat_id}_{sid}")
                ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"smod_dash_{chat_id}")])
    await query.answer()
    await query.message.edit_text(
        _truncate("\n".join(lines)),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^smod_logs_(?P<chatid>-?\d+)$"))
async def cb_smod_logs(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    logs = await get_recent_mod_logs(chat_id, limit=8)
    lines = [f"📜 **Mod Logs** (`{chat_id}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    if not logs:
        lines.append("_No logs yet._")
    else:
        for entry in logs:
            act = entry.get("action", "action")
            tid = entry.get("target_user_id")
            det = entry.get("detail") or ""
            t_str = f" -> `{tid}`" if tid else ""
            d_str = f" _({det})_" if det else ""
            lines.append(f"• `{act}`{t_str}{d_str}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=f"smod_dash_{chat_id}")]
    ])
    await query.answer()
    await query.message.edit_text(_truncate("\n".join(lines)), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_undo_(?P<chatid>-?\d+)$"))
async def cb_smod_undo_latest(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    ok, msg = await undo_snapshot(client, chat_id, snap_id=None)
    await query.answer(msg[:180], show_alert=True)
    text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_undo_id_(?P<chatid>-?\d+)_(?P<snapid>snap_\d+)$"))
async def cb_smod_undo_by_id(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    snap_id = query.matches[0].group("snapid")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    ok, msg = await undo_snapshot(client, chat_id, snap_id=snap_id)
    await query.answer(msg[:180], show_alert=True)
    try:
        text, kb = await build_smart_dashboard(client, chat_id, from_pm=_is_pm_query(query))
        await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^smod_t_(?P<act>warn|kick|ban|unmute|clrwarn)_(?P<chatid>-?\d+)_(?P<userid>\d+)$"))
async def cb_smod_target_action(client: Client, query: CallbackQuery):
    act = query.matches[0].group("act")
    chat_id = int(query.matches[0].group("chatid"))
    target_uid = int(query.matches[0].group("userid"))

    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_smart_cfg(chat_id)
    scope = str(cfg.get("punish_scope") or "perm")
    warn_limit = int(cfg.get("warn_limit") or 3)
    warn_action = str(cfg.get("warn_action") or "mute")

    try:
        u = await client.get_users(target_uid)
        uname = u.first_name or str(target_uid)
    except Exception:
        uname = str(target_uid)

    if act == "warn":
        st = await add_decay_warn_point(chat_id, target_uid, cfg["decay_days"], reason="inline mod", add_pts=1)
        await log_smart_action(chat_id, "warn", target_user_id=target_uid, detail=f"{st['points']}/{warn_limit}")
        if st["points"] >= warn_limit:
            res = await apply_custom_punishment(client, chat_id, target_uid, warn_action, scope=scope)
            await reset_user_warns(chat_id, target_uid)
            await query.answer(f"Limit reached -> {res}", show_alert=True)
            t_text, t_kb = build_target_mod_card(chat_id, target_uid, uname, 0, warn_limit, f"Escalated: {res}")
        else:
            await query.answer(f"Warned ({st['points']}/{warn_limit})", show_alert=True)
            t_text, t_kb = build_target_mod_card(chat_id, target_uid, uname, st["points"], warn_limit, "")
        await query.message.edit_text(_truncate(t_text), reply_markup=t_kb, parse_mode=ParseMode.MARKDOWN)
        return

    if act == "kick":
        try:
            res = await apply_custom_punishment(client, chat_id, target_uid, "kick", scope=scope)
            await log_smart_action(chat_id, "kick", target_user_id=target_uid, detail=res)
            await query.answer(f"Kicked {uname}", show_alert=True)
        except Exception as exc:
            return await query.answer(f"Kick failed: {str(exc)[:140]}", show_alert=True)
        return

    if act == "ban":
        try:
            res = await apply_custom_punishment(client, chat_id, target_uid, "ban", scope=scope)
            await log_smart_action(chat_id, "ban", target_user_id=target_uid, detail=res)
            await query.answer(f"Applied {res}", show_alert=True)
        except Exception as exc:
            return await query.answer(f"Ban failed: {str(exc)[:140]}", show_alert=True)
        return

    if act == "unmute":
        try:
            await client.restrict_chat_member(chat_id, target_uid, NORMAL_CHAT_PERMS)
            await log_smart_action(chat_id, "unmute", target_user_id=target_uid)
            await query.answer(f"Unmuted {uname}", show_alert=True)
        except Exception as exc:
            return await query.answer(f"Unmute failed: {str(exc)[:140]}", show_alert=True)
        return

    if act == "clrwarn":
        await reset_user_warns(chat_id, target_uid)
        await log_smart_action(chat_id, "reset_warns", target_user_id=target_uid)
        await query.answer("Warns reset to 0", show_alert=True)
        t_text, t_kb = build_target_mod_card(chat_id, target_uid, uname, 0, warn_limit, "Warns cleared")
        await query.message.edit_text(_truncate(t_text), reply_markup=t_kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^smod_close$"))
async def cb_smod_close(client: Client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass
