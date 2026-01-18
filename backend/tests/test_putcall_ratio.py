"""
Test script for put/call ratio data module.

Run with: python -m tests.test_putcall_ratio
From the backend directory.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache.putcall_ratio import PutCallRatioManager, PutCallValidator, get_putcall_manager
from config import Config
import logging

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    print("\n" + "=" * 70)
    print("PUT/CALL RATIO MODULE TEST")
    print("=" * 70)

    # Use a test database to avoid polluting production data
    test_db_path = "data/putcall_ratio_test.db"

    # Get API key from config
    api_key = Config.POLYGON_API_KEY

    print(f"\nTest database: {test_db_path}")
    print(f"Polygon API key: {'configured' if api_key else 'NOT CONFIGURED'}")

    # Initialize manager
    print("\n[Step 1] Initializing PutCallRatioManager...")
    manager = PutCallRatioManager(db_path=test_db_path, api_key=api_key)
    print("  Manager initialized successfully")

    # Load CBOE historical data
    print("\n[Step 2] Loading CBOE historical data...")
    records_loaded = manager.load_cboe_historical(force_reload=True)
    print(f"  Loaded {records_loaded} records from CBOE")

    # Get stats
    print("\n[Step 3] Checking data statistics...")
    stats = manager.get_stats()
    print(f"  Total records: {stats['total_records']}")
    print(f"  Date range: {stats.get('start_date')} to {stats.get('end_date')}")
    for source, source_stats in stats.get('sources', {}).items():
        print(f"  Source '{source}': {source_stats['count']} records "
              f"({source_stats['start']} to {source_stats['end']})")

    # Run validation
    print("\n[Step 4] Running validation tests...")
    validator = PutCallValidator(manager)
    validation_result = validator.run_all_validations(
        include_polygon=bool(api_key),
        polygon_ticker="SPY"
    )

    # Test ratio retrieval
    print("\n[Step 5] Testing ratio retrieval...")
    from datetime import date

    # Test a known historical date (should have CBOE data)
    test_dates = [
        date(2010, 1, 4),   # Early in dataset
        date(2015, 6, 15),  # Middle of dataset
        date(2016, 3, 1),   # Near end of CBOE data
    ]

    for test_date in test_dates:
        ratio = manager.get_ratio(test_date)
        if ratio:
            print(f"  {test_date}: P/C ratio = {ratio:.4f}")
        else:
            print(f"  {test_date}: No data available")

    # Test series retrieval
    print("\n[Step 6] Testing series retrieval...")
    series_start = date(2015, 1, 1)
    series_end = date(2015, 12, 31)
    df = manager.get_ratio_series(series_start, series_end)
    if not df.empty:
        print(f"  Retrieved {len(df)} records for {series_start} to {series_end}")
        print(f"  Mean ratio: {df['ratio'].mean():.4f}")
        print(f"  Min ratio: {df['ratio'].min():.4f}")
        print(f"  Max ratio: {df['ratio'].max():.4f}")
    else:
        print(f"  No data found for date range")

    # Summary
    print("\n" + "=" * 70)
    if validation_result['passed']:
        print("ALL TESTS PASSED")
    else:
        print(f"TESTS FAILED - {validation_result['errors']} errors")
    print("=" * 70 + "\n")

    return 0 if validation_result['passed'] else 1


if __name__ == "__main__":
    exit(main())
