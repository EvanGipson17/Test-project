"""
Slickdeals.net scraper.
Targets the Hot Deals frontpage and the deals/hot listing.
Returns Deal objects for electronics, sneakers, gaming, and appliances.
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

# Categories we care about — used to filter deals
TARGET_KEYWORDS = {
    "electronics": ["headphone", "speaker", "tv", "monitor", "laptop", "phone",
                     "tablet", "camera", "earbuds", "router", "hard drive", "ssd",
                     "keyboard", "mouse", "printer", "smart", "audio", "charger"],
    "gaming":       ["ps5", "xbox", "nintendo", "switch", "game", "gaming",
                     "controller", "playstation", "gpu", "graphics card"],
    "sneakers":     ["nike", "adidas", "jordan", "yeezy", "new balance", "sneaker",
                     "shoe", "puma", "reebok", "vans", "converse"],
    "appliances":   ["vacuum", "blender", "coffee", "instant pot", "air fryer",
                     "washer", "dryer", "refrigerator", "dishwasher", "microwave",
                     "toaster", "keurig", "roomba", "dyson"],
}

SCRAPE_URLS = [
    "https://slickdeals.net/?hp=frontpage",
    "https://slickdeals.net/deals/hot/",
]


def _headers() -> dict:
    return {
        "User-Agent": config.random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://slickdeals.net/",
    }


def _detect_category(title: str) -> Optional[str]:
    title_lower = title.lower()
    for cat, keywords in TARGET_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return None


def _parse_price(raw: str) -> Optional[float]:
    # Handles "$29.99", "Free", "$0.00"
    raw = raw.strip().replace(",", "")
    if raw.lower() in ("free", "$0", "$0.00"):
        return 0.0
    match = re.search(r"\$?([\d]+\.?\d*)", raw)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def _parse_deals_from_page(html: str) -> list[Deal]:
    soup = BeautifulSoup(html, "html.parser")
    deals: list[Deal] = []

    # Slickdeals uses several card layouts; try multiple selectors
    cards = (
        soup.select("li[data-type='threadList'] .bp-c-card")
        or soup.select(".dealCard")
        or soup.select(".bp-c-card")
        or soup.select("li.js-fp-deal")
    )

    if not cards:
        # Fallback: find any deal link blocks
        cards = soup.select("a[data-href*='/f/']")

    for card in cards:
        try:
            # Title
            title_el = (
                card.select_one(".bp-c-card__title")
                or card.select_one(".dealCard__title")
                or card.select_one(".dealTitle")
                or card.select_one("h2")
                or card.select_one("a[data-link-type='dealTitle']")
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # Filter by category
            category = _detect_category(title)
            if not category:
                continue

            # Price
            price_el = (
                card.select_one(".bp-c-card__price")
                or card.select_one(".dealCard__price")
                or card.select_one(".price")
                or card.select_one("[class*='price']")
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            buy_price = _parse_price(price_text) if price_text else None
            if buy_price is None or buy_price <= 0:
                continue
            if buy_price > config.MAX_BUY_PRICE:
                continue

            # URL
            link_el = card.select_one("a[href]") or card
            href = link_el.get("href", "") if hasattr(link_el, "get") else ""
            if href and not href.startswith("http"):
                href = "https://slickdeals.net" + href
            if not href:
                continue

            # Image
            img_el = card.select_one("img[src]") or card.select_one("img[data-src]")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            deals.append(Deal(
                title=title,
                buy_price=buy_price,
                source="slickdeals",
                url=href,
                category=category,
                image_url=image_url,
            ))
        except Exception as e:
            logger.debug("Error parsing Slickdeals card: %s", e)
            continue

    return deals


def scrape() -> list[Deal]:
    """
    Scrape Slickdeals frontpage + hot deals.
    Returns a deduplicated list of Deal objects.
    """
    all_deals: list[Deal] = []
    seen_urls: set[str] = set()
    session = requests.Session()

    for url in SCRAPE_URLS:
        try:
            time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))
            resp = session.get(url, headers=_headers(), timeout=15)
            resp.raise_for_status()
            page_deals = _parse_deals_from_page(resp.text)
            for d in page_deals:
                if d.url not in seen_urls:
                    seen_urls.add(d.url)
                    all_deals.append(d)
            logger.info("Slickdeals %s -> %d deals", url, len(page_deals))
        except Exception as e:
            logger.error("Slickdeals scrape failed for %s: %s", url, e)

    logger.info("Slickdeals total: %d unique deals", len(all_deals))
    return all_deals
