"""
Base Deal dataclass returned by every scraper.
All scrapers must return a list[Deal].
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Deal:
    # Required fields every scraper must fill
    title: str
    buy_price: float
    source: str          # "slickdeals" | "facebook" | "craigslist" | "amazon"
    url: str
    category: str        # electronics | gaming | sneakers | tools | appliances | furniture | other

    # Optional fields set by scrapers
    location: str = ""
    image_url: str = ""
    condition: str = "unknown"

    # Filled in by analyzer.normalize_item()
    standardized_name: str = ""
    brand: str = ""
    model_name: str = ""
    condition_estimate: str = "unknown"
    ebay_search_query: str = ""

    # Filled in by ebay.get_sold_data()
    ebay_avg_sold: float = 0.0
    velocity_score: float = 0.0   # 1-10: how many units sold on eBay in last 7 days

    # Filled in by scorer.calculate_flip_score()
    estimated_profit: float = 0.0
    roi_percent: float = 0.0
    flip_score: float = 0.0

    # Filled in by analyzer.analyze_deal_quality()
    liquidity_score: float = 5.0
    risk_score: float = 5.0
    is_legitimate: bool = True
    flip_tip: str = ""

    found_at: datetime = field(default_factory=datetime.utcnow)

    def is_profitable(self) -> bool:
        from config import MIN_PROFIT_THRESHOLD, MIN_ROI_THRESHOLD
        return (
            self.estimated_profit >= MIN_PROFIT_THRESHOLD
            and self.roi_percent >= MIN_ROI_THRESHOLD
            and self.is_legitimate
        )

    def __repr__(self) -> str:
        return (
            f"Deal({self.source}: {self.title[:40]!r} "
            f"buy=${self.buy_price:.0f} profit=${self.estimated_profit:.0f} "
            f"ROI={self.roi_percent:.0f}%)"
        )
