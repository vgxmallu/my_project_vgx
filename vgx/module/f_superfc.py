import asyncio
import ScraperFC as sfc

class ScraperEngine:
    def __init__(self):
        # Initialize the ScraperFC classes
        self.fbref = sfc.FBref()
        self.understat = sfc.Understat()
        self.sofascore = sfc.Sofascore()
        self.transfermarkt = sfc.Transfermarkt()
        self.capology = sfc.Capology()
        self.clubelo = sfc.ClubElo()

    async def get_xg_data(self, year: str, league: str):
        """Advanced xG & Performance Analytics Dashboard"""
        def _scrape():
            return self.understat.get_match_dfs(year=year, league=league)
        return await asyncio.to_thread(_scrape)

    async def get_market_valuations(self, year: str, league: str):
        """Player Market Valuation & Transfer Hub"""
        def _scrape():
            return self.transfermarkt.scrape_players(year=year, league=league)
        return await asyncio.to_thread(_scrape)

    async def get_salaries(self, year: str, league: str, currency: str = "EUR"):
        """Financial & Salary Intelligence System"""
        def _scrape():
            return self.capology.scrape_salaries(year=year, league=league, currency=currency)
        return await asyncio.to_thread(_scrape)

    async def get_elo_fixtures(self):
        """Elo-Based Match Predictor & Win Probability Engine"""
        def _scrape():
            return self.clubelo.scrape_fixtures()
        return await asyncio.to_thread(_scrape)

    async def get_elo_history(self, team: str):
        """Historical Club Ranking Timelines"""
        def _scrape():
            return self.clubelo.scrape_team(team=team)
        return await asyncio.to_thread(_scrape)

    async def get_league_table(self, year: str, league: str):
        """Comprehensive League Table & Match Log Viewer"""
        def _scrape():
            return self.fbref.scrape_league_table(year=year, league=league)
        return await asyncio.to_thread(_scrape)

engine = ScraperEngine()


from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 xG & Performance (Understat)", callback_data="xg_analytics")],
        [InlineKeyboardButton("💰 Market Valuations (TM)", callback_data="market_finance")],
        [InlineKeyboardButton("🏦 Player Salaries (Capology)", callback_data="salary_finance")],
        [InlineKeyboardButton("🏆 League Tables (FBref)", callback_data="league_tables")],
        [InlineKeyboardButton("🔮 Elo Match Predictor (ClubELO)", callback_data="elo_predictor")],
        [InlineKeyboardButton("📈 Club Elo History", callback_data="elo_history")],
        [InlineKeyboardButton("📡 Live Game Directory (Sofa)", callback_data="sofa_live")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ])




@Client.on_message(filters.command("fscraper"))
async def stacjrt_command(client: Client, message: Message):
    text = (
        "<b>⚽ ScraperFC Intelligence Hub</b>\n\n"
        "Select a module below to query deep football metrics."
    )
    await message.reply_text(text, reply_markup=main_menu_keyboard())

#====================================================
@Client.on_callback_query(filters.regex(r"^main_menu$"))
async def back_to_main(client: Client, query: CallbackQuery):
    await query.message.edit_text(
        "<b>⚽ ScraperFC Intelligence Hub</b>\n\nSelect a module below:",
        reply_markup=main_menu_keyboard()
    )

@Client.on_callback_query(filters.regex(r"^xg_analytics$"))
async def handle_xg(client: Client, query: CallbackQuery):
    await query.message.edit_text("🔄 <i>Scraping advanced Understat xG metrics...</i>")
    
    try:
        # Example parameters for the request
        data = await engine.get_xg_data(year="2023", league="EPL")
        
        # Format pandas dataframe output for Telegram
        text = "🎯 <b>Understat xG Matrix</b>\n\n"
        text += f"Data points loaded: {len(data)}\n"
        # Add pandas parsing logic here to format top 5 rows
        
        await query.message.edit_text(text, reply_markup=back_keyboard())
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}", reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex(r"^elo_predictor$"))
async def handle_elo_fixtures(client: Client, query: CallbackQuery):
    await query.message.edit_text("🔄 <i>Calculating Elo win probabilities for upcoming fixtures...</i>")
    
    try:
        df = await engine.get_elo_fixtures()
        
        text = "🔮 <b>ClubELO Match Predictor</b>\n\n"
        # ClubELO returns columns like HomeTeam, AwayTeam, HomeProb, AwayProb
        if not df.empty:
            for index, row in df.head(5).iterrows():
                home = row.get('HomeTeam', 'Unknown')
                away = row.get('AwayTeam', 'Unknown')
                text += f"▪️ {home} vs {away}\n"
        
        await query.message.edit_text(text, reply_markup=back_keyboard())
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}", reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex(r"^elo_history$"))
async def handle_elo_history(client: Client, query: CallbackQuery):
    await query.message.edit_text("🔄 <i>Fetching historical Club ELO ratings...</i>")
    
    try:
        # Hardcoded to Arsenal for the example, can be dynamic
        df = await engine.get_elo_history(team="Arsenal") 
        text = f"📈 <b>Arsenal Elo History</b>\nTotal days tracked: {len(df)}\n"
        await query.message.edit_text(text, reply_markup=back_keyboard())
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}", reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex(r"^(market_finance|salary_finance)$"))
async def handle_finance(client: Client, query: CallbackQuery):
    action = query.data
    await query.message.edit_text("🔄 <i>Scraping financial databases...</i>")
    
    try:
        if action == "market_finance":
            df = await engine.get_market_valuations(year="2023", league="EPL")
            title = "💰 <b>Transfermarkt Valuations</b>"
        else:
            df = await engine.get_salaries(year="2023", league="EPL", currency="EUR")
            title = "🏦 <b>Capology Payrolls (EUR)</b>"
            
        text = f"{title}\n\nRecords found: {len(df)}"
        await query.message.edit_text(text, reply_markup=back_keyboard())
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}", reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex(r"^league_tables$"))
async def handle_tables(client: Client, query: CallbackQuery):
    await query.message.edit_text("🔄 <i>Scraping FBref League Standings...</i>")
    
    try:
        tables = await engine.get_league_table(year="2023", league="EPL")
        
        text = "🏆 <b>FBref Official League Table</b>\n\n"
        if isinstance(tables, list) and len(tables) > 0:
            df = tables[0] # FBref returns a list of dataframes for the league homepage
            for _, row in df.head(10).iterrows():
                team = str(row.get('Squad', 'Team'))
                pts = str(row.get('Pts', '0'))
                text += f"▪️ {team}: {pts} pts\n"
                
        await query.message.edit_text(text, reply_markup=back_keyboard())
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}", reply_markup=back_keyboard())
