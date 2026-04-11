"""
eBay Sold Listings Price Engine.

Fetches average sold price + velocity for a given search query
by scraping eBay's completed/sold listings search page.
This is the "price truth engine" — not a source for buying.
"""
import re
import time
import logging
import random
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

_SESSION = requests.Session()


def _headers() -> dict:
    return {
        "User-Agent": config.random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.ebay.com/",
        "DNT": "1",
    }


def _parse_price(raw: str) -> Optional[float]:
    """Extract float from strings like '$149.99', '$20.00 to $25.00'."""
    # Take the lower bound for ranges
    raw = raw.split(" to ")[0]
    match = re.search(r"[\d,]+\.?\d*", raw.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def get_sold_data(query: str, days: int = 7) -> dict:
    """
    Search eBay completed/sold listings for `query`.

    Returns:
        {
            "avg_sold_price": float,
            "num_sold": int,       # items sold in the period
            "velocity_score": int, # 1-10 scale
            "prices": list[float], # raw prices for debugging
        }
    """
    if not query:
        return {"avg_sold_price": 0.0, "num_sold": 0, "velocity_score": 0, "prices": []}

    url = (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={quote_plus(query)}"
        "&LH_Sold=1&LH_Complete=1"
        "&_sacat=0&_ipg=60"
        "&_sop=13"   # sort: most recently listed
    )

    try:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))
        resp = _SESSION.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("eBay request failed for %r: %s", query, e)
        return {"avg_sold_price": 0.0, "num_sold": 0, "velocity_score": 0, "prices": []}

    soup = BeautifulSoup(resp.text, "html.parser")

    prices: list[float] = []

    # Each result is inside li.s-item
    for item in soup.select("li.s-item"):
        # Skip the first "ghost" placeholder eBay injects
        if "s-item--watch-at-corner" in item.get("class", []):
            continue

        price_el = item.select_one(".s-item__price")
        if not price_el:
            continue

        # Only count green "Sold" prices (not unsold completed)
        sold_label = item.select_one(".POSITIVE") or item.select_one(".s-item__purchase-options-cbx")
        if not sold_label and not item.select_one(".s-item__price.POSITIVE"):
            # Fallback: check text for 'Sold'
            detail = item.get_text(separator=" ")
            if "Sold" not in detail:
                continue

        p = _parse_price(price_el.get_text())
        if p and 1 < p < 10000:
            prices.append(p)

    if not prices:
        logger.debug("No sold prices found for %r", query)
        return {"avg_sold_price": 0.0, "num_sold": 0, "velocity_score": 0, "prices": []}

    # Remove outliers: drop bottom 10% and top 10%
    prices.sort()
    trim = max(1, len(prices) // 10)
    trimmed = prices[trim:-trim] if len(prices) > 4 else prices
    avg_price = sum(trimmed) / len(trimmed)

    num_sold = len(prices)
    # Velocity: 1-10 scale based on count
    # 1-2 sold → 1, 3-5 → 3, 6-10 → 5, 11-20 → 7, 21-30 → 8, 31+ → 10
    if num_sold <= 2:
        velocity = 1
    elif num_sold <= 5:
        velocity = 3
    elif num_sold <= 10:
        velocity = 5
    elif num_sold <= 20:
        velocity = 7
    elif num_sold <= 30:
        velocity = 8
    else:
        velocity = 10

    logger.debug("eBay: %r → avg=$%.2f sold=%d velocity=%d", query, avg_price, num_sold, velocity)
    return {
        "avg_sold_price": round(avg_price, 2),
        "num_sold": num_sold,
        "velocity_score": velocity,
        "prices": prices,
    }
