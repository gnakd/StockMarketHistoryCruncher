#!/usr/bin/env python3
"""Script to refresh the full cache with 10-year historical data."""

import sys
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from cache.db import init_db
from cache.manager import CacheManager
from cache.sp500_cacher import SP500Cacher, get_sp500_constituents
from app import fetch_aggregate_bars


def main():
    # Get API key from config or environment
    api_key = Config.POLYGON_API_KEY
    if not api_key:
        print("Error: POLYGON_API_KEY not set in .env file")
        sys.exit(1)

    # Initialize database
    print("Initializing database...")
    init_db()

    # Create cache manager (no rate limiting with unlimited API calls)
    cache_manager = CacheManager(api_key, fetch_func=fetch_aggregate_bars, rate_limit_delay=0)

    # Get date range
    start_date = date.fromisoformat(Config.HISTORICAL_START_DATE)
    end_date = date.today()

    print(f"\nCache refresh settings:")
    print(f"  Start date: {start_date}")
    print(f"  End date: {end_date}")
    print(f"  Rate limiting: Disabled (unlimited API)")

    # Get S&P 500 constituents
    tickers = get_sp500_constituents()
    print(f"  Tickers to cache: {len(tickers)}")

    # Progress callback
    def on_progress(processed, total, ticker):
        pct = processed / total * 100
        print(f"\r  Progress: {processed}/{total} ({pct:.1f}%) - Last: {ticker}    ", end="", flush=True)

    # Create cacher and run
    print("\nStarting cache refresh...")
    cacher = SP500Cacher(cache_manager, rate_limit_delay=0, on_progress=on_progress)

    result = cacher.cache_all(start_date, end_date, incremental=False)

    print(f"\n\nCache refresh complete!")
    print(f"  Successful: {result['success_count']}")
    print(f"  Failed: {result['fail_count']}")
    print(f"  Duration: {result['duration_seconds']:.1f} seconds")

    if result['failed_tickers']:
        print(f"  Failed tickers: {', '.join(result['failed_tickers'][:20])}")
        if len(result['failed_tickers']) > 20:
            print(f"    ... and {len(result['failed_tickers']) - 20} more")


if __name__ == "__main__":
    main()
