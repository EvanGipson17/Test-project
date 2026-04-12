"""
FlipFinder Configuration
All settings loaded from environment variables (.env file).
"""
import os
import random
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # Gmail App Password
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── Facebook Marketplace ──────────────────────────────────────────────────────
FACEBOOK_EMAIL = os.getenv("FACEBOOK_EMAIL", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")

# ── Location ──────────────────────────────────────────────────────────────────
AUSTIN_ZIP = os.getenv("AUSTIN_ZIP", "78701")
AUSTIN_LAT = 30.2672
AUSTIN_LON = -97.7431
SEARCH_RADIUS_MILES = int(os.getenv("SEARCH_RADIUS_MILES", "30"))

# ── Deal filters ──────────────────────────────────────────────────────────────
MIN_PROFIT_THRESHOLD = float(os.getenv("MIN_PROFIT_THRESHOLD", "50"))
MIN_ROI_THRESHOLD = float(os.getenv("MIN_ROI_THRESHOLD", "20"))
MAX_BUY_PRICE = float(os.getenv("MAX_BUY_PRICE", "250"))

# ── eBay fee model ────────────────────────────────────────────────────────────
EBAY_FEES_PERCENT = 0.13   # 13% combined eBay fees
SHIPPING_ESTIMATE = 8.0    # flat shipping cost estimate in USD

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────────
ROI_WEIGHT = 0.45
PROFIT_WEIGHT = 0.28
VELOCITY_WEIGHT = 0.17
CATEGORY_WEIGHT = 0.10

# ── Category priority scores (boosts flip_score for high-velocity categories) ─
# Scale: 1 (slow/risky) to 10 (fast/high-margin)
CATEGORY_PRIORITY = {
    "electronics": 10,
    "gaming":      9,
    "sneakers":    8,
    "streetwear":  8,
    "tools":       6,
    "appliances":  5,
    "furniture":   3,
    "other":       1,
}

# ── Scraping ──────────────────────────────────────────────────────────────────
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


def safe_str(x) -> str:
    """Convert any value to a UTF-8-safe string, replacing unencodable chars with '?'."""
    return str(x).encode("utf-8", errors="replace").decode("utf-8")


# ── Categories ────────────────────────────────────────────────────────────────
SLICKDEALS_CATEGORIES = ["electronics", "sneakers", "gaming", "appliances"]
FB_CATEGORIES = ["electronics", "gaming", "sneakers", "tools", "appliances", "furniture"]
CL_CATEGORIES = ["electronics", "tools", "gaming", "appliances"]
OFFERUP_CATEGORIES = ["electronics", "gaming", "sneakers", "tools", "appliances"]

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "flipfinder.db")

# ── Scheduler ─────────────────────────────────────────────────────────────────
TIMEZONE = "America/Chicago"
# Full scrape + report runs: list of (hour, minute) in CT
FULL_SCRAPE_TIMES = [(7, 45), (18, 0)]    # 7:45 AM and 6:00 PM CT daily
# Quick local scan (FB + CL + OfferUp): every N hours from START to END CT
QUICK_SCAN_START_HOUR = 8
QUICK_SCAN_END_HOUR = 21
QUICK_SCAN_INTERVAL_HOURS = 3             # runs at 8, 11, 14, 17, 20 CT
