"""
SQLite database handler for FlipFinder.
Stores deals, tracks reporting history, and logs scrape runs.
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    standardized_name   TEXT,
    buy_price           REAL NOT NULL,
    source              TEXT NOT NULL,
    url                 TEXT,
    category            TEXT,
    location            TEXT DEFAULT '',
    image_url           TEXT DEFAULT '',
    brand               TEXT DEFAULT '',
    model_name          TEXT DEFAULT '',
    condition_estimate  TEXT DEFAULT 'unknown',
    ebay_avg_sold       REAL DEFAULT 0.0,
    estimated_profit    REAL DEFAULT 0.0,
    roi_percent         REAL DEFAULT 0.0,
    velocity_score      REAL DEFAULT 0.0,
    flip_score          REAL DEFAULT 0.0,
    liquidity_score     REAL DEFAULT 0.0,
    risk_score          REAL DEFAULT 5.0,
    is_legitimate       INTEGER DEFAULT 1,
    flip_tip            TEXT DEFAULT '',
    found_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reported_at         TIMESTAMP,
    url_hash            TEXT,
    UNIQUE(url_hash)
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,
    run_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    items_found      INTEGER DEFAULT 0,
    items_qualified  INTEGER DEFAULT 0,
    status           TEXT NOT NULL,
    error_message    TEXT,
    duration_seconds REAL
);

CREATE INDEX IF NOT EXISTS idx_deals_flip_score ON deals(flip_score DESC);
CREATE INDEX IF NOT EXISTS idx_deals_found_at   ON deals(found_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_reported   ON deals(reported_at);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialised at %s", config.DB_PATH)


def _url_hash(url: str) -> str:
    import hashlib
    return hashlib.md5(url.encode()).hexdigest() if url else ""


def upsert_deal(deal) -> Optional[int]:
    """
    Insert a new deal or skip if the URL hash already exists.
    Returns the row id on insert, None on duplicate.
    """
    from scrapers.base import Deal
    h = _url_hash(deal.url)
    sql = """
        INSERT OR IGNORE INTO deals
            (title, standardized_name, buy_price, source, url, category, location,
             image_url, brand, model_name, condition_estimate, ebay_avg_sold,
             estimated_profit, roi_percent, velocity_score, flip_score,
             liquidity_score, risk_score, is_legitimate, flip_tip, found_at, url_hash)
        VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    params = (
        deal.title, deal.standardized_name, deal.buy_price, deal.source,
        deal.url, deal.category, deal.location, deal.image_url,
        deal.brand, deal.model_name, deal.condition_estimate,
        deal.ebay_avg_sold, deal.estimated_profit, deal.roi_percent,
        deal.velocity_score, deal.flip_score, deal.liquidity_score,
        deal.risk_score, int(deal.is_legitimate), deal.flip_tip,
        deal.found_at.isoformat(), h,
    )
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid if cur.rowcount else None


def get_unreported_deals(limit: int = 50):
    """Return qualified deals not yet included in any report, ranked by flip_score."""
    sql = """
        SELECT * FROM deals
        WHERE reported_at IS NULL
          AND estimated_profit >= ?
          AND roi_percent >= ?
        ORDER BY flip_score DESC
        LIMIT ?
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (config.MIN_PROFIT_THRESHOLD, config.MIN_ROI_THRESHOLD, limit)).fetchall()
    return [dict(r) for r in rows]


def mark_deals_reported(deal_ids: list) -> None:
    """Stamp reported_at on a list of deal IDs."""
    if not deal_ids:
        return
    placeholders = ",".join("?" * len(deal_ids))
    sql = f"UPDATE deals SET reported_at = ? WHERE id IN ({placeholders})"
    with get_conn() as conn:
        conn.execute(sql, [datetime.utcnow().isoformat()] + deal_ids)


def log_scrape(source: str, items_found: int, items_qualified: int,
               status: str, error_message: str = "", duration: float = 0.0) -> None:
    sql = """
        INSERT INTO scrape_logs (source, items_found, items_qualified, status, error_message, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    with get_conn() as conn:
        conn.execute(sql, (source, items_found, items_qualified, status, error_message, duration))


def get_recent_scrape_stats(hours: int = 24) -> dict:
    """Aggregate stats from the last N hours for the report header."""
    sql = """
        SELECT source, SUM(items_found) as total_found, SUM(items_qualified) as total_qualified
        FROM scrape_logs
        WHERE run_at >= datetime('now', ?)
        GROUP BY source
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (f"-{hours} hours",)).fetchall()
    return {r["source"]: dict(r) for r in rows}
