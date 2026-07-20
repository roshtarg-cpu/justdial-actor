"""URL helpers and delay utilities."""

import asyncio
import random


def _slug(text: str) -> str:
    """Convert a phrase to a JustDial-style URL slug (Title-Case-With-Hyphens)."""
    return "-".join(word.capitalize() for word in text.strip().split())


def build_justdial_url(city: str, query: str, page: int = 1) -> str:
    city_slug = _slug(city)
    query_slug = _slug(query)
    base = f"https://www.justdial.com/{city_slug}/{query_slug}"
    return base if page == 1 else f"{base}/page-{page}"


async def random_delay(min_sec: float = 1.5, max_sec: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_sec, max_sec))
