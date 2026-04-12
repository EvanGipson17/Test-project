"""
OfferUp Austin scraper.
Searches OfferUp for local Austin listings in configured categories.
Parses listings from the Next.js SSR data embedded in the page.
"""
import json
import re
import time
import logging
import random
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config
from scrapers.base import Deal

logger = logging.getLogger(__name__)

OFFERUP_SEARCH_URL = "https://offerup.com/search/"

# Category search terms -> our internal category names
OFFERUP_CATEGORIES = {
    "electronics":   "electronics",
    "gaming":        "gaming",
    "sneakers":      "sneakers",
    "tools":         "tools",
    "appliances":    "appliances",
}


def _headers() -> dict:
    return {
        "User-Agent": config.random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://offerup.com/",
        "DNT": "1",
    }


def _parse_price(raw) -> Optional[float]:
    raw = str(raw).replace(",", "").replace("$", "").strip()
    try:
        return float(raw)
    except (ValueError, TypeError):
        match = re.search(r"[\d]+\.?\d*", raw)
        return float(match.group()) if match else None


def _extract_listings_from_next_data(script_text: str) -> list:
    """Pull listing objects from Next.js __NEXT_DATA__ JSON blob."""
    try:
        data = json.loads(script_text)
    except json.JSONDecodeError:
        return []

    props = data.get("props", {}).get("pageProps", {})

    # OfferUp nests results under various keys depending on page version
    candidates = [
        props.get("searchResults", {}).get("items") if isinstance(props.get("searchResults"), dict) else None,
        props.get("listings"),
        props.get("results"),
        props.get("items"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return candidate

    # Deep search for any list of dicts that look like listings
    def _deep_find(obj, depth=0):
        if depth > 6:
            return []
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            if "title" in obj[0] or "price" in obj[0]:
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                result = _deep_find(v, depth + 1)
                if result:
                    return result
        return []

    return _deep_find(props)


def _scrape_category(query: str, category: str) -> list[Deal]:
    deals: list[Deal] = []
    params = {
        "q": query,
        "location": "Austin, TX",
        "radius": config.SEARCH_RADIUS_MILES,
        "price_max": int(config.MAX_BUY_PRICE),
    }

    try:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))
        resp = requests.get(OFFERUP_SEARCH_URL, params=params, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error("OfferUp request failed for %r: %s", query, config.safe_str(e))
        return deals

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        logger.warning("OfferUp: no __NEXT_DATA__ found for %r - may be blocked or layout changed", query)
        return deals

    listings = _extract_listings_from_next_data(script.string)
    if not listings:
        logger.debug("OfferUp: no listings parsed for %r", query)
        return deals

    for item in listings:
        try:
            title = str(item.get("title") or item.get("name") or "").strip()
            if not title:
                continue

            price_raw = item.get("price") or item.get("amount") or 0
            if isinstance(price_raw, dict):
                price_raw = price_raw.get("amount") or price_raw.get("value") or 0
            buy_price = _parse_price(price_raw)
            if buy_price is None or buy_price <= 0 or buy_price > config.MAX_BUY_PRICE:
                continue

            item_id = item.get("id") or item.get("listing_id") or item.get("pk") or ""
            if not item_id:
                continue
            url = f"https://offerup.com/item/detail/{item_id}/"

            location = "Austin, TX"
            loc = item.get("location") or item.get("city") or {}
            if isinstance(loc, dict):
                city = loc.get("city") or loc.get("name") or ""
                state = loc.get("state_abbr") or loc.get("state") or "TX"
                if city:
                    location = f"{city}, {state}"
            elif isinstance(loc, str) and loc:
                location = loc

            image_url = ""
            photos = item.get("photos") or item.get("images") or []
            photo_url = item.get("photo_url") or item.get("image_url") or ""
            if photo_url:
                image_url = photo_url
            elif isinstance(photos, list) and photos:
                first = photos[0]
                image_url = first.get("url") or first.get("src") or "" if isinstance(first, dict) else str(first)

            deals.append(Deal(
                title=title,
                buy_price=buy_price,
                source="offerup",
                url=url,
                category=category,
                location=location,
                image_url=image_url,
                is_local=True,
            ))
        except Exception as e:
            logger.debug("OfferUp item parse error: %s", config.safe_str(e))
            continue

    logger.info("OfferUp %r -> %d deals (<=$%.0f)", query, len(deals), config.MAX_BUY_PRICE)
    return deals


def scrape() -> list[Deal]:
    """Scrape OfferUp Austin listings across all configured categories."""
    all_deals: list[Deal] = []
    for query, category in OFFERUP_CATEGORIES.items():
        all_deals.extend(_scrape_category(query, category))

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[Deal] = []
    for d in all_deals:
        if d.url not in seen:
            seen.add(d.url)
            unique.append(d)

    logger.info("OfferUp total: %d unique deals", len(unique))
    return unique
