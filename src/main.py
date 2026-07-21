"""
JustDial Business Listings Scraper — curl_cffi + session edition
=================================================================
Akamai uses two detection layers:
  1. HTTP/2 SETTINGS frame fingerprint — curl_cffi impersonates Chrome exactly, passes.
     Playwright's headless Chromium has different SETTINGS values → Akamai sends GOAWAY.
  2. JavaScript challenge — Akamai sets bm_sz cookie on first response (14-byte HTML).
     curl_cffi AsyncSession persists cookies automatically, so the second GET (same session)
     carries those cookies and Akamai typically allows through.

All listing data is in <script id="__NEXT_DATA__"> — no JS execution needed once we
get the real page.
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


async def _fetch(url: str, proxy_url: str | None, max_attempts: int = 5) -> str | None:
    """
    Fetch a JustDial page using a persistent curl_cffi session.

    Akamai sets bm_sz on the first (blocked) response. The session carries
    that cookie automatically on retries, which often clears the challenge.
    """
    proxies = {"https": proxy_url, "http": proxy_url} if proxy_url else None

    async with AsyncSession(impersonate="chrome120") as session:
        for attempt in range(max_attempts):
            try:
                r = await session.get(
                    url,
                    headers=_HEADERS,
                    proxies=proxies,
                    timeout=30,
                )
                cookies_set = list(session.cookies.keys())
                Actor.log.info(
                    "Attempt %d: HTTP %d — %d bytes — cookies: %s",
                    attempt + 1, r.status_code, len(r.content), cookies_set,
                )

                if r.status_code == 200 and len(r.text) > 500:
                    return r.text

                if len(r.content) < 500:
                    Actor.log.warning(
                        "Short response — likely Akamai challenge. Retrying with session cookies."
                    )
                    await asyncio.sleep(2)
                    continue

            except Exception as exc:
                Actor.log.warning("Attempt %d/%d failed: %s", attempt + 1, max_attempts, exc)
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** min(attempt, 3))

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
                Actor.log.error("Failed to fetch page %d after all attempts.", page_num)
                break

            next_data = _extract_next_data(html)
            if not next_data:
                Actor.log.warning(
                    "No __NEXT_DATA__ on page %d (%d bytes).", page_num, len(html)
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
                "  • Akamai challenge not resolved — try running again (cookies may need a warmup)\n"
                "  • Use RESIDENTIAL proxies with apifyProxyCountry=IN\n"
                "  • The city/searchQuery returned no results"
            )
