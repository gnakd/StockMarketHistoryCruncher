"""
Test script for Fear & Greed Index data module.

Run with: python -m tests.test_fear_greed
From the backend directory.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache.fear_greed import FearGreedManager, get_feargreed_manager
import logging
from datetime import date

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    print("\n" + "=" * 60)
    print("FEAR & GREED INDEX DATA MODULE TEST")
    print("=" * 60)

    # Use a test database
    test_db_path = "data/fear_greed_test.db"

    print(f"\nTest database: {test_db_path}")

    # Initialize manager
    print("\n[Step 1] Initializing FearGreedManager...")
    manager = FearGreedManager(db_path=test_db_path)
    print("  Manager initialized successfully")

    # Load GitHub historical data
    print("\n[Step 2] Loading historical data from GitHub...")
    github_records = manager.load_github_historical(force_reload=True)
    print(f"  Loaded {github_records} records from GitHub")

    # Try loading CNN current data
    print("\n[Step 3] Attempting to load recent data from CNN...")
    cnn_records = manager.fetch_cnn_current()
    print(f"  Loaded {cnn_records} records from CNN")

    # Get stats
    print("\n[Step 4] Checking data statistics...")
    stats = manager.get_stats()
    print(f"  Total records: {stats.get('total_records')}")
    print(f"  Date range: {stats.get('start_date')} to {stats.get('end_date')}")
    print(f"  Average value: {stats.get('avg_value')}")
    print(f"  Min value: {stats.get('min_value')}")
    print(f"  Max value: {stats.get('max_value')}")
    if stats.get('sources'):
        print(f"  Sources: {stats.get('sources')}")

    # Test specific dates (known extreme fear/greed periods)
    print("\n[Step 5] Testing value retrieval for known events...")
    test_dates = [
        (date(2020, 3, 12), "COVID crash - expect extreme fear (<20)"),
        (date(2020, 3, 23), "COVID bottom - expect extreme fear"),
        (date(2018, 12, 24), "Christmas Eve 2018 - expect fear"),
        (date(2021, 1, 15), "Post-stimulus rally - expect greed"),
    ]

    for test_date, description in test_dates:
        value = manager.get_value(test_date)
        if value is not None:
            sentiment = "Extreme Fear" if value < 25 else "Fear" if value < 45 else "Neutral" if value < 55 else "Greed" if value < 75 else "Extreme Greed"
            print(f"  {test_date}: {value:.1f} ({sentiment}) - {description}")
        else:
            print(f"  {test_date}: No data available - {description}")

    # Test series retrieval
    print("\n[Step 6] Testing series retrieval...")
    series_start = date(2020, 1, 1)
    series_end = date(2020, 12, 31)
    df = manager.get_series(series_start, series_end)
    if not df.empty:
        print(f"  Retrieved {len(df)} records for {series_start} to {series_end}")
        print(f"  Mean value: {df['value'].mean():.1f}")
        print(f"  Max value: {df['value'].max():.1f}")
        print(f"  Min value: {df['value'].min():.1f}")
    else:
        print(f"  No data found for date range")

    # Test data range
    print("\n[Step 7] Testing data range...")
    min_date, max_date = manager.get_data_range()
    if min_date and max_date:
        print(f"  Data available from {min_date} to {max_date}")
    else:
        print("  Could not determine data range")

    # Summary
    print("\n" + "=" * 60)
    passed = github_records > 0 and stats.get('total_records', 0) > 100
    print(f"TEST {'PASSED' if passed else 'FAILED'}")

    if passed:
        print("  - GitHub data loaded successfully")
        print(f"  - {stats.get('total_records')} total records available")
    else:
        print("  - Failed to load sufficient data")
        if github_records == 0:
            print("  - GitHub data loading failed (network issue or data format changed)")

    print("=" * 60 + "\n")

    return 0 if passed else 1


if __name__ == "__main__":
    exit(main())
