"""
HTML email builder and Gmail sender for the nightly FlipFinder report.
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

# ── HTML template ──────────────────────────────────────────────────────────────
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FlipFinder Report</title>
<style>
  body { margin:0; padding:0; background:#f4f4f4; font-family: Arial, Helvetica, sans-serif; }
  .wrapper { max-width:680px; margin:0 auto; background:#ffffff; }
  /* Header */
  .header { background:#1a1a2e; padding:28px 32px; }
  .header h1 { color:#e94560; margin:0 0 4px; font-size:26px; letter-spacing:1px; }
  .header .subtitle { color:#a8a8b3; font-size:14px; margin:0; }
  /* Stats bar */
  .stats-bar { background:#16213e; padding:16px 32px; display:table; width:100%; box-sizing:border-box; }
  .stat { display:inline-block; margin-right:32px; }
  .stat .num { color:#e94560; font-size:22px; font-weight:bold; }
  .stat .label { color:#a8a8b3; font-size:11px; text-transform:uppercase; letter-spacing:1px; }
  /* Section headings */
  .section-title { background:#f0f0f0; padding:10px 32px; font-size:12px;
                   font-weight:bold; text-transform:uppercase; letter-spacing:2px;
                   color:#555; border-left:4px solid #e94560; }
  /* Deal card */
  .deal-card { border-bottom:1px solid #eeeeee; padding:20px 32px; }
  .deal-card:last-child { border-bottom:none; }
  .deal-rank { display:inline-block; background:#e94560; color:#fff;
               font-size:11px; font-weight:bold; padding:2px 8px;
               border-radius:3px; margin-bottom:8px; }
  .deal-title { font-size:17px; font-weight:bold; color:#1a1a2e; margin:0 0 4px; }
  .deal-source { font-size:12px; color:#888; margin:0 0 10px; }
  .deal-source a { color:#e94560; text-decoration:none; }
  .deal-meta { display:table; width:100%; margin-bottom:10px; }
  .meta-box { display:inline-block; margin-right:20px; }
  .meta-box .val { font-size:18px; font-weight:bold; color:#1a1a2e; }
  .meta-box .lbl { font-size:11px; color:#888; text-transform:uppercase; }
  .profit-val { color:#27ae60 !important; }
  .deal-tip { background:#fffbf0; border-left:3px solid #f39c12;
              padding:8px 12px; font-size:13px; color:#555; margin-top:8px;
              border-radius:2px; }
  .deal-tip strong { color:#e67e22; }
  .badges { margin-top:8px; }
  .badge { display:inline-block; font-size:11px; padding:2px 8px;
           border-radius:10px; margin-right:4px; font-weight:bold; }
  .badge-liq  { background:#e8f5e9; color:#2e7d32; }
  .badge-risk { background:#fff3e0; color:#e65100; }
  .badge-vel  { background:#e3f2fd; color:#1565c0; }
  /* Full list table */
  .table-wrap { padding:0 32px 24px; overflow-x:auto; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { background:#1a1a2e; color:#fff; text-align:left; padding:8px 10px;
       font-size:11px; text-transform:uppercase; letter-spacing:1px; }
  tr:nth-child(even) td { background:#f9f9f9; }
  td { padding:7px 10px; border-bottom:1px solid #eee; color:#333; }
  td a { color:#e94560; text-decoration:none; }
  .profit-td { color:#27ae60; font-weight:bold; }
  /* Footer */
  .footer { background:#1a1a2e; padding:20px 32px; text-align:center; }
  .footer p { color:#666; font-size:11px; margin:4px 0; }
  .footer a { color:#e94560; text-decoration:none; }
</style>
</head>
<body>
<div class="wrapper">

  <!-- Header -->
  <div class="header">
    <h1>FlipFinder Report</h1>
    <p class="subtitle">{{ report_date }} &mdash; Nightly deal scan</p>
  </div>

  <!-- Stats bar -->
  <div class="stats-bar">
    <div class="stat">
      <div class="num">{{ stats.total_scanned }}</div>
      <div class="label">Deals Scanned</div>
    </div>
    <div class="stat">
      <div class="num">{{ stats.deals_passing }}</div>
      <div class="label">Profitable</div>
    </div>
    <div class="stat">
      <div class="num">${{ "%.0f"|format(stats.total_profit) }}</div>
      <div class="label">Total Potential Profit</div>
    </div>
    <div class="stat">
      <div class="num">{{ stats.sources_active }}</div>
      <div class="label">Sources Active</div>
    </div>
  </div>

  <!-- Intro paragraph from Claude -->
  {% if intro %}
  <div style="padding:16px 32px; font-size:14px; line-height:1.6; color:#444; border-bottom:1px solid #eee;">
    {{ intro|safe }}
  </div>
  {% endif %}

  <!-- TOP DEALS -->
  <div class="section-title">Top {{ top_deals|length }} Deals Tonight</div>

  {% for deal in top_deals %}
  <div class="deal-card">
    <div class="deal-rank">#{{ loop.index }}</div>

    {% if deal.image_url %}
    <img src="{{ deal.image_url }}" alt="{{ deal.standardized_name or deal.title }}"
         style="float:right; max-width:90px; max-height:90px; margin-left:12px;
                border-radius:4px; object-fit:cover;" />
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
        <div class="lbl">Avg eBay Sold</div>
      </div>
      <div class="meta-box">
        <div class="val profit-val">+${{ "%.0f"|format(deal.estimated_profit) }}</div>
        <div class="lbl">Est. Profit</div>
      </div>
      <div class="meta-box">
        <div class="val">{{ "%.0f"|format(deal.roi_percent) }}%</div>
        <div class="lbl">ROI</div>
      </div>
    </div>

    <div class="badges">
      <span class="badge badge-liq">Liquidity {{ deal.liquidity_score }}/10</span>
      <span class="badge badge-risk">Risk {{ deal.risk_score }}/10</span>
      <span class="badge badge-vel">Velocity {{ deal.velocity_score|int }}/10</span>
    </div>

    {% if deal.flip_tip %}
    <div class="deal-tip"><strong>Tip:</strong> {{ deal.flip_tip }}</div>
    {% endif %}

    <div style="clear:both;"></div>
  </div>
  {% endfor %}

  {% if remaining_deals %}
  <!-- FULL LIST TABLE -->
  <div class="section-title">All Deals ({{ remaining_deals|length }} more)</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Source</th>
          <th>Buy</th>
          <th>eBay Avg</th>
          <th>Profit</th>
          <th>ROI</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {% for deal in remaining_deals %}
        <tr>
          <td><a href="{{ deal.url }}" target="_blank">{{ (deal.standardized_name or deal.title)[:55] }}</a></td>
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
    <p>Prices and profits are estimates. Always verify before purchasing.</p>
    <p>eBay fees assumed at 13% + $8 shipping. Past sold prices don't guarantee future sales.</p>
  </div>

</div>
</body>
</html>"""

_env = Environment(loader=BaseLoader())
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

    top_deals = deals[:top_n]
    remaining = deals[top_n:]

    return _tmpl.render(
        top_deals=top_deals,
        remaining_deals=remaining,
        stats=stats,
        intro=intro,
        report_date=report_date,
    )


def send_email(subject: str, html_body: str) -> bool:
    """
    Send an HTML email via Gmail SMTP.
    Returns True on success.
    """
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
        logger.error("Gmail authentication failed - check EMAIL_PASSWORD (use App Password, not account password)")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def send_report(deals: list[Deal], stats: dict, intro: str = "") -> bool:
    """Build and send the nightly report email."""
    today = datetime.now().strftime("%b %d")
    subject = (
        f"FlipFinder Report - {today} - "
        f"{stats.get('deals_passing', 0)} deals found"
    )
    html = build_html(deals, stats, intro=intro)
    return send_email(subject, html)
