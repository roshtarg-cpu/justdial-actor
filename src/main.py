"""
JustDial Business Listings Scraper — curl_cffi edition
========================================================
JustDial is a Next.js app protected by Akamai bot detection. Akamai fingerprints
the TLS handshake (JA3/JA4) and drops connections from headless Chromium even with
residential proxies. curl_cffi impersonates Chrome's exact TLS fingerprint at the
socket level, bypassing this check without needing a browser at all.

All listing data is server-rendered into <script id="__NEXT_DATA__"> so we only
need an HTTP GET — no JavaScript execution required.
"""

import asyncio
import json
import logging
import re

from apify import Actor
from curl_cffi.requests import AsyncSession

from .parser import parse_page
from .utils import build_justdial_url, random_delay

logger = logging.getLogger(__name__)

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


async def _fetch(url: str, proxy_url: str | None, retries: int = 3) -> str | None:
    proxies = {"https": proxy_url, "http": proxy_url} if proxy_url else None
    for attempt in range(retries):
        try:
            async with AsyncSession(impersonate="chrome120") as session:
                r = await session.get(url, headers=_HEADERS, proxies=proxies, timeout=30)
            if r.status_code == 200:
                return r.text
            Actor.log.warning("HTTP %d on %s", r.status_code, url)
        except Exception as exc:
            Actor.log.warning("Attempt %d/%d failed for %s: %s", attempt + 1, retries, url, exc)
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
        proxy_config_input = actor_input.get("proxyConfiguration")

        if not search_query or not city:
            await Actor.fail(status_message="Both 'searchQuery' and 'city' are required.")
            return

        Actor.log.info(
            "JustDial scrape — query: '%s' | city: '%s' | max: %d",
            search_query, city, max_results,
        )

        proxy_configuration = None
        if proxy_config_input:
            try:
                proxy_configuration = await Actor.create_proxy_configuration(
                    actor_proxy_input=proxy_config_input
                )
                Actor.log.info("Proxy configuration ready")
            except Exception as exc:
                Actor.log.warning("Could not create proxy config: %s", exc)

        results_count = 0
        page_num = 1

        while results_count < max_results:
            url = build_justdial_url(city, search_query, page=page_num)
            Actor.log.info("Fetching page %d: %s", page_num, url)

            proxy_url = None
            if proxy_configuration:
                proxy_url = await proxy_configuration.new_url(session_id=f"page_{page_num}")

            html = await _fetch(url, proxy_url)
            if not html:
                Actor.log.error("Failed to fetch page %d after retries.", page_num)
                break

            next_data = _extract_next_data(html)
            if not next_data:
                Actor.log.warning(
                    "No __NEXT_DATA__ on page %d (%d bytes) — possible block or end of results.",
                    page_num, len(html),
                )
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
                "Zero results. Possible causes:\n"
                "  • JustDial blocked the request — use RESIDENTIAL proxies with country=IN\n"
                "  • The city/searchQuery returned no results\n"
                "  • JustDial changed their data structure"
            )
