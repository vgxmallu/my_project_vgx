
import logging

logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)



import asyncio
import os
import re
import time
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import (
    CallbackQuery,
    ChatJoinRequest,
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

PROBATION_SWEEP_MINUTES = max(1, int(os.getenv("PROBATION_SWEEP_MINUTES", "2")))

DEFAULT_SCREEN_CFG = {
    "enabled": True,
    "auto_approve_clean": False,
    "auto_decline_high_risk": False,
    "auto_approve_threshold": 15,
    "auto_decline_threshold": 75,
    "screen_log_chat_id": None,
    "probation_enabled": True,
    "probation_minutes": 30,
    "probation_unlock_msgs": 3,
}

ALLOWED_PROBATION_MINS = [15, 30, 60, 120]
ALLOWED_UNLOCK_MSGS = [2, 3, 5]

PROBATION_PERMS = ChatPermissions(
    can_send_messages=True,
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

FULL_MEMBER_PERMS = ChatPermissions(
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

SUSPICIOUS_PATTERNS = re.compile(
    r"(https?://|t\.me/|joinchat|\+|free\s*(crypto|airdrop|nitro|robux|giveaway)|"
    r"earn\s*\$|dm\s*me\s*(for|to)|whatsapp|telegram\s*channel|casino|betting)",
    re.IGNORECASE,
)

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False
_prob_scheduler: AsyncIOScheduler | None = None
_prob_scheduler_lock = asyncio.Lock()


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "Unknown"
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


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
        await db["join_screen_cfg"].create_indexes([IndexModel([("chat_id", 1)], unique=True)])
        await db["join_screen_requests"].create_indexes([
            IndexModel([("req_id", 1)], unique=True),
            IndexModel([("chat_id", 1), ("status", 1), ("created_at", -1)]),
        ])
        await db["join_probation"].create_indexes([
            IndexModel([("chat_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("expires_at", 1)]),
        ])
        _indexes_ready = True
    return db


async def get_screen_cfg(chat_id: int, title: str | None = None) -> dict:
    db = await get_db()
    col = db["join_screen_cfg"]
    doc = await col.find_one({"chat_id": chat_id})
    out = dict(DEFAULT_SCREEN_CFG)
    if doc:
        for k in DEFAULT_SCREEN_CFG:
            if k in doc and doc[k] is not None:
                out[k] = doc[k]
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


async def update_screen_cfg(chat_id: int, **kwargs) -> dict:
    db = await get_db()
    col = db["join_screen_cfg"]
    current = await get_screen_cfg(chat_id)
    for k, v in kwargs.items():
        if k in DEFAULT_SCREEN_CFG:
            current[k] = v
    current["updated_at"] = time.time()
    await col.update_one({"chat_id": chat_id}, {"$set": current}, upsert=True)
    return current


# ==========================================
# --- POST-APPROVAL PROBATION & AUTO-VERIFY ---
# ==========================================

async def start_post_approval_probation(
    client: Client, chat_id: int, user_id: int, cfg: dict | None = None
) -> bool:
    """Places an approved user on probation if enabled. Returns True if applied."""
    active_cfg = cfg or await get_screen_cfg(chat_id)
    if not active_cfg.get("probation_enabled", True):
        return False

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}:
            return False
    except Exception:
        pass

    prob_mins = int(active_cfg.get("probation_minutes", 30))
    unlock_msgs = int(active_cfg.get("probation_unlock_msgs", 3))
    now = time.time()
    expires_at = now + (prob_mins * 60)

    try:
        await client.restrict_chat_member(chat_id, user_id, PROBATION_PERMS)
    except Exception:
        return False

    db = await get_db()
    await db["join_probation"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "chat_id": chat_id,
                "user_id": user_id,
                "msgs_sent": 0,
                "unlock_msgs": unlock_msgs,
                "expires_at": expires_at,
                "started_at": now,
                "verified": False,
            }
        },
        upsert=True,
    )
    await db["qol_members"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"verified": False}},
    )
    return True


async def complete_probation_verification(
    client: Client, chat_id: int, user_id: int, reason: str = "Auto-verified"
) -> None:
    """Restores full member permissions and marks the user as verified."""
    try:
        await client.restrict_chat_member(chat_id, user_id, FULL_MEMBER_PERMS)
    except Exception:
        pass

    db = await get_db()
    now = time.time()
    await db["join_probation"].delete_one({"chat_id": chat_id, "user_id": user_id})
    await db["qol_members"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "verified": True,
                "verified_at": now,
                "verify_reason": reason,
            }
        },
    )


async def evaluate_and_progress_probation(
    client: Client, chat_id: int, user_id: int
) -> bool:
    """Increments probation message counter and auto-verifies when threshold or timer is met.

    Returns True if the user was just auto-verified on this check.
    """
    db = await get_db()
    prob = await db["join_probation"].find_one({"chat_id": chat_id, "user_id": user_id})
    if not prob:
        return False

    now = time.time()
    expires_at = float(prob.get("expires_at", 0))
    unlock_msgs = max(1, int(prob.get("unlock_msgs", 3)))
    msgs_sent = int(prob.get("msgs_sent", 0)) + 1

    if now >= expires_at:
        await complete_probation_verification(client, chat_id, user_id, reason="Probation timer elapsed")
        return True

    await db["join_probation"].update_one(
        {"_id": prob["_id"]},
        {"$set": {"msgs_sent": msgs_sent, "last_msg_at": now}},
    )

    if msgs_sent >= unlock_msgs:
        await complete_probation_verification(
            client, chat_id, user_id, reason=f"Sent {msgs_sent}/{unlock_msgs} messages"
        )
        return True

    return False


async def sweep_expired_probations(client: Client) -> int:
    """Periodic cleanup job that auto-unlocks members whose probation timer has expired."""
    db = await get_db()
    now = time.time()
    cursor = db["join_probation"].find({"expires_at": {"$lte": now}}).limit(100)
    expired_docs = [doc async for doc in cursor]

    unlocked_count = 0
    for doc in expired_docs:
        chat_id = doc.get("chat_id")
        user_id = doc.get("user_id")
        if chat_id is None or user_id is None:
            continue
        await complete_probation_verification(
            client, int(chat_id), int(user_id), reason="Probation timer expired (cleanup sweep)"
        )
        unlocked_count += 1
    return unlocked_count


async def ensure_probation_scheduler_started(client: Client) -> AsyncIOScheduler:
    """Starts AsyncIOScheduler once to periodically sweep expired probation records."""
    global _prob_scheduler
    if _prob_scheduler is not None and _prob_scheduler.running:
        return _prob_scheduler

    async with _prob_scheduler_lock:
        if _prob_scheduler is not None and _prob_scheduler.running:
            return _prob_scheduler
        sched = AsyncIOScheduler(timezone="UTC")
        sched.add_job(
            sweep_expired_probations,
            trigger=IntervalTrigger(minutes=PROBATION_SWEEP_MINUTES),
            args=[client],
            id="join_probation_cleanup_sweep",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        sched.start()
        _prob_scheduler = sched
        return _prob_scheduler


# ==========================================
# --- JOIN RISK SCORING ---
# ==========================================

async def evaluate_join_risk(chat_id: int, join_req: ChatJoinRequest) -> tuple[int, list[str]]:
    """Computes a 0-100 risk score and returns (score, flags)."""
    user = join_req.from_user
    if not user:
        return 100, ["Missing user object"]

    score = 0
    flags: list[str] = []

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    bio = (getattr(join_req, "bio", None) or "").strip()

    if not user.username:
        score += 15
        flags.append("No @username (+15)")

    if getattr(user, "photo", None) is None:
        score += 20
        flags.append("No profile photo (+20)")

    if getattr(user, "is_scam", False):
        score += 80
        flags.append("Telegram Scam flag (+80)")

    if getattr(user, "is_fake", False):
        score += 70
        flags.append("Telegram Fake flag (+70)")

    combined_text = f"{full_name} {bio}".strip()
    if combined_text and SUSPICIOUS_PATTERNS.search(combined_text):
        score += 45
        flags.append("Promo/link pattern in name or bio (+45)")

    if len(full_name) > 50:
        score += 10
        flags.append("Unusually long display name (+10)")

    db = await get_db()
    prior_member = await db["qol_members"].find_one({"chat_id": chat_id, "user_id": user.id})
    if prior_member:
        warns = int(prior_member.get("warns", 0))
        if warns > 0:
            pts = min(40, warns * 15)
            score += pts
            flags.append(f"Prior warnings: {warns} (+{pts})")

    prev_declines = await db["join_screen_requests"].count_documents({
        "chat_id": chat_id,
        "user_id": user.id,
        "status": {"$in": ["declined", "banned"]},
    })
    if prev_declines > 0:
        pts = min(50, prev_declines * 25)
        score += pts
        flags.append(f"Prior declines/bans: {prev_declines} (+{pts})")

    return min(100, score), flags


# ==========================================
# --- UI CARDS & INLINE KEYBOARDS ---
# ==========================================

def build_screening_keyboard(req_id: str, chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"scr_act_{req_id}_approve"),
            InlineKeyboardButton("❌ Decline", callback_data=f"scr_act_{req_id}_decline"),
            InlineKeyboardButton("🚫 Decline & Ban", callback_data=f"scr_act_{req_id}_ban"),
        ],
        [
            InlineKeyboardButton("🔄 Re-check", callback_data=f"scr_recheck_{req_id}"),
            InlineKeyboardButton("✖️ Dismiss Card", callback_data="scr_close"),
        ],
    ])


async def build_screen_config_card(chat_id: int, title: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    cfg = await get_screen_cfg(chat_id, title=title)
    db = await get_db()
    pending_cnt = await db["join_screen_requests"].count_documents({"chat_id": chat_id, "status": "pending"})
    prob_cnt = await db["join_probation"].count_documents({"chat_id": chat_id})

    enabled = bool(cfg.get("enabled", True))
    auto_app = bool(cfg.get("auto_approve_clean", False))
    auto_dec = bool(cfg.get("auto_decline_high_risk", False))
    app_thr = int(cfg.get("auto_approve_threshold", 15))
    dec_thr = int(cfg.get("auto_decline_threshold", 75))
    prob_on = bool(cfg.get("probation_enabled", True))
    prob_mins = int(cfg.get("probation_minutes", 30))
    unlock_msgs = int(cfg.get("probation_unlock_msgs", 3))
    log_dest = cfg.get("screen_log_chat_id")
    log_label = f"`{log_dest}`" if log_dest else "_Group Admins DM_"

    text = (
        f"🛡️ **Join Screening Settings — {cfg['title']}** (`{chat_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Screening:** {'🟢 ON' if enabled else '🔴 OFF'}\n"
        f"• **Auto-Approve Clean:** {'🟢 ON' if auto_app else '🟡 OFF'} (score `< {app_thr}`)\n"
        f"• **Auto-Decline High Risk:** {'🔴 ON' if auto_dec else '🟡 OFF'} (score `>= {dec_thr}`)\n"
        f"• **Post-Approval Probation:** {'🟢 ON' if prob_on else '🟡 OFF'} (`{prob_mins}m` or `{unlock_msgs}` msgs • `{prob_cnt}` active)\n"
        f"• **Auto-Unlock Sweep:** Every `{PROBATION_SWEEP_MINUTES}m`\n"
        f"• **DM Alert Target:** {log_label}\n"
        f"• **Pending Requests:** `{pending_cnt}`"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 Screening: ON" if enabled else "🔴 Screening: OFF",
                callback_data=f"scr_tog_{chat_id}_enabled",
            ),
            InlineKeyboardButton(
                "🟢 Auto-Approve: ON" if auto_app else "🟡 Auto-Approve: OFF",
                callback_data=f"scr_tog_{chat_id}_autoapp",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔴 Auto-Decline: ON" if auto_dec else "🟡 Auto-Decline: OFF",
                callback_data=f"scr_tog_{chat_id}_autodec",
            ),
            InlineKeyboardButton(
                "🟢 Probation: ON" if prob_on else "🟡 Probation: OFF",
                callback_data=f"scr_tog_{chat_id}_prob",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if prob_mins == m else ''}{m}m",
                callback_data=f"scr_pmin_{chat_id}_{m}",
            )
            for m in ALLOWED_PROBATION_MINS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if unlock_msgs == n else ''}{n} msgs unlock",
                callback_data=f"scr_pmsg_{chat_id}_{n}",
            )
            for n in ALLOWED_UNLOCK_MSGS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if app_thr == t else ''}Approve < {t}",
                callback_data=f"scr_thr_{chat_id}_{t}",
            )
            for t in (0, 15, 25, 40)
        ],
        [
            InlineKeyboardButton(
                "📍 Use This DM as Target" if log_dest != chat_id else "📍 Reset to Admins DM",
                callback_data=f"scr_setdest_{chat_id}",
            ),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"scr_cfg_{chat_id}"),
        ],
        [InlineKeyboardButton("✖️ Close", callback_data="scr_close")],
    ])
    return text, kb


async def _dispatch_screening_card(
    client: Client,
    cfg: dict,
    req_doc: dict,
) -> int:
    """Sends the join-request card with inline buttons to configured log chat or group admins in DM."""
    chat_id = int(req_doc["chat_id"])
    user_id = int(req_doc["user_id"])
    req_id = req_doc["req_id"]
    score = int(req_doc.get("risk_score", 0))
    flags = req_doc.get("flags") or []
    uname = f"@{req_doc['username']}" if req_doc.get("username") else "None"
    bio = req_doc.get("bio") or ""

    risk_badge = "🟢 Low" if score < 25 else ("🟡 Medium" if score < 60 else "🔴 High")
    flag_block = "\n".join(f"  • {f}" for f in flags) if flags else "  • _No red flags triggered_"
    bio_line = f"\n• **Join Bio:** `{bio[:180]}`" if bio else ""

    card_text = (
        f"🚪 **Join Request — {cfg['title']}** (`{chat_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Applicant:** **{req_doc.get('full_name', user_id)}** (`{user_id}`)\n"
        f"• **Username:** {uname}\n"
        f"• **Risk Level:** {risk_badge} (`{score}/100`)\n"
        f"• **Request ID:** `{req_id}`{bio_line}\n\n"
        f"**Signals:**\n{flag_block}"
    )
    kb = build_screening_keyboard(req_id, chat_id, user_id)

    sent_count = 0
    dest = cfg.get("screen_log_chat_id")
    if dest:
        try:
            await client.send_message(int(dest), _truncate(card_text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            sent_count += 1
        except Exception:
            pass

    if sent_count == 0:
        try:
            async for member in client.get_chat_members(chat_id):
                if member.user and not member.user.is_bot and member.status in {
                    ChatMemberStatus.OWNER,
                    ChatMemberStatus.ADMINISTRATOR,
                }:
                    try:
                        await client.send_message(
                            member.user.id,
                            _truncate(card_text),
                            reply_markup=kb,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        sent_count += 1
                    except Exception:
                        continue
        except Exception:
            pass

    return sent_count


# ==========================================
# --- EVENT & COMMAND HANDLERS ---
# ==========================================

@app.on_chat_join_request()
async def on_chat_join_request_handler(client: Client, join_req: ChatJoinRequest):
    await ensure_probation_scheduler_started(client)
    chat = join_req.chat
    user = join_req.from_user
    if not chat or not user or user.is_bot:
        return

    chat_id = chat.id
    cfg = await get_screen_cfg(chat_id, title=chat.title)
    if not cfg.get("enabled", True):
        return

    now = time.time()
    req_id = f"jr_{int(now * 1000)}_{abs(user.id) % 10000}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or str(user.id)
    bio = (getattr(join_req, "bio", None) or "").strip()[:240]

    score, flags = await evaluate_join_risk(chat_id, join_req)
    auto_app = bool(cfg.get("auto_approve_clean", False))
    auto_dec = bool(cfg.get("auto_decline_high_risk", False))
    app_thr = int(cfg.get("auto_approve_threshold", 15))
    dec_thr = int(cfg.get("auto_decline_threshold", 75))

    db = await get_db()

    if auto_app and score < app_thr:
        try:
            await client.approve_chat_join_request(chat_id, user.id)
            prob_applied = await start_post_approval_probation(client, chat_id, user.id, cfg=cfg)
            await db["join_screen_requests"].insert_one({
                "req_id": req_id,
                "chat_id": chat_id,
                "user_id": user.id,
                "full_name": full_name[:64],
                "username": user.username,
                "bio": bio,
                "risk_score": score,
                "flags": flags,
                "status": "auto_approved",
                "probation_applied": prob_applied,
                "created_at": now,
                "resolved_at": now,
            })
            return
        except Exception:
            pass

    if auto_dec and score >= dec_thr:
        try:
            await client.decline_chat_join_request(chat_id, user.id)
            await db["join_screen_requests"].insert_one({
                "req_id": req_id,
                "chat_id": chat_id,
                "user_id": user.id,
                "full_name": full_name[:64],
                "username": user.username,
                "bio": bio,
                "risk_score": score,
                "flags": flags,
                "status": "auto_declined",
                "created_at": now,
                "resolved_at": now,
            })
            return
        except Exception:
            pass

    req_doc = {
        "req_id": req_id,
        "chat_id": chat_id,
        "user_id": user.id,
        "full_name": full_name[:64],
        "username": user.username,
        "bio": bio,
        "risk_score": score,
        "flags": flags,
        "status": "pending",
        "created_at": now,
    }
    await db["join_screen_requests"].insert_one(req_doc)
    await _dispatch_screening_card(client, cfg, req_doc)


@app.on_message(filters.group & ~filters.service, group=5)
async def on_group_probation_progress(client: Client, message: Message):
    """Advances post-approval probation and auto-verifies once message or timer threshold is met."""
    await ensure_probation_scheduler_started(client)
    if not message.from_user or message.from_user.is_bot:
        return
    unlocked = await evaluate_and_progress_probation(client, message.chat.id, message.from_user.id)
    if unlocked:
        try:
            await message.reply_text(
                f"✅ {message.from_user.mention} has completed probation and is now **Verified**!",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


@app.on_message(filters.command(["screencfg", "joinscreen"]) & (filters.group | filters.private))
async def cmd_screen_cfg(client: Client, message: Message):
    await ensure_probation_scheduler_started(client)
    actor_id = message.from_user.id if message.from_user else None
    if not actor_id:
        return

    if message.chat.type == ChatType.PRIVATE:
        args = message.command[1:]
        if not args:
            db = await get_db()
            recent = [
                d async for d in db["join_screen_cfg"].find({}).sort("updated_at", -1).limit(8)
            ]
            admin_groups = []
            for g in recent:
                gid = g.get("chat_id")
                if gid is not None and await is_admin(client, int(gid), actor_id):
                    admin_groups.append(g)
            if not admin_groups:
                return await message.reply_text(
                    "🛡️ Run `/screencfg` inside your group or pass a chat ID: `/screencfg -1001234567890`.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            rows = [
                [
                    InlineKeyboardButton(
                        f"🛡️ {(g.get('title') or str(g['chat_id']))[:26]}",
                        callback_data=f"scr_cfg_{int(g['chat_id'])}",
                    )
                ]
                for g in admin_groups
            ]
            rows.append([InlineKeyboardButton("✖️ Close", callback_data="scr_close")])
            return await message.reply_text(
                "🛡️ **Select Group for Join Screening Settings:**",
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode=ParseMode.MARKDOWN,
            )

        raw = args[0].strip()
        try:
            lookup: int | str = int(raw) if raw.lstrip("-").isdigit() else raw
            chat_obj = await client.get_chat(lookup)
            chat_id = chat_obj.id
            title = chat_obj.title
        except Exception as exc:
            return await message.reply_text(f"❌ Invalid group `{raw}`: `{exc}`", parse_mode=ParseMode.MARKDOWN)

        if not await is_admin(client, chat_id, actor_id):
            return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)
        text, kb = await build_screen_config_card(chat_id, title=title)
        return await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    chat_id = message.chat.id
    if not await is_admin(client, chat_id, actor_id):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)
    text, kb = await build_screen_config_card(chat_id, title=message.chat.title)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^scr_act_(?P<reqid>jr_\d+_\d+)_(?P<act>approve|decline|ban)$"))
async def cb_screen_action(client: Client, query: CallbackQuery):
    req_id = query.matches[0].group("reqid")
    act = query.matches[0].group("act")
    db = await get_db()
    req_doc = await db["join_screen_requests"].find_one({"req_id": req_id})
    if not req_doc:
        return await query.answer("Join request record not found.", show_alert=True)

    chat_id = int(req_doc["chat_id"])
    user_id = int(req_doc["user_id"])
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    status_label = ""
    if act == "approve":
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            cfg = await get_screen_cfg(chat_id)
            prob_applied = await start_post_approval_probation(client, chat_id, user_id, cfg=cfg)
            status_label = "✅ Approved" + (" (on probation)" if prob_applied else " (verified)")
        except Exception as exc:
            return await query.answer(f"Approve failed: {str(exc)[:120]}", show_alert=True)

    elif act == "decline":
        try:
            await client.decline_chat_join_request(chat_id, user_id)
            status_label = "❌ Declined"
        except Exception as exc:
            return await query.answer(f"Decline failed: {str(exc)[:120]}", show_alert=True)

    elif act == "ban":
        try:
            await client.decline_chat_join_request(chat_id, user_id)
        except Exception:
            pass
        try:
            await client.ban_chat_member(chat_id, user_id)
            status_label = "🚫 Declined & Banned"
        except Exception as exc:
            return await query.answer(f"Ban failed: {str(exc)[:120]}", show_alert=True)

    await db["join_screen_requests"].update_one(
        {"req_id": req_id},
        {
            "$set": {
                "status": act,
                "resolved_by": query.from_user.id,
                "resolved_at": time.time(),
            }
        },
    )
    await query.answer(f"{req_id}: {status_label}", show_alert=True)

    updated = (
        f"{query.message.text or f'Request `{req_id}`'}\n\n"
        f"**Decision:** {status_label} by `{query.from_user.id}` (`{_fmt_ts(time.time())}`)"
    )
    try:
        await query.message.edit_text(_truncate(updated), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^scr_recheck_(?P<reqid>jr_\d+_\d+)$"))
async def cb_screen_recheck(client: Client, query: CallbackQuery):
    req_id = query.matches[0].group("reqid")
    db = await get_db()
    req_doc = await db["join_screen_requests"].find_one({"req_id": req_id})
    if not req_doc:
        return await query.answer("Request not found.", show_alert=True)

    chat_id = int(req_doc["chat_id"])
    user_id = int(req_doc["user_id"])
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    score = 0
    flags: list[str] = []
    uname = req_doc.get("username")
    full_name = req_doc.get("full_name") or ""
    bio = req_doc.get("bio") or ""

    try:
        u = await client.get_users(user_id)
        uname = u.username
        full_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or full_name
        if not u.username:
            score += 15
            flags.append("No @username (+15)")
        if getattr(u, "photo", None) is None:
            score += 20
            flags.append("No profile photo (+20)")
        if getattr(u, "is_scam", False):
            score += 80
            flags.append("Telegram Scam flag (+80)")
        if getattr(u, "is_fake", False):
            score += 70
            flags.append("Telegram Fake flag (+70)")
    except Exception:
        pass

    if f"{full_name} {bio}".strip() and SUSPICIOUS_PATTERNS.search(f"{full_name} {bio}"):
        score += 45
        flags.append("Promo/link pattern in name or bio (+45)")

    score = min(100, score)
    await db["join_screen_requests"].update_one(
        {"req_id": req_id},
        {"$set": {"risk_score": score, "flags": flags, "full_name": full_name[:64], "username": uname}},
    )
    cfg = await get_screen_cfg(chat_id)
    risk_badge = "🟢 Low" if score < 25 else ("🟡 Medium" if score < 60 else "🔴 High")
    flag_block = "\n".join(f"  • {f}" for f in flags) if flags else "  • _No red flags triggered_"
    uname_disp = f"@{uname}" if uname else "None"

    card_text = (
        f"🚪 **Join Request — {cfg['title']}** (`{chat_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Applicant:** **{full_name}** (`{user_id}`)\n"
        f"• **Username:** {uname_disp}\n"
        f"• **Risk Level:** {risk_badge} (`{score}/100`)\n"
        f"• **Request ID:** `{req_id}`\n\n"
        f"**Signals (Re-checked):**\n{flag_block}"
    )
    await query.answer(f"Risk updated: {score}/100", show_alert=False)
    try:
        await query.message.edit_text(
            _truncate(card_text),
            reply_markup=build_screening_keyboard(req_id, chat_id, user_id),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^scr_cfg_(?P<chatid>-?\d+)$"))
async def cb_screen_cfg_open(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    text, kb = await build_screen_config_card(chat_id)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_tog_(?P<chatid>-?\d+)_(?P<key>enabled|autoapp|autodec|prob)$"))
async def cb_screen_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    key = query.matches[0].group("key")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    field_map = {
        "enabled": "enabled",
        "autoapp": "auto_approve_clean",
        "autodec": "auto_decline_high_risk",
        "prob": "probation_enabled",
    }
    field = field_map[key]
    cfg = await get_screen_cfg(chat_id)
    nxt = not bool(cfg.get(field, False))
    await update_screen_cfg(chat_id, **{field: nxt})
    await query.answer("🟢 Enabled" if nxt else "🔴 Disabled", show_alert=True)

    text, kb = await build_screen_config_card(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_pmin_(?P<chatid>-?\d+)_(?P<mins>\d+)$"))
async def cb_screen_prob_mins(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    mins = int(query.matches[0].group("mins"))
    if mins not in ALLOWED_PROBATION_MINS:
        return await query.answer("Invalid probation duration.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_screen_cfg(chat_id, probation_minutes=mins)
    await query.answer(f"Probation duration -> {mins}m", show_alert=True)
    text, kb = await build_screen_config_card(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_pmsg_(?P<chatid>-?\d+)_(?P<msgs>\d+)$"))
async def cb_screen_prob_msgs(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    msgs = int(query.matches[0].group("msgs"))
    if msgs not in ALLOWED_UNLOCK_MSGS:
        return await query.answer("Invalid message threshold.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_screen_cfg(chat_id, probation_unlock_msgs=msgs)
    await query.answer(f"Auto-verify after -> {msgs} msgs", show_alert=True)
    text, kb = await build_screen_config_card(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_setdest_(?P<chatid>-?\d+)$"))
async def cb_screen_set_dest(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_screen_cfg(chat_id)
    msg_chat_id = query.message.chat.id if query.message and query.message.chat else None
    is_pm = bool(query.message and query.message.chat and query.message.chat.type == ChatType.PRIVATE)

    if cfg.get("screen_log_chat_id") == msg_chat_id:
        await update_screen_cfg(chat_id, screen_log_chat_id=None)
        await query.answer("Reset to group admins DM", show_alert=True)
    elif is_pm and msg_chat_id:
        await update_screen_cfg(chat_id, screen_log_chat_id=msg_chat_id)
        await query.answer("📍 This DM set as screening alert target", show_alert=True)
    else:
        await query.answer("Open in DM to set a DM alert target", show_alert=True)

    text, kb = await build_screen_config_card(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_thr_(?P<chatid>-?\d+)_(?P<thr>\d+)$"))
async def cb_screen_threshold(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    thr = int(query.matches[0].group("thr"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    await update_screen_cfg(chat_id, auto_approve_threshold=thr)
    await query.answer(f"Auto-approve threshold set to < {thr}", show_alert=True)
    text, kb = await build_screen_config_card(chat_id)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^scr_close$"))
async def cb_screen_close(client: Client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass
