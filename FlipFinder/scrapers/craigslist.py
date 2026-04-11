"""
Craigslist Austin scraper.
Covers: electronics (ela), tools (tla), video gaming (vga), appliances (app).
Filters to items under MAX_BUY_PRICE within SEARCH_RADIUS_MILES of Austin.
"""
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

# Craigslist Austin section codes → our category names
CL_SECTIONS = {
    "ela": "electronics",
    "tla": "tools",
    "vga": "gaming",
    "app": "appliances",
}

BASE_URL = "https://austin.craigslist.org"


def _headers() -> dict:
    return {
        "User-Agent": config.random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _parse_price(text: str) -> Optional[float]:
    text = text.strip().replace(",", "").replace("$", "")
    try:
        return float(text)
    except ValueError:
        match = re.search(r"[\d]+\.?\d*", text)
        return float(match.group()) if match else None


def _scrape_section(section: str, category: str) -> list[Deal]:
    """Scrape one Craigslist section (e.g. 'ela' for electronics)."""
    deals: list[Deal] = []
    url = (
        f"{BASE_URL}/search/{section}"
        f"?max_price={int(config.MAX_BUY_PRICE)}"
        f"&postal={config.AUSTIN_ZIP}"
        f"&search_distance={config.SEARCH_RADIUS_MILES}"
        "&availabilityMode=0"
        "&sale_date=all+dates"
    )

    try:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Craigslist %s request failed: %s", section, e)
        return deals

    soup = BeautifulSoup(resp.text, "html.parser")

    # CL result rows are in li.cl-static-search-result or .result-row
    rows = soup.select("li.cl-static-search-result") or soup.select("li.result-row")

    for row in rows:
        try:
            # Title and URL
            title_el = (
                row.select_one("a.posting-title")
                or row.select_one(".result-title")
                or row.select_one("a[href*='/d/']")
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href

            # Price
            price_el = row.select_one(".priceinfo") or row.select_one(".result-price")
            if not price_el:
                continue
            buy_price = _parse_price(price_el.get_text())
            if buy_price is None or buy_price <= 0:
                continue
            if buy_price > config.MAX_BUY_PRICE:
                continue

            # Location
            loc_el = row.select_one(".location") or row.select_one(".result-hood")
            location = loc_el.get_text(strip=True).strip("() ") if loc_el else "Austin, TX"

            # Image
            img_el = row.select_one("img")
            image_url = img_el.get("src", "") if img_el else ""

            deals.append(Deal(
                title=title,
                buy_price=buy_price,
                source="craigslist",
                url=href,
                category=category,
                location=location,
                image_url=image_url,
            ))
        except Exception as e:
            logger.debug("CL row parse error: %s", e)
            continue

    logger.info("Craigslist /%s -> %d deals (<=$%.0f)", section, len(deals), config.MAX_BUY_PRICE)
    return deals


def scrape() -> list[Deal]:
    """Scrape all configured Craigslist Austin sections."""
    all_deals: list[Deal] = []
    for section, category in CL_SECTIONS.items():
        all_deals.extend(_scrape_section(section, category))
    logger.info("Craigslist total: %d deals", len(all_deals))
    return all_deals
