import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app

# --- CONFIGURATION & ENDPOINT ---
# Uses a reliable public mock REST wrapper or placeholder generator for Faker data
FAKER_API_BASE = "https://fakerapi.it/api/v1"


async def fetch_fake_data(resource: str, quantity: int = 1) -> dict:
    """Async helper to fetch mock data from Faker API wrapper."""
    url = f"{FAKER_API_BASE}/{resource}?_quantity={quantity}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
            print(f"Faker API Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"Faker API Exception: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_faker_main_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker data generator."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Fake User Persona", callback_data="faker_user"),
            InlineKeyboardButton("📍 Fake Address", callback_data="faker_address")
        ],
        [
            InlineKeyboardButton("🏢 Fake Company", callback_data="faker_company"),
            InlineKeyboardButton("💳 Fake Credit Card", callback_data="faker_card")
        ],
        [
            InlineKeyboardButton("📚 Read Documentation", url="https://fakerjs.dev/api/"),
            InlineKeyboardButton("❌ Close", callback_data="faker_close")
        ]
    ])


@app.on_message(filters.command(["faker", "mock", "fakegen"]))
async def cmd_faker_dashboard(client: Client, message: Message):
    """Command: /faker - Opens the interactive Faker mock data generation dashboard."""
    text = (
        "🎭 **Faker Mock Data Intelligence Suite**\n\n"
        "Generate realistic fake user profiles, addresses, company info, and financial test records instantly "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_faker_main_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["fakeuser", "fakeperson"]))
async def cmd_fake_user(client: Client, message: Message):
    """Command: /fakeuser - Generates realistic random user profiles."""
    msg = await message.reply_text("👤 Generating fake user profile...")
    data = await fetch_fake_data("persons", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await msg.edit_text("❌ Failed to generate user persona.")

    user = data_list[0]
    fname = user.get("firstname", "")
    lname = user.get("lastname", "")
    email = user.get("email", "")
    gender = user.get("gender", "")
    phone = user.get("phone", "")
    dob = user.get("birthday", "")
    address = user.get("address", {})
    street = address.get("street", "")
    city = address.get("city", "")
    country = address.get("country", "")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_user")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await msg.edit_text(
        f"👤 **Generated User Persona**\n\n"
        f"• **Name:** `{fname} {lname}`\n"
        f"• **Gender:** `{gender}` | **DOB:** `{dob}`\n"
        f"• **Email:** `{email}`\n"
        f"• **Phone:** `{phone}`\n"
        f"• **Location:** `{street}, {city}, {country}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command(["fakeaddress"]))
async def cmd_fake_address(client: Client, message: Message):
    """Command: /fakeaddress - Generates fake geographical address details."""
    msg = await message.reply_text("📍 Generating mock address...")
    data = await fetch_fake_data("addresses", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await msg.edit_text("❌ Failed to generate address.")

    addr = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_address")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await msg.edit_text(
        f"📍 **Generated Mock Address**\n\n"
        f"• **Street:** `{addr.get('street', '')}`\n"
        f"• **Street Name:** `{addr.get('streetName', '')}`\n"
        f"• **City:** `{addr.get('city', '')}`\n"
        f"• **State:** `{addr.get('state', '')}`\n"
        f"• **Zipcode:** `{addr.get('zipcode', '')}`\n"
        f"• **Country:** `{addr.get('country', '')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^faker_home$"))
async def cb_faker_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "🎭 **Faker Mock Data Intelligence Suite**\n\n"
        "Generate realistic fake user profiles, addresses, company info, and financial test records instantly "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_faker_main_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^faker_user$"))
async def cb_faker_user(client: Client, query: CallbackQuery):
    await query.answer("Generating user...")
    data = await fetch_fake_data("persons", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate user.", show_alert=True)

    user = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_user")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"👤 **Generated User Persona**\n\n"
        f"• **Name:** `{user.get('firstname')} {user.get('lastname')}`\n"
        f"• **Email:** `{user.get('email')}`\n"
        f"• **Phone:** `{user.get('phone')}`\n"
        f"• **Country:** `{user.get('address', {}).get('country')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_address$"))
async def cb_faker_address(client: Client, query: CallbackQuery):
    await query.answer("Generating address...")
    data = await fetch_fake_data("addresses", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate address.", show_alert=True)

    addr = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_address")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"📍 **Generated Mock Address**\n\n"
        f"• **Street:** `{addr.get('street')}`\n"
        f"• **City:** `{addr.get('city')}`\n"
        f"• **Zipcode:** `{addr.get('zipcode')}`\n"
        f"• **Country:** `{addr.get('country')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_company$"))
async def cb_faker_company(client: Client, query: CallbackQuery):
    await query.answer("Generating company...")
    data = await fetch_fake_data("companies", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate company.", show_alert=True)

    comp = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_company")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"🏢 **Generated Mock Company**\n\n"
        f"• **Company Name:** `{comp.get('name')}`\n"
        f"• **Catch Phrase:** _{comp.get('catchPhrase', 'N/A')}_\n"
        f"• **Email:** `{comp.get('email')}`\n"
        f"• **Website:** `{comp.get('website')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_card$"))
async def cb_faker_card(client: Client, query: CallbackQuery):
    await query.answer("Generating credit card...")
    data = await fetch_fake_data("credit_cards", quantity=1)
    data_list = data.get("data", [])

    if not data_list:
        return await query.answer("Failed to generate card.", show_alert=True)

    card = data_list[0]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="faker_card")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="faker_home")]
    ])

    await query.message.edit_text(
        f"💳 **Generated Mock Credit Card**\n\n"
        f"• **Type:** `{card.get('type')}`\n"
        f"• **Number:** `{card.get('number')}`\n"
        f"• **Expiration:** `{card.get('expiration')}`\n"
        f"• **Owner:** `{card.get('owner')}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_callback_query(filters.regex(r"^faker_close$"))
async def cb_faker_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
