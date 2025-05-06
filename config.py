from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DATABASE_URL")
TOKEN_KINOPOISK = os.getenv("TOKEN_KINOPOISK")
ZONA_URL = os.getenv("ZONA_URL")
SECRET_KEY = "SECRET"###os.getenv("SECRET_KEY")###
DOMAIN = "https://true-buckets-shop.loca.lt"