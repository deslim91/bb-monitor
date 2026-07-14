# 🌀 Beyblade X Stock Monitor (Malaysia)

Watches multiple MY toy stores for Beyblade X stock and pings you on
Telegram. Runs free on GitHub Actions every ~15 minutes — no server,
no PC left running.

**Sites out of the box**

| Site | Method | Status |
|---|---|---|
| Toys"R"Us MY | Server-rendered SFCC tiles | ✅ |
| Kelab Gasing Beyblade | Server-rendered product links | ✅ |
| Toy Garden | Next.js embedded JSON | ⚠️ may need one-time tweak |

**Alert types:** 🆕 new listing · 🟢 restock · 🟡 pre-order · 💰 price change
· 🔥 PRIORITY (watchlist item becomes orderable)

---

## Setup (~10 min)

1. **Create a Telegram bot** — message [@BotFather](https://t.me/BotFather),
   send `/newbot`, copy the **bot token**.
2. **Get your chat ID** — message your new bot anything, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy
   `message.chat.id`.
3. **Create a private GitHub repo** and push these files.
4. **Add secrets** — repo → Settings → Secrets and variables → Actions:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. **Run it** — Actions tab → *Beyblade Stock Monitor* → *Run workflow*.
   First run captures a baseline and sends **"✅ Monitor is live!"**.
   After that, you only get pinged on changes.

---

## The data file: `config.yaml`

Everything you'll edit day-to-day lives here — commit a change and the
next run picks it up (you can edit it straight in the GitHub mobile app).

- **`watchlist`** — add product names/codes you're hunting
  (e.g. `"UX-20"`, `"Glory Valkyrie"`). Watched items trigger a separate
  🔥 PRIORITY ping the moment they become orderable anywhere.
- **`keywords`** — the global filter; anything not matching is ignored.
- **`sites`** — flip `enabled: false` to pause a store, or add URLs
  (e.g. another TRU category page) under an existing site.
- **`notify`** — toggle alert types. `out_of_stock` is off by default.

## Adding a whole new store later

1. Copy `sites/kelabgasing.py` → `sites/mystore.py` and adjust the
   parsing (that file is the simplest template).
2. Register it in `sites/__init__.py` (one line).
3. Add an entry in `config.yaml` with the same `id`.

Shopify-based stores are even easier: fetch `https://store.com/products.json`
and read `variants[].available` — no HTML parsing at all.
(Shopee/Lazada are bot-protected; not recommended here.)

## Fixing a parser (esp. Toy Garden)

If a site changes layout, the run log prints
`[site] scraped 0 items` and (for Toy Garden) uploads
`debug_toygarden.html` as a workflow artifact. Download it, paste the
relevant chunk to Claude with the adapter file, and ask for a patch.

## Notes

- `state.json` is auto-committed after each run — that's the bot's memory.
  Delete it to reset the baseline.
- GitHub cron isn't exact; expect 15–25 min between runs.
- Scraping is polite: one request per page per run, desktop UA.
