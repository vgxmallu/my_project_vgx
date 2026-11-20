from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import Message
from vgx import app


async def _is_admin(client: Client, chat_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception:
        return False


@app.on_message(filters.command(["kickme"]) & filters.group)
async def cmd_kickme(client: Client, message: Message):
    """Immediately kicks a non-admin group member who runs /kickme."""
    user = message.from_user
    if not user:
        return

    chat_id = message.chat.id
    if await _is_admin(client, chat_id, user.id):
        return await message.reply_text(
            "⛔ Admins and chat owners cannot use `/kickme`.",
            parse_mode=ParseMode.MARKDOWN,
        )

    try:
        await client.ban_chat_member(chat_id, user.id)
        await client.unban_chat_member(chat_id, user.id)
    except Exception as exc:
        return await message.reply_text(
            f"❌ Failed to kick you: `{str(exc)[:140]}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    await message.reply_text(
        f"👢 {user.mention} kicked themselves from the group. Get Out yourself😂",
        parse_mode=ParseMode.MARKDOWN,
    )
