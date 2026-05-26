import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
USER_ID = os.getenv("USER_ID")

BASE_URL = "https://graph.facebook.com/v18.0"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

INSTAGRAM_PROVIDER = os.getenv("INSTAGRAM_PROVIDER", "mock")  # "apify" | "mock"
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_INSTAGRAM_ACTOR = os.getenv("APIFY_INSTAGRAM_ACTOR", "apify~instagram-scraper")
APIFY_INSTAGRAM_PROFILE_ACTOR = os.getenv("APIFY_INSTAGRAM_PROFILE_ACTOR", "apify~instagram-profile-scraper")
APIFY_RESULTS_LIMIT = int(os.getenv("APIFY_RESULTS_LIMIT", "30"))
APIFY_TIMEOUT_SECONDS = int(os.getenv("APIFY_TIMEOUT_SECONDS", "180"))