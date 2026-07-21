"""
JustDial Business Listings Scraper — ScraperAPI edition
=========================================================
JustDial is protected by Akamai bot detection that requires a real browser
to complete a JavaScript challenge. ScraperAPI handles this transparently:
we send them the URL, they return the rendered HTML.

Requires SCRAPERAPI_KEY environment variable set in actor settings.
"""

import asyncio
import json
import logging
import os
import re

import aiohttp
from apify import Actor

from .parser import parse_page
from .utils import build_justdial_url, random_delay

logger = logging.getLogger(__name__)

_SCRAPERAPI_URL = "https://api.scraperapi.com/"


async def _fetch(url: str, api_key: str, retries: int = 3) -> str | None:
    params = {
        "api_key": api_key,
        "url": url,
        "render": "true",
        "country_code": "in",
    }
    timeout = aiohttp.ClientTimeout(total=120)

    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_SCRAPERAPI_URL, params=params) as r:
                    Actor.log.info("Attempt %d: HTTP %d", attempt + 1, r.status)
                    if r.status == 200:
                        html = await r.text()
                        if len(html) > 500:
                            return html
                        Actor.log.warning("Short response (%d bytes)", len(html))
                    else:
                        Actor.log.warning("ScraperAPI error: HTTP %d", r.status)
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

        api_key = os.environ.get("SCRAPERAPI_KEY", "").strip()
        if not api_key:
            await Actor.fail(status_message="SCRAPERAPI_KEY environment variable not set.")
            return

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
