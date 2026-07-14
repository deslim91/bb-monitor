"""Kelab Gasing Beyblade — server-rendered Laravel shop.

Product cards are anchors to /products/<slug> whose text contains:
    "[ Starter ] BX-01 DRAN SWORD 3-60F MYR 79.90 Out of Stock"
    "[ Booster ] BX-06 KNIGHT SHIELD 3-80N MYR 54.90 Add to Cart"
Category pages may paginate via ?page=N — we follow rel=next links.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Product, fetch, classify_status, clean

SITE_ID = "kelabgasing"
PRICE_RE = re.compile(r"(MYR|RM)\s*[\d,]+(?:\.\d{2})?", re.I)
MAX_PAGES = 10


def _parse_page(html: str, page_url: str, products: dict[str, Product]) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select("a[href*='/products/']"):
        href = urljoin(page_url, a.get("href", ""))
        slug = href.rstrip("/").split("/")[-1]
        text = clean(a.get_text(" "))
        if not text or len(text) < 5:
            continue

        m = PRICE_RE.search(text)
        price = m.group(0) if m else ""
        status = classify_status(text)

        # Name = text before the price
        name = clean(text[: m.start()] if m else text)
        # Strip trailing status words if no price matched
        for suffix in ("Out of Stock", "Add to Cart", "Pre Order", "Pre-Order"):
            if name.lower().endswith(suffix.lower()):
                name = clean(name[: -len(suffix)])
        if not name:
            continue

        key = f"{SITE_ID}:{slug}"
        # Keep the richest record if the same product shows on multiple pages
        if key not in products or (price and not products[key].price):
            products[key] = Product(
                site=SITE_ID, key=key, name=name, url=href,
                price=price, status=status,
            )

    nxt = soup.select_one("a[rel='next'], .pagination a[rel='next']")
    return urljoin(page_url, nxt["href"]) if nxt and nxt.get("href") else None


def scrape(urls: list[str]) -> list[Product]:
    products: dict[str, Product] = {}
    for url in urls:
        page_url, pages = url, 0
        while page_url and pages < MAX_PAGES:
            html = fetch(page_url)
            page_url = _parse_page(html, page_url, products)
            pages += 1
    return list(products.values())
