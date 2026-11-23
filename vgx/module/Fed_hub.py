import csv
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pymongo import AsyncMongoClient, IndexModel
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import (
    CallbackQuery,
    ChatJoinRequest,
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

SUPPORTED_LOG_LANGS = ["en", "ml", "hi", "kn", "es"]

_mongo_client: AsyncMongoClient | None = None
_indexes_ready = False


# ==========================================
# --- HELPERS & MONGO INITIALIZATION ---
# ==========================================

def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "Unknown"
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _truncate(text: str, limit: int = 3800) -> str:
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + "\n\n_...truncated_"


def _parse_bool_arg(raw: str | None, current: bool) -> bool:
    if not raw:
        return not current
    val = raw.strip().lower()
    if val in {"yes", "on", "true", "1", "enable", "enabled"}:
        return True
    if val in {"no", "off", "false", "0", "disable", "disabled"}:
        return False
    return not current


async def get_db():
    global _mongo_client, _indexes_ready
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(MONGO_URI)
    db = _mongo_client[MONGO_DB_NAME]
    if not _indexes_ready:
        await db["feds"].create_indexes([
            IndexModel([("fed_id", 1)], unique=True),
            IndexModel([("owner_id", 1)]),
            IndexModel([("admins", 1)]),
        ])
        await db["fed_bans"].create_indexes([
            IndexModel([("fed_id", 1), ("user_id", 1)], unique=True),
            IndexModel([("user_id", 1)]),
        ])
        await db["fed_chat_links"].create_indexes([
            IndexModel([("chat_id", 1)], unique=True),
            IndexModel([("fed_id", 1)]),
        ])
        await db["fed_pending_promos"].create_indexes([
            IndexModel([("promo_id", 1)], unique=True),
        ])
        _indexes_ready = True
    return db


async def is_chat_owner(client: Client, chat_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def is_chat_admin(client: Client, chat_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception:
        return False


async def resolve_user_arg(
    client: Client, message: Message, arg_index: int = 1
) -> tuple[int | None, str, list[str]]:
    """Resolves target user from reply or command token; returns (user_id, name, remaining_args)."""
    args = message.command[1:]
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or str(u.id)
        return u.id, name, args[arg_index - 1 :]

    if len(args) >= arg_index:
        token = args[arg_index - 1].strip()
        rem = args[arg_index:]
        try:
            lookup: int | str = int(token) if token.lstrip("-").isdigit() else token
            u = await client.get_users(lookup)
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or str(u.id)
            return u.id, name, rem
        except Exception:
            if token.lstrip("-").isdigit():
                return int(token), token, rem

    return None, "", args


# ==========================================
# --- FEDERATION DATA ACCESS ---
# ==========================================

async def get_fed(fed_id: str) -> dict | None:
    if not fed_id:
        return None
    db = await get_db()
    return await db["feds"].find_one({"fed_id": fed_id.strip()})


async def get_user_owned_fed(user_id: int) -> dict | None:
    db = await get_db()
    return await db["feds"].find_one({"owner_id": int(user_id)})


async def get_user_admin_feds(user_id: int) -> list[dict]:
    db = await get_db()
    cursor = db["feds"].find({
        "$or": [{"owner_id": int(user_id)}, {"admins": int(user_id)}]
    }).sort("name", 1)
    return [d async for d in cursor]


def is_fed_owner(fed: dict | None, user_id: int | None) -> bool:
    if not fed or not user_id:
        return False
    return int(fed.get("owner_id", 0)) == int(user_id)


def is_fed_admin(fed: dict | None, user_id: int | None) -> bool:
    if not fed or not user_id:
        return False
    uid = int(user_id)
    if int(fed.get("owner_id", 0)) == uid:
        return True
    return uid in {int(a) for a in (fed.get("admins") or [])}


async def get_chat_link(chat_id: int, title: str | None = None) -> dict:
    db = await get_db()
    col = db["fed_chat_links"]
    doc = await col.find_one({"chat_id": int(chat_id)})
    now = time.time()
    if not doc:
        doc = {
            "chat_id": int(chat_id),
            "title": (title or str(chat_id))[:80],
            "fed_id": None,
            "quiet_fed": False,
            "updated_at": now,
        }
        await col.update_one({"chat_id": int(chat_id)}, {"$set": doc}, upsert=True)
    elif title and doc.get("title") != title:
        doc["title"] = title[:80]
        await col.update_one({"chat_id": int(chat_id)}, {"$set": {"title": doc["title"]}})
    return doc


async def set_chat_fed(chat_id: int, fed_id: str | None, title: str | None = None) -> dict:
    db = await get_db()
    cur = await get_chat_link(chat_id, title=title)
    cur["fed_id"] = fed_id
    cur["updated_at"] = time.time()
    await db["fed_chat_links"].update_one({"chat_id": int(chat_id)}, {"$set": cur}, upsert=True)
    return cur


async def set_chat_quiet(chat_id: int, quiet: bool, title: str | None = None) -> dict:
    db = await get_db()
    cur = await get_chat_link(chat_id, title=title)
    cur["quiet_fed"] = bool(quiet)
    cur["updated_at"] = time.time()
    await db["fed_chat_links"].update_one({"chat_id": int(chat_id)}, {"$set": cur}, upsert=True)
    return cur


async def get_effective_fed_chain(fed: dict, visited: set[str] | None = None) -> list[dict]:
    """Returns [fed, ...subscribed_feds] without cycles."""
    seen = visited if visited is not None else set()
    fid = fed.get("fed_id")
    if not fid or fid in seen:
        return []
    seen.add(fid)
    chain = [fed]
    for sub_id in fed.get("subscribed_feds") or []:
        sub_fed = await get_fed(sub_id)
        if sub_fed:
            chain.extend(await get_effective_fed_chain(sub_fed, seen))
    return chain


async def find_ban_in_fed_chain(fed: dict, user_id: int) -> tuple[dict | None, dict | None]:
    """Checks fed and its subscribed feds for a ban on user_id. Returns (ban_doc, source_fed)."""
    db = await get_db()
    chain = await get_effective_fed_chain(fed)
    for f in chain:
        doc = await db["fed_bans"].find_one({"fed_id": f["fed_id"], "user_id": int(user_id)})
        if doc:
            return doc, f
    return None, None


async def send_fed_log(client: Client, fed: dict, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    log_chat = fed.get("log_chat_id")
    if log_chat:
        lang = fed.get("log_lang", "en")
        tagged = f"`[{lang.upper()}]` {text}"
        try:
            await client.send_message(int(log_chat), _truncate(tagged), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    if fed.get("notif_enabled", True):
        owner_id = fed.get("owner_id")
        if owner_id and int(owner_id) != int(log_chat or 0):
            try:
                await client.send_message(int(owner_id), _truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass


async def enforce_fed_ban_in_linked_chats(
    client: Client, fed_id: str, user_id: int, user_name: str, reason: str, quiet_override: bool | None = None
) -> int:
    """Bans user_id across all groups linked to fed_id (and feds subscribing to fed_id)."""
    db = await get_db()
    fed = await get_fed(fed_id)
    if not fed:
        return 0

    subscriber_ids = {fed_id}
    async for f in db["feds"].find({"subscribed_feds": fed_id}):
        if f.get("fed_id"):
            subscriber_ids.add(f["fed_id"])

    banned_chats = 0
    async for link in db["fed_chat_links"].find({"fed_id": {"$in": list(subscriber_ids)}}):
        cid = int(link["chat_id"])
        try:
            await client.ban_chat_member(cid, int(user_id))
            banned_chats += 1
            is_quiet = bool(link.get("quiet_fed", False)) if quiet_override is None else quiet_override
            if not is_quiet:
                try:
                    await client.send_message(
                        cid,
                        f"🌐🚫 **Fedban Enforced**\n"
                        f"• **User:** **{user_name}** (`{user_id}`)\n"
                        f"• **Federation:** **{fed.get('name')}** (`{fed_id}`)\n"
                        f"• **Reason:** _{reason}_",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass
        except Exception:
            continue
    return banned_chats


async def unban_fed_user_in_linked_chats(client: Client, fed_id: str, user_id: int) -> int:
    db = await get_db()
    unbanned = 0
    async for link in db["fed_chat_links"].find({"fed_id": fed_id}):
        try:
            await client.unban_chat_member(int(link["chat_id"]), int(user_id))
            unbanned += 1
        except Exception:
            continue
    return unbanned


# ==========================================
# --- UI CARD BUILDERS ---
# ==========================================

def build_fed_info_card(fed: dict, linked_count: int = 0, ban_count: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    fid = fed["fed_id"]
    subs = fed.get("subscribed_feds") or []
    admins = fed.get("admins") or []
    text = (
        f"🌐 **Federation Info — {fed.get('name')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Fed ID:** `{fid}`\n"
        f"• **Owner ID:** `{fed.get('owner_id')}`\n"
        f"• **Admins:** `{len(admins) + 1}` (incl. owner)\n"
        f"• **Linked Chats:** `{linked_count}`\n"
        f"• **Active Fedbans:** `{ban_count}`\n"
        f"• **Subscribed Feds:** `{len(subs)}`\n"
        f"• **Reason Required:** `{'Yes' if fed.get('require_reason') else 'No'}`\n"
        f"• **Owner Notifs:** `{'On' if fed.get('notif_enabled', True) else 'Off'}`\n"
        f"• **Log Chat:** `{fed.get('log_chat_id') or 'None'}` (`{fed.get('log_lang', 'en')}`)"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👮 Admins", callback_data=f"fh_adm_{fid}_0"),
            InlineKeyboardButton("🔗 Subscribed Feds", callback_data=f"fh_sub_{fid}_0"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"fh_info_{fid}"),
            InlineKeyboardButton("✖️ Close", callback_data="fh_close"),
        ],
    ])
    return text, kb


def build_fed_owner_panel(fed: dict) -> tuple[str, InlineKeyboardMarkup]:
    fid = fed["fed_id"]
    notif_on = bool(fed.get("notif_enabled", True))
    reason_on = bool(fed.get("require_reason", False))
    lang = fed.get("log_lang", "en")

    text = (
        f"👑 **Federation Owner Control — {fed.get('name')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Fed ID:** `{fid}`\n"
        f"• **Owner PM Notifs:** {'🟢 ON' if notif_on else '🔴 OFF'}\n"
        f"• **Reason Required:** {'🟢 YES' if reason_on else '🟡 NO'}\n"
        f"• **Log Language:** `{lang.upper()}`\n"
        f"• **Log Channel:** `{fed.get('log_chat_id') or 'Unset'}`\n"
        f"• **Subscribed Feds:** `{len(fed.get('subscribed_feds') or [])}`"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔔 Notifs: ON" if notif_on else "🔕 Notifs: OFF",
                callback_data=f"fh_otog_{fid}_notif",
            ),
            InlineKeyboardButton(
                "📝 Reason Req: YES" if reason_on else "📝 Reason Req: NO",
                callback_data=f"fh_otog_{fid}_reason",
            ),
        ],
        [
            InlineKeyboardButton(f"🌐 Log Lang: {lang.upper()}", callback_data=f"fh_lang_{fid}"),
            InlineKeyboardButton("👮 Admins", callback_data=f"fh_adm_{fid}_0"),
        ],
        [
            InlineKeyboardButton("🔗 Subscribed", callback_data=f"fh_sub_{fid}_0"),
            InlineKeyboardButton("🗑️ Delete Fed?", callback_data=f"fh_delask_{fid}"),
        ],
        [InlineKeyboardButton("✖️ Close", callback_data="fh_close")],
    ])
    return text, kb


# ==========================================
# --- JOIN & JOIN-REQUEST ENFORCEMENT ---
# ==========================================

async def _check_and_enforce_on_join(
    client: Client, chat_id: int, chat_title: str, user_id: int, user_name: str, is_req: bool = False
) -> None:
    link = await get_chat_link(chat_id, title=chat_title)
    fid = link.get("fed_id")
    if not fid:
        return
    fed = await get_fed(fid)
    if not fed:
        return

    ban_doc, src_fed = await find_ban_in_fed_chain(fed, user_id)
    if not ban_doc:
        return

    reason = ban_doc.get("reason") or "Federated ban"
    src_name = (src_fed or fed).get("name") or fid

    try:
        if is_req:
            await client.decline_chat_join_request(chat_id, user_id)
        await client.ban_chat_member(chat_id, user_id)
    except Exception:
        pass

    if not link.get("quiet_fed", False):
        try:
            await client.send_message(
                chat_id,
                f"🌐🚫 **Federated Ban Match**\n"
                f"• **User:** **{user_name}** (`{user_id}`)\n"
                f"• **Source Fed:** **{src_name}** (`{(src_fed or fed).get('fed_id')}`)\n"
                f"• **Reason:** _{reason}_",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    await send_fed_log(
        client,
        fed,
        f"🌐🚫 Auto-banned **{user_name}** (`{user_id}`) in **{chat_title}** (`{chat_id}`) via **{src_name}** — _{reason}_",
    )


@app.on_message(filters.new_chat_members)
async def on_fed_new_chat_members(client: Client, message: Message):
    cid = message.chat.id
    ctitle = message.chat.title or str(cid)
    await get_chat_link(cid, title=ctitle)
    for m in message.new_chat_members:
        if not m or m.is_bot:
            continue
        await _check_and_enforce_on_join(
            client, cid, ctitle, m.id, m.first_name or str(m.id), is_req=False
        )


@app.on_chat_join_request()
async def on_fed_join_req(client: Client, join_req: ChatJoinRequest):
    if not join_req.chat or not join_req.from_user or join_req.from_user.is_bot:
        return
    cid = join_req.chat.id
    ctitle = join_req.chat.title or str(cid)
    await _check_and_enforce_on_join(
        client,
        cid,
        ctitle,
        join_req.from_user.id,
        join_req.from_user.first_name or str(join_req.from_user.id),
        is_req=True,
    )


# ==========================================
# --- FED ADMIN COMMANDS ---
# ==========================================

@app.on_message(filters.command("fban") & filters.group)
async def cmd_fban(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    link = await get_chat_link(message.chat.id, title=message.chat.title)
    fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("⚠️ This chat is not joined to any federation.", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed or not is_fed_admin(fed, actor.id):
        return await message.reply_text("⛔ You must be a federation admin for this federation.", parse_mode=ParseMode.MARKDOWN)

    target_id, target_name, rem_args = await resolve_user_arg(client, message, arg_index=1)
    if not target_id:
        return await message.reply_text("💡 Reply to a user or use `/fban @username|user_id [reason]`.", parse_mode=ParseMode.MARKDOWN)

    reason = " ".join(rem_args).strip()
    if fed.get("require_reason", False) and not reason:
        return await message.reply_text("⚠️ This federation requires a reason: `/fban <user> <reason>`.", parse_mode=ParseMode.MARKDOWN)

    clean_reason = reason or "No reason given"
    db = await get_db()
    now = time.time()
    await db["fed_bans"].update_one(
        {"fed_id": fid, "user_id": int(target_id)},
        {
            "$set": {
                "fed_id": fid,
                "user_id": int(target_id),
                "user_name": (target_name or str(target_id))[:64],
                "reason": clean_reason[:240],
                "banned_by": actor.id,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    enforced = await enforce_fed_ban_in_linked_chats(
        client, fid, int(target_id), target_name or str(target_id), clean_reason
    )
    await message.reply_text(
        f"🌐🚫 **Fedbanned**\n"
        f"• **Federation:** **{fed.get('name')}** (`{fid}`)\n"
        f"• **User:** **{target_name or target_id}** (`{target_id}`)\n"
        f"• **Enforced in Chats:** `{enforced}`\n"
        f"• **Reason:** _{clean_reason}_",
        parse_mode=ParseMode.MARKDOWN,
    )
    await send_fed_log(
        client,
        fed,
        f"🌐🚫 **Fedban** by `{actor.id}` on **{target_name or target_id}** (`{target_id}`) in `{enforced}` chat(s) — _{clean_reason}_",
    )


@app.on_message(filters.command("unfban") & filters.group)
async def cmd_unfban(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    link = await get_chat_link(message.chat.id, title=message.chat.title)
    fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("⚠️ This chat is not joined to any federation.", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed or not is_fed_admin(fed, actor.id):
        return await message.reply_text("⛔ You must be a federation admin for this federation.", parse_mode=ParseMode.MARKDOWN)

    target_id, target_name, _ = await resolve_user_arg(client, message, arg_index=1)
    if not target_id:
        return await message.reply_text("💡 Reply to a user or use `/unfban @username|user_id`.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    res = await db["fed_bans"].delete_one({"fed_id": fid, "user_id": int(target_id)})
    unbanned = await unban_fed_user_in_linked_chats(client, fid, int(target_id))

    if not res.deleted_count and not unbanned:
        return await message.reply_text(f"ℹ️ `{target_id}` was not banned in **{fed.get('name')}**.", parse_mode=ParseMode.MARKDOWN)

    await message.reply_text(
        f"🌐🔓 **Unfedbanned**\n"
        f"• **Federation:** **{fed.get('name')}** (`{fid}`)\n"
        f"• **User:** **{target_name or target_id}** (`{target_id}`)\n"
        f"• **Unbanned in Chats:** `{unbanned}`",
        parse_mode=ParseMode.MARKDOWN,
    )
    await send_fed_log(
        client,
        fed,
        f"🌐🔓 **Unfedban** by `{actor.id}` for **{target_name or target_id}** (`{target_id}`) across `{unbanned}` chat(s).",
    )


@app.on_message(filters.command("feddemoteme"))
async def cmd_feddemoteme(client: Client, message: Message):
    actor = message.from_user
    if not actor or len(message.command) < 2:
        return await message.reply_text("💡 Usage: `/feddemoteme <fedID>`", parse_mode=ParseMode.MARKDOWN)

    fid = message.command[1].strip()
    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text("❌ Federation not found.", parse_mode=ParseMode.MARKDOWN)
    if is_fed_owner(fed, actor.id):
        return await message.reply_text("⚠️ Owners cannot demote themselves; use `/fedtransfer` or `/delfed`.", parse_mode=ParseMode.MARKDOWN)

    admins = [int(a) for a in (fed.get("admins") or [])]
    if actor.id not in admins:
        return await message.reply_text("ℹ️ You are not an admin of that federation.", parse_mode=ParseMode.MARKDOWN)

    admins.remove(actor.id)
    db = await get_db()
    await db["feds"].update_one({"fed_id": fid}, {"$set": {"admins": admins, "updated_at": time.time()}})
    await message.reply_text(f"✅ You have stepped down as admin of **{fed.get('name')}** (`{fid}`).", parse_mode=ParseMode.MARKDOWN)
    await send_fed_log(client, fed, f"📉 Fed admin `{actor.id}` stepped down via `/feddemoteme`.")


@app.on_message(filters.command("myfeds"))
async def cmd_myfeds(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    feds = await get_user_admin_feds(actor.id)
    if not feds:
        return await message.reply_text("ℹ️ You do not own or moderate any federations.", parse_mode=ParseMode.MARKDOWN)

    lines = ["🌐 **Your Federations**", "━━━━━━━━━━━━━━━━━━━━━━"]
    rows: list[list[InlineKeyboardButton]] = []
    for f in feds[:12]:
        role = "👑 Owner" if is_fed_owner(f, actor.id) else "👮 Admin"
        lines.append(f"• {role} **{f.get('name')}** (`{f['fed_id']}`)")
        rows.append([
            InlineKeyboardButton(
                f"{'👑' if is_fed_owner(f, actor.id) else '👮'} {f.get('name')[:28]}",
                callback_data=f"fh_info_{f['fed_id']}",
            )
        ])
    rows.append([InlineKeyboardButton("✖️ Close", callback_data="fh_close")])
    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- FEDERATION OWNER COMMANDS ---
# ==========================================

@app.on_message(filters.command("newfed"))
async def cmd_newfed(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed_name = " ".join(message.command[1:]).strip()
    if not fed_name:
        return await message.reply_text("💡 Usage: `/newfed <fedname>`", parse_mode=ParseMode.MARKDOWN)

    existing = await get_user_owned_fed(actor.id)
    if existing:
        return await message.reply_text(
            f"⚠️ You already own **{existing.get('name')}** (`{existing['fed_id']}`). Only one federation per user is allowed.",
            parse_mode=ParseMode.MARKDOWN,
        )

    fid = f"fed_{uuid.uuid4().hex[:10]}"
    now = time.time()
    fed_doc = {
        "fed_id": fid,
        "name": fed_name[:64],
        "owner_id": int(actor.id),
        "admins": [],
        "subscribed_feds": [],
        "require_reason": False,
        "notif_enabled": True,
        "log_chat_id": None,
        "log_lang": "en",
        "created_at": now,
        "updated_at": now,
    }
    db = await get_db()
    await db["feds"].insert_one(fed_doc)

    if message.chat.type != ChatType.PRIVATE:
        await set_chat_fed(message.chat.id, fid, title=message.chat.title)

    text, kb = build_fed_owner_panel(fed_doc)
    await message.reply_text(
        f"🎉 Created federation **{fed_doc['name']}** (`{fid}`)!\n\n{text}",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("renamefed"))
async def cmd_renamefed(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    new_name = " ".join(message.command[1:]).strip()
    if not new_name:
        return await message.reply_text("💡 Usage: `/renamefed <fedname>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    await db["feds"].update_one(
        {"fed_id": fed["fed_id"]},
        {"$set": {"name": new_name[:64], "updated_at": time.time()}},
    )
    fed["name"] = new_name[:64]
    await message.reply_text(f"✅ Renamed federation (`{fed['fed_id']}`) to **{fed['name']}**.", parse_mode=ParseMode.MARKDOWN)
    await send_fed_log(client, fed, f"✏️ Federation renamed to **{fed['name']}** by `{actor.id}`.")


@app.on_message(filters.command("delfed"))
async def cmd_delfed(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    fid = fed["fed_id"]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Confirm Delete", callback_data=f"fh_delok_{fid}"),
            InlineKeyboardButton("❌ Cancel", callback_data="fh_close"),
        ]
    ])
    await message.reply_text(
        f"⚠️ Are you sure you want to delete **{fed.get('name')}** (`{fid}`)?\n"
        f"This removes federation metadata and links, and **will not unban** already-banned users.",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("fedtransfer"))
async def cmd_fedtransfer(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    target_id, target_name, _ = await resolve_user_arg(client, message, arg_index=1)
    if not target_id or int(target_id) == int(actor.id):
        return await message.reply_text("💡 Reply to or specify another user: `/fedtransfer @username|user_id`", parse_mode=ParseMode.MARKDOWN)

    already_owner = await get_user_owned_fed(int(target_id))
    if already_owner:
        return await message.reply_text("⚠️ Target user already owns a federation.", parse_mode=ParseMode.MARKDOWN)

    fid = fed["fed_id"]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Confirm Transfer", callback_data=f"fh_trfok_{fid}_{target_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="fh_close"),
        ]
    ])
    await message.reply_text(
        f"⚠️ Transfer ownership of **{fed.get('name')}** (`{fid}`) to **{target_name or target_id}** (`{target_id}`)?",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("fedpromote"))
async def cmd_fedpromote(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    target_id, target_name, _ = await resolve_user_arg(client, message, arg_index=1)
    if not target_id:
        return await message.reply_text("💡 Reply to or specify a user: `/fedpromote @username|user_id`", parse_mode=ParseMode.MARKDOWN)

    admins = [int(a) for a in (fed.get("admins") or [])]
    if int(target_id) == int(actor.id) or int(target_id) in admins:
        return await message.reply_text("ℹ️ User is already an admin or owner of this federation.", parse_mode=ParseMode.MARKDOWN)

    promo_id = f"pr_{uuid.uuid4().hex[:10]}"
    db = await get_db()
    await db["fed_pending_promos"].insert_one({
        "promo_id": promo_id,
        "fed_id": fed["fed_id"],
        "fed_name": fed.get("name"),
        "target_id": int(target_id),
        "invited_by": int(actor.id),
        "status": "pending",
        "created_at": time.time(),
    })

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept Fed Admin", callback_data=f"fh_pr_acc_{promo_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"fh_pr_dec_{promo_id}"),
        ]
    ])
    prompt_text = (
        f"📩 **Federation Admin Invite**\n"
        f"**{target_name or target_id}** (`{target_id}`), you have been invited to become a Fed Admin of "
        f"**{fed.get('name')}** (`{fed['fed_id']}`) by `{actor.id}`."
    )
    sent_dm = False
    try:
        await client.send_message(int(target_id), prompt_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        sent_dm = True
    except Exception:
        pass

    if not sent_dm or message.chat.type != ChatType.PRIVATE:
        await message.reply_text(prompt_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(f"📨 Promotion confirmation sent to **{target_name or target_id}** (`{target_id}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("feddemote"))
async def cmd_feddemote(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    target_id, target_name, _ = await resolve_user_arg(client, message, arg_index=1)
    if not target_id:
        return await message.reply_text("💡 Reply to or specify a user: `/feddemote @username|user_id`", parse_mode=ParseMode.MARKDOWN)

    admins = [int(a) for a in (fed.get("admins") or [])]
    if int(target_id) not in admins:
        return await message.reply_text("ℹ️ That user is not a fed admin in your federation.", parse_mode=ParseMode.MARKDOWN)

    admins.remove(int(target_id))
    db = await get_db()
    await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"admins": admins, "updated_at": time.time()}})
    await message.reply_text(f"📉 Demoted **{target_name or target_id}** (`{target_id}`) from **{fed.get('name')}**.", parse_mode=ParseMode.MARKDOWN)
    await send_fed_log(client, fed, f"📉 Demoted `{target_id}` from fed admin by owner `{actor.id}`.")


@app.on_message(filters.command("fednotif"))
async def cmd_fednotif(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    arg = message.command[1] if len(message.command) > 1 else None
    nxt = _parse_bool_arg(arg, bool(fed.get("notif_enabled", True)))
    db = await get_db()
    await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"notif_enabled": nxt, "updated_at": time.time()}})
    await message.reply_text(f"🔔 Federation owner PM notifications: **{'ON' if nxt else 'OFF'}**.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("fedreason"))
async def cmd_fedreason(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    arg = message.command[1] if len(message.command) > 1 else None
    nxt = _parse_bool_arg(arg, bool(fed.get("require_reason", False)))
    db = await get_db()
    await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"require_reason": nxt, "updated_at": time.time()}})
    await message.reply_text(f"📝 Fedban reason required: **{'YES' if nxt else 'NO'}**.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("subfed"))
async def cmd_subfed(client: Client, message: Message):
    actor = message.from_user
    if not actor or len(message.command) < 2:
        return await message.reply_text("💡 Usage: `/subfed <FedId>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    sub_id = message.command[1].strip()
    if sub_id == fed["fed_id"]:
        return await message.reply_text("⚠️ You cannot subscribe a federation to itself.", parse_mode=ParseMode.MARKDOWN)

    target_fed = await get_fed(sub_id)
    if not target_fed:
        return await message.reply_text("❌ Target federation not found.", parse_mode=ParseMode.MARKDOWN)

    subs = list(dict.fromkeys(fed.get("subscribed_feds") or []))
    if sub_id not in subs:
        subs.append(sub_id)
        db = await get_db()
        await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"subscribed_feds": subs, "updated_at": time.time()}})

    await message.reply_text(
        f"🔗 **{fed.get('name')}** is now subscribed to **{target_fed.get('name')}** (`{sub_id}`).\n"
        f"_Your banlist is unchanged; bans from the subscribed fed are inherited._",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("unsubfed"))
async def cmd_unsubfed(client: Client, message: Message):
    actor = message.from_user
    if not actor or len(message.command) < 2:
        return await message.reply_text("💡 Usage: `/unsubfed <FedId>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    sub_id = message.command[1].strip()
    subs = [s for s in (fed.get("subscribed_feds") or []) if s != sub_id]
    db = await get_db()
    await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"subscribed_feds": subs, "updated_at": time.time()}})
    await message.reply_text(f"✂️ Unsubscribed **{fed.get('name')}** from `{sub_id}`.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("fedexport"))
async def cmd_fedexport(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    fmt = (message.command[1] if len(message.command) > 1 else "csv").strip().lower()
    db = await get_db()
    bans = [b async for b in db["fed_bans"].find({"fed_id": fed["fed_id"]}).sort("created_at", -1)]

    if fmt == "json":
        payload = json.dumps(
            [
                {
                    "user_id": int(b["user_id"]),
                    "user_name": b.get("user_name") or "",
                    "reason": b.get("reason") or "",
                    "created_at": b.get("created_at", 0),
                }
                for b in bans
            ],
            indent=2,
        )
        filename = f"{fed['fed_id']}_bans.json"
    elif fmt == "minicsv":
        payload = "\n".join(f"{b['user_id']},{b.get('reason') or ''}" for b in bans)
        filename = f"{fed['fed_id']}_mini.csv"
    elif fmt == "human":
        payload = "\n".join(
            f"- {b.get('user_name') or b['user_id']} ({b['user_id']}): {b.get('reason') or 'No reason'}"
            for b in bans
        ) or "No bans."
        filename = f"{fed['fed_id']}_bans.txt"
    else:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["user_id", "user_name", "reason", "created_at"])
        for b in bans:
            writer.writerow([b["user_id"], b.get("user_name") or "", b.get("reason") or "", b.get("created_at", 0)])
        payload = buf.getvalue()
        filename = f"{fed['fed_id']}_bans.csv"

    bio = io.BytesIO(payload.encode("utf-8"))
    bio.name = filename
    await message.reply_document(bio, caption=f"📦 Exported `{len(bans)}` bans from **{fed.get('name')}** (`{fmt}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("fedimport"))
async def cmd_fedimport(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    mode = (message.command[1] if len(message.command) > 1 else "keep").strip().lower()
    fmt = (message.command[2] if len(message.command) > 2 else "csv").strip().lower()
    if mode not in {"overwrite", "keep"}:
        return await message.reply_text("💡 Usage: `/fedimport <overwrite/keep> <csv/minicsv/json/human>` (reply to a file or text).", parse_mode=ParseMode.MARKDOWN)

    raw_text = ""
    if message.reply_to_message:
        if message.reply_to_message.document:
            data_bytes = await message.reply_to_message.download(in_memory=True)
            raw_text = bytes(data_bytes.getvalue()).decode("utf-8", errors="ignore")
        elif message.reply_to_message.text:
            raw_text = message.reply_to_message.text

    if not raw_text.strip():
        return await message.reply_text("⚠️ Reply to a ban list file or message to import.", parse_mode=ParseMode.MARKDOWN)

    parsed: list[tuple[int, str, str]] = []
    if fmt == "json":
        try:
            items = json.loads(raw_text)
            if isinstance(items, list):
                for item in items:
                    uid = int(item.get("user_id"))
                    parsed.append((uid, str(item.get("user_name") or uid), str(item.get("reason") or "Imported")))
        except Exception as exc:
            return await message.reply_text(f"❌ Invalid JSON: `{exc}`", parse_mode=ParseMode.MARKDOWN)
    elif fmt == "minicsv":
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 1)
            if parts[0].strip().lstrip("-").isdigit():
                uid = int(parts[0].strip())
                rsn = parts[1].strip() if len(parts) > 1 else "Imported"
                parsed.append((uid, str(uid), rsn or "Imported"))
    elif fmt == "human":
        for line in raw_text.splitlines():
            if "(" in line and ")" in line:
                inside = line.split("(", 1)[1].split(")", 1)[0].strip()
                if inside.lstrip("-").isdigit():
                    uid = int(inside)
                    rsn = line.split("):", 1)[1].strip() if "):" in line else "Imported"
                    parsed.append((uid, str(uid), rsn or "Imported"))
    else:
        reader = csv.DictReader(io.StringIO(raw_text))
        for row in reader:
            raw_uid = (row.get("user_id") or "").strip()
            if raw_uid.lstrip("-").isdigit():
                uid = int(raw_uid)
                uname = (row.get("user_name") or str(uid)).strip()
                rsn = (row.get("reason") or "Imported").strip()
                parsed.append((uid, uname or str(uid), rsn or "Imported"))

    db = await get_db()
    fid = fed["fed_id"]
    if mode == "overwrite":
        await db["fed_bans"].delete_many({"fed_id": fid})

    now = time.time()
    imported = 0
    for uid, uname, rsn in parsed:
        if mode == "keep":
            ex = await db["fed_bans"].find_one({"fed_id": fid, "user_id": uid})
            if ex:
                continue
        await db["fed_bans"].update_one(
            {"fed_id": fid, "user_id": uid},
            {
                "$set": {
                    "fed_id": fid,
                    "user_id": uid,
                    "user_name": uname[:64],
                    "reason": rsn[:240],
                    "banned_by": actor.id,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        imported += 1

    await message.reply_text(f"📥 Imported `{imported}` ban entry(ies) into **{fed.get('name')}** (`{mode}`).", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("setfedlog") & filters.group)
async def cmd_setfedlog(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    await db["feds"].update_one(
        {"fed_id": fed["fed_id"]},
        {"$set": {"log_chat_id": int(message.chat.id), "updated_at": time.time()}},
    )
    await message.reply_text(f"📋 Set **{message.chat.title or message.chat.id}** (`{message.chat.id}`) as federation log for **{fed.get('name')}**.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("unsetfedlog"))
async def cmd_unsetfedlog(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    await db["feds"].update_one(
        {"fed_id": fed["fed_id"]},
        {"$set": {"log_chat_id": None, "updated_at": time.time()}},
    )
    await message.reply_text(f"🗑️ Unset federation log channel for **{fed.get('name')}**.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("setfedlang"))
async def cmd_setfedlang(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return
    fed = await get_user_owned_fed(actor.id)
    if not fed:
        return await message.reply_text("⛔ You do not own a federation.", parse_mode=ParseMode.MARKDOWN)

    if len(message.command) > 1:
        lang = message.command[1].strip().lower()
        if lang not in SUPPORTED_LOG_LANGS:
            return await message.reply_text(f"⚠️ Supported log languages: `{'`, `'.join(SUPPORTED_LOG_LANGS)}`.", parse_mode=ParseMode.MARKDOWN)
        db = await get_db()
        await db["feds"].update_one({"fed_id": fed["fed_id"]}, {"$set": {"log_lang": lang, "updated_at": time.time()}})
        return await message.reply_text(f"🌐 Federation log language set to `{lang.upper()}`.", parse_mode=ParseMode.MARKDOWN)

    fed["log_lang"] = fed.get("log_lang", "en")
    text, kb = build_fed_owner_panel(fed)
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- USER COMMANDS ---
# ==========================================

@app.on_message(filters.command("fedinfo"))
async def cmd_fedinfo(client: Client, message: Message):
    fid = message.command[1].strip() if len(message.command) > 1 else None
    if not fid and message.chat.type != ChatType.PRIVATE:
        link = await get_chat_link(message.chat.id, title=message.chat.title)
        fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("💡 Usage: `/fedinfo <FedID>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text("❌ Federation not found.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    linked_cnt = await db["fed_chat_links"].count_documents({"fed_id": fid})
    ban_cnt = await db["fed_bans"].count_documents({"fed_id": fid})
    text, kb = build_fed_info_card(fed, linked_count=linked_cnt, ban_count=ban_cnt)
    await message.reply_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("fedadmins"))
async def cmd_fedadmins(client: Client, message: Message):
    fid = message.command[1].strip() if len(message.command) > 1 else None
    if not fid and message.chat.type != ChatType.PRIVATE:
        link = await get_chat_link(message.chat.id, title=message.chat.title)
        fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("💡 Usage: `/fedadmins <FedID>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text("❌ Federation not found.", parse_mode=ParseMode.MARKDOWN)

    all_ids = [int(fed["owner_id"])] + [int(a) for a in (fed.get("admins") or []) if int(a) != int(fed["owner_id"])]
    lines = [f"👮 **Admins — {fed.get('name')}** (`{fid}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, uid in enumerate(all_ids):
        role = "👑 Owner" if idx == 0 else "👮 Admin"
        lines.append(f"• {role}: `{uid}`")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ℹ️ Fed Info", callback_data=f"fh_info_{fid}"),
            InlineKeyboardButton("✖️ Close", callback_data="fh_close"),
        ]
    ])
    await message.reply_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("fedsubs"))
async def cmd_fedsubs(client: Client, message: Message):
    fid = message.command[1].strip() if len(message.command) > 1 else None
    if not fid and message.chat.type != ChatType.PRIVATE:
        link = await get_chat_link(message.chat.id, title=message.chat.title)
        fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("💡 Usage: `/fedsubs <FedID>`", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text("❌ Federation not found.", parse_mode=ParseMode.MARKDOWN)

    subs = fed.get("subscribed_feds") or []
    lines = [f"🔗 **Subscribed Feds — {fed.get('name')}** (`{fid}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    if not subs:
        lines.append("_No subscribed federations._")
    else:
        for sid in subs:
            sf = await get_fed(sid)
            lines.append(f"• **{(sf or {}).get('name') or sid}** (`{sid}`)")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ℹ️ Fed Info", callback_data=f"fh_info_{fid}"),
            InlineKeyboardButton("✖️ Close", callback_data="fh_close"),
        ]
    ])
    await message.reply_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("joinfed") & filters.group)
async def cmd_joinfed(client: Client, message: Message):
    actor = message.from_user
    if not actor or not await is_chat_owner(client, message.chat.id, actor.id):
        return await message.reply_text("⛔ Only the chat owner can join a federation.", parse_mode=ParseMode.MARKDOWN)

    if len(message.command) < 2:
        return await message.reply_text("💡 Usage: `/joinfed <FedID>`", parse_mode=ParseMode.MARKDOWN)

    fid = message.command[1].strip()
    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text("❌ Federation not found.", parse_mode=ParseMode.MARKDOWN)

    link = await get_chat_link(message.chat.id, title=message.chat.title)
    if link.get("fed_id"):
        return await message.reply_text(
            f"⚠️ This chat is already in federation `{link['fed_id']}`. Run `/leavefed` first.",
            parse_mode=ParseMode.MARKDOWN,
        )

    await set_chat_fed(message.chat.id, fid, title=message.chat.title)
    await message.reply_text(
        f"🔗 Joined **{message.chat.title or message.chat.id}** to federation **{fed.get('name')}** (`{fid}`).",
        parse_mode=ParseMode.MARKDOWN,
    )
    await send_fed_log(client, fed, f"➕ Chat **{message.chat.title or message.chat.id}** (`{message.chat.id}`) joined the federation.")


@app.on_message(filters.command("leavefed") & filters.group)
async def cmd_leavefed(client: Client, message: Message):
    actor = message.from_user
    if not actor or not await is_chat_owner(client, message.chat.id, actor.id):
        return await message.reply_text("⛔ Only the chat owner can leave a federation.", parse_mode=ParseMode.MARKDOWN)

    link = await get_chat_link(message.chat.id, title=message.chat.title)
    fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("ℹ️ This chat is not currently in any federation.", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    await set_chat_fed(message.chat.id, None, title=message.chat.title)
    await message.reply_text(f"🚪 Left federation **{(fed or {}).get('name') or fid}** (`{fid}`).", parse_mode=ParseMode.MARKDOWN)
    if fed:
        await send_fed_log(client, fed, f"➖ Chat **{message.chat.title or message.chat.id}** (`{message.chat.id}`) left the federation.")


@app.on_message(filters.command("fedstat"))
async def cmd_fedstat(client: Client, message: Message):
    actor = message.from_user
    if not actor:
        return

    args = message.command[1:]
    target_uid: int | None = None
    target_fid: str | None = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_uid = message.reply_to_message.from_user.id
        if args:
            target_fid = args[0].strip()
    elif len(args) == 0:
        target_uid = actor.id
    elif len(args) == 1:
        tok = args[0].strip()
        if tok.lstrip("-").isdigit():
            target_uid = int(tok)
        else:
            target_uid = actor.id
            target_fid = tok
    else:
        if args[0].strip().lstrip("-").isdigit():
            target_uid = int(args[0].strip())
            target_fid = args[1].strip()
        elif args[1].strip().lstrip("-").isdigit():
            target_fid = args[0].strip()
            target_uid = int(args[1].strip())
        else:
            target_uid = actor.id
            target_fid = args[0].strip()

    db = await get_db()
    if target_fid:
        fed = await get_fed(target_fid)
        ban_doc = await db["fed_bans"].find_one({"fed_id": target_fid, "user_id": int(target_uid)})
        fed_label = (fed or {}).get("name") or target_fid
        if not ban_doc:
            return await message.reply_text(f"✅ User `{target_uid}` is **not** banned in **{fed_label}** (`{target_fid}`).", parse_mode=ParseMode.MARKDOWN)
        return await message.reply_text(
            f"🚫 **Fedban Record**\n"
            f"• **User:** `{target_uid}`\n"
            f"• **Federation:** **{fed_label}** (`{target_fid}`)\n"
            f"• **Reason:** _{ban_doc.get('reason') or 'No reason'}_\n"
            f"• **Date:** `{_fmt_ts(ban_doc.get('created_at'))}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    bans = [b async for b in db["fed_bans"].find({"user_id": int(target_uid)}).sort("created_at", -1)]
    if not bans:
        return await message.reply_text(f"✅ User `{target_uid}` has no recorded federation bans.", parse_mode=ParseMode.MARKDOWN)

    lines = [f"📊 **Fedstat for `{target_uid}`** (`{len(bans)}` ban(s))", "━━━━━━━━━━━━━━━━━━━━━━"]
    for b in bans[:15]:
        f = await get_fed(b["fed_id"])
        fname = (f or {}).get("name") or b["fed_id"]
        lines.append(f"• **{fname}** (`{b['fed_id']}`) — _{b.get('reason') or 'No reason'}_ (`{_fmt_ts(b.get('created_at'))}`)")
    await message.reply_text(_truncate("\n".join(lines)), parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("chatfed") & filters.group)
async def cmd_chatfed(client: Client, message: Message):
    link = await get_chat_link(message.chat.id, title=message.chat.title)
    fid = link.get("fed_id")
    if not fid:
        return await message.reply_text("ℹ️ This chat is not joined to any federation.", parse_mode=ParseMode.MARKDOWN)

    fed = await get_fed(fid)
    if not fed:
        return await message.reply_text(f"⚠️ Linked to `{fid}`, but federation record was not found.", parse_mode=ParseMode.MARKDOWN)

    db = await get_db()
    linked_cnt = await db["fed_chat_links"].count_documents({"fed_id": fid})
    ban_cnt = await db["fed_bans"].count_documents({"fed_id": fid})
    text, kb = build_fed_info_card(fed, linked_count=linked_cnt, ban_count=ban_cnt)
    quiet_str = "ON (silent join bans)" if link.get("quiet_fed") else "OFF (announce join bans)"
    await message.reply_text(
        _truncate(f"💬 **Chat Federation (`{quiet_str}`)**\n\n{text}"),
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("quietfed") & filters.group)
async def cmd_quietfed(client: Client, message: Message):
    actor = message.from_user
    if not actor or not await is_chat_admin(client, message.chat.id, actor.id):
        return await message.reply_text("⛔ Chat admins only.", parse_mode=ParseMode.MARKDOWN)

    link = await get_chat_link(message.chat.id, title=message.chat.title)
    arg = message.command[1] if len(message.command) > 1 else None
    nxt = _parse_bool_arg(arg, bool(link.get("quiet_fed", False)))
    await set_chat_quiet(message.chat.id, nxt, title=message.chat.title)
    await message.reply_text(
        f"🔇 Quiet fedban notifications in this chat: **{'ON' if nxt else 'OFF'}**.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ==========================================
# --- CALLBACK CONTROLLERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^fh_info_(?P<fid>fed_[a-zA-Z0-9_]+)$"))
async def cb_fh_info(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed:
        return await query.answer("Federation not found.", show_alert=True)
    db = await get_db()
    linked_cnt = await db["fed_chat_links"].count_documents({"fed_id": fid})
    ban_cnt = await db["fed_bans"].count_documents({"fed_id": fid})
    text, kb = build_fed_info_card(fed, linked_count=linked_cnt, ban_count=ban_cnt)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_adm_(?P<fid>fed_[a-zA-Z0-9_]+)_(?P<page>\d+)$"))
async def cb_fh_admins(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed:
        return await query.answer("Federation not found.", show_alert=True)
    all_ids = [int(fed["owner_id"])] + [int(a) for a in (fed.get("admins") or []) if int(a) != int(fed["owner_id"])]
    lines = [f"👮 **Admins — {fed.get('name')}** (`{fid}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, uid in enumerate(all_ids):
        lines.append(f"• {'👑 Owner' if idx == 0 else '👮 Admin'}: `{uid}`")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Fed Info", callback_data=f"fh_info_{fid}")],
        [InlineKeyboardButton("✖️ Close", callback_data="fh_close")],
    ])
    await query.answer()
    await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_sub_(?P<fid>fed_[a-zA-Z0-9_]+)_(?P<page>\d+)$"))
async def cb_fh_subs(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed:
        return await query.answer("Federation not found.", show_alert=True)
    subs = fed.get("subscribed_feds") or []
    lines = [f"🔗 **Subscribed Feds — {fed.get('name')}** (`{fid}`)", "━━━━━━━━━━━━━━━━━━━━━━"]
    if not subs:
        lines.append("_No subscribed federations._")
    else:
        for sid in subs:
            sf = await get_fed(sid)
            lines.append(f"• **{(sf or {}).get('name') or sid}** (`{sid}`)")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Fed Info", callback_data=f"fh_info_{fid}")],
        [InlineKeyboardButton("✖️ Close", callback_data="fh_close")],
    ])
    await query.answer()
    await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_otog_(?P<fid>fed_[a-zA-Z0-9_]+)_(?P<key>notif|reason)$"))
async def cb_fh_owner_toggle(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    key = query.matches[0].group("key")
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)

    field = "notif_enabled" if key == "notif" else "require_reason"
    nxt = not bool(fed.get(field, False if key == "reason" else True))
    db = await get_db()
    await db["feds"].update_one({"fed_id": fid}, {"$set": {field: nxt, "updated_at": time.time()}})
    fed[field] = nxt
    await query.answer("🟢 Enabled" if nxt else "🔴 Disabled", show_alert=True)
    text, kb = build_fed_owner_panel(fed)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_lang_(?P<fid>fed_[a-zA-Z0-9_]+)$"))
async def cb_fh_cycle_lang(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)

    cur = fed.get("log_lang", "en")
    idx = SUPPORTED_LOG_LANGS.index(cur) if cur in SUPPORTED_LOG_LANGS else 0
    nxt = SUPPORTED_LOG_LANGS[(idx + 1) % len(SUPPORTED_LOG_LANGS)]
    db = await get_db()
    await db["feds"].update_one({"fed_id": fid}, {"$set": {"log_lang": nxt, "updated_at": time.time()}})
    fed["log_lang"] = nxt
    await query.answer(f"Log language -> {nxt.upper()}", show_alert=False)
    text, kb = build_fed_owner_panel(fed)
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_delask_(?P<fid>fed_[a-zA-Z0-9_]+)$"))
async def cb_fh_del_ask(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Yes, Delete Forever", callback_data=f"fh_delok_{fid}"),
            InlineKeyboardButton("⬅️ Back", callback_data=f"fh_backown_{fid}"),
        ]
    ])
    await query.answer()
    await query.message.edit_text(
        f"⚠️ Delete **{fed.get('name')}** (`{fid}`)? Bans will remain in place.",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^fh_backown_(?P<fid>fed_[a-zA-Z0-9_]+)$"))
async def cb_fh_back_owner(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)
    text, kb = build_fed_owner_panel(fed)
    await query.answer()
    await query.message.edit_text(_truncate(text), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_delok_(?P<fid>fed_[a-zA-Z0-9_]+)$"))
async def cb_fh_del_ok(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)

    db = await get_db()
    await db["feds"].delete_one({"fed_id": fid})
    await db["fed_chat_links"].update_many({"fed_id": fid}, {"$set": {"fed_id": None}})
    await query.answer("Federation deleted", show_alert=True)
    await query.message.edit_text(f"🗑️ Federation **{fed.get('name')}** (`{fid}`) has been deleted.", parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_trfok_(?P<fid>fed_[a-zA-Z0-9_]+)_(?P<uid>\d+)$"))
async def cb_fh_transfer_ok(client: Client, query: CallbackQuery):
    fid = query.matches[0].group("fid")
    new_owner = int(query.matches[0].group("uid"))
    fed = await get_fed(fid)
    if not fed or not is_fed_owner(fed, query.from_user.id):
        return await query.answer("⛔ Fed owner only.", show_alert=True)

    admins = [int(a) for a in (fed.get("admins") or []) if int(a) != new_owner]
    db = await get_db()
    await db["feds"].update_one(
        {"fed_id": fid},
        {"$set": {"owner_id": new_owner, "admins": admins, "updated_at": time.time()}},
    )
    await query.answer("Ownership transferred", show_alert=True)
    await query.message.edit_text(
        f"👑 Ownership of **{fed.get('name')}** (`{fid}`) transferred to `{new_owner}`.",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_callback_query(filters.regex(r"^fh_pr_(?P<act>acc|dec)_(?P<pid>pr_[a-zA-Z0-9_]+)$"))
async def cb_fh_promo_decision(client: Client, query: CallbackQuery):
    act = query.matches[0].group("act")
    pid = query.matches[0].group("pid")
    db = await get_db()
    promo = await db["fed_pending_promos"].find_one({"promo_id": pid})
    if not promo or promo.get("status") != "pending":
        return await query.answer("Invitation expired or already handled.", show_alert=True)

    if int(query.from_user.id) != int(promo["target_id"]):
        return await query.answer("⛔ Only the invited user can respond to this prompt.", show_alert=True)

    fid = promo["fed_id"]
    fed = await get_fed(fid)
    if act == "acc":
        if fed:
            admins = list(dict.fromkeys([int(a) for a in (fed.get("admins") or [])] + [int(promo["target_id"])]))
            await db["feds"].update_one({"fed_id": fid}, {"$set": {"admins": admins, "updated_at": time.time()}})
            await send_fed_log(client, fed, f"👮 User `{promo['target_id']}` accepted Fed Admin invite.")
        await db["fed_pending_promos"].update_one({"promo_id": pid}, {"$set": {"status": "accepted"}})
        await query.answer("✅ You are now a Fed Admin!", show_alert=True)
        await query.message.edit_text(f"✅ Accepted Fed Admin role for **{promo.get('fed_name') or fid}**.", parse_mode=ParseMode.MARKDOWN)
    else:
        await db["fed_pending_promos"].update_one({"promo_id": pid}, {"$set": {"status": "declined"}})
        if fed:
            await send_fed_log(client, fed, f"ℹ️ User `{promo['target_id']}` declined Fed Admin invite.")
        await query.answer("Declined", show_alert=True)
        await query.message.edit_text(f"❌ Declined Fed Admin invite for **{promo.get('fed_name') or fid}**.", parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^fh_close$"))
async def cb_fh_close(client: Client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass
