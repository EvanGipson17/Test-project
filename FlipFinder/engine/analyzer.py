"""
Claude API integration for FlipFinder.

Three functions:
  1. normalize_item()      - standardize raw listing titles + generate eBay search query
  2. analyze_deal_quality()- rate liquidity/risk/legitimacy, generate flip_tip
  3. generate_report_intro()- write email summary intro paragraph

Uses claude-opus-4-6 with prompt caching on system prompts (called many times per run).
"""
import json
import logging
from typing import Optional

import anthropic

import config
from scrapers.base import Deal

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# ── Cached system prompts ───────────────────────────────────────────────────────
# These are marked ephemeral so they're cached across the many calls per scrape run.

_NORMALIZE_SYSTEM = (
    "You are a product identification expert for a reselling business. "
    "Analyze raw listing titles from online marketplaces and extract structured information.\n\n"
    "Respond ONLY with a valid JSON object (no markdown, no extra text) containing exactly these keys:\n"
    "  standardized_name   : clean, normalized product name (e.g. 'Sony WH-1000XM4 Wireless Headphones')\n"
    "  category            : one of: electronics | gaming | sneakers | tools | appliances | furniture | other\n"
    "  brand               : brand name, or 'Unknown'\n"
    "  model_name          : model number/name, or 'Unknown'\n"
    "  condition_estimate  : one of: new | like_new | good | fair | poor | unknown\n"
    "  ebay_search_query   : optimised eBay sold-listings search query for accurate pricing "
    "(specific enough to match the item, exclude condition words)\n"
)

_QUALITY_SYSTEM = (
    "You are an expert reseller with 10+ years flipping items on eBay, Facebook Marketplace, "
    "and Craigslist. Evaluate deals for resell potential.\n\n"
    "Respond ONLY with a valid JSON object (no markdown, no extra text) containing exactly these keys:\n"
    "  liquidity_score  : integer 1-10 — how quickly/easily can this sell on eBay? (10=fastest)\n"
    "  risk_score       : integer 1-10 — risk of fakes, damage, scam, or saturation? (1=safest)\n"
    "  is_legitimate    : boolean — does the price seem real, not a scam or error?\n"
    "  flip_tip         : one actionable sentence of advice specific to THIS item\n"
)


def normalize_item(raw_title: str) -> dict:
    """
    Use Claude to parse a raw listing title into structured fields.
    Returns a dict with standardized_name, category, brand, model_name,
    condition_estimate, and ebay_search_query.
    Falls back to safe defaults on any error.
    """
    default = {
        "standardized_name": raw_title,
        "category": "other",
        "brand": "Unknown",
        "model_name": "Unknown",
        "condition_estimate": "unknown",
        "ebay_search_query": raw_title[:60].strip(),
    }

    if not config.ANTHROPIC_API_KEY:
        logger.debug("No ANTHROPIC_API_KEY - skipping item normalization")
        return default

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=[{
                "type": "text",
                "text": _NORMALIZE_SYSTEM,
                "cache_control": {"type": "ephemeral"},  # cached across all calls
            }],
            messages=[{
                "role": "user",
                "content": f"Listing title: {raw_title}",
            }],
        )
        text = resp.content[0].text.strip()
        result = json.loads(text)
        # Merge with defaults for any missing keys
        return {**default, **result}
    except json.JSONDecodeError as e:
        logger.warning("normalize_item JSON parse error for %r: %s", raw_title, e)
        return default
    except anthropic.APIError as e:
        logger.error("Claude API error in normalize_item: %s", e)
        return default
    except Exception as e:
        logger.error("normalize_item unexpected error: %s", str(e).encode('ascii', errors='replace').decode('ascii'))
        return default


def analyze_deal_quality(deal: Deal) -> dict:
    """
    Use Claude to rate deal quality and produce a flip_tip.
    Mutates the passed deal's quality fields and also returns the dict.
    """
    default = {
        "liquidity_score": 5,
        "risk_score": 5,
        "is_legitimate": True,
        "flip_tip": "Verify item condition and check recent eBay sold prices before buying.",
    }

    if not config.ANTHROPIC_API_KEY:
        return default

    deal_summary = (
        f"Item: {deal.standardized_name or deal.title}\n"
        f"Category: {deal.category}\n"
        f"Buy price: ${deal.buy_price:.2f}\n"
        f"Source: {deal.source}\n"
        f"Location: {deal.location or 'N/A'}\n"
        f"Condition: {deal.condition_estimate}\n"
        f"eBay avg sold: ${deal.ebay_avg_sold:.2f}\n"
        f"Estimated profit: ${deal.estimated_profit:.2f}\n"
        f"ROI: {deal.roi_percent:.1f}%\n"
        f"eBay velocity score: {deal.velocity_score}/10\n"
    )

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=[{
                "type": "text",
                "text": _QUALITY_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"Analyze this deal:\n{deal_summary}",
            }],
        )
        text = resp.content[0].text.strip()
        result = json.loads(text)
        return {**default, **result}
    except json.JSONDecodeError as e:
        logger.warning("analyze_deal_quality JSON parse error: %s", e)
        return default
    except anthropic.APIError as e:
        logger.error("Claude API error in analyze_deal_quality: %s", e)
        return default
    except Exception as e:
        logger.error("analyze_deal_quality unexpected error: %s", e)
        return default


def generate_report_intro(deals: list[Deal], stats: dict) -> str:
    """
    Use Claude to write a punchy 2-3 sentence intro for the nightly email.
    stats dict: {total_scanned, deals_passing, total_profit}
    Falls back to a plain text version if the API is unavailable.
    """
    fallback = (
        f"Tonight's scan found <strong>{stats.get('deals_passing', 0)} profitable flip "
        f"opportunities</strong> out of {stats.get('total_scanned', 0)} deals scanned. "
        f"Total potential profit if all deals purchased: "
        f"<strong>${stats.get('total_profit', 0):.0f}</strong>."
    )

    if not config.ANTHROPIC_API_KEY or not deals:
        return fallback

    top_lines = "\n".join(
        f"  - {d.standardized_name or d.title[:50]}: "
        f"buy ${d.buy_price:.0f} -> sell ~${d.ebay_avg_sold:.0f} "
        f"(profit ${d.estimated_profit:.0f}, ROI {d.roi_percent:.0f}%)"
        for d in deals[:5]
    )

    prompt = (
        f"Write a 2-3 sentence intro for a nightly deal-flipping email report.\n"
        f"Stats: {stats.get('total_scanned', 0)} deals scanned, "
        f"{stats.get('deals_passing', 0)} profitable opportunities found, "
        f"${stats.get('total_profit', 0):.0f} total potential profit.\n\n"
        f"Top deals:\n{top_lines}\n\n"
        f"Be direct, energetic, and specific. No fluff or filler sentences. "
        f"Use HTML <strong> tags for numbers. Do NOT use emojis."
    )

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.error("generate_report_intro error: %s", e)
        return fallback
