# filepath: /home/iron/playground_API/config.py
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class Settings:
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    HOST: str = os.getenv("HOST")  # Default to 'postgres' for Docker
    PORT: str = os.getenv("PORT")  # Default to '5432' for PostgreSQL
    DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{HOST}:{PORT}/{POSTGRES_DB}"
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

settings = Settings()