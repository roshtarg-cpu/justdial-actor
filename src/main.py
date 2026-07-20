"""
JustDial Business Listings Scraper — Playwright edition
=========================================================
JustDial is a Next.js SPA protected by Akamai bot detection. Plain HTTP
clients (even those that mimic browser TLS) receive an empty <HTML></HTML>
response. Only a real Chromium browser executing the Akamai JS challenge
gets the actual page.

Approach
--------
1. PlaywrightCrawler opens each search-result page in a real Chromium tab.
2. We wait for Next.js to embed the full dataset in <script id="__NEXT_DATA__">.
3. We extract and parse that JSON — no CSS selectors, no phone-CSS decoding.
   All fields (name, phone, address, rating, verified, open status, years...)
   are available directly in the JSON.
4. Pagination: JustDial appends /page-2, /page-3, … to the base URL.
   We queue subsequent pages until maxResults is reached or the page is empty.
"""

import asyncio
import json
import logging
import random
from datetime import timedelta

from apify import Actor
from playwright_stealth import stealth_async

from .parser import parse_page
from .utils import build_justdial_url, random_delay

logger = logging.getLogger(__name__)

try:
    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
    from crawlee import Request
except ImportError as e:
    raise ImportError(
        "crawlee[playwright] is required. Run: pip install 'crawlee[playwright]'"
    ) from e


# ---------------------------------------------------------------------------
# Shared mutable state (written and read inside crawler handlers)
# ---------------------------------------------------------------------------
class _State:
    def __init__(self, max_results: int) -> None:
        self.results_count = 0
        self.max_results = max_results
        self.done = False
        self.pages_scraped = 0

    @property
    def needs_more(self) -> bool:
        return not self.done and self.results_count < self.max_results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with Actor:
        # ----------------------------------------------------------------
        # 1. Input
        # ----------------------------------------------------------------
        actor_input = await Actor.get_input() or {}

        search_query: str = actor_input.get("searchQuery", "").strip()
        city: str = actor_input.get("city", "").strip()
        max_results: int = int(actor_input.get("maxResults", 50))
        proxy_config_input = actor_input.get("proxyConfiguration")

        if not search_query or not city:
            await Actor.fail(
                status_message="Both 'searchQuery' and 'city' are required."
            )
            return

        Actor.log.info(
            "JustDial scrape — query: '%s' | city: '%s' | max: %d",
            search_query, city, max_results,
        )

        # ----------------------------------------------------------------
        # 2. Proxy
        # ----------------------------------------------------------------
        proxy_configuration = None
        if proxy_config_input:
            try:
                proxy_configuration = await Actor.create_proxy_configuration(
                    actor_proxy_input=proxy_config_input
                )
                Actor.log.info("Proxy configuration ready")
            except Exception as exc:
                Actor.log.warning("Could not create proxy config: %s", exc)

        # ----------------------------------------------------------------
        # 3. State
        # ----------------------------------------------------------------
        state = _State(max_results)

        # ----------------------------------------------------------------
        # 4. Playwright crawler
        # ----------------------------------------------------------------
        crawler = PlaywrightCrawler(
            proxy_configuration=proxy_configuration,
            max_request_retries=3,
            request_handler_timeout=timedelta(seconds=120),
            headless=True,
            browser_type="chromium",
            browser_launch_options={
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            },
            browser_new_context_options={
                "locale": "en-IN",
                "timezone_id": "Asia/Kolkata",
                "extra_http_headers": {
                    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                },
            },
            goto_options={
                "wait_until": "domcontentloaded",
            },
        )

        @crawler.router.default_handler
        async def handle_page(context: PlaywrightCrawlingContext) -> None:
            if not state.needs_more:
                return

            page = context.page
            await stealth_async(page)
            url = context.request.url

            # --------------------------------------------------------
            # Wait for Next.js to inject __NEXT_DATA__
            # --------------------------------------------------------
            try:
                await page.wait_for_selector(
                    "#__NEXT_DATA__",
                    timeout=60_000,
                    state="attached",
                )
            except Exception:
                Actor.log.warning(
                    "Timed out waiting for __NEXT_DATA__ on %s — "
                    "possible CAPTCHA or network block. Enable residential proxies.",
                    url,
                )
                return

            # --------------------------------------------------------
            # Extract the JSON blob
            # --------------------------------------------------------
            raw_json: str = await page.evaluate(
                "document.getElementById('__NEXT_DATA__').textContent"
            )
            try:
                next_data = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                Actor.log.error("Could not parse __NEXT_DATA__ JSON: %s", exc)
                return

            # --------------------------------------------------------
            # Parse listings
            # --------------------------------------------------------
            listings, pagination = parse_page(next_data, city)
            state.pages_scraped += 1

            if not listings:
                Actor.log.warning(
                    "Page %d (%s): zero listings parsed.", state.pages_scraped, url
                )
                return

            Actor.log.info(
                "Page %d: %d listings found", state.pages_scraped, len(listings)
            )

            # --------------------------------------------------------
            # Push to dataset
            # --------------------------------------------------------
            for item in listings:
                if not state.needs_more:
                    state.done = True
                    break
                await Actor.push_data(item)
                state.results_count += 1

                if state.results_count % 10 == 0:
                    Actor.log.info(
                        "Progress: %d / %d results saved",
                        state.results_count, state.max_results,
                    )

            # --------------------------------------------------------
            # Pagination — queue next page if needed
            # --------------------------------------------------------
            if state.needs_more and len(listings) > 0:
                await random_delay(1.5, 3.0)

                next_page_num = state.pages_scraped + 1
                next_url = _next_page_url(url, next_page_num)
                Actor.log.info("Queuing page %d: %s", next_page_num, next_url)
                await context.add_requests([Request.from_url(next_url)])

        # ----------------------------------------------------------------
        # 5. Run
        # ----------------------------------------------------------------
        start_url = build_justdial_url(city, search_query, page=1)
        await crawler.run([Request.from_url(start_url)])

        # ----------------------------------------------------------------
        # 6. Summary
        # ----------------------------------------------------------------
        Actor.log.info(
            "Done. Results saved: %d / %d | Pages: %d",
            state.results_count, state.max_results, state.pages_scraped,
        )
        if state.results_count == 0:
            Actor.log.warning(
                "Zero results saved. Possible causes:\n"
                "  • JustDial blocked the browser (use residential proxies)\n"
                "  • The city/searchQuery returned no results\n"
                "  • JustDial changed their Next.js data structure"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_page_url(current_url: str, page_num: int) -> str:
    """Construct the URL for page N from the current URL."""
    import re
    # Remove any existing /page-N suffix
    base = re.sub(r"/page-\d+/?$", "", current_url.rstrip("/"))
    return f"{base}/page-{page_num}"
