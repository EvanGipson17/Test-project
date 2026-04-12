"""
Flip Score Engine.

Calculates estimated profit, ROI, category-boosted flip_score,
and per-platform sell guide for each deal.
"""
import logging
from scrapers.base import Deal
import config

logger = logging.getLogger(__name__)

# ── Platform rankings by category ────────────────────────────────────────────
# (platform, fee_multiplier, base_days_label_by_velocity_bucket)
# velocity buckets: [very_low(1-2), low(3-4), med(5-7), high(8-10)]
_PLATFORM_DATA = {
    "eBay": {
        "fee": 0.13,
        "days": ["1-3 months", "3-4 weeks", "1-2 weeks", "1-3 days"],
    },
    "Facebook Marketplace": {
        "fee": 0.0,
        "days": ["1-2 months", "2-3 weeks", "5-10 days", "1-2 days"],
    },
    "Mercari": {
        "fee": 0.10,
        "days": ["2-3 months", "3-4 weeks", "1-2 weeks", "3-5 days"],
    },
    "OfferUp": {
        "fee": 0.099,
        "days": ["1-2 months", "2-3 weeks", "1-2 weeks", "2-4 days"],
    },
    "StockX": {
        "fee": 0.12,
        "days": ["1-2 weeks", "3-7 days", "1-3 days", "same day"],
    },
    "Craigslist": {
        "fee": 0.0,
        "days": ["2-3 months", "3-4 weeks", "1-2 weeks", "2-5 days"],
    },
}

# Top 3 platforms per category, ordered by expected sell speed
_CATEGORY_PLATFORMS = {
    "electronics":  ["eBay", "Mercari", "Facebook Marketplace"],
    "gaming":       ["eBay", "Facebook Marketplace", "Mercari"],
    "sneakers":     ["StockX", "eBay", "Mercari"],
    "streetwear":   ["StockX", "eBay", "Mercari"],
    "tools":        ["Facebook Marketplace", "Craigslist", "eBay"],
    "appliances":   ["Facebook Marketplace", "OfferUp", "Craigslist"],
    "furniture":    ["Facebook Marketplace", "Craigslist", "OfferUp"],
    "other":        ["eBay", "Facebook Marketplace", "Mercari"],
}


def _velocity_bucket(score: float) -> int:
    """Map velocity_score (1-10) to 0-3 bucket index for days_to_sell lookup."""
    if score <= 2:
        return 0
    elif score <= 4:
        return 1
    elif score <= 7:
        return 2
    else:
        return 3


def compute_sell_guide(deal: Deal) -> list[dict]:
    """
    Build a sell guide: top 3 platforms for this deal with recommended list price
    and estimated days to sell.
    """
    platforms = _CATEGORY_PLATFORMS.get(deal.category, _CATEGORY_PLATFORMS["other"])
    bucket = _velocity_bucket(deal.velocity_score)
    guide = []
    ref_price = deal.ebay_avg_sold if deal.ebay_avg_sold > 0 else deal.buy_price * 1.5

    for platform in platforms:
        pdata = _PLATFORM_DATA.get(platform, {"fee": 0.0, "days": ["unknown"] * 4})
        # List price: aim to net the eBay average after this platform's fees
        list_price = round(ref_price / (1 - pdata["fee"]) if pdata["fee"] < 1 else ref_price, 0)
        days_to_sell = pdata["days"][bucket]
        guide.append({
            "platform": platform,
            "list_price": list_price,
            "days_to_sell": days_to_sell,
        })

    return guide


def calculate_flip_score(deal: Deal) -> Deal:
    """
    Populate estimated_profit, roi_percent, flip_score, and sell_guide on a Deal.
    Mutates in place and also returns the deal.

    Formula:
        ebay_fees    = ebay_avg_sold * 0.13
        net_sell     = ebay_avg_sold - shipping_est - ebay_fees
        profit       = net_sell - buy_price
        roi          = (profit / buy_price) * 100
        cat_priority = CATEGORY_PRIORITY[category]  (1-10)
        flip_score   = (roi*0.45) + (profit*0.28) + (velocity*0.17) + (cat_priority*0.10)
    """
    if deal.ebay_avg_sold <= 0 or deal.buy_price <= 0:
        deal.estimated_profit = 0.0
        deal.roi_percent = 0.0
        deal.flip_score = 0.0
        return deal

    ebay_fees = deal.ebay_avg_sold * config.EBAY_FEES_PERCENT
    net_sell = deal.ebay_avg_sold - config.SHIPPING_ESTIMATE - ebay_fees
    profit = net_sell - deal.buy_price
    roi = (profit / deal.buy_price) * 100 if deal.buy_price > 0 else 0.0
    cat_priority = config.CATEGORY_PRIORITY.get(deal.category, 1)

    flip_score = (
        (roi * config.ROI_WEIGHT)
        + (profit * config.PROFIT_WEIGHT)
        + (deal.velocity_score * config.VELOCITY_WEIGHT)
        + (cat_priority * config.CATEGORY_WEIGHT)
    )

    deal.estimated_profit = round(profit, 2)
    deal.roi_percent = round(roi, 2)
    deal.flip_score = round(flip_score, 2)
    deal.sell_guide = compute_sell_guide(deal)

    logger.debug(
        "Scored: %r | buy=$%.0f sell=$%.0f profit=$%.0f ROI=%.0f%% cat=%s score=%.1f",
        deal.title[:40], deal.buy_price, deal.ebay_avg_sold,
        profit, roi, deal.category, flip_score,
    )
    return deal


def filter_profitable(deals: list[Deal]) -> list[Deal]:
    """Return only deals that meet minimum profit and ROI thresholds."""
    qualified = [d for d in deals if d.is_profitable()]
    logger.info(
        "Profit filter: %d/%d deals passed (profit>=$%.0f, ROI>=%.0f%%)",
        len(qualified), len(deals),
        config.MIN_PROFIT_THRESHOLD, config.MIN_ROI_THRESHOLD,
    )
    return qualified


def rank_deals(deals: list[Deal]) -> list[Deal]:
    """Sort deals by flip_score descending."""
    return sorted(deals, key=lambda d: d.flip_score, reverse=True)
