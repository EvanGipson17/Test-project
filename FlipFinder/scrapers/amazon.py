"""
Amazon Warehouse / Clearance deals scraper.

Amazon Warehouse Deals are sold by seller ID A2L77EE7U53NWQ.
We search that seller's inventory filtered to electronics and home categories
and look for items with 30%+ discount marked.

NOTE: Amazon's anti-bot measures are aggressive. This scraper uses
realistic headers and delays but may need a proxy rotation service
or manual cookie injection for reliable long-term operation.
"""
import re
import time
import logging
import random
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import config
from scrapers.base import Deal

logger = logging.getLogger(__name__)

WAREHOUSE_SELLER_ID = "A2L77EE7U53NWQ"  # Amazon Warehouse Deals official seller

# Categories to search: (Amazon category node, our category name)
CATEGORIES = [
    ("172282",  "electronics"),   # Electronics
    ("1055398", "appliances"),    # Home & Kitchen
    ("468642",  "electronics"),   # Computers
    ("16225007011", "electronics"), # Headphones
    ("541966",  "gaming"),        # PC Gaming
]

MIN_DISCOUNT_PERCENT = 30


def _headers() -> dict:
    return {
        "User-Agent": config.random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


def _parse_price(raw: str) -> Optional[float]:
    raw = raw.replace(",", "").replace("$", "").strip()
    try:
        return float(raw)
    except ValueError:
        match = re.search(r"[\d]+\.?\d*", raw)
        return float(match.group()) if match else None


def _parse_discount(raw: str) -> Optional[int]:
    """Extract integer discount percentage from '-30%' style strings."""
    match = re.search(r"(\d+)%", raw)
    return int(match.group(1)) if match else None


def _scrape_category(session: requests.Session, node_id: str, category: str) -> list[Deal]:
    """Fetch one page of Amazon Warehouse results for a given category node."""
    deals: list[Deal] = []
    params = {
        "me": WAREHOUSE_SELLER_ID,
        "_encoding": "UTF8",
        "node": node_id,
        "pf_rd_r": "",
        "pf_rd_p": "",
        "ref_": "olp_aod_NEW_mbc",
    }
    url = "https://www.amazon.com/s?" + urlencode(params)

    try:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN + 1, config.REQUEST_DELAY_MAX + 2))
        resp = session.get(url, headers=_headers(), timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Amazon request failed for node %s: %s", node_id, e)
        return deals

    # If Amazon returns a CAPTCHA page, bail gracefully
    if "captcha" in resp.url.lower() or "robot" in resp.text[:500].lower():
        logger.warning("Amazon returned CAPTCHA for node %s - skipping", node_id)
        return deals

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("[data-component-type='s-search-result']")

    for item in items:
        try:
            # Title
            title_el = item.select_one("h2 a span") or item.select_one("h2 span.a-size-medium")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # URL
            link_el = item.select_one("h2 a[href]")
            if not link_el:
                continue
            href = link_el["href"]
            if not href.startswith("http"):
                href = "https://www.amazon.com" + href

            # Current (sale) price
            price_el = (
                item.select_one(".a-price .a-offscreen")
                or item.select_one("span.a-price-whole")
            )
            if not price_el:
                continue
            buy_price = _parse_price(price_el.get_text())
            if buy_price is None or buy_price <= 0 or buy_price > config.MAX_BUY_PRICE:
                continue

            # Original price (for discount calculation)
            orig_el = item.select_one("span.a-price.a-text-price .a-offscreen")
            orig_price = _parse_price(orig_el.get_text()) if orig_el else None

            # Check savings badge / discount
            savings_el = item.select_one(".a-badge-text") or item.select_one("[class*='savingsPercentage']")
            discount = None
            if savings_el:
                discount = _parse_discount(savings_el.get_text())
            elif orig_price and orig_price > buy_price:
                discount = int((orig_price - buy_price) / orig_price * 100)

            if discount is None or discount < MIN_DISCOUNT_PERCENT:
                continue

            # Image
            img_el = item.select_one("img.s-image")
            image_url = img_el.get("src", "") if img_el else ""

            # Condition note (warehouse items often have condition descriptions)
            cond_el = item.select_one(".a-color-secondary") or item.select_one("[class*='condition']")
            condition = cond_el.get_text(strip=True)[:80] if cond_el else "Warehouse"

            deals.append(Deal(
                title=title,
                buy_price=buy_price,
                source="amazon",
                url=href,
                category=category,
                image_url=image_url,
                condition=condition,
            ))
        except Exception as e:
            logger.debug("Amazon item parse error: %s", e)
            continue

    logger.info("Amazon node %s (%s) -> %d deals with >=%d%% discount",
                node_id, category, len(deals), MIN_DISCOUNT_PERCENT)
    return deals


def scrape() -> list[Deal]:
    """Scrape Amazon Warehouse deals across configured categories."""
    all_deals: list[Deal] = []
    seen_urls: set[str] = set()
    session = requests.Session()

    for node_id, category in CATEGORIES:
        for deal in _scrape_category(session, node_id, category):
            if deal.url not in seen_urls:
                seen_urls.add(deal.url)
                all_deals.append(deal)

    logger.info("Amazon Warehouse total: %d unique deals", len(all_deals))
    return all_deals
