
import asyncio
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from vgx import app
from config import Config




def upload_to_imgbb(file_path: str):
    """Synchronous helper for ImgBB multipart POST request"""
    url = "https://api.imgbb.com/1/upload"
    with open(file_path, "rb") as file:
        payload = {"key": Config.IMGBB_API_KEY}
        files = {"image": file}
        response = requests.post(url, data=payload, files=files)
        return response.json()

@Client.on_message(filters.command("imgbb") & filters.private)
async def imgbb_reply_handler(client: Client, message: Message):
    # 1. Check if replying to a message
    if not message.reply_to_message:
        return await message.reply_text("❌ Please **reply to a photo or image file** and use the `/imgbb` command.")
    
    target_msg = message.reply_to_message
    
    # 2. Check if the message contains an image or document
    target_media = target_msg.photo or target_msg.document
    if not target_media:
        return await message.reply_text("❌ The message you replied to does not contain an image or photo.")
    
    if target_msg.document:
        if not target_msg.document.mime_type or not target_msg.document.mime_type.startswith("image/"):
            return await message.reply_text("❌ The replied document is not a valid image file.")

    status_msg = await message.reply_text("📥 **Downloading image from Telegram...**")
    
    file_path = None
    try:
        # Download the media from the replied message
        file_path = await client.download_media(target_msg)
        
        await status_msg.edit_text("🚀 **Uploading to ImgBB servers...**")
        
        # Run blocking requests call in a separate thread
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, upload_to_imgbb, file_path, Config.IMGBB_API_KEY)
        
        # Clean up local temporary file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            
        if result.get("success"):
            data = result["data"]
            image_url = data["url"]
            display_url = data["display_url"]
            delete_url = data["delete_url"]
            
            response_text = (
                f"✅ **Image Uploaded Successfully!**\n\n"
                f"🔗 **Direct Link:**\n`{image_url}`\n\n"
                f"🌐 [View Image Online]({display_url})\n"
                f"🗑️ [Delete Image]({delete_url})"
            )
            await status_msg.edit_text(response_text, disable_web_page_preview=True)
        else:
            error_msg = result.get("error", {}).get("message", "Unknown API error")
            await status_msg.edit_text(f"❌ **Upload Failed:** `{error_msg}`")
            
    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.edit_text(f"❌ **An error occurred:** `{str(e)}`")
