# JustDial Business Listings Scraper

Scrapes public business listings from [JustDial.com](https://www.justdial.com) — India's largest local-business directory.

Built with **Python**, **Crawlee** (`BeautifulSoupCrawler`), and the **Apify SDK**.

---

## What it does

Given a business category and an Indian city, the actor fetches paginated JustDial search results and outputs one structured record per listing.

---

## Input

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `searchQuery` | string | ✅ | — | Business type, e.g. `restaurants`, `dentists`, `plumbers` |
| `city` | string | ✅ | — | Indian city name, e.g. `Delhi`, `Mumbai`, `Bangalore` |
| `maxResults` | integer | — | `50` | Maximum listings to return (1–500) |
| `proxyConfiguration` | object | — | — | Apify proxy settings (residential recommended) |

### Example input

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

---

## Output

Each record in the dataset has these fields:

| Field | Type | Description |
|---|---|---|
| `businessName` | string \| null | Name of the business |
| `category` | string \| null | Business category / type |
| `phone` | string \| null | Decoded phone number |
| `address` | string \| null | Full address text |
| `locality` | string \| null | Neighbourhood / locality name |
| `city` | string | City as provided in input |
| `rating` | float \| null | Star rating (0–5) |
| `reviewCount` | integer \| null | Number of reviews |
| `isVerified` | boolean | Whether the listing is JustDial-verified |
| `hasWebsite` | boolean | Whether the business has a website listed |
| `websiteUrl` | string \| null | Website URL if present |
| `profileUrl` | string \| null | Full JustDial profile URL |
| `openNow` | boolean \| null | Open/closed status at scrape time |
| `yearsInBusiness` | integer \| null | Years since establishment |

### Example output record

```json
{
  "businessName": "Spice Garden Restaurant",
  "category": "Restaurants",
  "phone": "9876543210",
  "address": "12, MG Road, Opposite Central Mall, Andheri West, Mumbai",
  "locality": "Andheri West",
  "city": "Mumbai",
  "rating": 4.2,
  "reviewCount": 318,
  "isVerified": true,
  "hasWebsite": true,
  "websiteUrl": "https://www.spicegarden.in",
  "profileUrl": "https://www.justdial.com/Mumbai/Spice-Garden-Restaurant/...",
  "openNow": true,
  "yearsInBusiness": 12
}
```

---

## Technical notes

### Phone number decoding

JustDial obfuscates phone numbers with CSS `:before` pseudo-elements. Each digit is stored in a `<span>` with a class that maps to a character via the page's inline `<style>` block. The actor:

1. Extracts the `{class → character}` mapping from every `<style>` tag.
2. Walks each phone-number container's spans to reconstruct digits.
3. Falls back to `tel:` href links if the mapping yields nothing.

### Anti-scraping

- **Proxy rotation** — pass `proxyConfiguration` with `RESIDENTIAL` group for best results.
- **User-agent rotation** — 10 realistic desktop/mobile UAs, picked randomly per request.
- **Random delays** — 1.5–3 s between page requests.
- **Automatic retries** — up to 3 retries per failed request (handled by Crawlee).
- **CAPTCHA detection** — the actor logs a clear error and skips the page rather than crashing.

### Pagination

JustDial search results are split across pages. The actor automatically discovers and queues the next-page URL until `maxResults` is reached.

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires Apify CLI or APIFY_TOKEN env var for storage)
python -m src
```

Set `APIFY_TOKEN` in your environment or use the Apify CLI (`apify run`) to persist results to the Apify platform.

---

## Limitations

- JustDial occasionally serves a CAPTCHA — residential proxies reduce (but don't eliminate) this.
- JustDial's HTML structure changes periodically; if zero results are returned, the CSS selectors in `src/parser.py` may need updating.
- Phone numbers are only decoded when JustDial includes its CSS mapping on the page. Some pages omit it, resulting in `null` phone fields.
