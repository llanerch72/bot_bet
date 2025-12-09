import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self) -> None:
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        self.api_football_key = os.getenv("API_FOOTBALL_KEY")
        self.api_football_league_id = int(os.getenv("API_FOOTBALL_LEAGUE_ID", "140"))
        self.api_football_season = int(os.getenv("API_FOOTBALL_SEASON", "2025"))

        if not self.telegram_bot_token:
            raise ValueError("Falta TELEGRAM_BOT_TOKEN en el .env")
        if not self.telegram_chat_id:
            raise ValueError("Falta TELEGRAM_CHAT_ID en el .env")
        if not self.api_football_key:
            raise ValueError("Falta API_FOOTBALL_KEY en el .env")

settings = Settings()
