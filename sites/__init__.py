"""Adapter registry — add new sites here (one line per adapter)."""
from . import toysrus, kelabgasing, toygarden

ADAPTERS = {
    "toysrus": toysrus.scrape,
    "kelabgasing": kelabgasing.scrape,
    "toygarden": toygarden.scrape,
}
