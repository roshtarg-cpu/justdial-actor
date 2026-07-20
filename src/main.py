"""
JustDial Business Listings Scraper — direct Playwright + stealth edition
=========================================================================
JustDial is protected by Akamai bot detection with two layers:
  1. TLS fingerprint check  — solved by NOT disabling HTTP/2 (Chromium's TLS matches real Chrome)
  2. JavaScript challenge   — solved by playwright-stealth applied BEFORE navigation

playwright-stealth MUST run before page.goto(). Using crawlee's PlaywrightCrawler
is not possible here because it navigates before our handler runs. We use the
Playwright SDK directly for full control.

All listing data is server-rendered into <script id="__NEXT_DATA__"> so once
the page loads, extraction is a simple JSON parse — no CSS selectors needed.
"""

import asyncio
import json
import logging
import re

from apify import Actor
from playwright.async_api import async_playwright

from .parser import parse_page
from .utils import build_justdial_url, random_delay

logger = logging.getLogger(__name__)

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en', 'hi'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
const _origPermissions = window.navigator.permissions.query.bind(navigator.permissions);
window.navigator.permissions.query = p => p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : _origPermissions(p);
"""

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_page(url: str, proxy_url: str | None, retries: int = 3) -> str | None:
    proxy = {"server": proxy_url} if proxy_url else None

    for attempt in range(retries):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = await browser.new_context(
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    viewport={"width": 1366, "height": 768},
                    user_agent=_UA,
                    extra_http_headers={
                        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                    },
                )
                page = await context.new_page()

                # Stealth BEFORE navigation — add_init_script runs before any page JS
                await page.add_init_script(_STEALTH_JS)

                await page.goto(url, wait_until="networkidle", timeout=60_000)

                # Wait for Next.js to inject __NEXT_DATA__
                try:
                    await page.wait_for_selector("#__NEXT_DATA__", timeout=15_000, state="attached")
                except Exception:
                    html = await page.content()
                    Actor.log.warning(
                        "No __NEXT_DATA__ after networkidle on %s (%d bytes) — possible challenge page.",
                        url, len(html),
                    )
                    await browser.close()
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

                html = await page.content()
                await browser.close()
                return html

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

            html = await _fetch_page(url, proxy_url)
            if not html:
                Actor.log.error("Failed to fetch page %d after retries.", page_num)
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
                "  • JustDial blocked the request — use RESIDENTIAL proxies with country=IN\n"
                "  • The city/searchQuery returned no results\n"
                "  • JustDial changed their data structure"
            )
