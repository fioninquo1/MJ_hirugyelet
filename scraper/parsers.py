import calendar
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import unquote

import feedparser
from bs4 import BeautifulSoup


def extract_image_from_html(html_string: str) -> Optional[str]:
    """Extract the first image URL from an HTML string."""
    if not html_string:
        return None
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_string)
    return match.group(1) if match else None


def _get_entry_image(entry) -> Optional[str]:
    """Try multiple sources to find an article image from an RSS entry."""
    # 1. enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/") or enc.get("href", "").endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                return enc.get("href")

    # 2. media:content
    if hasattr(entry, "media_content") and entry.media_content:
        return entry.media_content[0].get("url")

    # 3. media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")

    # 4. Extract from summary/content HTML
    for field in ("summary", "description"):
        val = getattr(entry, field, None)
        if val:
            img = extract_image_from_html(val)
            if img:
                return img

    if hasattr(entry, "content") and entry.content:
        img = extract_image_from_html(entry.content[0].get("value", ""))
        if img:
            return img

    return None


def _parse_date(entry) -> Optional[str]:
    """Parse the published date from an RSS entry to ISO 8601."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = calendar.timegm(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OverflowError):
            pass

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            ts = calendar.timegm(entry.updated_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OverflowError):
            pass

    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)


def parse_rss(config, content: str) -> list[dict]:
    """Parse an RSS feed and return a list of article dicts."""
    feed = feedparser.parse(content)
    articles = []

    for entry in feed.entries[: config.max_articles]:
        title = getattr(entry, "title", None)
        if not title:
            continue

        link = getattr(entry, "link", None)
        if not link:
            continue

        category = None
        if hasattr(entry, "tags") and entry.tags:
            category = entry.tags[0].get("term")

        author = getattr(entry, "author", None) or getattr(entry, "dc_creator", None)

        description = _strip_html(getattr(entry, "summary", "") or "")
        # Truncate long descriptions
        if len(description) > 300:
            description = description[:297] + "..."

        articles.append(
            {
                "title": title.strip(),
                "url": link.strip(),
                "published": _parse_date(entry),
                "description": description,
                "image": _get_entry_image(entry),
                "category": category,
                "author": author,
            }
        )

    return articles


def parse_hungarian_relative_date(text: str) -> Optional[str]:
    """Parse Hungarian relative date strings like '2 perce', '1 órája', 'Ma 10:30'."""
    if not text:
        return None
    text = text.strip()
    now = datetime.now(tz=timezone(timedelta(hours=1)))  # CET

    # "X perce" (X minutes ago)
    m = re.match(r"(\d+)\s*perc", text)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).isoformat()

    # "X órája" (X hours ago)
    m = re.match(r"(\d+)\s*[oó]r[aá]", text)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).isoformat()

    # "Ma HH:MM" (today)
    m = re.match(r"[Mm]a\s+(\d{1,2}):(\d{2})", text)
    if m:
        return now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0).isoformat()

    # "Tegnap HH:MM" (yesterday)
    m = re.match(r"[Tt]egnap\s+(\d{1,2}):(\d{2})", text)
    if m:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(
            hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0
        ).isoformat()

    # "YYYY.MM.DD. HH:MM" or "YYYY.MM.DD HH:MM"
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})\.?\s+(\d{1,2}):(\d{2})", text)
    if m:
        return datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
            tzinfo=timezone(timedelta(hours=1)),
        ).isoformat()

    # "YYYY.MM.DD."
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", text)
    if m:
        return datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            tzinfo=timezone(timedelta(hours=1)),
        ).isoformat()

    return None


def parse_kontroll(config, html: str) -> list[dict]:
    """Parse kontroll.hu front page - targets the 'Friss hirek' section with timestamps."""
    soup = BeautifulSoup(html, "lxml")
    articles = []
    seen_urls = set()

    # Find the "Friss hirek" section - it has items with timestamp + article link
    # Structure: div > div.font-roboto-slab.text-sm (timestamp) + div > a[href^="/cikk/"]
    friss_section = None
    for el in soup.find_all(string=re.compile(r"Friss h")):
        parent = el.parent
        if parent and "text-center" in " ".join(parent.get("class", [])):
            friss_section = parent.parent
            break

    if friss_section:
        for item in friss_section.select("div.min-w-\\[75vw\\], div.pb-2"):
            # Timestamp: first div with text-sm class
            time_div = item.find(
                "div", class_=lambda c: c and "text-sm" in c
            )
            time_text = time_div.get_text(strip=True) if time_div else None

            # Article link
            link = item.select_one('a[href^="/cikk/"]')
            if not link:
                continue
            href = link.get("href", "")
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if not title:
                continue

            published = parse_hungarian_relative_date(time_text) if time_text else None

            # Category from URL: /cikk/{category}/...
            category = None
            cat_match = re.search(r"/cikk/(\w+)/", href)
            if cat_match:
                category = cat_match.group(1).capitalize()

            articles.append({
                "title": title,
                "url": config.selectors["url_prefix"] + href,
                "published": published,
                "description": None,
                "image": None,
                "category": category,
                "author": None,
            })

            if len(articles) >= config.max_articles:
                break

    # If Friss section didn't yield enough, also grab featured hero articles
    if len(articles) < 5:
        for link in soup.select('a[href^="/cikk/"]'):
            href = link.get("href", "")
            if not href or href in seen_urls:
                continue
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            seen_urls.add(href)

            # Only include today/yesterday from URL date
            date_match = re.search(r"/cikk/\w+/(\d{4})/(\d{2})/(\d{2})/", href)
            if not date_match:
                continue
            now = datetime.now(tz=timezone(timedelta(hours=1)))
            article_date = datetime(
                int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)),
                tzinfo=timezone(timedelta(hours=1)),
            )
            if (now - article_date).days > 1:
                continue

            articles.append({
                "title": title,
                "url": config.selectors["url_prefix"] + href,
                "published": article_date.isoformat(),
                "description": None,
                "image": None,
                "category": None,
                "author": None,
            })

            if len(articles) >= config.max_articles:
                break

    return articles


def _parse_origo_sitemap(sitemap_xml: str, url_prefix: str, cat_map: dict) -> list[dict]:
    """Parse Origo news_sitemap.xml entries into article dicts."""
    soup = BeautifulSoup(sitemap_xml, "lxml-xml")
    articles = []

    for url_el in soup.find_all("url"):
        loc = url_el.find("loc")
        if not loc:
            continue
        full_url = loc.get_text(strip=True)

        news = url_el.find("news:news") or url_el.find("news")
        if not news:
            continue

        title_el = news.find("news:title") or news.find("title")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        date_el = news.find("news:publication_date") or news.find("publication_date")
        published = date_el.get_text(strip=True) if date_el else None

        # Category from URL path
        category = None
        path = full_url.replace(url_prefix, "")
        cat_match = re.match(r"/(\w[\w-]*)/", path)
        if cat_match:
            category = cat_map.get(cat_match.group(1), cat_match.group(1).capitalize())

        articles.append({
            "title": title,
            "url": full_url,
            "published": published,
            "description": None,
            "image": None,
            "category": category,
            "author": None,
        })

    return articles


def parse_origo(config, html: str, sitemap_xml: str = None) -> list[dict]:
    """Parse origo.hu/24 page + news_sitemap.xml for full coverage.

    The /24 page gives ~10 Featured cards with images, descriptions, and HH:MM
    timestamps. The sitemap fills up to max_articles with precise ISO timestamps.
    """
    soup = BeautifulSoup(html, "lxml")
    articles = []
    seen_urls = set()
    url_prefix = config.selectors["url_prefix"]
    now = datetime.now(tz=timezone(timedelta(hours=1)))  # CET

    cat_map = {
        "belpol": "Belpolitika",
        "nagyvilag": "Nagyvilág",
        "kulpol": "Külpolitika",
        "gazdasag": "Gazdaság",
        "sport": "Sport",
        "auto": "Autó",
        "techbazis": "Tech",
        "szorakozas": "Szórakozás",
        "teve": "TV",
        "kek-hirek": "Kék hírek",
    }

    # --- Phase 1: /24 page Featured cards (rich data: images, descriptions) ---
    for card in soup.select(".article-card"):
        style_classes = " ".join(card.get("class", []))
        if "Featured" not in style_classes:
            continue
        if "FeaturedImgTitle" in style_classes and "FeaturedBigImgTitle" not in style_classes:
            continue

        link_el = card.select_one(".article-card-link")
        if not link_el:
            continue
        href = link_el.get("href", "").strip()
        if not href or not href.startswith("/"):
            continue

        full_url = url_prefix + href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title_el = card.select_one(".article-card-title")
        title = title_el.get_text(strip=True) if title_el else None
        if not title or len(title) < 5:
            continue

        lead_el = card.select_one(".article-card-lead")
        description = lead_el.get_text(strip=True) if lead_el else None

        published = None
        date_el = card.select_one(".article-card-publish-date")
        if date_el:
            time_text = date_el.get_text(strip=True)
            time_match = re.match(r"(\d{1,2}):(\d{2})", time_text)
            if time_match:
                published = now.replace(
                    hour=int(time_match.group(1)),
                    minute=int(time_match.group(2)),
                    second=0,
                    microsecond=0,
                ).isoformat()

        category = None
        tag_el = card.select_one(".article-card-tag")
        if tag_el:
            category = tag_el.get_text(strip=True)
        else:
            cat_match = re.match(r"/(\w[\w-]*)/", href)
            if cat_match:
                category = cat_map.get(cat_match.group(1), cat_match.group(1).capitalize())

        image = None
        img_el = card.select_one("img")
        if img_el:
            src = img_el.get("src") or ""
            if src and not src.startswith("data:"):
                image = src if src.startswith("http") else url_prefix + src

        articles.append({
            "title": title,
            "url": full_url,
            "published": published,
            "description": description,
            "image": image,
            "category": category,
            "author": None,
        })

    # --- Phase 2: Fill from sitemap (precise ISO timestamps) ---
    if sitemap_xml and len(articles) < config.max_articles:
        sitemap_articles = _parse_origo_sitemap(sitemap_xml, url_prefix, cat_map)
        for sa in sitemap_articles:
            if sa["url"] in seen_urls:
                continue
            seen_urls.add(sa["url"])
            articles.append(sa)
            if len(articles) >= config.max_articles:
                break

    return articles


def parse_24hu(config, html: str) -> list[dict]:
    """Parse 24.hu/hirfolyam page.

    Structure: date headers (h2.m-nonstopWidget__entryDate "2026.03.02.")
    followed by article lists. Each article has a time div
    (div.m-nonstopWidget__entryTime "12:18").
    """
    soup = BeautifulSoup(html, "lxml")
    articles = []
    seen_urls = set()

    # Find the main feed container
    feed = soup.select_one(".m-nonstopWidget__wrap .m-feedBox")
    if not feed:
        feed = soup

    current_date = None

    # Iterate through direct children to track date headers
    for element in feed.children:
        if not hasattr(element, "name") or not element.name:
            continue

        # Date header: <h2 class="m-nonstopWidget__entryDate">2026.03.02.</h2>
        if element.name == "h2" and "m-nonstopWidget__entryDate" in " ".join(
            element.get("class", [])
        ):
            date_text = element.get_text(strip=True)
            date_match = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", date_text)
            if date_match:
                current_date = (
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3)),
                )
            continue

        # Article list: <ul class="m-nonstopWidget__list">
        if element.name == "ul" and "m-nonstopWidget__list" in " ".join(
            element.get("class", [])
        ):
            for article in element.select("article.m-articleWidget__wrap"):
                if len(articles) >= config.max_articles:
                    break

                # Title + URL
                link_el = article.select_one("a.m-articleWidget__link")
                if not link_el:
                    continue
                href = link_el.get("href", "").strip()
                if not href:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                title = link_el.get_text(strip=True)
                if not title:
                    continue

                # Time: div.m-nonstopWidget__entryTime
                published = None
                time_el = article.select_one(".m-nonstopWidget__entryTime")
                if time_el and current_date:
                    time_text = time_el.get_text(strip=True)
                    time_match = re.match(r"(\d{1,2}):(\d{2})", time_text)
                    if time_match:
                        published = datetime(
                            current_date[0],
                            current_date[1],
                            current_date[2],
                            int(time_match.group(1)),
                            int(time_match.group(2)),
                            tzinfo=timezone(timedelta(hours=1)),
                        ).isoformat()

                # If no time element, try date from URL
                if not published and current_date:
                    published = datetime(
                        current_date[0],
                        current_date[1],
                        current_date[2],
                        tzinfo=timezone(timedelta(hours=1)),
                    ).isoformat()

                # Category
                category = None
                cat_el = article.select_one(".m-nonstopWidget__entryCategory a")
                if cat_el:
                    category = cat_el.get_text(strip=True)

                # Author
                author = None
                author_el = article.select_one(".m-nonstopWidget__entryAuthorName a")
                if author_el:
                    author = author_el.get_text(strip=True)

                # Description/lead
                lead_el = article.select_one(".m-articleWidget__lead")
                description = lead_el.get_text(strip=True) if lead_el else None
                if description and len(description) > 300:
                    description = description[:297] + "..."

                # Image
                image = None
                img_el = article.select_one("img.wp-post-image")
                if img_el:
                    src = img_el.get("src") or ""
                    if src and not src.startswith("data:"):
                        image = src

                articles.append({
                    "title": title,
                    "url": href,
                    "published": published,
                    "description": description,
                    "image": image,
                    "category": category,
                    "author": author,
                })

            if len(articles) >= config.max_articles:
                break

    return articles
