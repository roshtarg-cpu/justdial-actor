# JustDial Business Listings Scraper

Extract structured business lead data from [JustDial.com](https://www.justdial.com) — India's largest local business directory — with no manual effort.

Search by category and city to get clean, export-ready records: business name, phone number, address, rating, review count, verified status, open/closed status, years in business, and a direct profile link.

---

## What you get

| Field | Type | Example |
|---|---|---|
| `businessName` | string | `Pind Balluchi Restaurant` |
| `category` | string | `Restaurants` |
| `phone` | string | `08123061405` |
| `address` | string | `Sector 63 Market, Noida Sector 62` |
| `locality` | string | `Noida Sector 62` |
| `city` | string | `Noida` |
| `rating` | float | `4.1` |
| `reviewCount` | integer | `4642` |
| `isVerified` | boolean | `true` |
| `hasWebsite` | boolean | `false` |
| `websiteUrl` | string\|null | `null` |
| `profileUrl` | string | `https://www.justdial.com/Noida/Pind-Balluchi-...` |
| `openNow` | boolean\|null | `false` |
| `yearsInBusiness` | integer\|null | `9` |

---

## Input

```json
{
  "searchQuery": "restaurants",
  "city": "Mumbai",
  "maxResults": 100,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `searchQuery` | ✅ | — | Business type: `restaurants`, `dentists`, `plumbers`, etc. |
| `city` | ✅ | — | Indian city: `Delhi`, `Mumbai`, `Bangalore`, etc. |
| `maxResults` | — | `50` | Max listings to return (1–500) |
| `proxyConfiguration` | — | — | Apify proxy settings — **RESIDENTIAL recommended** |

---

## Use cases

- **Sales lead generation** — get phone numbers and addresses for cold outreach
- **Market research** — map competitors by city and category
- **AI pipelines** — feed structured business data directly into agents or CRMs
- **Directory building** — compile local business databases for any Indian city
- **Rating analysis** — track ratings and review counts across a category

---

## How it works

JustDial is a Next.js app that embeds all search results as a JSON object (`__NEXT_DATA__`) in the initial HTML. This actor:

1. Opens each search page in a real Chromium browser (via Playwright) to pass bot-detection
2. Extracts the embedded JSON — no fragile CSS selectors
3. Maps the clean data fields to the output schema
4. Paginates automatically until `maxResults` is reached
5. Adds 1.5–3 s random delays between pages to respect rate limits

Phone numbers are available directly in the JSON (no CSS decoding required).

---

## Tips

- **Use RESIDENTIAL proxies** — JustDial runs Akamai bot detection. Datacenter IPs will be blocked.
- One JustDial page returns ~10 listings. For 100 results the actor fetches ~10 pages.
- Results are ready to export as **CSV, JSON, or Excel** from the dataset view.
- The `profileUrl` field links directly to each business's full JustDial page for deeper scraping.

---

## Output example

```json
{
  "businessName": "Pind Balluchi Restaurant",
  "category": "Restaurants",
  "phone": "08123061405",
  "address": "Sector 63 Market Noida Sector 62",
  "locality": "Noida Sector 62",
  "city": "Noida",
  "rating": 4.1,
  "reviewCount": 4642,
  "isVerified": true,
  "hasWebsite": false,
  "websiteUrl": null,
  "profileUrl": "https://www.justdial.com/Noida/Pind-Balluchi-Restaurant-Sector-63-Market-Noida-Sector-62/011PXX11-XX11-170123181948-M3H8_BZDET",
  "openNow": false,
  "yearsInBusiness": 9
}
```
