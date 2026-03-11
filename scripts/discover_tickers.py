#!/usr/bin/env python3
"""Discover Kalshi tickers for March Madness / NCAA tournament markets.

Run this one-off to explore what markets exist:
    python scripts/discover_tickers.py

Then update src/odds.py SERIES_TICKERS and ROUND_KEYWORDS with what you find.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

from src.kalshi_client import get_client


# Search terms to try — Kalshi's naming conventions may vary
SEARCH_TERMS = [
    "march madness",
    "ncaa",
    "ncaat",
    "march mad",
    "college basketball",
    "final four",
    "sweet 16",
    "elite 8",
    "national champion",
]


def search_events(client, term: str):
    """Search for events matching a term."""
    try:
        result = client.get_events(
            series_ticker=None,
            status="open",
            limit=100,
        )
        events = result if isinstance(result, list) else result.get("events", [])
        matches = [
            e for e in events
            if term.lower() in (e.get("title", "") + " " + e.get("ticker", "")).lower()
        ]
        return matches
    except Exception as exc:
        logger.warning("Event search failed", term=term, error=str(exc))
        return []


def search_markets(client, term: str):
    """Search for markets matching a term."""
    try:
        result = client.get_markets(
            limit=200,
        )
        markets = result if isinstance(result, list) else result.get("markets", [])
        matches = [
            m for m in markets
            if term.lower() in (
                m.get("title", "") + " " +
                m.get("subtitle", "") + " " +
                m.get("ticker", "") + " " +
                m.get("series_ticker", "")
            ).lower()
        ]
        return matches
    except Exception as exc:
        logger.warning("Market search failed", term=term, error=str(exc))
        return []


def main():
    logger.info("Connecting to Kalshi...")
    client = get_client()

    print("\n" + "=" * 80)
    print("KALSHI MARCH MADNESS MARKET DISCOVERY")
    print("=" * 80)

    all_event_tickers = set()
    all_series_tickers = set()
    all_market_tickers = set()

    for term in SEARCH_TERMS:
        print(f"\n--- Searching: '{term}' ---")

        # Search events
        events = search_events(client, term)
        if events:
            print(f"\n  Events ({len(events)}):")
            for e in events[:10]:
                ticker = e.get("ticker", "?")
                title = e.get("title", "?")
                series = e.get("series_ticker", "")
                print(f"    {ticker:30s} | {title}")
                if series:
                    print(f"      series: {series}")
                    all_series_tickers.add(series)
                all_event_tickers.add(ticker)

        # Search markets
        markets = search_markets(client, term)
        if markets:
            print(f"\n  Markets ({len(markets)}):")
            for m in markets[:20]:
                ticker = m.get("ticker", "?")
                title = m.get("title", "?")
                subtitle = m.get("subtitle", "")
                series = m.get("series_ticker", "")
                event = m.get("event_ticker", "")
                yes_bid = m.get("yes_bid", "?")
                yes_ask = m.get("yes_ask", "?")
                print(f"    {ticker:35s} | {title}")
                if subtitle:
                    print(f"      subtitle: {subtitle}")
                print(f"      event: {event} | series: {series} | bid/ask: {yes_bid}/{yes_ask}")
                all_market_tickers.add(ticker)
                if series:
                    all_series_tickers.add(series)

        if not events and not markets:
            print("  (no results)")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nUnique series tickers: {sorted(all_series_tickers)}")
    print(f"Unique event tickers:  {len(all_event_tickers)}")
    print(f"Unique market tickers: {len(all_market_tickers)}")
    print("\nNext step: Add relevant series tickers to src/odds.py SERIES_TICKERS")


if __name__ == "__main__":
    main()
