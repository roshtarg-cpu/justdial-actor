"""
JustDial __NEXT_DATA__ JSON parser.

JustDial is a Next.js SPA. The server embeds ALL search-result data
in a <script id="__NEXT_DATA__"> tag as a single JSON blob. The
listing data lives at:

    props.pageProps.listData.results

which uses a columnar layout:

    {
        "columns": ["docid", "name", "VNumber", "compRating", ...],
        "data":    [["011PXX...", "Pind Balluchi", "08123...", "4.1", ...],
                    ...]
    }

We zip each row with the column names to produce a dict, then map to
the output schema.
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Top-level extraction from the raw __NEXT_DATA__ object
# ---------------------------------------------------------------------------

def extract_list_data(next_data: dict) -> dict | None:
    """Pull `listData` out of pageProps, return None on any key error."""
    try:
        return next_data["props"]["pageProps"]["listData"]
    except (KeyError, TypeError):
        return None


def extract_pagination_info(list_data: dict) -> dict:
    return {
        "totalResults": list_data.get("totalNumberofResults", "0"),
        "nextDocId": list_data.get("nextdocid", ""),
        "nextDocIdCount": int(list_data.get("nextdocidcount", 10)),
    }


def rows_to_dicts(results: dict) -> list[dict]:
    """Convert the columnar results structure to a list of row-dicts."""
    columns: list[str] = results.get("columns", [])
    data: list[list] = results.get("data", [])
    return [dict(zip(columns, row)) for row in data]


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _str(v: Any, fallback: str | None = None) -> str | None:
    if v is None or v == "" or v == [] or v == {}:
        return fallback
    return str(v).strip() or fallback


def _float(v: Any) -> float | None:
    try:
        f = float(str(v).strip().replace(",", ""))
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _int_from_str(v: Any) -> int | None:
    """Parse integers from strings like '4,642 Ratings' or '4642'."""
    try:
        digits = re.sub(r"[^\d]", "", str(v))
        return int(digits) if digits else None
    except (ValueError, TypeError):
        return None


def _parse_years(attr_data: Any) -> int | None:
    """
    attr_data.node3 is typically:
        ["<span ...>9 Years in Business</span>", 1, 0]
    Extract the integer year count.
    """
    if not isinstance(attr_data, dict):
        return None
    node3 = attr_data.get("node3")
    if not node3:
        return None
    text = str(node3[0]) if isinstance(node3, list) else str(node3)
    m = re.search(r"(\d+)\s*[Yy]ear", text)
    if m:
        return int(m.group(1))
    return None


def _profile_url(weburl: Any) -> str | None:
    """weburl is a relative path like 'Delhi/Foo-Bar/011PXX...'"""
    s = _str(weburl)
    if not s:
        return None
    return f"https://www.justdial.com/{s}"


def _phone(vnumber: Any) -> str | None:
    s = _str(vnumber)
    if not s:
        return None
    # Strip non-digit characters except leading +
    digits = re.sub(r"[^\d+]", "", s)
    return digits if len(digits) >= 7 else None


def _open_now(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    try:
        return bool(int(v))
    except (ValueError, TypeError):
        return None


def _category(type_val: Any, hcatarr: Any) -> str | None:
    # `type` is a comma-separated list e.g. "Restaurants, North Indian Restaurants"
    s = _str(type_val)
    if s:
        return s.split(",")[0].strip()
    if isinstance(hcatarr, dict):
        return _str(hcatarr.get("name"))
    return None


def _locality(area: Any, arealn: Any) -> str | None:
    return _str(arealn) or _str(area)


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------

def parse_listing(row: dict, input_city: str) -> dict | None:
    """
    Map a JustDial columnar row dict to the actor's output schema.
    Returns None if the row has no business name (e.g. ad slot).
    """
    name = _str(row.get("name") or row.get("nameln"))
    if not name:
        return None

    return {
        "businessName": name,
        "category": _category(row.get("type"), row.get("hcatarr")),
        "phone": _phone(row.get("VNumber")),
        "address": _str(row.get("NewAddress") or row.get("NewAddressln")),
        "locality": _locality(row.get("area"), row.get("arealn")),
        "city": _str(row.get("loccity") or row.get("city") or input_city),
        "rating": _float(row.get("compRating") or row.get("compRatingln")),
        "reviewCount": _int_from_str(row.get("totJdReviews") or row.get("totalReviews")),
        "isVerified": str(row.get("verified", "0")) == "1",
        "hasWebsite": False,   # Website URL is only on the detail page; skip here
        "websiteUrl": None,
        "profileUrl": _profile_url(row.get("weburl")),
        "openNow": _open_now(row.get("opennow")),
        "yearsInBusiness": _parse_years(row.get("attr_data")),
    }


def parse_page(next_data: dict, input_city: str) -> tuple[list[dict], dict]:
    """
    Parse one page of JustDial __NEXT_DATA__ JSON.

    Returns:
        (listings, pagination_info)
        pagination_info has keys: totalResults, nextDocId, nextDocIdCount
    """
    list_data = extract_list_data(next_data)
    if not list_data:
        page_props = next_data.get("props", {}).get("pageProps", {})
        logger.warning("listData not found. pageProps keys: %s", list(page_props.keys())[:20])
        return [], {}

    pagination = extract_pagination_info(list_data)

    results = list_data.get("results", {})
    rows = rows_to_dicts(results)

    listings: list[dict] = []
    for row in rows:
        try:
            item = parse_listing(row, input_city)
            if item:
                listings.append(item)
        except Exception as exc:
            logger.warning("Skipped a row: %s", exc)

    return listings, pagination
