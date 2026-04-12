"""
eBay Sold Listings Price Engine.

Fetches average sold price, velocity, and price confidence for a search query
by scraping eBay's completed/sold listings (covers last ~30 days of sales).
This is the price truth engine - not a source for buying.
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
    raw = raw.split(" to ")[0]
    match = re.search(r"[\d,]+\.?\d*", raw.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def get_sold_data(query: str) -> dict:
    """
    Search eBay completed/sold listings for `query` (last ~30 days).

    Outlier trimming: drops bottom 15% and top 15% of prices for accuracy.
    Price confidence is rated 1-10 based on how many sold listings were found
    (more data = higher confidence in the average).

    Returns:
        {
            "avg_sold_price":   float,
            "num_sold":         int,
            "velocity_score":   int,   # 1-10: sell speed
            "price_confidence": int,   # 1-10: data confidence
            "prices":           list[float],
        }
    """
    empty = {"avg_sold_price": 0.0, "num_sold": 0, "velocity_score": 0,
             "price_confidence": 0, "prices": []}

    if not query:
        return empty

    url = (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={quote_plus(query)}"
        "&LH_Sold=1&LH_Complete=1"
        "&_sacat=0&_ipg=120"   # up to 120 results for better 30-day coverage
        "&_sop=13"             # sort: most recently listed
    )

    try:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))
        resp = _SESSION.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("eBay request failed for %r: %s", query, config.safe_str(e))
        return empty

    soup = BeautifulSoup(resp.text, "html.parser")
    prices: list[float] = []

    for item in soup.select("li.s-item"):
        if "s-item--watch-at-corner" in item.get("class", []):
            continue

        price_el = item.select_one(".s-item__price")
        if not price_el:
            continue

        # Only count green "Sold" prices
        sold_label = item.select_one(".POSITIVE") or item.select_one(".s-item__purchase-options-cbx")
        if not sold_label and not item.select_one(".s-item__price.POSITIVE"):
            detail = item.get_text(separator=" ")
            if "Sold" not in detail:
                continue

        p = _parse_price(price_el.get_text())
        if p and 1 < p < 10000:
            prices.append(p)

    if not prices:
        logger.debug("No sold prices found for %r", query)
        return empty

    # Remove outliers: drop bottom 15% and top 15% for accurate pricing
    prices.sort()
    trim = max(1, int(len(prices) * 0.15))
    trimmed = prices[trim:-trim] if len(prices) > 6 else prices
    avg_price = sum(trimmed) / len(trimmed)

    num_sold = len(prices)

    # Velocity score (1-10): how many units sold
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

    # Price confidence (1-10): based on how many data points we have
    # More sold listings = more reliable average price
    if num_sold <= 2:
        confidence = 2
    elif num_sold <= 5:
        confidence = 4
    elif num_sold <= 10:
        confidence = 6
    elif num_sold <= 25:
        confidence = 8
    else:
        confidence = 10

    logger.debug(
        "eBay: %r -> avg=$%.2f sold=%d velocity=%d confidence=%d",
        query, avg_price, num_sold, velocity, confidence,
    )
    return {
        "avg_sold_price": round(avg_price, 2),
        "num_sold": num_sold,
        "velocity_score": velocity,
        "price_confidence": confidence,
        "prices": prices,
    }
