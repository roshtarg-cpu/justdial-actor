"""
JustDial Business Listings Scraper — Camoufox edition
======================================================
Uses Camoufox (stealthy Firefox) + Apify residential proxies to bypass
Akamai bot detection. No external services required.
"""

import json
import re
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession
from apify import Actor

from .parser import parse_page
from .utils import build_justdial_url, random_delay

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}


def _extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


async def _fetch(url: str, proxy_cfg, max_retries: int = 8) -> str | None:
    for attempt in range(1, max_retries + 1):
        proxy_url = await proxy_cfg.new_url() if proxy_cfg else None
        Actor.log.info("Attempt %d/%d", attempt, max_retries)
        try:
            async with AsyncSession(impersonate="chrome120") as session:
                r = await session.get(
                    url,
                    headers=_HEADERS,
                    proxies={"https": proxy_url, "http": proxy_url} if proxy_url else None,
                    timeout=60,
                )
                html = r.text
                Actor.log.info("HTTP %d | %d bytes", r.status_code, len(html))
                if r.status_code == 200 and len(html) > 500 and "Access Denied" not in html and '"bot":true' not in html:
                    return html
                Actor.log.warning("Blocked response — rotating IP")
        except Exception as exc:
            Actor.log.warning("Attempt %d failed: %s", attempt, exc)
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

        proxy_cfg = await Actor.create_proxy_configuration(
            actor_proxy_input=actor_input.get("proxyConfiguration"),
        )

        Actor.log.info(
            "JustDial scrape — query: '%s' | city: '%s' | max: %d",
            search_query, city, max_results,
        )

        results_count = 0
        page_num = 1

        while results_count < max_results:
            url = build_justdial_url(city, search_query, page=page_num)
            Actor.log.info("Fetching page %d: %s", page_num, url)

            html = await _fetch(url, proxy_cfg)

            if not html:
                Actor.log.error("Failed to fetch page %d.", page_num)
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
