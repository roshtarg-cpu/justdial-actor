"""
JustDial Business Listings Scraper — ScraperAPI edition
=========================================================
JustDial is protected by Akamai bot detection. ScraperAPI with premium Indian
residential IPs bypasses it without a browser — JustDial serves __NEXT_DATA__
in the initial HTML, so no JS execution is needed.

Requires scraperApiKey actor input or SCRAPERAPI_KEY environment variable.
"""

import asyncio
import json
import os
import re

import aiohttp
from apify import Actor

from .parser import parse_page
from .utils import build_justdial_url, random_delay

_SCRAPERAPI_URL = "https://api.scraperapi.com/"
_BASE_PARAMS = {"render": "false", "country_code": "in", "premium": "true"}
_MAX_RETRIES = 8


def _extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


async def _fetch(url: str, api_key: str) -> str | None:
    timeout = aiohttp.ClientTimeout(total=120)
    for attempt in range(1, _MAX_RETRIES + 1):
        params = {"api_key": api_key, "url": url, **_BASE_PARAMS}
        Actor.log.info("Attempt %d / %d", attempt, _MAX_RETRIES)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_SCRAPERAPI_URL, params=params) as r:
                    Actor.log.info("HTTP %d — %d bytes", r.status, r.content_length or 0)
                    if r.status == 200:
                        html = await r.text()
                        Actor.log.info("Response size: %d bytes", len(html))
                        if len(html) > 500:
                            return html
                        Actor.log.warning("Short response (%d bytes) — rotating IP", len(html))
                    else:
                        Actor.log.warning("ScraperAPI HTTP %d", r.status)
        except Exception as exc:
            Actor.log.warning("Attempt %d failed: %s", attempt, exc)
        await asyncio.sleep(3)
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

        api_key = (
            actor_input.get("scraperApiKey", "")
            or os.environ.get("SCRAPERAPI_KEY", "")
            or "0e8ae0f9818e60aab8add3b0bf2cb632"
        ).strip()

        Actor.log.info(
            "JustDial scrape — query: '%s' | city: '%s' | max: %d",
            search_query, city, max_results,
        )

        results_count = 0
        page_num = 1

        while results_count < max_results:
            url = build_justdial_url(city, search_query, page=page_num)
            Actor.log.info("Fetching page %d: %s", page_num, url)

            html = await _fetch(url, api_key)
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
