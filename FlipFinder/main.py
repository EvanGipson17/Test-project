# ── Windows encoding fix (MUST be first — before every other import) ───────────
import os
import sys
import io
# Force Python's default text encoding to UTF-8 on Windows.
# This affects stdin/stdout/stderr AND internal codec lookups used by
# httpx / http.client when encoding HTTP headers.
os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass
try:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

"""
FlipFinder - main entry point.

Orchestrates all scrapers, the scoring/analysis pipeline, and the email report.
Runs as a daemon with APScheduler, or once in single-run modes.

Usage:
    python main.py                   # start the scheduler (daemon)
    python main.py --test            # run full pipeline once, print table, no email
    python main.py --test --scraper slickdeals   # test one scraper only
    python main.py --quick           # run quick scan (FB + CL + OfferUp) once
    python main.py --report          # build and send report from existing DB deals
    python main.py --history         # show all past deals from the database
"""
import argparse
import logging
import time
from datetime import datetime


class AsciiSafeStreamHandler(logging.StreamHandler):
    """StreamHandler that strips every non-ASCII character before writing.

    This is the definitive fix for UnicodeEncodeError on Windows consoles.
    No matter what encoding sys.stdout reports, and no matter where the
    non-ASCII character came from (scraped title, Claude response, exception
    message, repr() of a deal object), it will be replaced with '?' before
    it ever reaches the console write call.
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            self.stream.write(safe + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        AsciiSafeStreamHandler(sys.stdout),
        logging.FileHandler("flipfinder.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("flipfinder")

# ── Local imports (after logging is configured) ────────────────────────────────
import config
from database import db
from scrapers.base import Deal
from scrapers import slickdeals, ebay, facebook, craigslist, amazon, offerup
from engine import scorer, analyzer
from notifier import emailer


def _s(x) -> str:
    """Shorthand for config.safe_str — makes all log args Windows-safe."""
    return config.safe_str(x)


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _enrich_deal(deal: Deal) -> Deal:
    """
    Run a single deal through the full enrichment pipeline:
    1. Normalize title via Claude
    2. Fetch eBay sold price data (last ~30 days)
    3. Calculate flip score + sell guide
    4. Quality analysis via Claude (profitable deals only)
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
    deal.price_confidence = float(ebay_data.get("price_confidence", 0))

    # 3. Score + sell guide
    scorer.calculate_flip_score(deal)

    # 4. Quality analysis (only for deals that pass the threshold)
    if deal.is_profitable():
        quality = analyzer.analyze_deal_quality(deal)
        deal.liquidity_score = float(quality.get("liquidity_score", 5))
        deal.risk_score = float(quality.get("risk_score", 5))
        deal.is_legitimate = bool(quality.get("is_legitimate", True))
        deal.flip_tip = quality.get("flip_tip", "")
        deal.listing_title = quality.get("listing_title", deal.standardized_name or deal.title)

    return deal


def run_scrapers(sources: list[str]) -> list[Deal]:
    """Run requested scrapers, return raw deal list."""
    raw_deals: list[Deal] = []
    source_map = {
        "slickdeals": slickdeals.scrape,
        "craigslist": craigslist.scrape,
        "amazon": amazon.scrape,
        "offerup": offerup.scrape,
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
        logger.info("Scraper [%s] -> %d raw deals (%.1fs)", name, len(items), duration)
    except Exception as e:
        duration = time.time() - start
        db.log_scrape(name, 0, 0, "error", _s(e), duration=duration)
        logger.error("Scraper [%s] FAILED: %s", name, _s(e))


def run_full_pipeline(sources: list[str] = None, test_mode: bool = False) -> list[Deal]:
    """
    Full pipeline: scrape -> enrich (normalize + eBay + score) -> filter -> persist
    Returns qualified, ranked deals.
    """
    if sources is None:
        sources = ["slickdeals", "facebook", "craigslist", "amazon", "offerup"]
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
                    logger.info(
                        "  [NEW] %s | profit=$%.0f ROI=%.0f%% score=%.1f",
                        _s(deal.title[:45]), deal.estimated_profit,
                        deal.roi_percent, deal.flip_score,
                    )
                else:
                    logger.debug("  [DUP] %s", _s(deal.title[:45]))
        except Exception as e:
            logger.error("Pipeline error for deal %r: %s", _s(getattr(deal, "title", "?")), _s(e))

        if (i + 1) % 10 == 0:
            logger.info("Progress: %d/%d enriched, %d qualified so far",
                        i + 1, len(raw_deals), len(qualified))

    ranked = scorer.rank_deals(qualified)
    logger.info("=== Pipeline complete: %d qualified deals ===", len(ranked))
    return ranked


def _rebuild_deal_from_row(row: dict) -> Deal:
    """Reconstruct a Deal object from a DB row dict."""
    d = Deal(
        title=row["title"],
        buy_price=row["buy_price"],
        source=row["source"],
        url=row["url"] or "",
        category=row["category"] or "other",
    )
    d.standardized_name = row.get("standardized_name") or row["title"]
    d.ebay_avg_sold = row.get("ebay_avg_sold") or 0
    d.estimated_profit = row.get("estimated_profit") or 0
    d.roi_percent = row.get("roi_percent") or 0
    d.velocity_score = row.get("velocity_score") or 0
    d.price_confidence = row.get("price_confidence") or 0
    d.flip_score = row.get("flip_score") or 0
    d.liquidity_score = row.get("liquidity_score") or 5
    d.risk_score = row.get("risk_score") or 5
    d.flip_tip = row.get("flip_tip") or ""
    d.listing_title = row.get("listing_title") or ""
    d.image_url = row.get("image_url") or ""
    d.location = row.get("location") or ""
    d.is_local = bool(row.get("is_local", 0))
    d.report_count = row.get("report_count") or 0
    # Rebuild sell guide from scorer (uses category + price data)
    d.sell_guide = scorer.compute_sell_guide(d)
    return d


def build_report_and_send(deals: list[Deal] = None, test_mode: bool = False) -> None:
    """
    Build the email report and send it (or print in test_mode).
    If deals is None, pulls unreported deals + still-available from the DB.
    """
    if deals is None:
        unreported = db.get_unreported_deals(limit=50)
        still_avail = db.get_still_available_deals(limit=15)
        deals = [_rebuild_deal_from_row(r) for r in unreported]
        # Append still-available deals (avoid duplicates by URL)
        seen_urls = {d.url for d in deals}
        for row in still_avail:
            if row["url"] not in seen_urls:
                deals.append(_rebuild_deal_from_row(row))
                seen_urls.add(row["url"])

    if not deals:
        logger.info("No deals to report - skipping report")
        return

    deals = scorer.rank_deals(deals)

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
        _print_test_table(deals, stats, intro)
    else:
        success = emailer.send_report(deals, stats, intro=intro)
        if success:
            # Mark newly-reported deals (those with report_count == 0)
            new_deal_ids = []
            all_db_rows = db.get_unreported_deals(limit=100)
            reported_urls = {d.url for d in deals}
            for row in all_db_rows:
                if row["url"] in reported_urls:
                    new_deal_ids.append(row["id"])
            db.mark_deals_reported(new_deal_ids)


def _print_test_table(deals: list[Deal], stats: dict, intro: str) -> None:
    """Print a formatted table of deals to stdout for test mode."""
    sep = "-" * 110
    print("\n" + "=" * 110)
    print(f"  FLIPFINDER TEST REPORT  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
          f"{stats.get('deals_passing', 0)} deals  |  "
          f"Est. ${stats.get('total_profit', 0):.0f} total profit")
    print("=" * 110)
    if intro:
        # Strip HTML tags for terminal display
        import re
        plain = re.sub(r"<[^>]+>", "", intro)
        print(f"\n  {plain.strip()}\n")
    print(sep)
    header = (
        f"  {'#':>2}  {'SOURCE':<12}  {'ITEM':<38}  "
        f"{'BUY':>6}  {'SELL':>6}  {'PROFIT':>7}  {'ROI':>5}  {'SCORE':>6}  CAT"
    )
    print(header)
    print(sep)
    for i, d in enumerate(deals[:30], 1):
        name = _s(d.standardized_name or d.title)[:38]
        local_flag = " *" if d.is_local else "  "
        repeat_flag = f" [Day {d.report_count + 1}]" if d.report_count > 0 else ""
        print(
            f"  {i:>2}  {d.source:<12}  {name:<38}  "
            f"${d.buy_price:>5.0f}  ${d.ebay_avg_sold:>5.0f}  "
            f"+${d.estimated_profit:>5.0f}  {d.roi_percent:>4.0f}%"
            f"  {d.flip_score:>6.1f}  {d.category}{local_flag}{repeat_flag}"
        )
        if d.flip_tip:
            print(f"       TIP: {_s(d.flip_tip)[:90]}")
        if d.listing_title:
            print(f"     TITLE: {_s(d.listing_title)[:90]}")
        if d.sell_guide:
            for idx, sg in enumerate(d.sell_guide, 1):
                print(f"      SELL: #{idx} {sg['platform']:<22} list at ${sg['list_price']:.0f}  (~{sg['days_to_sell']})")
    print(sep)
    print("  * = local deal (disappears fast!)")
    print("=" * 110 + "\n")


def _print_history_table() -> None:
    """Print all past deals from the database."""
    rows = db.get_all_deals_history(limit=200)
    if not rows:
        print("\nNo deals in database yet. Run the pipeline first.\n")
        return

    sep = "-" * 115
    print("\n" + "=" * 115)
    print(f"  FLIPFINDER DEAL HISTORY  |  {len(rows)} deals in database")
    print("=" * 115)
    print(f"  {'ID':>5}  {'DATE':<17}  {'SOURCE':<10}  {'TITLE':<40}  "
          f"{'BUY':>6}  {'PROFIT':>7}  {'ROI':>5}  {'RPTS':>4}  STATUS")
    print(sep)
    for r in rows:
        found = r["found_at"][:16] if r["found_at"] else "unknown"
        status = "Reported" if r["reported_at"] else "Not sent"
        rpts = r["report_count"] or 0
        title = _s(r["title"])[:40]
        print(
            f"  {r['id']:>5}  {found:<17}  {r['source']:<10}  {title:<40}  "
            f"${r['buy_price']:>5.0f}  +${r.get('estimated_profit', 0):>5.0f}"
            f"  {r.get('roi_percent', 0):>4.0f}%  {rpts:>4}  {status}"
        )
    print(sep)
    print(f"  Total: {len(rows)} deals\n")


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

def job_full_scrape_and_report():
    logger.info("=== SCHEDULED: Full scrape + report ===")
    deals = run_full_pipeline()
    build_report_and_send(deals=deals)


def job_quick_scan():
    logger.info("=== SCHEDULED: Quick local scan (FB + CL + OfferUp) ===")
    deals = run_full_pipeline(sources=["facebook", "craigslist", "offerup"])
    if deals:
        build_report_and_send(deals=deals)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FlipFinder - automated deal-finding and resell analysis bot"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run full pipeline once, print table, do NOT send email")
    parser.add_argument("--quick", action="store_true",
                        help="Run quick scan (Facebook + Craigslist + OfferUp) once")
    parser.add_argument("--report", action="store_true",
                        help="Send report from existing DB deals (no scraping)")
    parser.add_argument("--history", action="store_true",
                        help="Show all past deals from the database")
    parser.add_argument("--scraper",
                        choices=["slickdeals", "facebook", "craigslist", "amazon", "offerup"],
                        help="Test a single scraper and print results")
    args = parser.parse_args()

    db.init_db()

    # ── Single-run modes ─────────────────────────────────────────────────────
    if args.history:
        _print_history_table()
        return

    if args.scraper:
        logger.info("Testing scraper: %s", args.scraper)
        scraper_map = {
            "slickdeals": slickdeals.scrape,
            "facebook": lambda: facebook.scrape(headless=False),
            "craigslist": craigslist.scrape,
            "amazon": amazon.scrape,
            "offerup": offerup.scrape,
        }
        deals = scraper_map[args.scraper]()
        print(f"\n{args.scraper}: {len(deals)} deals found")
        for d in deals[:20]:
            print(f"  ${d.buy_price:>6.0f}  {_s(d.title[:60])}")
        return

    if args.test:
        logger.info("Running in TEST MODE (no email will be sent)")
        qualified = run_full_pipeline(test_mode=True)
        build_report_and_send(deals=qualified, test_mode=True)
        return

    if args.quick:
        qualified = run_full_pipeline(sources=["facebook", "craigslist", "offerup"])
        if qualified:
            build_report_and_send(deals=qualified, test_mode=False)
        return

    if args.report:
        build_report_and_send(test_mode=False)
        return

    # ── Daemon mode: start APScheduler ───────────────────────────────────────
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone=config.TIMEZONE)

    # Full scrape + report at 7:45 AM and 6:00 PM CT
    for (hour, minute) in config.FULL_SCRAPE_TIMES:
        scheduler.add_job(
            job_full_scrape_and_report,
            CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
            id=f"full_{hour:02d}{minute:02d}",
            name=f"Full scrape + report at {hour:02d}:{minute:02d} CT",
        )

    # Quick scan every 3 hours from 8 AM to 9 PM CT (8, 11, 14, 17, 20)
    quick_hours = list(range(
        config.QUICK_SCAN_START_HOUR,
        config.QUICK_SCAN_END_HOUR,
        config.QUICK_SCAN_INTERVAL_HOURS,
    ))
    for h in quick_hours:
        scheduler.add_job(
            job_quick_scan,
            CronTrigger(hour=h, minute=0, timezone=config.TIMEZONE),
            id=f"quick_{h:02d}",
            name=f"Quick scan {h:02d}:00 CT",
        )

    logger.info("FlipFinder scheduler started.")
    logger.info("  Full scrape + report: %s CT daily",
                ", ".join(f"{h:02d}:{m:02d}" for h, m in config.FULL_SCRAPE_TIMES))
    logger.info("  Quick scans: %s CT (every %dh)",
                ", ".join(f"{h:02d}:00" for h in quick_hours),
                config.QUICK_SCAN_INTERVAL_HOURS)
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
