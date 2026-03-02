from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PortalConfig:
    id: str
    name: str
    url: str
    color: str
    feed_url: Optional[str]
    scrape_type: str  # "rss" or "html"
    max_articles: int = 25
    selectors: dict = field(default_factory=dict)


PORTALS = [
    PortalConfig(
        id="telex",
        name="Telex.hu",
        url="https://telex.hu",
        color="#2ec4b6",
        feed_url="https://telex.hu/rss",
        scrape_type="rss",
    ),
    PortalConfig(
        id="444",
        name="444.hu",
        url="https://444.hu",
        color="#e6db00",
        feed_url="https://444.hu/feed",
        scrape_type="rss",
    ),
    PortalConfig(
        id="index",
        name="Index.hu",
        url="https://index.hu",
        color="#f26522",
        feed_url="https://index.hu/24ora/rss/",
        scrape_type="rss",
    ),
    PortalConfig(
        id="magyarnemzet",
        name="Magyar Nemzet",
        url="https://magyarnemzet.hu",
        color="#ffffff",
        feed_url="https://magyarnemzet.hu/feed",
        scrape_type="rss",
    ),
    PortalConfig(
        id="mandiner",
        name="Mandiner",
        url="https://mandiner.hu",
        color="#c46a2f",
        feed_url="https://mandiner.hu/rss",
        scrape_type="rss",
    ),
    PortalConfig(
        id="24hu",
        name="24.hu",
        url="https://24.hu/hirfolyam/",
        color="#888888",
        feed_url=None,
        scrape_type="html",
        selectors={
            "url_prefix": "https://24.hu",
        },
    ),
    PortalConfig(
        id="neokohn",
        name="Neokohn",
        url="https://neokohn.hu",
        color="#5ba8d6",
        feed_url="https://neokohn.hu/feed/",
        scrape_type="rss",
    ),
    PortalConfig(
        id="hvg",
        name="HVG",
        url="https://hvg.hu",
        color="#f26522",
        feed_url="https://hvg.hu/rss",
        scrape_type="rss",
    ),
    PortalConfig(
        id="kontroll",
        name="Kontroll.hu",
        url="https://kontroll.hu",
        color="#22c55e",
        feed_url=None,
        scrape_type="html",
        selectors={
            "article_link": 'a[href^="/cikk/"]',
            "category_link": 'a[href^="/rovat/"]',
            "image": "img",
            "url_prefix": "https://kontroll.hu",
            "date_from_url_pattern": r"/cikk/\w+/(\d{4})/(\d{2})/(\d{2})/",
        },
    ),
    PortalConfig(
        id="origo",
        name="Origo",
        url="https://www.origo.hu/24",
        color="#0033a0",
        feed_url=None,
        scrape_type="html",
        selectors={
            "url_prefix": "https://www.origo.hu",
            "sitemap_url": "https://www.origo.hu/news_sitemap.xml",
        },
    ),
]
