from pyrogram.enums import ChatMemberStatus
from pyrogram.enums import ChatType


async def is_user_admin(client, chat_id: int, user_id: int) -> bool:
    """Checks if a user is an admin or owner in the specified chat."""
    # If they are using it in their own private messages, they are the admin!
    if chat_id == user_id:
        return True
        
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception:
        # If the bot isn't in the chat or the user is invalid, deny access
        return False
      
