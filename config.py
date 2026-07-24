import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()




class Config:
    API_ID = int(os.environ.get("API_ID", "12345")) # Get from my.telegram.org
    API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
    
    # MongoDB Connection URL (Get from MongoDB Atlas)
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://...")   
    DB_NAME = "GroupSchedulerBot" # Database name 

    SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID", "your_client_id_here")
    SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET", "your_client_secret_here")

    # Bot Owner / Admin User IDs (Comma-separated)
    SUDO_USERS = [int(x) for x in os.getenv("SUDO_USERS", "784589736").split(",") if x.strip()]

    ADMIN_ID = 784589736 # Your Telegram ID (to prevent abuse)
    DEFAULT_INTERVAL = 3600 # Default interval in seconds (3 hours =
    # Viral threshold: 1.5 = 50% higher than average
    VIRAL_THRESHOLD = 1.5 
    # Polling interval in seconds (e.g., check feeds every 5 minutes
    UPDATE_INTERVAL = 300 
    # Directory to temporarily store downloads
    DOWNLOAD_DIR = "downloads"

    #API's
    #1
    FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")
    #2
    API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
    API_FOOTBALL_HOST = "v3.football.api-sports.io"
    #3
    # Highlightly API Configuration
    HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY", "YOUR_HIGHLIGHTLY_KEY")
    HIGHLIGHTLY_BASE_URL = "https://api.highlightly.net/v1" # Standardized endpoint base

    # Supported Sports List
    SPORTS = [
         "football", "basketball", "american-football", "hockey", 
         "baseball", "cricket", "rugby", "volleyball", "handball"
    ]   
    # Ensure download directory exists
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)


    
        
