"""
Facebook Marketplace Austin scraper.

Uses Selenium + undetected_chromedriver to log in to Facebook and
scrape Marketplace listings within SEARCH_RADIUS_MILES of Austin, TX.

Setup requirements:
  - Chrome browser installed (chromium-browser or google-chrome)
  - FACEBOOK_EMAIL and FACEBOOK_PASSWORD set in .env
  - undetected-chromedriver installed: pip install undetected-chromedriver

Known limitations:
  - Meta/Facebook has aggressive bot detection; this approach works best
    with a real account that has existing activity.
  - Headless mode may trigger 2FA or CAPTCHA on new accounts.
  - Run headed (HEADLESS=False) on first use to complete any manual login.
"""
import os
import re
import time
import logging
import random
from typing import Optional

from scrapers.base import Deal
import config

logger = logging.getLogger(__name__)

# Facebook Marketplace category slugs
FB_CATEGORY_SLUGS = {
    "electronics": "electronics",
    "gaming":      "electronics/gaming-consoles-and-accessories",
    "sneakers":    "clothing-accessories/shoes-women",  # FB combines these
    "tools":       "home-goods/power-tools",
    "appliances":  "appliances",
    "furniture":   "furniture",
}

AUSTIN_CITY_ID = "austin"   # FB uses city names in URLs


def _try_import_uc():
    """Late-import undetected_chromedriver to avoid hard dependency at module load."""
    try:
        import undetected_chromedriver as uc
        return uc
    except ImportError:
        logger.error(
            "undetected_chromedriver not installed. "
            "Run: pip install undetected-chromedriver"
        )
        return None


def _parse_price(text: str) -> Optional[float]:
    text = text.strip()
    if "free" in text.lower():
        return 0.0
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


class FacebookMarketplaceScraper:
    def __init__(self):
        self.driver = None
        self._logged_in = False

    def _make_driver(self, headless: bool = True):
        uc = _try_import_uc()
        if not uc:
            return None
        from selenium.webdriver.chrome.options import Options
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={config.random_user_agent()}")
        options.add_argument("--window-size=1280,900")
        try:
            driver = uc.Chrome(options=options, use_subprocess=True)
            return driver
        except Exception as e:
            logger.error("Failed to start Chrome driver: %s", e)
            return None

    def login(self, headless: bool = True) -> bool:
        """Log into Facebook. Returns True on success."""
        if not config.FACEBOOK_EMAIL or not config.FACEBOOK_PASSWORD:
            logger.error("FACEBOOK_EMAIL / FACEBOOK_PASSWORD not configured.")
            return False

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException

        self.driver = self._make_driver(headless=headless)
        if not self.driver:
            return False

        try:
            self.driver.get("https://www.facebook.com/login")
            time.sleep(random.uniform(2, 4))

            # Accept cookies if the banner appears
            try:
                cookie_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Allow') or contains(., 'Accept')]"))
                )
                cookie_btn.click()
                time.sleep(1)
            except TimeoutException:
                pass

            # Enter credentials
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field.clear()
            for ch in config.FACEBOOK_EMAIL:
                email_field.send_keys(ch)
                time.sleep(random.uniform(0.04, 0.12))

            pass_field = self.driver.find_element(By.ID, "pass")
            pass_field.clear()
            for ch in config.FACEBOOK_PASSWORD:
                pass_field.send_keys(ch)
                time.sleep(random.uniform(0.04, 0.12))

            time.sleep(random.uniform(0.5, 1.5))
            pass_field.submit()

            # Wait for the marketplace icon to confirm login
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.any_of(
                        EC.url_contains("facebook.com/marketplace"),
                        EC.url_contains("facebook.com/?"),
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'marketplace')]")),
                    )
                )
                self._logged_in = True
                logger.info("Facebook login successful")
                return True
            except TimeoutException:
                logger.warning("Facebook login timeout — may need manual 2FA")
                return False

        except Exception as e:
            logger.error("Facebook login error: %s", e)
            return False

    def scrape_category(self, category_slug: str, category_name: str,
                        max_price: float = None) -> list[Deal]:
        """Scrape one FB Marketplace category in Austin."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException

        if not self._logged_in or not self.driver:
            return []

        max_price = max_price or config.MAX_BUY_PRICE
        url = (
            f"https://www.facebook.com/marketplace/{AUSTIN_CITY_ID}/{category_slug}"
            f"?maxPrice={int(max_price)}"
            f"&deliveryMethod=local_pick_up"
            f"&radius={config.SEARCH_RADIUS_MILES}"
        )

        deals: list[Deal] = []
        try:
            self.driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Scroll to load more listings
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 2.5))

            # Wait for listing cards
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='marketplace_feed_item']"))
                )
            except TimeoutException:
                pass  # Try to parse whatever loaded

            items = (
                self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='marketplace_feed_item']")
                or self.driver.find_elements(By.CSS_SELECTOR, "div[class*='x1i10hfl'] a[href*='/marketplace/item/']")
            )

            for item in items[:40]:  # Cap at 40 per category
                try:
                    # Find the anchor for URL
                    if item.tag_name == "a":
                        link_el = item
                    else:
                        link_el = item.find_element(By.CSS_SELECTOR, "a[href*='/marketplace/item/']")
                    href = link_el.get_attribute("href") or ""

                    # Title
                    spans = item.find_elements(By.CSS_SELECTOR, "span[dir='auto']")
                    title = ""
                    for s in spans:
                        text = s.text.strip()
                        if text and len(text) > 5 and not text.startswith("$"):
                            title = text
                            break
                    if not title:
                        continue

                    # Price
                    price_text = ""
                    for s in spans:
                        t = s.text.strip()
                        if "$" in t and len(t) < 15:
                            price_text = t
                            break
                    buy_price = _parse_price(price_text)
                    if buy_price is None or buy_price <= 0:
                        continue
                    if buy_price > config.MAX_BUY_PRICE:
                        continue

                    # Image
                    img_el = None
                    try:
                        img_el = item.find_element(By.CSS_SELECTOR, "img")
                    except NoSuchElementException:
                        pass
                    image_url = img_el.get_attribute("src") or "" if img_el else ""

                    deals.append(Deal(
                        title=title,
                        buy_price=buy_price,
                        source="facebook",
                        url=href,
                        category=category_name,
                        location="Austin, TX",
                        image_url=image_url,
                    ))
                except Exception as e:
                    logger.debug("FB item parse error: %s", e)
                    continue

        except Exception as e:
            logger.error("FB Marketplace scrape error for %s: %s", category_slug, e)

        logger.info("Facebook Marketplace /%s → %d deals", category_slug, len(deals))
        return deals

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        self._logged_in = False


def scrape(headless: bool = True) -> list[Deal]:
    """
    Main entry point: log in and scrape all configured FB Marketplace categories.
    Pass headless=False when running interactively for first-time login.
    """
    scraper = FacebookMarketplaceScraper()

    if not scraper.login(headless=headless):
        logger.error("Facebook login failed — skipping FB Marketplace scrape")
        return []

    all_deals: list[Deal] = []
    seen_urls: set[str] = set()

    try:
        for category_name in config.FB_CATEGORIES:
            slug = FB_CATEGORY_SLUGS.get(category_name, category_name)
            for deal in scraper.scrape_category(slug, category_name):
                if deal.url and deal.url not in seen_urls:
                    seen_urls.add(deal.url)
                    all_deals.append(deal)
            time.sleep(random.uniform(3, 6))
    finally:
        scraper.quit()

    logger.info("Facebook Marketplace total: %d unique deals", len(all_deals))
    return all_deals
