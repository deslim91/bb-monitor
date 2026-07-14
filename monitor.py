"""Beyblade X Stock Monitor — main entry point.

Scrapes every enabled site, diffs against state.json, sends grouped
Telegram alerts, then writes state.json back (committed by the workflow).
"""
from __future__ import annotations

import json
import os
import sys
import traceback

import requests
import yaml

from sites import ADAPTERS
from sites.base import Product, matches_keywords, AVAILABLE, PREORDER, OOS

STATE_FILE = "state.json"
CONFIG_FILE = "config.yaml"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# ---------------------------------------------------------------- telegram
def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[dry-run] Telegram message:\n" + text)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram hard-limits messages to 4096 chars — chunk if needed
    for i in range(0, len(text), 3900):
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text[i:i + 3900],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        if r.status_code != 200:
            print(f"Telegram error {r.status_code}: {r.text}")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def line(p: Product) -> str:
    price = f" — {esc(p.price)}" if p.price else ""
    return f'• <a href="{p.url}">{esc(p.name)}</a>{price}'


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------- main
def main() -> int:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    keywords = cfg.get("keywords", [])
    # Normalize watchlist: strings -> default rule; dicts -> scoped rule
    watchlist = []
    for w in cfg.get("watchlist", []) or []:
        if isinstance(w, str):
            watchlist.append({"match": w.lower(), "sites": None,
                              "statuses": [AVAILABLE, PREORDER]})
        else:
            watchlist.append({
                "match": str(w.get("match", "")).lower(),
                "sites": w.get("sites") or None,
                "statuses": w.get("statuses") or [AVAILABLE, PREORDER],
            })
    watchlist = [w for w in watchlist if w["match"]]
    notify_cfg = cfg.get("notify", {})
    first_run = not os.path.exists(STATE_FILE)

    state = load_state()
    new_state: dict = {}
    events = {"new": [], "restock": [], "preorder": [], "oos": [], "price": []}
    priority: list[str] = []
    errors: list[str] = []
    site_names = {s["id"]: s.get("name", s["id"]) for s in cfg["sites"]}

    for site in cfg["sites"]:
        if not site.get("enabled", True):
            continue
        sid = site["id"]
        scraper = ADAPTERS.get(sid)
        if not scraper:
            errors.append(f"{sid}: no adapter registered in sites/__init__.py")
            continue
        try:
            found = scraper(site.get("urls", []))
        except Exception:
            errors.append(f"{sid}: {traceback.format_exc(limit=2)}")
            continue

        kept = [p for p in found if matches_keywords(p.name, keywords)]
        print(f"[{sid}] scraped {len(found)} items, {len(kept)} match keywords")

        for p in kept:
            new_state[p.key] = p.to_dict()
            old = state.get(p.key)
            tag = f"[{site_names.get(p.site, p.site)}] "

            if old is None:
                if not first_run:
                    events["new"].append(tag + line(p))
                    if p.status == PREORDER:
                        events["preorder"].append(tag + line(p))
            else:
                was, now = old.get("status"), p.status
                if was != now:
                    if now == AVAILABLE and was in (OOS, "unknown"):
                        events["restock"].append(tag + line(p))
                    elif now == PREORDER and was != PREORDER:
                        events["preorder"].append(tag + line(p))
                    elif now == OOS and was == AVAILABLE:
                        events["oos"].append(tag + line(p))
                if old.get("price") and p.price and old["price"] != p.price:
                    events["price"].append(
                        f"{tag}{line(p)} (was {esc(old['price'])})")

            # Watchlist: rule-based priority alerts
            for rule in watchlist:
                if rule["match"] not in p.name.lower():
                    continue
                if rule["sites"] and p.site not in rule["sites"]:
                    continue
                hit = p.status in rule["statuses"] and (
                    old is None or old.get("status") not in rule["statuses"]
                )
                if hit and not first_run:
                    priority.append(tag + line(p) + f" — <b>{p.status}</b>")
                break

    # Carry forward items from sites that errored so we don't lose state
    for key, val in state.items():
        sid = val.get("site")
        if any(e.startswith(f"{sid}:") for e in errors) and key not in new_state:
            new_state[key] = val

    save_state(new_state)

    # ---------------- build messages ----------------
    if priority:
        send_telegram("🔥 <b>PRIORITY — watchlist item orderable!</b>\n" +
                      "\n".join(priority))

    parts = []
    if notify_cfg.get("new_listing", True) and events["new"]:
        parts.append("🆕 <b>New listings</b>\n" + "\n".join(events["new"]))
    if notify_cfg.get("restock", True) and events["restock"]:
        parts.append("🟢 <b>Restocked</b>\n" + "\n".join(events["restock"]))
    if notify_cfg.get("preorder_open", True) and events["preorder"]:
        parts.append("🟡 <b>Pre-orders</b>\n" + "\n".join(events["preorder"]))
    if notify_cfg.get("out_of_stock", False) and events["oos"]:
        parts.append("🔴 <b>Went out of stock</b>\n" + "\n".join(events["oos"]))
    if notify_cfg.get("price_change", True) and events["price"]:
        parts.append("💰 <b>Price changes</b>\n" + "\n".join(events["price"]))

    if parts:
        send_telegram("\n\n".join(parts))

    if first_run:
        n = len(new_state)
        send_telegram(f"✅ Monitor is live! Baseline captured: {n} Beyblade "
                      f"items across {len([s for s in cfg['sites'] if s.get('enabled')])} sites. "
                      f"You'll be pinged on changes from now on.")

    if errors:
        print("ERRORS:\n" + "\n---\n".join(errors))
        # Only nag about errors once per day (03:00–03:15 UTC window)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.hour == 3 and now.minute < 20:
            send_telegram("⚠️ Monitor had scraper errors today:\n" +
                          "\n".join(e.splitlines()[0] for e in errors))

    return 0


if __name__ == "__main__":
    sys.exit(main())
