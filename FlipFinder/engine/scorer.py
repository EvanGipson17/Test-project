"""
Flip Score Engine.

Calculates estimated profit, ROI, and a composite flip_score for each deal.
All deals must have ebay_avg_sold populated before calling this module.
"""
import logging
from scrapers.base import Deal
import config

logger = logging.getLogger(__name__)


def calculate_flip_score(deal: Deal) -> Deal:
    """
    Populate estimated_profit, roi_percent, and flip_score on a Deal object.
    Mutates in place and also returns the deal.

    Formula:
        ebay_fees   = ebay_avg_sold * 0.13
        net_sell    = ebay_avg_sold - shipping_est - ebay_fees
        profit      = net_sell - buy_price
        roi         = (profit / buy_price) * 100
        flip_score  = (roi * 0.5) + (profit * 0.3) + (velocity_score * 0.2)
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

    flip_score = (
        (roi * config.ROI_WEIGHT)
        + (profit * config.PROFIT_WEIGHT)
        + (deal.velocity_score * config.VELOCITY_WEIGHT)
    )

    deal.estimated_profit = round(profit, 2)
    deal.roi_percent = round(roi, 2)
    deal.flip_score = round(flip_score, 2)

    logger.debug(
        "Scored: %r | buy=$%.0f sell=$%.0f profit=$%.0f ROI=%.0f%% score=%.1f",
        deal.title[:40], deal.buy_price, deal.ebay_avg_sold,
        profit, roi, flip_score,
    )
    return deal


def filter_profitable(deals: list[Deal]) -> list[Deal]:
    """Return only deals that meet minimum profit and ROI thresholds."""
    qualified = [d for d in deals if d.is_profitable()]
    logger.info(
        "Profit filter: %d/%d deals passed (profit≥$%.0f, ROI≥%.0f%%)",
        len(qualified), len(deals),
        config.MIN_PROFIT_THRESHOLD, config.MIN_ROI_THRESHOLD,
    )
    return qualified


def rank_deals(deals: list[Deal]) -> list[Deal]:
    """Sort deals by flip_score descending."""
    return sorted(deals, key=lambda d: d.flip_score, reverse=True)
