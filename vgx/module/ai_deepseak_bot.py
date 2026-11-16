import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config


DB_NAME = "deepseek_commands_bot"

# --- INITIALIZE CLIENTS ---

mongo_client = AsyncIOMotorClient(Config.MONGO_URL)
db = mongo_client[DB_NAME]
users_col = db["users"]
chats_col = db["chats"]

ds_client = AsyncOpenAI(
    api_key=Config.DEEPSEEK_API_KEY,
    base_url=Config.DEEPSEEK_BASE_URL
)



DEFAULT_SYSTEM_PROMPT = "You are a professional, high-speed AI assistant."

# --- DATABASE HELPERS ---
async def get_user_settings(user_id: int) -> dict:
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "model": "deepseek-chat",
            "temperature": 0.7,
            "system_prompt": DEFAULT_SYSTEM_PROMPT
        }
        await users_col.insert_one(user)
    return user

async def get_chat_history(user_id: int, limit: int = 10) -> list:
    chat = await chats_col.find_one({"user_id": user_id})
    if not chat or "messages" not in chat:
        return []
    return chat["messages"][-limit:]

async def append_message_history(user_id: int, role: str, content: str, reasoning_content: str = None):
    msg_data = {"role": role, "content": content}
    if reasoning_content:
        msg_data["reasoning_content"] = reasoning_content
    
    await chats_col.update_one(
        {"user_id": user_id},
        {"$push": {"messages": msg_data}},
        upsert=True
    )

# --- COMMANDS: SETTINGS & MANAGEMENT ---

@app.on_message(filters.command("dssettings") & filters.private)
async def settinggss_command(client: Client, message: Message):
    user_id = message.from_user.id
    settings = await get_user_settings(user_id)
    text = (
        f"⚙️ **Your DeepSeek Settings**\n\n"
        f"• **Model:** `{settings['model']}`\n"
        f"• **Temperature:** `{settings['temperature']}`\n"
        f"• **System Prompt:** `{settings['system_prompt']}`\n\n"
        f"_Change settings using:_\n"
        f"`/model chat` or `/model reasoner`\n"
        f"`/temp 0.2`\n"
        f"`/system Your prompt here`"
    )
    await message.reply_text(text)

@app.on_message(filters.command("dsmodel") & filters.private)
async def modeshl_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/model chat` or `/model reasoner`")
        return
    
    arg = message.command[1].lower()
    if "reason" in arg:
        new_model = "deepseek-reasoner"
    else:
        new_model = "deepseek-chat"

    await users_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"model": new_model}},
        upsert=True
    )
    await message.reply_text(f"✅ Model successfully updated to: `{new_model}`")

@app.on_message(filters.command("temp") & filters.private)
async def temp_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/temp 0.7` (values between 0.0 and 1.5)")
        return
    try:
        temp = float(message.command[1])
        if not (0.0 <= temp <= 2.0):
            raise ValueError()
        await users_col.update_one(
            {"user_id": message.from_user.id},
            {"$set": {"temperature": temp}},
            upsert=True
        )
        await message.reply_text(f"✅ Temperature set to: `{temp}`")
    except ValueError:
        await message.reply_text("❌ Invalid value. Provide a float between 0.0 and 2.0.")

@app.on_message(filters.command("system") & filters.private)
async def system_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/system Your custom system instructions here`")
        return
    
    prompt = message.text.split(None, 1)[1]
    await users_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"system_prompt": prompt}},
        upsert=True
    )
    await message.reply_text("✅ Custom system prompt updated successfully!")

@app.on_message(filters.command("dcclear") & filters.private)
async def clear_cfommand(client: Client, message: Message):
    await chats_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"messages": []}},
        upsert=True
    )
    await message.reply_text("🧹 Conversation context history wiped clean.")

# --- CORE COMMAND CHAT HANDLER (`/ask` or `/ai`) ---
@app.on_message(filters.command("deepseek") & filters.private)
async def deepask_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a prompt. Example:\n`/ask Explain quantum computing in 3 sentences.`")
        return

    user_id = message.from_user.id
    user_query = message.text.split(None, 1)[1]

    # Fetch user configuration & history
    settings = await get_user_settings(user_id)
    history = await get_chat_history(user_id, limit=12)

    # Build compliant payload
    messages_payload = [{"role": "system", "content": settings["system_prompt"]}]
    
    for hist in history:
        item = {"role": hist["role"], "content": hist["content"]}
        if "reasoning_content" in hist and hist["reasoning_content"]:
            item["reasoning_content"] = hist["reasoning_content"]
        messages_payload.append(item)

    messages_payload.append({"role": "user", "content": user_query})
    await append_message_history(user_id, "user", user_query)

    status_msg = await message.reply_text("⚡ *Processing request via DeepSeek...*")

    try:
        # High-speed stream generation request
        stream = await ds_client.chat.completions.create(
            model=settings["model"],
            messages=messages_payload,
            temperature=settings["temperature"],
            stream=True
        )

        full_response = ""
        reasoning_text = ""
        throttle_counter = 0

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_text += delta.reasoning_content

            if delta.content:
                full_response += delta.content

            throttle_counter += 1
            if throttle_counter >= 12:
                display_text = ""
                if reasoning_text:
                    display_text += f"🧠 **Reasoning:**\n> {reasoning_text.strip()}\n\n"
                display_text += f"💬 **Answer:**\n{full_response}"

                if len(display_text) > 4000:
                    display_text = display_text[:4000] + "..."

                await status_msg.edit_text(display_text)
                throttle_counter = 0

        # Final Render Output
        final_display = ""
        if reasoning_text:
            final_display += f"🧠 **Reasoning:**\n> {reasoning_text.strip()}\n\n"
        final_display += f"💬 **Answer:**\n{full_response}"

        if not final_display.strip():
            final_display = "⚠️ Received empty response stream."

        await status_msg.edit_text(final_display)
        await append_message_history(user_id, "assistant", full_response, reasoning_text if reasoning_text else None)

    except Exception as e:
        logger.error(f"DeepSeek API Error: {e}")
        await status_msg.edit_text(f"❌ **API Error:**\n`{str(e)}`")

