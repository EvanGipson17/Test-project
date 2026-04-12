"""
HTML email builder and Gmail sender for the FlipFinder report.
Mobile-friendly, dark-themed, with sell guides and urgency flags.
"""
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from jinja2 import Environment, BaseLoader

import config
from scrapers.base import Deal

logger = logging.getLogger(__name__)

LOCAL_SOURCES = {"facebook", "craigslist", "offerup"}


def _time_of_day() -> str:
    h = datetime.now().hour
    if h < 12:
        return "MORNING"
    elif h < 17:
        return "AFTERNOON"
    else:
        return "EVENING"


def _velocity_label(score: float) -> str:
    if score >= 8:
        return "Sells in 1-3 days"
    elif score >= 6:
        return "Sells in 1-2 weeks"
    elif score >= 4:
        return "Sells in 2-4 weeks"
    elif score >= 2:
        return "May take 1-2 months"
    else:
        return "Slow mover"


# ── HTML Template ─────────────────────────────────────────────────────────────
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FlipFinder Report</title>
<style>
  /* ── Reset ── */
  * { box-sizing: border-box; }
  body { margin:0; padding:0; background:#f0f0f0;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; }
  a { color:#e94560; text-decoration:none; }
  a:hover { text-decoration:underline; }
  img { display:block; max-width:100%; }

  /* ── Wrapper ── */
  .wrapper { max-width:660px; margin:0 auto; background:#ffffff; }

  /* ── Header ── */
  .header { background:#1a1a2e; padding:24px 28px 20px; }
  .header h1 { color:#e94560; margin:0 0 4px; font-size:24px; letter-spacing:0.5px; }
  .header .subtitle { color:#a8a8b3; font-size:13px; margin:0; }

  /* ── Stats bar ── */
  .stats-bar { background:#16213e; padding:14px 28px; }
  .stats-inner { display:flex; flex-wrap:wrap; gap:16px; }
  .stat { min-width:100px; }
  .stat .num { color:#e94560; font-size:22px; font-weight:700; line-height:1.1; }
  .stat .lbl { color:#a8a8b3; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }

  /* ── Section titles ── */
  .section-title { background:#f0f0f0; padding:9px 28px;
                   font-size:11px; font-weight:700; text-transform:uppercase;
                   letter-spacing:2px; color:#555; border-left:4px solid #e94560; }

  /* ── Intro ── */
  .intro { padding:16px 28px; font-size:14px; line-height:1.65; color:#444;
           border-bottom:1px solid #eee; }

  /* ── BEST DEAL banner ── */
  .best-deal-wrap { background:#fff8f0; border:2px solid #f39c12; margin:0; }
  .best-deal-label { background:#f39c12; color:#fff; font-size:11px; font-weight:700;
                     letter-spacing:2px; text-transform:uppercase; padding:6px 28px; }

  /* ── Deal card ── */
  .deal-card { border-bottom:1px solid #eeeeee; padding:18px 28px; }
  .deal-card:last-child { border-bottom:none; }
  .deal-rank { display:inline-block; background:#e94560; color:#fff;
               font-size:10px; font-weight:700; padding:2px 7px;
               border-radius:3px; margin-bottom:6px; }
  .deal-title { font-size:16px; font-weight:700; color:#1a1a2e; margin:0 0 3px; }
  .deal-source { font-size:12px; color:#888; margin:0 0 2px; }
  .deal-source a { color:#e94560; }

  /* Urgency badge */
  .urgency { display:inline-block; background:#e94560; color:#fff;
             font-size:10px; font-weight:700; padding:3px 8px;
             border-radius:3px; letter-spacing:0.5px; margin-bottom:8px; }

  /* Still available badge */
  .still-avail { display:inline-block; background:#2196f3; color:#fff;
                 font-size:10px; font-weight:700; padding:3px 8px;
                 border-radius:3px; letter-spacing:0.5px; margin-bottom:8px; margin-left:4px; }

  /* ── Deal meta numbers ── */
  .deal-meta { display:flex; flex-wrap:wrap; gap:12px; margin:10px 0 8px; }
  .meta-box .val { font-size:18px; font-weight:700; color:#1a1a2e; }
  .meta-box .lbl { font-size:10px; color:#888; text-transform:uppercase; }
  .profit-val { color:#27ae60 !important; }
  .conf-val   { color:#1565c0 !important; }

  /* ── Badges row ── */
  .badges { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:10px; }
  .badge { font-size:10px; padding:2px 8px; border-radius:10px; font-weight:700; }
  .badge-liq   { background:#e8f5e9; color:#2e7d32; }
  .badge-risk  { background:#fff3e0; color:#e65100; }
  .badge-vel   { background:#e3f2fd; color:#1565c0; }
  .badge-conf  { background:#f3e5f5; color:#6a1b9a; }
  .badge-cat   { background:#fce4ec; color:#880e4f; }

  /* ── Sell guide ── */
  .sell-guide { background:#f8f9fa; border:1px solid #e0e0e0; border-radius:6px;
                padding:12px 14px; margin:10px 0; }
  .sell-guide-title { font-size:11px; font-weight:700; text-transform:uppercase;
                      letter-spacing:1px; color:#555; margin-bottom:8px; }
  .platform-row { display:flex; align-items:center; gap:8px;
                  padding:5px 0; border-bottom:1px solid #eeeeee; }
  .platform-row:last-child { border-bottom:none; }
  .platform-rank { width:18px; height:18px; border-radius:50%; background:#1a1a2e;
                   color:#fff; font-size:10px; font-weight:700;
                   display:flex; align-items:center; justify-content:center;
                   flex-shrink:0; }
  .platform-name { font-size:13px; font-weight:600; color:#1a1a2e; flex:1; }
  .platform-price { font-size:14px; font-weight:700; color:#27ae60; }
  .platform-days { font-size:11px; color:#888; margin-left:8px; }

  /* ── Listing title suggestion ── */
  .listing-title-box { background:#fffde7; border-left:3px solid #ffc107;
                        padding:8px 12px; margin:8px 0; border-radius:2px; }
  .listing-title-box .lt-label { font-size:10px; font-weight:700; color:#f57f17;
                                  text-transform:uppercase; letter-spacing:1px; }
  .listing-title-box .lt-text { font-size:13px; color:#333; margin-top:3px; font-style:italic; }

  /* ── Flip tip ── */
  .deal-tip { background:#fffbf0; border-left:3px solid #f39c12;
              padding:8px 12px; font-size:13px; color:#555; margin:8px 0;
              border-radius:2px; }
  .deal-tip strong { color:#e67e22; }

  /* ── Deal image (float right) ── */
  .deal-img { float:right; max-width:85px; max-height:85px;
              margin-left:14px; border-radius:5px; object-fit:cover; }

  /* ── Full list table ── */
  .table-wrap { padding:0 28px 20px; overflow-x:auto; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th { background:#1a1a2e; color:#fff; text-align:left; padding:7px 8px;
       font-size:10px; text-transform:uppercase; letter-spacing:1px; }
  tr:nth-child(even) td { background:#f9f9f9; }
  td { padding:6px 8px; border-bottom:1px solid #eee; color:#333; vertical-align:middle; }
  td a { color:#e94560; }
  .profit-td { color:#27ae60; font-weight:700; }
  .local-td { background:#fce4ec; color:#c62828; font-size:10px;
               font-weight:700; padding:2px 5px; border-radius:3px; white-space:nowrap; }

  /* ── Footer ── */
  .footer { background:#1a1a2e; padding:18px 28px; text-align:center; }
  .footer p { color:#666; font-size:11px; margin:3px 0; }
  .footer a { color:#e94560; }

  /* ── Mobile ── */
  @media (max-width: 600px) {
    .header { padding:16px 16px 14px; }
    .header h1 { font-size:20px; }
    .stats-bar { padding:12px 16px; }
    .stats-inner { gap:12px; }
    .stat .num { font-size:18px; }
    .section-title { padding:8px 16px; }
    .intro { padding:12px 16px; }
    .best-deal-label { padding:5px 16px; }
    .deal-card { padding:14px 16px; }
    .deal-meta { gap:8px; }
    .meta-box .val { font-size:16px; }
    .deal-img { max-width:60px; max-height:60px; }
    .platform-row { flex-wrap:wrap; }
    .table-wrap { padding:0 16px 16px; }
    .footer { padding:14px 16px; }
  }
</style>
</head>
<body>
<div class="wrapper">

  <!-- Header -->
  <div class="header">
    <h1>FlipFinder {{ time_of_day }} Report</h1>
    <p class="subtitle">{{ report_date }}</p>
  </div>

  <!-- Stats bar -->
  <div class="stats-bar">
    <div class="stats-inner">
      <div class="stat">
        <div class="num">{{ stats.total_scanned }}</div>
        <div class="lbl">Scanned</div>
      </div>
      <div class="stat">
        <div class="num">{{ stats.deals_passing }}</div>
        <div class="lbl">Profitable</div>
      </div>
      <div class="stat">
        <div class="num">${{ "%.0f"|format(stats.total_profit) }}</div>
        <div class="lbl">Total Profit</div>
      </div>
      <div class="stat">
        <div class="num">{{ stats.sources_active }}</div>
        <div class="lbl">Sources</div>
      </div>
    </div>
  </div>

  {% if intro %}
  <div class="intro">{{ intro|safe }}</div>
  {% endif %}

  <!-- BEST DEAL OF THE DAY -->
  {% if best_deal %}
  <div class="best-deal-wrap">
    <div class="best-deal-label">Best Deal of the Day</div>
    <div class="deal-card">
      {% if best_deal.image_url %}
      <img class="deal-img" src="{{ best_deal.image_url }}"
           alt="{{ best_deal.standardized_name or best_deal.title }}" />
      {% endif %}

      {% if best_deal.source in local_sources %}
      <span class="urgency">LOCAL DEAL - ACT FAST</span>
      {% endif %}
      {% if best_deal.report_count > 0 %}
      <span class="still-avail">Still Available - Day {{ best_deal.report_count + 1 }}</span>
      {% endif %}

      <div class="deal-title">{{ best_deal.standardized_name or best_deal.title }}</div>
      <div class="deal-source">
        {{ best_deal.source|title }}
        {% if best_deal.location %} &bull; {{ best_deal.location }}{% endif %}
        &bull; <a href="{{ best_deal.url }}" target="_blank">View listing &rarr;</a>
      </div>

      <div class="deal-meta">
        <div class="meta-box">
          <div class="val">${{ "%.0f"|format(best_deal.buy_price) }}</div>
          <div class="lbl">Buy Price</div>
        </div>
        <div class="meta-box">
          <div class="val">${{ "%.0f"|format(best_deal.ebay_avg_sold) }}</div>
          <div class="lbl">eBay Avg</div>
        </div>
        <div class="meta-box">
          <div class="val profit-val">+${{ "%.0f"|format(best_deal.estimated_profit) }}</div>
          <div class="lbl">Est. Profit</div>
        </div>
        <div class="meta-box">
          <div class="val">{{ "%.0f"|format(best_deal.roi_percent) }}%</div>
          <div class="lbl">ROI</div>
        </div>
        {% if best_deal.price_confidence %}
        <div class="meta-box">
          <div class="val conf-val">{{ best_deal.price_confidence|int }}/10</div>
          <div class="lbl">Price Confidence</div>
        </div>
        {% endif %}
      </div>

      <div class="badges">
        <span class="badge badge-liq">Liquidity {{ best_deal.liquidity_score|int }}/10</span>
        <span class="badge badge-risk">Risk {{ best_deal.risk_score|int }}/10</span>
        <span class="badge badge-vel">{{ velocity_label(best_deal.velocity_score) }}</span>
        <span class="badge badge-cat">{{ best_deal.category|title }}</span>
      </div>

      {% if best_deal.listing_title %}
      <div class="listing-title-box">
        <div class="lt-label">Suggested Listing Title</div>
        <div class="lt-text">{{ best_deal.listing_title }}</div>
      </div>
      {% endif %}

      {% if best_deal.sell_guide %}
      <div class="sell-guide">
        <div class="sell-guide-title">Sell Guide — Top Platforms</div>
        {% for entry in best_deal.sell_guide %}
        <div class="platform-row">
          <div class="platform-rank">{{ loop.index }}</div>
          <div class="platform-name">{{ entry.platform }}</div>
          <div class="platform-price">List at ${{ "%.0f"|format(entry.list_price) }}</div>
          <div class="platform-days">~{{ entry.days_to_sell }}</div>
        </div>
        {% endfor %}
      </div>
      {% endif %}

      {% if best_deal.flip_tip %}
      <div class="deal-tip"><strong>Tip:</strong> {{ best_deal.flip_tip }}</div>
      {% endif %}

      <div style="clear:both;"></div>
    </div>
  </div>
  {% endif %}

  <!-- TOP DEALS -->
  <div class="section-title">Top {{ top_deals|length }} Deals</div>

  {% for deal in top_deals %}
  <div class="deal-card">
    <div class="deal-rank">#{{ loop.index }}</div>

    {% if deal.image_url %}
    <img class="deal-img" src="{{ deal.image_url }}"
         alt="{{ deal.standardized_name or deal.title }}" />
    {% endif %}

    {% if deal.source in local_sources %}
    <span class="urgency">LOCAL DEAL - ACT FAST</span>
    {% endif %}
    {% if deal.report_count > 0 %}
    <span class="still-avail">Still Available - Day {{ deal.report_count + 1 }}</span>
    {% endif %}

    <div class="deal-title">{{ deal.standardized_name or deal.title }}</div>
    <div class="deal-source">
      {{ deal.source|title }}
      {% if deal.location %} &bull; {{ deal.location }}{% endif %}
      &bull; <a href="{{ deal.url }}" target="_blank">View listing &rarr;</a>
    </div>

    <div class="deal-meta">
      <div class="meta-box">
        <div class="val">${{ "%.0f"|format(deal.buy_price) }}</div>
        <div class="lbl">Buy Price</div>
      </div>
      <div class="meta-box">
        <div class="val">${{ "%.0f"|format(deal.ebay_avg_sold) }}</div>
        <div class="lbl">eBay Avg</div>
      </div>
      <div class="meta-box">
        <div class="val profit-val">+${{ "%.0f"|format(deal.estimated_profit) }}</div>
        <div class="lbl">Est. Profit</div>
      </div>
      <div class="meta-box">
        <div class="val">{{ "%.0f"|format(deal.roi_percent) }}%</div>
        <div class="lbl">ROI</div>
      </div>
      {% if deal.price_confidence %}
      <div class="meta-box">
        <div class="val conf-val">{{ deal.price_confidence|int }}/10</div>
        <div class="lbl">Confidence</div>
      </div>
      {% endif %}
    </div>

    <div class="badges">
      <span class="badge badge-liq">Liquidity {{ deal.liquidity_score|int }}/10</span>
      <span class="badge badge-risk">Risk {{ deal.risk_score|int }}/10</span>
      <span class="badge badge-vel">{{ velocity_label(deal.velocity_score) }}</span>
      <span class="badge badge-cat">{{ deal.category|title }}</span>
    </div>

    {% if deal.listing_title %}
    <div class="listing-title-box">
      <div class="lt-label">Suggested Listing Title</div>
      <div class="lt-text">{{ deal.listing_title }}</div>
    </div>
    {% endif %}

    {% if deal.sell_guide %}
    <div class="sell-guide">
      <div class="sell-guide-title">Sell Guide — Top Platforms</div>
      {% for entry in deal.sell_guide %}
      <div class="platform-row">
        <div class="platform-rank">{{ loop.index }}</div>
        <div class="platform-name">{{ entry.platform }}</div>
        <div class="platform-price">List at ${{ "%.0f"|format(entry.list_price) }}</div>
        <div class="platform-days">~{{ entry.days_to_sell }}</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

    {% if deal.flip_tip %}
    <div class="deal-tip"><strong>Tip:</strong> {{ deal.flip_tip }}</div>
    {% endif %}

    <div style="clear:both;"></div>
  </div>
  {% endfor %}

  <!-- REMAINING DEALS TABLE -->
  {% if remaining_deals %}
  <div class="section-title">All Deals ({{ remaining_deals|length }} more)</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Source</th>
          <th>Buy</th>
          <th>Sell</th>
          <th>Profit</th>
          <th>ROI</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {% for deal in remaining_deals %}
        <tr>
          <td>
            <a href="{{ deal.url }}" target="_blank">
              {{ (deal.standardized_name or deal.title)[:50] }}
            </a>
            {% if deal.source in local_sources %}
            <br><span class="local-td">LOCAL</span>
            {% endif %}
          </td>
          <td>{{ deal.source|title }}</td>
          <td>${{ "%.0f"|format(deal.buy_price) }}</td>
          <td>${{ "%.0f"|format(deal.ebay_avg_sold) }}</td>
          <td class="profit-td">+${{ "%.0f"|format(deal.estimated_profit) }}</td>
          <td>{{ "%.0f"|format(deal.roi_percent) }}%</td>
          <td>{{ "%.1f"|format(deal.flip_score) }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- Footer -->
  <div class="footer">
    <p>Generated by <strong>FlipFinder</strong> at {{ report_date }}</p>
    <p>Estimates based on eBay sold listings (last ~30 days). Always verify before purchasing.</p>
    <p>eBay fees assumed at 13% + $8 shipping. Past sales don't guarantee future results.</p>
  </div>

</div>
</body>
</html>"""

_env = Environment(loader=BaseLoader())
_env.globals["velocity_label"] = _velocity_label
_tmpl = _env.from_string(_TEMPLATE)


def build_html(
    deals: list[Deal],
    stats: dict,
    intro: str = "",
    report_date: str = "",
    top_n: int = 5,
) -> str:
    """Render the full HTML email body."""
    if not report_date:
        report_date = datetime.now().strftime("%B %d, %Y %I:%M %p CT")

    # Best deal = highest flip_score overall
    best_deal = deals[0] if deals else None
    # Top deals = next N after best (or all if fewer)
    top_deals = deals[1:top_n + 1] if best_deal else deals[:top_n]
    remaining = deals[top_n + 1:] if best_deal else deals[top_n:]

    return _tmpl.render(
        best_deal=best_deal,
        top_deals=top_deals,
        remaining_deals=remaining,
        stats=stats,
        intro=intro,
        report_date=report_date,
        time_of_day=_time_of_day(),
        local_sources=LOCAL_SOURCES,
    )


def send_email(subject: str, html_body: str) -> bool:
    """Send an HTML email via Gmail SMTP. Returns True on success."""
    if not all([config.EMAIL_FROM, config.EMAIL_TO, config.EMAIL_PASSWORD]):
        logger.error("Email credentials not configured - cannot send report")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"FlipFinder <{config.EMAIL_FROM}>"
    msg["To"] = config.EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
        logger.info("Report email sent to %s", config.EMAIL_TO)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed - check EMAIL_PASSWORD (use App Password)")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", config.safe_str(e))
        return False


def send_report(deals: list[Deal], stats: dict, intro: str = "") -> bool:
    """Build and send the report email."""
    today = datetime.now().strftime("%b %d")
    tod = _time_of_day()
    total_profit = stats.get("total_profit", 0)
    n_deals = stats.get("deals_passing", 0)
    # Emoji in subject is fine - MIME encodes it as UTF-8
    subject = (
        f"\U0001f525 FlipFinder {tod} Report - {today} - "
        f"{n_deals} deals found - Est. ${total_profit:.0f} profit"
    )
    html = build_html(deals, stats, intro=intro)
    return send_email(subject, html)
