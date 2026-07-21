"""
JustDial Business Listings Scraper — Apify Scraping Browser edition
====================================================================
JustDial is protected by Akamai bot detection that requires:
  1. Chrome-identical TLS + HTTP/2 fingerprint
  2. JavaScript sensor data collected and signed by the browser

Both are handled by Apify's Scraping Browser — a managed real Chrome instance
accessible via CDP WebSocket. We connect to it instead of launching a local browser.

All listing data is in <script id="__NEXT_DATA__"> — once we get past Akamai,
extraction is a simple JSON parse.

Setup required: Enable "Scraping Browser" in your Apify actor's settings.
"""

import asyncio
import json
import logging
import os
import re

from apify import Actor
from playwright.async_api import async_playwright

from .parser import parse_page
from .utils import build_justdial_url, random_delay

logger = logging.getLogger(__name__)


async def _fetch_page(url: str, retries: int = 3) -> str | None:
    token = os.environ.get("APIFY_TOKEN", "")
    endpoint = f"wss://chrome.apify.com?token={token}"

    for attempt in range(retries):
        try:
            async with async_playwright() as pw:
                Actor.log.info("Connecting to Apify Scraping Browser (attempt %d)…", attempt + 1)
                browser = await pw.chromium.connect_over_cdp(endpoint, timeout=30_000)

                context = await browser.new_context(
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={
                        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                    },
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=60_000)

                try:
                    await page.wait_for_selector("#__NEXT_DATA__", timeout=15_000, state="attached")
                except Exception:
                    html = await page.content()
                    Actor.log.warning(
                        "No __NEXT_DATA__ after networkidle (%d bytes) — possible block.", len(html)
                    )
                    await browser.close()
                    if attempt < retries - 1:
                        await asyncio.sleep(3)
                    continue

                html = await page.content()
                await browser.close()
                return html

        except Exception as exc:
            Actor.log.warning("Attempt %d/%d failed: %s", attempt + 1, retries, exc)
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)

    return None


def _extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        search_query: str = actor_input.get("searchQuery", "").strip()
        city: str = actor_input.get("city", "").strip()
        max_results: int = int(actor_input.get("maxResults", 50))

        if not search_query or not city:
            await Actor.fail(status_message="Both 'searchQuery' and 'city' are required.")
            return

        Actor.log.info(
            "JustDial scrape — query: '%s' | city: '%s' | max: %d",
            search_query, city, max_results,
        )

        if not os.environ.get("APIFY_TOKEN"):
            await Actor.fail(
                status_message="APIFY_TOKEN not found. Enable 'Scraping Browser' in actor settings."
            )
            return

        results_count = 0
        page_num = 1

        while results_count < max_results:
            url = build_justdial_url(city, search_query, page=page_num)
            Actor.log.info("Fetching page %d: %s", page_num, url)

            html = await _fetch_page(url)
            if not html:
                Actor.log.error("Failed to fetch page %d after retries.", page_num)
                break

            next_data = _extract_next_data(html)
            if not next_data:
                Actor.log.warning("No __NEXT_DATA__ on page %d (%d bytes).", page_num, len(html))
                break

            listings, _ = parse_page(next_data, city)
            if not listings:
                Actor.log.info("No listings on page %d — end of results.", page_num)
                break

            Actor.log.info("Page %d: %d listings found", page_num, len(listings))

            for item in listings:
                if results_count >= max_results:
                    break
                await Actor.push_data(item)
                results_count += 1

            Actor.log.info("Progress: %d / %d", results_count, max_results)

            if results_count < max_results:
                await random_delay(1.5, 3.0)
                page_num += 1

        Actor.log.info(
            "Done. Results saved: %d / %d | Pages: %d",
            results_count, max_results, page_num,
        )
        if results_count == 0:
            Actor.log.warning(
                "Zero results. Check:\n"
                "  • Scraping Browser is enabled in actor settings\n"
                "  • The city/searchQuery is valid\n"
                "  • JustDial has not changed their data structure"
            )
