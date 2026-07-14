"""Toy Garden — Next.js storefront (SiteGiant platform).

Products are NOT in the visible HTML; they load client-side. Strategy:
  1. Parse the __NEXT_DATA__ JSON blob embedded in the raw HTML and walk it
     for anything that looks like a product list.
  2. If that yields nothing, log a warning so you can inspect
     debug_toygarden.html from the workflow artifacts and adjust.

This is the adapter most likely to need a one-time tweak — see README.
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .base import Product, fetch, clean, AVAILABLE, OOS, PREORDER, UNKNOWN

SITE_ID = "toygarden"
BASE = "https://www.toygarden.com"

NAME_KEYS = ("name", "product_name", "title", "productName")
PRICE_KEYS = ("price", "sale_price", "selling_price", "display_price", "final_price")
URL_KEYS = ("url", "slug", "seo_url", "product_url", "handle")
STOCK_KEYS = ("stock", "quantity", "qty", "stock_status", "availability",
              "is_in_stock", "in_stock", "sold_out")


def _status_from_obj(obj: dict) -> str:
    for k in STOCK_KEYS:
        if k in obj:
            v = obj[k]
            if isinstance(v, bool):
                if k == "sold_out":
                    return OOS if v else AVAILABLE
                return AVAILABLE if v else OOS
            if isinstance(v, (int, float)):
                return AVAILABLE if v > 0 else OOS
            if isinstance(v, str):
                s = v.lower()
                if "pre" in s:
                    return PREORDER
                if any(x in s for x in ("out", "sold", "0")):
                    return OOS
                if any(x in s for x in ("in stock", "available", "1", "true")):
                    return AVAILABLE
    return UNKNOWN


def _looks_like_product(obj) -> bool:
    return (
        isinstance(obj, dict)
        and any(k in obj for k in NAME_KEYS)
        and (any(k in obj for k in PRICE_KEYS) or any(k in obj for k in URL_KEYS))
    )


def _walk(node, found: list[dict]):
    if isinstance(node, dict):
        if _looks_like_product(node):
            found.append(node)
        for v in node.values():
            _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


def _first(obj: dict, keys) -> str:
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return str(obj[k])
    return ""


def scrape(urls: list[str]) -> list[Product]:
    products: dict[str, Product] = {}
    for url in urls:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        raw = None
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag and tag.string:
            raw = tag.string
        else:
            # Next 13+ app router streams data via self.__next_f.push chunks
            chunks = re.findall(
                r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)', html, re.S
            )
            if chunks:
                raw = "".join(c.encode().decode("unicode_escape") for c in chunks)

        found: list[dict] = []
        if raw:
            if raw.lstrip().startswith("{"):
                try:
                    _walk(json.loads(raw), found)
                except json.JSONDecodeError:
                    pass
            if not found:
                # Scan for embedded JSON objects containing a product-ish shape
                for m in re.finditer(r'\{"[^"]*(?:product|name)[^"]*":.{0,20000}?\}', raw):
                    try:
                        _walk(json.loads(m.group(0)), found)
                    except json.JSONDecodeError:
                        continue

        if not found:
            with open("debug_toygarden.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[toygarden] WARNING: no products parsed from {url}. "
                  f"Saved debug_toygarden.html — see README 'Fixing a parser'.")
            continue

        for obj in found:
            name = clean(_first(obj, NAME_KEYS))
            if not name:
                continue
            slug = _first(obj, URL_KEYS)
            href = slug if slug.startswith("http") else f"{BASE}/product/{slug.lstrip('/')}"
            price = _first(obj, PRICE_KEYS)
            if price and not price.upper().startswith(("RM", "MYR")):
                price = f"RM {price}"
            key = f"{SITE_ID}:{slug or name}"
            products[key] = Product(
                site=SITE_ID, key=key, name=name, url=href,
                price=price, status=_status_from_obj(obj),
            )
    return list(products.values())
