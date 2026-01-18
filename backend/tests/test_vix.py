"""
Test script for VIX data module.

Run with: python -m tests.test_vix
From the backend directory.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache.vix import VIXManager, get_vix_manager
import logging
from datetime import date

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    print("\n" + "=" * 60)
    print("VIX DATA MODULE TEST")
    print("=" * 60)

    # Use a test database
    test_db_path = "data/vix_test.db"

    print(f"\nTest database: {test_db_path}")

    # Initialize manager
    print("\n[Step 1] Initializing VIXManager...")
    manager = VIXManager(db_path=test_db_path)
    print("  Manager initialized successfully")

    # Load FRED data
    print("\n[Step 2] Loading VIX data from FRED...")
    records_loaded = manager.load_fred_data(force_reload=True)
    print(f"  Loaded {records_loaded} records")

    # Get stats
    print("\n[Step 3] Checking data statistics...")
    stats = manager.get_stats()
    print(f"  Total records: {stats.get('total_records')}")
    print(f"  Date range: {stats.get('start_date')} to {stats.get('end_date')}")
    print(f"  Average VIX: {stats.get('avg_vix')}")
    print(f"  Min VIX: {stats.get('min_vix')}")
    print(f"  Max VIX: {stats.get('max_vix')}")

    # Test specific dates
    print("\n[Step 4] Testing value retrieval...")
    test_dates = [
        date(2008, 10, 27),  # 2008 financial crisis peak
        date(2020, 3, 16),   # COVID crash
        date(2017, 11, 3),   # Low volatility period
    ]

    for test_date in test_dates:
        value = manager.get_value(test_date)
        if value:
            print(f"  {test_date}: VIX = {value:.2f}")
        else:
            print(f"  {test_date}: No data available")

    # Test series retrieval
    print("\n[Step 5] Testing series retrieval...")
    series_start = date(2020, 1, 1)
    series_end = date(2020, 12, 31)
    df = manager.get_series(series_start, series_end)
    if not df.empty:
        print(f"  Retrieved {len(df)} records for {series_start} to {series_end}")
        print(f"  Mean VIX: {df['value'].mean():.2f}")
        print(f"  Max VIX: {df['value'].max():.2f} (COVID spike)")
        print(f"  Min VIX: {df['value'].min():.2f}")
    else:
        print(f"  No data found for date range")

    # Summary
    print("\n" + "=" * 60)
    passed = records_loaded > 0 and stats.get('total_records', 0) > 1000
    print(f"TEST {'PASSED' if passed else 'FAILED'}")
    print("=" * 60 + "\n")

    return 0 if passed else 1


if __name__ == "__main__":
    exit(main())
