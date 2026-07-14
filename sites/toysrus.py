"""Toys"R"Us Malaysia — Salesforce Commerce Cloud (Demandware).

Product tiles are server-rendered on category pages. Each tile carries a
data-pid and the tile text includes price + availability badges.
Appending ?sz=200 to the category URL returns the full grid in one page.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .base import Product, fetch, classify_status, clean, UNKNOWN, AVAILABLE

SITE_ID = "toysrus"


def scrape(urls: list[str]) -> list[Product]:
    products: dict[str, Product] = {}
    for url in urls:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        tiles = soup.select("[data-pid]")
        if not tiles:
            # Fallback: any product detail links in the grid
            tiles = soup.select("div.product-tile, div.product")

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
    return list(products.values())
