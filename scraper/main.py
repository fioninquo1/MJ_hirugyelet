import asyncio
import json
import os
from datetime import datetime, timezone

import aiohttp

from scraper.portals import PORTALS
from scraper.parsers import parse_rss, parse_kontroll, parse_origo, parse_24hu

TIMEOUT = aiohttp.ClientTimeout(total=15)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "news.json")
USER_AGENT = "MJ-Scraper/1.0 (GitHub Actions news aggregator)"


async def fetch_portal(session: aiohttp.ClientSession, portal) -> dict:
    """Fetch and parse a single portal. Returns dict for JSON output."""
    url = portal.feed_url if portal.feed_url else portal.url
    try:
        async with session.get(url, timeout=TIMEOUT, ssl=False) as response:
            response.raise_for_status()
            content = await response.text()

        if portal.scrape_type == "rss":
            articles = parse_rss(portal, content)
        elif portal.id == "kontroll":
            articles = parse_kontroll(portal, content)
        elif portal.id == "origo":
            # Also fetch news sitemap for additional articles beyond the /24 page
            sitemap_xml = None
            sitemap_url = portal.selectors.get("sitemap_url")
            if sitemap_url:
                try:
                    async with session.get(sitemap_url, timeout=TIMEOUT, ssl=False) as resp:
                        resp.raise_for_status()
                        sitemap_xml = await resp.text()
                except Exception:
                    pass
            articles = parse_origo(portal, content, sitemap_xml=sitemap_xml)
        elif portal.id == "24hu":
            articles = parse_24hu(portal, content)
        else:
            articles = []

        return {
            "id": portal.id,
            "name": portal.name,
            "url": portal.url,
            "color": portal.color,
            "status": "ok",
            "error": None,
            "article_count": len(articles),
            "articles": articles,
        }
    except Exception as e:
        return {
            "id": portal.id,
            "name": portal.name,
            "url": portal.url,
            "color": portal.color,
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)}",
            "article_count": 0,
            "articles": [],
        }


async def scrape_all() -> dict:
    """Scrape all portals in parallel and write JSON output."""
    headers = {"User-Agent": USER_AGENT}
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [fetch_portal(session, portal) for portal in PORTALS]
        results = await asyncio.gather(*tasks)

    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "portals": list(results),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Print summary
    ok_count = 0
    for r in results:
        status = "OK" if r["status"] == "ok" else "FAIL"
        print(f"  [{status}] {r['name']}: {r['article_count']} articles")
        if r["error"]:
            print(f"         Error: {r['error']}")
        if r["status"] == "ok":
            ok_count += 1

    print(f"\n  {ok_count}/{len(results)} portals OK")
    return output


def main():
    print("Starting scrape...")
    asyncio.run(scrape_all())
    print(f"Done. Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
