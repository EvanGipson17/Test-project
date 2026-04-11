"""
FlipFinder — main entry point.

Orchestrates all scrapers, the scoring/analysis pipeline, and the email report.
Runs as a daemon with APScheduler, or once in --test mode.

Usage:
    python main.py                   # start the scheduler (daemon)
    python main.py --test            # run full pipeline once, print results, no email
    python main.py --test --scraper slickdeals   # test one scraper only
    python main.py --quick           # run quick scan (FB + CL) once
    python main.py --report          # build and send report from existing DB deals
"""
import argparse
import logging
import sys
import time
from datetime import datetime

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flipfinder.log", mode="a"),
    ],
)
logger = logging.getLogger("flipfinder")

# ── Local imports (after logging is configured) ────────────────────────────────
import config
from database import db
from scrapers.base import Deal
from scrapers import slickdeals, ebay, facebook, craigslist, amazon
from engine import scorer, analyzer
from notifier import emailer


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _enrich_deal(deal: Deal) -> Deal:
    """
    Run a single deal through the full enrichment pipeline:
    1. Normalize title via Claude
    2. Fetch eBay sold price data
    3. Calculate flip score
    4. Quality analysis via Claude
    """
    # 1. Normalize
    norm = analyzer.normalize_item(deal.title)
    deal.standardized_name = norm.get("standardized_name", deal.title)
    deal.category = norm.get("category", deal.category)
    deal.brand = norm.get("brand", "")
    deal.model_name = norm.get("model_name", "")
    deal.condition_estimate = norm.get("condition_estimate", "unknown")
    deal.ebay_search_query = norm.get("ebay_search_query", deal.title)

    # 2. eBay price lookup
    ebay_data = ebay.get_sold_data(deal.ebay_search_query)
    deal.ebay_avg_sold = ebay_data.get("avg_sold_price", 0.0)
    deal.velocity_score = float(ebay_data.get("velocity_score", 0))

    # 3. Score
    scorer.calculate_flip_score(deal)

    # 4. Quality analysis (only for deals that pass the threshold)
    if deal.is_profitable():
        quality = analyzer.analyze_deal_quality(deal)
        deal.liquidity_score = float(quality.get("liquidity_score", 5))
        deal.risk_score = float(quality.get("risk_score", 5))
        deal.is_legitimate = bool(quality.get("is_legitimate", True))
        deal.flip_tip = quality.get("flip_tip", "")

    return deal


def run_scrapers(sources: list[str]) -> list[Deal]:
    """Run requested scrapers, return raw deal list."""
    raw_deals: list[Deal] = []
    source_map = {
        "slickdeals": slickdeals.scrape,
        "craigslist": craigslist.scrape,
        "amazon": amazon.scrape,
    }

    for source in sources:
        if source == "facebook":
            _run_scraper_safe("facebook", lambda: facebook.scrape(), raw_deals)
        elif source in source_map:
            _run_scraper_safe(source, source_map[source], raw_deals)
        else:
            logger.warning("Unknown scraper: %s", source)

    return raw_deals


def _run_scraper_safe(name: str, fn, accumulator: list) -> None:
    """Run a scraper function, log to DB, and accumulate results. Never crashes the run."""
    start = time.time()
    try:
        items = fn()
        duration = time.time() - start
        db.log_scrape(name, len(items), 0, "success", duration=duration)
        accumulator.extend(items)
        logger.info("Scraper [%s] → %d raw deals (%.1fs)", name, len(items), duration)
    except Exception as e:
        duration = time.time() - start
        db.log_scrape(name, 0, 0, "error", str(e), duration=duration)
        logger.error("Scraper [%s] FAILED: %s", name, e)


def run_full_pipeline(sources: list[str] = None, test_mode: bool = False) -> list[Deal]:
    """
    Full pipeline:
      scrape → enrich (normalize + eBay price + score) → filter → persist
    Returns qualified, ranked deals.
    """
    if sources is None:
        sources = ["slickdeals", "ebay_check", "facebook", "craigslist", "amazon"]
    # Remove 'ebay_check' from scraper list (ebay is used internally in _enrich_deal)
    scraper_sources = [s for s in sources if s != "ebay_check"]

    logger.info("=== Starting full pipeline: %s ===", ", ".join(scraper_sources))

    raw_deals = run_scrapers(scraper_sources)
    logger.info("Total raw deals collected: %d", len(raw_deals))

    qualified: list[Deal] = []
    for i, deal in enumerate(raw_deals):
        try:
            deal = _enrich_deal(deal)
            if deal.is_profitable():
                row_id = db.upsert_deal(deal)
                if row_id:
                    qualified.append(deal)
                    logger.info("  [NEW] %r profit=$%.0f ROI=%.0f%%",
                                deal.title[:45], deal.estimated_profit, deal.roi_percent)
                else:
                    logger.debug("  [DUP] %r", deal.title[:45])
        except Exception as e:
            logger.error("Pipeline error for deal %r: %s", getattr(deal, "title", "?"), e)

        # Progress every 10 items
        if (i + 1) % 10 == 0:
            logger.info("Progress: %d/%d enriched, %d qualified so far",
                        i + 1, len(raw_deals), len(qualified))

    ranked = scorer.rank_deals(qualified)
    logger.info("=== Pipeline complete: %d qualified deals ===", len(ranked))
    return ranked


def build_report_and_send(deals: list[Deal] = None, test_mode: bool = False) -> None:
    """
    Build the email report and send it (or print in test_mode).
    If deals is None, pulls unreported deals from the DB.
    """
    if deals is None:
        db_rows = db.get_unreported_deals(limit=50)
        # Reconstruct minimal Deal objects from DB rows for the email
        deals = []
        for row in db_rows:
            d = Deal(
                title=row["title"],
                buy_price=row["buy_price"],
                source=row["source"],
                url=row["url"] or "",
                category=row["category"] or "other",
            )
            d.standardized_name = row.get("standardized_name") or row["title"]
            d.ebay_avg_sold = row.get("ebay_avg_sold", 0)
            d.estimated_profit = row.get("estimated_profit", 0)
            d.roi_percent = row.get("roi_percent", 0)
            d.velocity_score = row.get("velocity_score", 0)
            d.flip_score = row.get("flip_score", 0)
            d.liquidity_score = row.get("liquidity_score", 5)
            d.risk_score = row.get("risk_score", 5)
            d.flip_tip = row.get("flip_tip") or ""
            d.image_url = row.get("image_url") or ""
            d.location = row.get("location") or ""
            deals.append(d)

    if not deals:
        logger.info("No unreported deals — skipping report")
        return

    stats = {
        "total_scanned": sum(
            v.get("total_found", 0)
            for v in db.get_recent_scrape_stats(hours=24).values()
        ),
        "deals_passing": len(deals),
        "total_profit": sum(d.estimated_profit for d in deals),
        "sources_active": len({d.source for d in deals}),
    }

    intro = analyzer.generate_report_intro(deals[:5], stats)

    if test_mode:
        print("\n" + "=" * 60)
        print(f"REPORT STATS: {stats}")
        print(f"\nINTRO:\n{intro}\n")
        print(f"TOP DEALS ({len(deals)} total):")
        for i, d in enumerate(deals[:10], 1):
            print(f"  {i}. {d.standardized_name or d.title[:50]}")
            print(f"     Buy ${d.buy_price:.0f} → Sell ${d.ebay_avg_sold:.0f} "
                  f"| Profit ${d.estimated_profit:.0f} | ROI {d.roi_percent:.0f}%")
            if d.flip_tip:
                print(f"     Tip: {d.flip_tip}")
        print("=" * 60)
    else:
        success = emailer.send_report(deals, stats, intro=intro)
        if success:
            deal_ids = [getattr(d, "db_id", None) for d in deals if hasattr(d, "db_id")]
            # Mark reported via DB IDs from unreported_deals query
            db_rows = db.get_unreported_deals(limit=1)  # quick check
            db.mark_deals_reported([
                row["id"] for row in db.get_unreported_deals(limit=100)
                if row["estimated_profit"] > 0
            ])


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

def job_full_scrape():
    logger.info("=== SCHEDULED: Full nightly scrape ===")
    run_full_pipeline()


def job_send_report():
    logger.info("=== SCHEDULED: Sending nightly report ===")
    build_report_and_send()


def job_quick_scan():
    logger.info("=== SCHEDULED: Quick local scan (FB + CL) ===")
    run_full_pipeline(sources=["facebook", "craigslist"])


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FlipFinder — automated deal-finding and resell analysis bot"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run full pipeline once, print results, do NOT send email")
    parser.add_argument("--quick", action="store_true",
                        help="Run quick scan (Facebook + Craigslist) once")
    parser.add_argument("--report", action="store_true",
                        help="Send report from existing DB deals (no scraping)")
    parser.add_argument("--scraper", choices=["slickdeals", "facebook", "craigslist", "amazon"],
                        help="Test a single scraper and print results")
    args = parser.parse_args()

    db.init_db()

    # ── Single-run modes ──────────────────────────────────────────────────────
    if args.scraper:
        logger.info("Testing scraper: %s", args.scraper)
        scraper_map = {
            "slickdeals": slickdeals.scrape,
            "facebook": lambda: facebook.scrape(headless=False),
            "craigslist": craigslist.scrape,
            "amazon": amazon.scrape,
        }
        deals = scraper_map[args.scraper]()
        print(f"\n{args.scraper}: {len(deals)} deals found")
        for d in deals[:20]:
            print(f"  ${d.buy_price:>6.0f}  {d.title[:60]}")
        return

    if args.test:
        logger.info("Running in TEST MODE (no email will be sent)")
        qualified = run_full_pipeline(test_mode=True)
        build_report_and_send(deals=qualified, test_mode=True)
        return

    if args.quick:
        qualified = run_full_pipeline(sources=["facebook", "craigslist"])
        if qualified:
            build_report_and_send(deals=qualified, test_mode=False)
        return

    if args.report:
        build_report_and_send(test_mode=False)
        return

    # ── Daemon mode: start APScheduler ────────────────────────────────────────
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone=config.TIMEZONE)

    # Full scrape at 8 PM CT every night
    scheduler.add_job(
        job_full_scrape,
        CronTrigger(hour=config.FULL_SCRAPE_HOUR, minute=0, timezone=config.TIMEZONE),
        id="full_scrape",
        name="Nightly full scrape",
    )

    # Send report at 9 PM CT
    scheduler.add_job(
        job_send_report,
        CronTrigger(hour=config.REPORT_HOUR, minute=0, timezone=config.TIMEZONE),
        id="send_report",
        name="Nightly report email",
    )

    # Quick scan at 8 AM and 2 PM CT (local deals disappear fast)
    for hour_str in config.QUICK_SCAN_HOURS.split(","):
        h = int(hour_str.strip())
        scheduler.add_job(
            job_quick_scan,
            CronTrigger(hour=h, minute=0, timezone=config.TIMEZONE),
            id=f"quick_scan_{h}",
            name=f"Quick scan {h}:00 CT",
        )

    logger.info("FlipFinder scheduler started.")
    logger.info("  Full scrape:  %d:00 CT daily", config.FULL_SCRAPE_HOUR)
    logger.info("  Report email: %d:00 CT daily", config.REPORT_HOUR)
    logger.info("  Quick scans:  %s CT", config.QUICK_SCAN_HOURS)
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
