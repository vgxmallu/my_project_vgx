import os
import re
import time
from datetime import datetime, timezone
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import (
    CallbackQuery,
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

DEFAULT_LOOP_CFG = {
    "rep_enabled": True,
    "allow_thanks_trigger": False,
    "daily_giver_limit": 5,
    "pair_cooldown_hours": 12,
    "streaks_enabled": True,
    "faq_enabled": True,
}

ALLOWED_DAILY_LIMITS = [3, 5, 8, 12]
ALLOWED_PAIR_COOLDOWNS = [1, 6, 12, 24]
REP_MILESTONES = [5, 20, 50, 100]
STREAK_MILESTONES = [7, 14, 30]

PLUS_REP_RE = re.compile(r"^\s*(?:\+{1,2}\s*rep|kudos)\b(?:\s+(.+))?$", re.IGNORECASE | re.DOTALL)
THANKS_REP_RE = re.compile(r"^\s*(?:thanks|thx|ty)\b(?:\s+(.+))?$", re.IGNORECASE | re.DOTALL)

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False


def _today_key(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _day_ordinal(ts: float | None = None) -> int:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)
    return dt.date().toordinal()


def _rank_for_rep(rep: int) -> tuple[str, str]:
    if rep >= 100:
        return "👑", "Legend"
    if rep >= 50:
        return "🌟", "Veteran"
    if rep >= 20:
        return "🛡️", "Trusted"
    if rep >= 5:
        return "✨", "Helper"
    return "🌱", "Newcomer"


def _format_duration(seconds: float) -> str:
    secs = max(1, int(seconds))
    hrs, rem = divmod(secs, 3600)
    mins, _ = divmod(rem, 60)
    if hrs > 0 and mins > 0:
        return f"{hrs}h {mins}m"
    if hrs > 0:
        return f"{hrs}h"
    return f"{max(1, mins)}m"


def _slugify_topic(raw: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (raw or "").strip().lower()).strip("-")
    return cleaned[:32] or f"faq-{int(time.time())}"


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
        await db["loop_groups"].create_indexes([IndexModel([("chat_id", 1)], unique=True)])
        await db["loop_members"].create_indexes([
            IndexModel([("chat_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("chat_id", 1), ("rep", -1)]),
            IndexModel([("chat_id", 1), ("weekly_rep", -1)]),
            IndexModel([("chat_id", 1), ("streak_days", -1)]),
        ])
        await db["loop_rep_events"].create_indexes([
            IndexModel([("chat_id", 1), ("giver_id", 1), ("created_at", -1)]),
            IndexModel([("chat_id", 1), ("giver_id", 1), ("receiver_id", 1), ("created_at", -1)]),
            IndexModel([("created_at", 1)], expireAfterSeconds=90 * 86400),
        ])
        await db["loop_faqs"].create_indexes([
            IndexModel([("chat_id", 1), ("topic", 1)], unique=True),
            IndexModel([("chat_id", 1), ("updated_at", -1)]),
        ])
        _indexes_ready = True
    return db


async def get_loop_cfg(chat_id: int, title: str | None = None) -> dict:
    db = await get_db()
    col = db["loop_groups"]
    doc = await col.find_one({"chat_id": chat_id})
    out = dict(DEFAULT_LOOP_CFG)
    if doc:
        for k in DEFAULT_LOOP_CFG:
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


async def update_loop_cfg(chat_id: int, **kwargs) -> dict:
    db = await get_db()
    col = db["loop_groups"]
    current = await get_loop_cfg(chat_id)
    for k, v in kwargs.items():
        if k in DEFAULT_LOOP_CFG:
            current[k] = v
    current["updated_at"] = time.time()
    await col.update_one({"chat_id": chat_id}, {"$set": current}, upsert=True)
    return current


# ==========================================
# --- STREAKS, MILESTONES & BADGES ---
# ==========================================

async def record_daily_activity(chat_id: int, user_id: int, display_name: str, now_ts: float | None = None) -> dict:
    """Updates daily activity streak on UTC calendar days and keeps display name fresh."""
    cfg = await get_loop_cfg(chat_id)
    db = await get_db()
    col = db["loop_members"]
    now = now_ts if now_ts is not None else time.time()
    today_ord = _day_ordinal(now)
    today_str = _today_key(now)

    doc = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not doc:
        new_doc = {
            "chat_id": chat_id,
            "user_id": user_id,
            "name": (display_name or str(user_id))[:64],
            "rep": 0,
            "weekly_rep": 0,
            "weekly_reset_at": now + 7 * 86400,
            "streak_days": 1 if cfg.get("streaks_enabled", True) else 0,
            "best_streak": 1 if cfg.get("streaks_enabled", True) else 0,
            "last_active_day": today_str,
            "last_active_ord": today_ord,
            "badge_opt_in": True,
            "recent_reasons": [],
            "updated_at": now,
        }
        await col.update_one({"chat_id": chat_id, "user_id": user_id}, {"$set": new_doc}, upsert=True)
        return new_doc

    streak = int(doc.get("streak_days", 0))
    best_streak = int(doc.get("best_streak", 0))
    last_ord = doc.get("last_active_ord")

    if cfg.get("streaks_enabled", True):
        if last_ord is None:
            streak = 1
        elif today_ord == int(last_ord):
            streak = max(1, streak)
        elif today_ord == int(last_ord) + 1:
            streak = max(1, streak) + 1
        else:
            streak = 1
        best_streak = max(best_streak, streak)

    weekly_rep = int(doc.get("weekly_rep", 0))
    weekly_reset_at = float(doc.get("weekly_reset_at", now + 7 * 86400))
    if now >= weekly_reset_at:
        weekly_rep = 0
        weekly_reset_at = now + 7 * 86400

    patch = {
        "name": (display_name or doc.get("name") or str(user_id))[:64],
        "streak_days": streak,
        "best_streak": best_streak,
        "last_active_day": today_str,
        "last_active_ord": today_ord,
        "weekly_rep": weekly_rep,
        "weekly_reset_at": weekly_reset_at,
        "updated_at": now,
    }
    await col.update_one({"chat_id": chat_id, "user_id": user_id}, {"$set": patch})
    doc.update(patch)
    return doc


async def toggle_badge_opt_in(chat_id: int, user_id: int, display_name: str = "") -> bool:
    db = await get_db()
    col = db["loop_members"]
    doc = await col.find_one({"chat_id": chat_id, "user_id": user_id}) or {}
    current = bool(doc.get("badge_opt_in", True))
    nxt = not current
    await col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "badge_opt_in": nxt,
                "name": (display_name or doc.get("name") or str(user_id))[:64],
                "updated_at": time.time(),
            },
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
                "rep": 0,
                "weekly_rep": 0,
                "streak_days": 0,
                "best_streak": 0,
                "recent_reasons": [],
            },
        },
        upsert=True,
    )
    return nxt


# ==========================================
# --- RATE-LIMITED +REP / KUDOS ENGINE ---
# ==========================================

async def check_rep_limits(chat_id: int, giver_id: int, receiver_id: int, cfg: dict) -> tuple[bool, str]:
    db = await get_db()
    events = db["loop_rep_events"]
    now = time.time()

    daily_limit = int(cfg.get("daily_giver_limit", 5))
    pair_cd_secs = int(cfg.get("pair_cooldown_hours", 12)) * 3600

    last_pair = await events.find_one(
        {"chat_id": chat_id, "giver_id": giver_id, "receiver_id": receiver_id},
        sort=[("created_at", -1)],
    )
    if last_pair:
        elapsed = now - float(last_pair.get("created_at", 0))
        if elapsed < pair_cd_secs:
            rem = _format_duration(pair_cd_secs - elapsed)
            return False, f"Cooldown active for this user — try again in **{rem}**."

    day_ago = now - 86400
    cursor = events.find(
        {"chat_id": chat_id, "giver_id": giver_id, "created_at": {"$gte": day_ago}}
    ).sort("created_at", 1)
    recent_docs = [doc async for doc in cursor]
    if len(recent_docs) >= daily_limit:
        oldest_ts = float(recent_docs[0].get("created_at", now))
        rem = _format_duration(86400 - (now - oldest_ts))
        return False, f"Daily `+rep` limit (`{daily_limit}/24h`) reached — resets in **{rem}**."

    return True, ""


async def award_kudos(
    chat_id: int,
    giver_id: int,
    giver_name: str,
    receiver_id: int,
    receiver_name: str,
    reason: str = "",
) -> tuple[bool, str, dict]:
    cfg = await get_loop_cfg(chat_id)
    if not cfg.get("rep_enabled", True):
        return False, "`+rep` kudos is disabled in this group.", {}

    if giver_id == receiver_id:
        return False, "You cannot give `+rep` to yourself.", {}

    allowed, reason_blocked = await check_rep_limits(chat_id, giver_id, receiver_id, cfg)
    if not allowed:
        return False, reason_blocked, {}

    now = time.time()
    db = await get_db()

    # Keep giver's streak updated too
    await record_daily_activity(chat_id, giver_id, giver_name, now_ts=now)
    prev_doc = await record_daily_activity(chat_id, receiver_id, receiver_name, now_ts=now)

    prev_rep = int(prev_doc.get("rep", 0))
    prev_streak = int(prev_doc.get("streak_days", 0))
    weekly_rep = int(prev_doc.get("weekly_rep", 0))
    weekly_reset_at = float(prev_doc.get("weekly_reset_at", now + 7 * 86400))
    if now >= weekly_reset_at:
        weekly_rep = 0
        weekly_reset_at = now + 7 * 86400

    clean_reason = (reason or "").strip()[:140]

    await db["loop_rep_events"].insert_one({
        "chat_id": chat_id,
        "giver_id": giver_id,
        "receiver_id": receiver_id,
        "reason": clean_reason,
        "created_at": now,
    })

    new_rep = prev_rep + 1
    new_weekly = weekly_rep + 1

    set_fields: dict = {
        "name": (receiver_name or str(receiver_id))[:64],
        "rep": new_rep,
        "weekly_rep": new_weekly,
        "weekly_reset_at": weekly_reset_at,
        "updated_at": now,
    }
    update_ops: dict = {"$set": set_fields}
    if clean_reason:
        update_ops["$push"] = {
            "recent_reasons": {
                "$each": [{"text": clean_reason, "by": giver_id, "at": now}],
                "$slice": -5,
            }
        }

    updated_doc = await db["loop_members"].find_one_and_update(
        {"chat_id": chat_id, "user_id": receiver_id},
        update_ops,
        upsert=True,
        return_document=True,
    ) or {**prev_doc, "rep": new_rep, "weekly_rep": new_weekly}

    milestones_hit: list[str] = []
    for m in REP_MILESTONES:
        if prev_rep < m <= new_rep:
            milestones_hit.append(f"`{m}` Helpful Reps")
    if cfg.get("streaks_enabled", True):
        for s in STREAK_MILESTONES:
            if prev_streak == s:
                milestones_hit.append(f"`{s}d` Activity Streak")

    updated_doc["_milestones_hit"] = milestones_hit
    return True, "", updated_doc


# ==========================================
# --- SMART "WHO KNOWS / FAQ" PINS ---
# ==========================================

async def upsert_faq_entry(
    chat_id: int,
    question: str,
    answer: str,
    author_id: int,
    source_msg_id: int | None = None,
) -> dict:
    db = await get_db()
    col = db["loop_faqs"]
    q_clean = (question or "").strip()[:120]
    a_clean = (answer or "").strip()[:1200]
    topic = _slugify_topic(q_clean)
    now = time.time()

    doc = {
        "chat_id": chat_id,
        "topic": topic,
        "question": q_clean,
        "answer": a_clean,
        "author_id": author_id,
        "source_msg_id": source_msg_id,
        "updated_at": now,
    }
    await col.update_one(
        {"chat_id": chat_id, "topic": topic},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


async def search_faqs(chat_id: int, query_text: str = "", limit: int = 6) -> list[dict]:
    db = await get_db()
    col = db["loop_faqs"]
    q = (query_text or "").strip().lower()
    if not q:
        cursor = col.find({"chat_id": chat_id}).sort("updated_at", -1).limit(limit)
        return [doc async for doc in cursor]

    terms = [t for t in re.split(r"\W+", q) if len(t) >= 2]
    cursor = col.find({"chat_id": chat_id}).sort("updated_at", -1).limit(40)
    all_docs = [doc async for doc in cursor]
    scored: list[tuple[int, dict]] = []
    for d in all_docs:
        hay = f"{d.get('topic', '')} {d.get('question', '')} {d.get('answer', '')}".lower()
        score = sum(1 for t in (terms or [q]) if t in hay)
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda pair: (-pair[0], -float(pair[1].get("updated_at", 0))))
    return [d for _, d in scored[:limit]]


async def delete_faq_topic(chat_id: int, topic: str) -> bool:
    db = await get_db()
    res = await db["loop_faqs"].delete_one({"chat_id": chat_id, "topic": topic})
    return bool(res.deleted_count)


# ==========================================
# --- UI CARDS & INLINE KEYBOARDS ---
# ==========================================

async def build_leaderboard_card(
    chat_id: int, title: str, tab: str = "rep", page: int = 0, page_size: int = 7
) -> tuple[str, InlineKeyboardMarkup]:
    tab = tab if tab in {"rep", "weekly", "streak"} else "rep"
    db = await get_db()
    col = db["loop_members"]

    if tab == "weekly":
        query = {"chat_id": chat_id, "weekly_rep": {"$gt": 0}}
        sort_spec = [("weekly_rep", -1), ("rep", -1)]
        header_label = "Weekly Kudos"
    elif tab == "streak":
        query = {"chat_id": chat_id, "streak_days": {"$gt": 0}}
        sort_spec = [("streak_days", -1), ("best_streak", -1), ("rep", -1)]
        header_label = "Daily Streaks"
    else:
        query = {"chat_id": chat_id, "rep": {"$gt": 0}}
        sort_spec = [("rep", -1), ("streak_days", -1)]
        header_label = "All-Time Rep"

    total = await col.count_documents(query)
    max_page = max(0, (total - 1) // page_size) if total else 0
    page = max(0, min(page, max_page))

    cursor = col.find(query).sort(sort_spec).skip(page * page_size).limit(page_size)
    docs = [doc async for doc in cursor]

    lines = [
        f"🏆 **Community Board — {title}**",
        f"Mode: **{header_label}** • Page `{page + 1}/{max_page + 1}`",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not docs:
        lines.append("_No activity recorded for this tab yet. Reply with `+rep` or stay active daily!_")
    else:
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        for idx, item in enumerate(docs, start=page * page_size + 1):
            prefix = medals.get(idx - 1, f"`{idx}.`")
            rep_val = int(item.get("rep", 0))
            wk_val = int(item.get("weekly_rep", 0))
            st_val = int(item.get("streak_days", 0))
            badge, _ = _rank_for_rep(rep_val)
            badge_str = f" {badge}" if item.get("badge_opt_in", True) else ""
            uname = item.get("name") or str(item.get("user_id"))

            if tab == "weekly":
                metric = f"**`{wk_val}`** wk rep (`{rep_val}` total)"
            elif tab == "streak":
                metric = f"🔥 **`{st_val}d`** streak (`{rep_val}` rep)"
            else:
                metric = f"**`{rep_val}`** rep • 🔥 `{st_val}d`"

            lines.append(f"{prefix}{badge_str} **{uname}** — {metric}")

    tab_row = [
        InlineKeyboardButton(
            f"{'• ' if tab == 'rep' else ''}🏆 Rep",
            callback_data=f"loop_lb_{chat_id}_rep_0",
        ),
        InlineKeyboardButton(
            f"{'• ' if tab == 'weekly' else ''}⚡ Weekly",
            callback_data=f"loop_lb_{chat_id}_weekly_0",
        ),
        InlineKeyboardButton(
            f"{'• ' if tab == 'streak' else ''}🔥 Streak",
            callback_data=f"loop_lb_{chat_id}_streak_0",
        ),
    ]

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"loop_lb_{chat_id}_{tab}_{page - 1}"))
    nav_row.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"loop_lb_{chat_id}_{tab}_{page}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"loop_lb_{chat_id}_{tab}_{page + 1}"))

    kb = InlineKeyboardMarkup([
        tab_row,
        nav_row,
        [
            InlineKeyboardButton("📌 FAQ Pins", callback_data=f"loop_faq_list_{chat_id}_0"),
            InlineKeyboardButton("⚙️ Settings", callback_data=f"loop_cfg_{chat_id}"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="loop_close")],
    ])
    return "\n".join(lines), kb


async def build_faq_list_card(chat_id: int, title: str, page: int = 0, page_size: int = 5) -> tuple[str, InlineKeyboardMarkup]:
    db = await get_db()
    col = db["loop_faqs"]
    total = await col.count_documents({"chat_id": chat_id})
    max_page = max(0, (total - 1) // page_size) if total else 0
    page = max(0, min(page, max_page))

    cursor = col.find({"chat_id": chat_id}).sort("updated_at", -1).skip(page * page_size).limit(page_size)
    faqs = [doc async for doc in cursor]

    lines = [
        f"📌 **Who Knows / FAQ Pins — {title}**",
        f"Page `{page + 1}/{max_page + 1}` • `{total}` saved answers",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    if not faqs:
        lines.append("_No FAQ entries yet. Admins can use `/faq <question> | <answer>` or reply to an answer with `/faq <question>`._")
    else:
        for item in faqs:
            q_txt = item.get("question") or item.get("topic", "Topic")
            t_slug = item.get("topic", "")
            lines.append(f"• **{q_txt}** (`{t_slug}`)")
            rows.append([
                InlineKeyboardButton(f"📖 {q_txt[:26]}", callback_data=f"loop_faq_view_{chat_id}_{t_slug}")
            ])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"loop_faq_list_{chat_id}_{page - 1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"loop_faq_list_{chat_id}_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("🏆 Leaderboard", callback_data=f"loop_lb_{chat_id}_rep_0"),
        InlineKeyboardButton("❌ Close", callback_data="loop_close"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def build_faq_detail_card(chat_id: int, topic: str, is_admin_user: bool) -> tuple[str, InlineKeyboardMarkup]:
    db = await get_db()
    doc = await db["loop_faqs"].find_one({"chat_id": chat_id, "topic": topic})
    if not doc:
        text = f"❓ FAQ topic `{topic}` was not found."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ All FAQs", callback_data=f"loop_faq_list_{chat_id}_0")]
        ])
        return text, kb

    q_txt = doc.get("question") or topic
    a_txt = doc.get("answer") or ""
    auth_id = doc.get("author_id")
    text = (
        f"📌 **FAQ: {q_txt}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{a_txt}\n\n"
        f"_Tagged by `{auth_id}` • Topic: `{topic}`_"
    )
    rows: list[list[InlineKeyboardButton]] = []
    if is_admin_user:
        rows.append([
            InlineKeyboardButton("🗑️ Delete FAQ", callback_data=f"loop_faq_del_{chat_id}_{topic}")
        ])
    rows.append([
        InlineKeyboardButton("⬅️ All FAQs", callback_data=f"loop_faq_list_{chat_id}_0"),
        InlineKeyboardButton("❌ Close", callback_data="loop_close"),
    ])
    return text, InlineKeyboardMarkup(rows)


async def build_loop_config_card(chat_id: int, title: str) -> tuple[str, InlineKeyboardMarkup]:
    cfg = await get_loop_cfg(chat_id, title=title)
    text = (
        f"⚙️ **Community Loop Settings — {cfg['title']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **+Rep System:** {'On ✅' if cfg.get('rep_enabled', True) else 'Off ❌'}\n"
        f"• **Thanks Trigger:** {'On ✅' if cfg.get('allow_thanks_trigger', False) else 'Off ❌'}\n"
        f"• **Daily Giver Quota:** `{cfg.get('daily_giver_limit', 5)}/24h`\n"
        f"• **Same-User Cooldown:** `{cfg.get('pair_cooldown_hours', 12)}h`\n"
        f"• **Activity Streaks:** {'On ✅' if cfg.get('streaks_enabled', True) else 'Off ❌'}\n"
        f"• **FAQ Pins:** {'On ✅' if cfg.get('faq_enabled', True) else 'Off ❌'}"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅' if cfg.get('rep_enabled', True) else '❌'} +Rep",
                callback_data=f"loop_cfg_tog_{chat_id}_rep",
            ),
            InlineKeyboardButton(
                f"{'✅' if cfg.get('allow_thanks_trigger', False) else '❌'} Thanks",
                callback_data=f"loop_cfg_tog_{chat_id}_thanks",
            ),
            InlineKeyboardButton(
                f"{'✅' if cfg.get('streaks_enabled', True) else '❌'} Streaks",
                callback_data=f"loop_cfg_tog_{chat_id}_streak",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if lim == cfg.get('daily_giver_limit') else ''}{lim}/day",
                callback_data=f"loop_cfg_lim_{chat_id}_{lim}",
            )
            for lim in ALLOWED_DAILY_LIMITS
        ],
        [
            InlineKeyboardButton(
                f"{'• ' if cd == cfg.get('pair_cooldown_hours') else ''}{cd}h CD",
                callback_data=f"loop_cfg_cd_{chat_id}_{cd}",
            )
            for cd in ALLOWED_PAIR_COOLDOWNS
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data=f"loop_lb_{chat_id}_rep_0"),
            InlineKeyboardButton("❌ Close", callback_data="loop_close"),
        ],
    ])
    return text, kb


# ==========================================
# --- MESSAGE & COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.group & ~filters.service, group=3)
async def on_group_activity_and_kudos(client: Client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    chat_id = message.chat.id
    giver = message.from_user
    giver_name = giver.first_name or str(giver.id)

    # Track daily activity streak for any non-bot group message
    await record_daily_activity(chat_id, giver.id, giver_name)

    # Check reply-based +rep / kudos (and optional thanks trigger)
    if not message.reply_to_message or not message.text:
        return

    raw_text = message.text.strip()
    match = PLUS_REP_RE.match(raw_text)
    if not match:
        cfg = await get_loop_cfg(chat_id, title=message.chat.title)
        if cfg.get("allow_thanks_trigger", False):
            match = THANKS_REP_RE.match(raw_text)
    if not match:
        return

    receiver = message.reply_to_message.from_user
    if not receiver:
        return
    if receiver.is_bot:
        await message.reply_text("🤖 Bots cannot receive `+rep` kudos.", parse_mode=ParseMode.MARKDOWN)
        return

    reason = (match.group(1) or "").strip()
    receiver_name = receiver.first_name or str(receiver.id)

    ok, block_msg, doc = await award_kudos(
        chat_id=chat_id,
        giver_id=giver.id,
        giver_name=giver_name,
        receiver_id=receiver.id,
        receiver_name=receiver_name,
        reason=reason,
    )
    if not ok:
        await message.reply_text(f"⏳ {block_msg}", parse_mode=ParseMode.MARKDOWN)
        return

    new_rep = int(doc.get("rep", 1))
    streak_days = int(doc.get("streak_days", 1))
    badge, rank_title = _rank_for_rep(new_rep)
    show_badge = bool(doc.get("badge_opt_in", True))

    lines = [
        f"{badge if show_badge else '✨'} **{receiver.mention}** received `+1 rep` from {giver.mention}!",
        f"Score: **`{new_rep}`** rep (**{rank_title}**) • Streak: 🔥 **`{streak_days}d`**",
    ]
    if reason:
        lines.append(f"📝 _{reason}_")
    if doc.get("_milestones_hit"):
        lines.append("🎉 **Milestone Unlocked:** " + ", ".join(doc["_milestones_hit"]))

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏅 Toggle Badge", callback_data=f"loop_badge_{chat_id}_{receiver.id}"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data=f"loop_lb_{chat_id}_rep_0"),
        ]
    ])
    await message.reply_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["leaderboard", "top"]) & filters.group)
async def cmd_leaderboard(client: Client, message: Message):
    if message.from_user and not message.from_user.is_bot:
        await record_daily_activity(
            message.chat.id, message.from_user.id, message.from_user.first_name or str(message.from_user.id)
        )
    title = message.chat.title or str(message.chat.id)
    text, kb = await build_leaderboard_card(message.chat.id, title=title, tab="rep", page=0)
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["badge", "mystats"]) & filters.group)
async def cmd_badge_status(client: Client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    uname = message.from_user.first_name or str(uid)
    doc = await record_daily_activity(message.chat.id, uid, uname)

    rep_val = int(doc.get("rep", 0))
    wk_val = int(doc.get("weekly_rep", 0))
    st_val = int(doc.get("streak_days", 0))
    best_st = int(doc.get("best_streak", st_val))
    badge, rank_title = _rank_for_rep(rep_val)
    opted_in = bool(doc.get("badge_opt_in", True))

    text = (
        f"{badge} **Member Card — {uname}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Reputation:** **`{rep_val}`** rep (**{rank_title}**)\n"
        f"• **Weekly Kudos:** **`{wk_val}`** rep\n"
        f"• **Activity Streak:** 🔥 **`{st_val}d`** (Best: `{best_st}d`)\n"
        f"• **Badge Display:** {'Visible ✅' if opted_in else 'Hidden (Opted Out)'}"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🙈 Hide Badge" if opted_in else "👀 Show Badge",
                callback_data=f"loop_badge_{message.chat.id}_{uid}",
            ),
            InlineKeyboardButton("🏆 Leaderboard", callback_data=f"loop_lb_{message.chat.id}_rep_0"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="loop_close")],
    ])
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["faq"]) & filters.group)
async def cmd_faq(client: Client, message: Message):
    chat_id = message.chat.id
    title = message.chat.title or str(chat_id)
    cfg = await get_loop_cfg(chat_id, title=title)
    if not cfg.get("faq_enabled", True):
        return await message.reply_text("📌 FAQ pins are disabled in this group.", parse_mode=ParseMode.MARKDOWN)

    args_raw = message.text.split(None, 1)[1].strip() if message.text and len(message.text.split(None, 1)) > 1 else ""
    actor_id = message.from_user.id if message.from_user else None

    # Admin adding/updating a FAQ:
    # Case 1: /faq Question | Answer
    # Case 2: Reply to a message + /faq Question
    if args_raw and ("|" in args_raw or message.reply_to_message):
        if not await is_admin(client, chat_id, actor_id):
            return await message.reply_text("⛔ Only admins can add or update FAQ pins.", parse_mode=ParseMode.MARKDOWN)

        if "|" in args_raw:
            q_part, a_part = args_raw.split("|", 1)
        else:
            q_part = args_raw
            replied = message.reply_to_message
            a_part = (replied.text or replied.caption or "").strip() if replied else ""

        if not q_part.strip() or not a_part.strip():
            return await message.reply_text(
                "⚠️ Usage: `/faq <question> | <answer>` or reply to an answer with `/faq <question>`.",
                parse_mode=ParseMode.MARKDOWN,
            )

        src_id = message.reply_to_message.id if message.reply_to_message else None
        saved = await upsert_faq_entry(chat_id, q_part.strip(), a_part.strip(), actor_id or 0, source_msg_id=src_id)
        return await message.reply_text(
            f"📌 Saved FAQ pin **{saved['question']}** (`{saved['topic']}`).",
            parse_mode=ParseMode.MARKDOWN,
        )

    if args_raw:
        matches = await search_faqs(chat_id, args_raw, limit=1)
        if matches:
            text, kb = await build_faq_detail_card(
                chat_id, matches[0]["topic"], is_admin_user=await is_admin(client, chat_id, actor_id)
            )
            return await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    text, kb = await build_faq_list_card(chat_id, title=title, page=0)
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["whoknows"]) & filters.group)
async def cmd_whoknows(client: Client, message: Message):
    """Finds top helpers for a topic and matching FAQ entries."""
    chat_id = message.chat.id
    query_str = message.text.split(None, 1)[1].strip() if message.text and len(message.text.split(None, 1)) > 1 else ""
    if not query_str:
        return await message.reply_text("💡 Usage: `/whoknows <topic or keyword>`", parse_mode=ParseMode.MARKDOWN)

    faqs = await search_faqs(chat_id, query_str, limit=4)
    db = await get_db()
    top_cursor = db["loop_members"].find({"chat_id": chat_id, "rep": {"$gt": 0}}).sort([("rep", -1)]).limit(5)
    top_helpers = [doc async for doc in top_cursor]

    lines = [
        f"🧭 **Who Knows — `{query_str}`**",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    rows: list[list[InlineKeyboardButton]] = []

    if faqs:
        lines.append("**📌 Relevant FAQ Pins:**")
        for f in faqs:
            lines.append(f"• **{f.get('question')}** (`{f.get('topic')}`)")
            rows.append([
                InlineKeyboardButton(f"📖 {f.get('question', 'FAQ')[:26]}", callback_data=f"loop_faq_view_{chat_id}_{f.get('topic')}")
            ])
        lines.append("")

    lines.append("**🏅 Top Rep Contributors:**")
    if not top_helpers:
        lines.append("_No rep contributors recorded yet._")
    else:
        for idx, h in enumerate(top_helpers, start=1):
            badge, rank = _rank_for_rep(int(h.get("rep", 0)))
            lines.append(f"`{idx}.` {badge} **{h.get('name', h.get('user_id'))}** — `{h.get('rep', 0)}` rep ({rank})")

    rows.append([
        InlineKeyboardButton("📌 All FAQs", callback_data=f"loop_faq_list_{chat_id}_0"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data=f"loop_lb_{chat_id}_rep_0"),
        InlineKeyboardButton("❌ Close", callback_data="loop_close"),
    ])
    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command(["loopcfg"]) & filters.group)
async def cmd_loopcfg(client: Client, message: Message):
    uid = message.from_user.id if message.from_user else None
    if not await is_admin(client, message.chat.id, uid):
        return await message.reply_text("⛔ Admins only.", parse_mode=ParseMode.MARKDOWN)
    text, kb = await build_loop_config_card(message.chat.id, title=message.chat.title or str(message.chat.id))
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^loop_lb_(?P<chatid>-?\d+)_(?P<tab>rep|weekly|streak)_(?P<page>\d+)$"))
async def cb_loop_leaderboard(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    tab = query.matches[0].group("tab")
    page = int(query.matches[0].group("page"))
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_leaderboard_card(chat_id, title=title, tab=tab, page=page)
    await query.answer()
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_badge_(?P<chatid>-?\d+)_(?P<userid>\d+)$"))
async def cb_loop_badge_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    target_uid = int(query.matches[0].group("userid"))
    if query.from_user.id != target_uid and not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("You can only toggle your own badge.", show_alert=True)

    uname = query.from_user.first_name if query.from_user.id == target_uid else ""
    nxt = await toggle_badge_opt_in(chat_id, target_uid, display_name=uname)
    await query.answer("Badge visible ✅" if nxt else "Badge hidden 🙈", show_alert=True)


@app.on_callback_query(filters.regex(r"^loop_faq_list_(?P<chatid>-?\d+)_(?P<page>\d+)$"))
async def cb_loop_faq_list(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    page = int(query.matches[0].group("page"))
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_faq_list_card(chat_id, title=title, page=page)
    await query.answer()
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_faq_view_(?P<chatid>-?\d+)_(?P<topic>[a-z0-9-]+)$"))
async def cb_loop_faq_view(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    topic = query.matches[0].group("topic")
    admin_flag = await is_admin(client, chat_id, query.from_user.id)
    text, kb = await build_faq_detail_card(chat_id, topic, is_admin_user=admin_flag)
    await query.answer()
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_faq_del_(?P<chatid>-?\d+)_(?P<topic>[a-z0-9-]+)$"))
async def cb_loop_faq_delete(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    topic = query.matches[0].group("topic")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    deleted = await delete_faq_topic(chat_id, topic)
    await query.answer("FAQ deleted 🗑️" if deleted else "Not found", show_alert=True)
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_faq_list_card(chat_id, title=title, page=0)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_cfg_(?P<chatid>-?\d+)$"))
async def cb_loop_cfg_open(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_loop_config_card(chat_id, title=title)
    await query.answer()
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_cfg_tog_(?P<chatid>-?\d+)_(?P<key>rep|thanks|streak)$"))
async def cb_loop_cfg_toggle(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    key = query.matches[0].group("key")
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)

    cfg = await get_loop_cfg(chat_id)
    field_map = {
        "rep": "rep_enabled",
        "thanks": "allow_thanks_trigger",
        "streak": "streaks_enabled",
    }
    field = field_map[key]
    nxt = not bool(cfg.get(field, False))
    await update_loop_cfg(chat_id, **{field: nxt})
    await query.answer(f"{key.upper()} -> {'On' if nxt else 'Off'}", show_alert=True)

    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_loop_config_card(chat_id, title=title)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_cfg_lim_(?P<chatid>-?\d+)_(?P<lim>\d+)$"))
async def cb_loop_cfg_limit(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    lim = int(query.matches[0].group("lim"))
    if lim not in ALLOWED_DAILY_LIMITS:
        return await query.answer("Invalid limit.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_loop_cfg(chat_id, daily_giver_limit=lim)
    await query.answer(f"Quota -> {lim}/day", show_alert=True)
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_loop_config_card(chat_id, title=title)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_cfg_cd_(?P<chatid>-?\d+)_(?P<cd>\d+)$"))
async def cb_loop_cfg_cooldown(client: Client, query: CallbackQuery):
    chat_id = int(query.matches[0].group("chatid"))
    cd = int(query.matches[0].group("cd"))
    if cd not in ALLOWED_PAIR_COOLDOWNS:
        return await query.answer("Invalid cooldown.", show_alert=True)
    if not await is_admin(client, chat_id, query.from_user.id):
        return await query.answer("⛔ Admins only.", show_alert=True)
    await update_loop_cfg(chat_id, pair_cooldown_hours=cd)
    await query.answer(f"Cooldown -> {cd}h", show_alert=True)
    title = query.message.chat.title if query.message and query.message.chat else str(chat_id)
    text, kb = await build_loop_config_card(chat_id, title=title)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^loop_close$"))
async def cb_loop_close(client: Client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass
