"""
FlipFinder Configuration
All settings loaded from environment variables (.env file).
"""
import os
import random
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # Gmail App Password
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── Facebook Marketplace ───────────────────────────────────────────────────────
FACEBOOK_EMAIL = os.getenv("FACEBOOK_EMAIL", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")

# ── Location ───────────────────────────────────────────────────────────────────
AUSTIN_ZIP = os.getenv("AUSTIN_ZIP", "78701")
AUSTIN_LAT = 30.2672
AUSTIN_LON = -97.7431
SEARCH_RADIUS_MILES = int(os.getenv("SEARCH_RADIUS_MILES", "30"))

# ── Profit thresholds ──────────────────────────────────────────────────────────
MIN_PROFIT_THRESHOLD = float(os.getenv("MIN_PROFIT_THRESHOLD", "30"))
MIN_ROI_THRESHOLD = float(os.getenv("MIN_ROI_THRESHOLD", "20"))
MAX_BUY_PRICE = float(os.getenv("MAX_BUY_PRICE", "500"))

# ── eBay fee model ─────────────────────────────────────────────────────────────
EBAY_FEES_PERCENT = 0.13   # 13% combined eBay + PayPal fees
SHIPPING_ESTIMATE = 8.0    # flat shipping cost estimate in USD

# ── Scoring weights ────────────────────────────────────────────────────────────
ROI_WEIGHT = 0.5
PROFIT_WEIGHT = 0.3
VELOCITY_WEIGHT = 0.2

# ── Scraping ───────────────────────────────────────────────────────────────────
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 8

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.2151.97",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


# ── Categories ─────────────────────────────────────────────────────────────────
SLICKDEALS_CATEGORIES = ["electronics", "sneakers", "gaming", "appliances"]
FB_CATEGORIES = ["electronics", "gaming", "sneakers", "tools", "appliances", "furniture"]
CL_CATEGORIES = ["electronics", "tools", "gaming", "appliances"]

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "flipfinder.db")

# ── Scheduler ──────────────────────────────────────────────────────────────────
TIMEZONE = "America/Chicago"
FULL_SCRAPE_HOUR = 20    # 8 PM CT
REPORT_HOUR = 21         # 9 PM CT
QUICK_SCAN_HOURS = "8,14"  # 8 AM and 2 PM CT
