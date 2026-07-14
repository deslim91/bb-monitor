"""Toys"R"Us Malaysia — Salesforce Commerce Cloud (Demandware).

Product tiles are server-rendered on category pages. Each tile carries a
data-pid and the tile text includes price + availability badges.
Appending ?sz=200 to the category URL returns the full grid in one page.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .base import Product, fetch, dump_debug, classify_status, clean, UNKNOWN, AVAILABLE

SITE_ID = "toysrus"

# SFCC AJAX endpoint that returns just the product grid HTML.
# cgid is the category id — for /beyblade/ it is normally "beyblade".
GRID_FALLBACK = ("https://www.toysrus.com.my/on/demandware.store/"
                 "Sites-ToysRUs_MY-Site/en_MY/Search-UpdateGrid"
                 "?cgid=beyblade&start=0&sz=200")


def _parse(html: str) -> dict[str, Product]:
    products: dict[str, Product] = {}
    soup = BeautifulSoup(html, "html.parser")

    tiles = soup.select("[data-pid]")
    if not tiles:
        tiles = soup.select("div.product-tile, div.product, div.grid-tile")

    for tile in tiles:
        pid = tile.get("data-pid") or ""
        link = tile.select_one("a[href*='.html']")
        if not link:
            continue
        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://www.toysrus.com.my" + href

        name_el = tile.select_one(".pdp-link a, .product-name, a.link") or link
        name = clean(name_el.get_text(" "))
        if not name:
            continue

        price_el = tile.select_one(".sales .value, .price .value, .price")
        price = clean(price_el.get_text(" ")) if price_el else ""

        tile_text = clean(tile.get_text(" "))
        status = classify_status(tile_text)
        # SFCC listing pages often hide availability; a purchasable tile
        # with a price and no OOS badge is treated as available.
        if status == UNKNOWN and price:
            status = AVAILABLE
        # Pre-orders on TRU MY are flagged in the product name itself.
        if "pre order" in name.lower() or "pre-order" in name.lower():
            status = "preorder"

        key = f"{SITE_ID}:{pid or href}"
        products[key] = Product(
            site=SITE_ID, key=key, name=name, url=href,
            price=price, status=status,
        )
    return products


def scrape(urls: list[str]) -> list[Product]:
    products: dict[str, Product] = {}
    last_html, last_url = "", ""
    for url in urls:
        html = fetch(url)
        last_html, last_url = html, url
        products.update(_parse(html))

    if not products:
        # Category page yielded nothing — try the AJAX grid endpoint
        try:
            html = fetch(GRID_FALLBACK)
            products.update(_parse(html))
            if products:
                print(f"[{SITE_ID}] category page empty; AJAX grid fallback "
                      f"worked ({len(products)} items)")
        except Exception as e:  # noqa: BLE001
            print(f"[{SITE_ID}] AJAX grid fallback failed: {e}")

    if not products and last_html:
        dump_debug(SITE_ID, last_html, last_url)
    return list(products.values())
