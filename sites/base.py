"""Shared base for all site adapters."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-MY,en;q=0.9",
}

# Normalized statuses
AVAILABLE = "available"
PREORDER = "preorder"
OOS = "out_of_stock"
UNKNOWN = "unknown"


@dataclass
class Product:
    site: str          # site id from config
    key: str           # stable unique key (site + slug/pid)
    name: str
    url: str
    price: str = ""    # display string, e.g. "MYR 79.90"
    status: str = UNKNOWN

    def to_dict(self):
        return asdict(self)


def fetch(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def classify_status(text: str) -> str:
    """Map raw availability text to a normalized status."""
    t = text.lower()
    if any(k in t for k in ("pre order", "pre-order", "preorder")):
        return PREORDER
    if any(k in t for k in ("out of stock", "sold out", "unavailable", "notify me", "oos")):
        return OOS
    if any(k in t for k in ("add to cart", "in stock", "available", "buy now")):
        return AVAILABLE
    return UNKNOWN


def matches_keywords(name: str, keywords: list[str]) -> bool:
    n = name.lower()
    return any(k.lower() in n for k in keywords)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
