import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from vgx import app
import random
from datetime import datetime, timedelta

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


# --- CONFIGURATION & STATE ---
# Mock API wrapper for structured random test records
FAKER_API_BASE = "https://fakerapi.ai/api/v1" if False else "https://fakerapi.it/api/v1"

# Persistent active seed state for reproducible random generation
CURRENT_SEED = None


def set_custom_seed(seed_value: int):
    """Sets Python's random seed to simulate Faker's reproducible seed behavior."""
    global CURRENT_SEED
    CURRENT_SEED = seed_value
    random.seed(seed_value)


async def fetch_random_record(resource: str) -> dict:
    """Fetches a random mock data entity."""
    url = f"{FAKER_API_BASE}/{resource}?_quantity=1"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    return data[0]
        except Exception as e:
            print(f"Faker Randomizer Exception: {e}")
        return {}


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_randomizer_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for Faker Randomizer controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Generate Float (0-1)", callback_data="rand_float"),
            InlineKeyboardButton("🔢 Roll Random Int", callback_data="rand_int")
        ],
        [
            InlineKeyboardButton("🌱 Set Seed (42)", callback_data="rand_seed_42"),
            InlineKeyboardButton("🧹 Clear Seed", callback_data="rand_seed_clear")
        ],
        [
            InlineKeyboardButton("👤 Random Seeded Profile", callback_data="rand_profile"),
            InlineKeyboardButton("📚 API Docs", url="https://fakerjs.dev/api/randomizer")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="rand_close")]
    ])


@app.on_message(filters.command(["randomizer", "fakerand", "seed"]))
async def cmd_randomizer_dashboard(client: Client, message: Message):
    """Command: /randomizer - Opens the interactive Faker Randomizer dashboard."""
    seed_status = f"`{CURRENT_SEED}`" if CURRENT_SEED is not None else "_None (Unseeded)_"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Control pseudo-random generation, test reproducible seeds, and generate random datasets using the UI below:"
    )
    await message.reply_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["setseed"]))
async def cmd_set_seed(client: Client, message: Message):
    """Command: /setseed <number> - Sets a custom random seed for reproducibility."""
    args = message.command
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply_text(
            "⚠️ **Usage:** `/setseed <number>`\n\n_Example:_ `/setseed 42`",
            parse_mode=ParseMode.MARKDOWN
        )

    seed_val = int(args[1])
    set_custom_seed(seed_val)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="rand_home")]])
    await message.reply_text(
        f"🌱 **Seed Successfully Updated!**\n\n"
        f"• **New Seed:** `{seed_val}`\n"
        f"• Subsequent random generations will now be 100% reproducible.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^rand_home$"))
async def cb_rand_home(client: Client, query: CallbackQuery):
    await query.answer()
    seed_status = f"`{CURRENT_SEED}`" if CURRENT_SEED is not None else "_None (Unseeded)_"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Control pseudo-random generation, test reproducible seeds, and generate random datasets using the UI below:"
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_float$"))
async def cb_rand_float(client: Client, query: CallbackQuery):
    val = random.random()
    await query.answer(f"Generated: {val:.4f}", show_alert=True)


@app.on_callback_query(filters.regex(r"^rand_int$"))
async def cb_rand_int(client: Client, query: CallbackQuery):
    val = random.randint(1, 1000)
    await query.answer(f"Random Integer: {val}", show_alert=True)


@app.on_callback_query(filters.regex(r"^rand_seed_42$"))
async def cb_rand_seed_42(client: Client, query: CallbackQuery):
    set_custom_seed(42)
    await query.answer("Seed set to 42 🌿", show_alert=False)
    
    seed_status = f"`{CURRENT_SEED}`"
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** {seed_status}\n\n"
        "Seed locked to `42`. All outputs will now be deterministic."
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_seed_clear$"))
async def cb_rand_seed_clear(client: Client, query: CallbackQuery):
    global CURRENT_SEED
    CURRENT_SEED = None
    random.seed()  # Reset to system entropy source
    await query.answer("Seed cleared 🧹", show_alert=False)
    
    text = (
        "🎲 **Faker Randomizer & Seed Intelligence Suite**\n\n"
        f"• **Current Active Seed:** _None (System Entropy)_\n\n"
        "Randomizer reset to standard non-deterministic behavior."
    )
    await query.message.edit_text(text, reply_markup=get_randomizer_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^rand_profile$"))
async def cb_rand_profile(client: Client, query: CallbackQuery):
    await query.answer("Fetching seeded profile...")
    user = await fetch_random_record("persons")
    
    if not user:
        return await query.answer("Failed to generate entity.", show_alert=True)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="rand_profile")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="rand_home")]
    ])

    await query.message.edit_text(
        f"👤 **Seeded Random User Persona**\n\n"
        f"• **Name:** `{user.get('firstname')} {user.get('lastname')}`\n"
        f"• **Email:** `{user.get('email')}`\n"
        f"• **Active Seed:** `{CURRENT_SEED if CURRENT_SEED is not None else 'Unseeded'}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^rand_close$"))
async def cb_rand_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()


# --- MOCK DATA POOLS (Faker Airline Standard) ---
AIRLINES = [
    {"name": "Singapore Airlines", "iata": "SQ"},
    {"name": "Emirates", "iata": "EK"},
    {"name": "Delta Air Lines", "iata": "DL"},
    {"name": "Lufthansa", "iata": "LH"},
    {"name": "Qatar Airways", "iata": "QR"},
    {"name": "Japan Airlines", "iata": "JL"}
]

AIRPORTS = [
    {"city": "New York (JFK)", "code": "JFK"},
    {"city": "London (LHR)", "code": "LHR"},
    {"city": "Tokyo (HND)", "code": "HND"},
    {"city": "Dubai (DXB)", "code": "DXB"},
    {"city": "Singapore (SIN)", "code": "SIN"},
    {"city": "Paris (CDG)", "code": "CDG"},
    {"city": "Sydney (SYD)", "code": "SYD"}
]

AIRCRAFT_TYPES = [
    {"name": "Airbus A350-900", "type": "Widebody"},
    {"name": "Boeing 777-300ER", "type": "Widebody"},
    {"name": "Airbus A321neo", "type": "Narrowbody"},
    {"name": "Boeing 787-9 Dreamliner", "type": "Widebody"}
]

FIRST_NAMES = ["Alexander", "Sophia", "Liam", "Emma", "Noah", "Olivia", "Lucas", "Ava"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]


def generate_flight_itinerary() -> dict:
    """Simulates Faker.js airline & booking generators for complete itineraries."""
    airline = random.choice(AIRLINES)
    origin, destination = random.sample(AIRPORTS, 2)
    aircraft = random.choice(AIRCRAFT_TYPES)
    
    # Flight number (e.g., EK402)
    flight_num = f"{airline['iata']}{random.randint(100, 999)}"
    
    # Seat (e.g., 14A, 32K)
    row = random.randint(5, 45)
    seat_letter = random.choice(["A", "B", "C", "D", "E", "F", "J", "K"])
    seat = f"{row}{seat_letter}"
    
    # Record Locator / PNR (6 alphanumeric characters)
    pnr = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
    
    # Passenger
    passenger = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    
    # Timings
    dep_time = datetime.utcnow() + timedelta(hours=random.randint(6, 72))
    arr_time = dep_time + timedelta(hours=random.randint(3, 14), minutes=random.choice([0, 15, 30, 45]))

    return {
        "passenger": passenger,
        "airline": airline["name"],
        "flight": flight_num,
        "origin": origin["city"],
        "destination": destination["city"],
        "aircraft": aircraft["name"],
        "seat": seat,
        "pnr": pnr,
        "departure": dep_time.strftime("%d %b %Y, %H:%M UTC"),
        "arrival": arr_time.strftime("%d %b %Y, %H:%M UTC"),
        "class": random.choice(["Economy", "Business Class", "First Class"])
    }


# ==========================================
# --- INTERACTIVE DASHBOARD MENU ---
# ==========================================

def get_airline_menu() -> InlineKeyboardMarkup:
    """Master inline keyboard dashboard for flight generator controls."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ Generate Itinerary", callback_data="air_generate"),
            InlineKeyboardButton("💺 Shuffle Seat", callback_data="air_generate")
        ],
        [
            InlineKeyboardButton("📚 Airline Docs", url="https://fakerjs.dev/api/airline.html"),
            InlineKeyboardButton("❌ Close", callback_data="air_close")
        ]
    ])


@app.on_message(filters.command(["airline", "flight", "boardingpass"]))
async def cmd_airline_dashboard(client: Client, message: Message):
    """Command: /airline - Opens the interactive Faker Airline Itinerary generator."""
    text = (
        "✈️ **Faker Airline Intelligence Suite**\n\n"
        "Generate realistic airline bookings, boarding passes, flight numbers, and PNR locators instantly "
        "using the interactive controls below:"
    )
    await message.reply_text(text, reply_markup=get_airline_menu(), parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- COMMAND HANDLERS ---
# ==========================================

@app.on_message(filters.command(["bookflight", "itinerary"]))
async def cmd_generate_itinerary(client: Client, message: Message):
    """Command: /bookflight - Generates a complete mock boarding pass itinerary."""
    flight = generate_flight_itinerary()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="air_generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="air_home")]
    ])

    itinerary_text = (
        f"🎫 **CONFIRMED FLIGHT ITINERARY**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Passenger Name:** `{flight['passenger']}`\n"
        f"• **Booking Reference (PNR):** `{flight['pnr']}`\n\n"
        f"✈️ **Flight Details:**\n"
        f"• **Airline:** `{flight['airline']}` (`{flight['flight']}`)\n"
        f"• **Aircraft:** `{flight['aircraft']}`\n"
        f"• **Travel Class:** `{flight['class']}`\n"
        f"• **Seat Assignment:** `{flight['seat']}`\n\n"
        f"📍 **Route & Schedule:**\n"
        f"• **From:** `{flight['origin']}`\n"
        f"• **Departure:** `{flight['departure']}`\n"
        f"• **To:** `{flight['destination']}`\n"
        f"• **Arrival:** `{flight['arrival']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.reply_text(itinerary_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# --- INTERACTIVE CALLBACK ROUTERS ---
# ==========================================

@app.on_callback_query(filters.regex(r"^air_home$"))
async def cb_air_home(client: Client, query: CallbackQuery):
    await query.answer()
    text = (
        "✈️ **Faker Airline Intelligence Suite**\n\n"
        "Generate realistic airline bookings, boarding passes, flight numbers, and PNR locators instantly "
        "using the interactive controls below:"
    )
    await query.message.edit_text(text, reply_markup=get_airline_menu(), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^air_generate$"))
async def cb_air_generate(client: Client, query: CallbackQuery):
    await query.answer("Generating new flight itinerary...")
    flight = generate_flight_itinerary()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Another", callback_data="air_generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="air_home")]
    ])

    itinerary_text = (
        f"🎫 **CONFIRMED FLIGHT ITINERARY**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Passenger Name:** `{flight['passenger']}`\n"
        f"• **Booking Reference (PNR):** `{flight['pnr']}`\n\n"
        f"✈️ **Flight Details:**\n"
        f"• **Airline:** `{flight['airline']}` (`{flight['flight']}`)\n"
        f"• **Aircraft:** `{flight['aircraft']}`\n"
        f"• **Travel Class:** `{flight['class']}`\n"
        f"• **Seat Assignment:** `{flight['seat']}`\n\n"
        f"📍 **Route & Schedule:**\n"
        f"• **From:** `{flight['origin']}`\n"
        f"• **Departure:** `{flight['departure']}`\n"
        f"• **To:** `{flight['destination']}`\n"
        f"• **Arrival:** `{flight['arrival']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    await query.message.edit_text(itinerary_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^air_close$"))
async def cb_air_close(client: Client, query: CallbackQuery):
    await query.answer("Closed ❌")
    await query.message.delete()
