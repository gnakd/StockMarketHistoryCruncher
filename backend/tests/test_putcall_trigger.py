"""
Test script for put/call ratio trigger integration.

Run with: python -m tests.test_putcall_trigger
From the backend directory.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache.putcall_ratio import get_putcall_manager
from config import Config
import logging

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def test_find_putcall_events():
    """Test finding put/call ratio crossover events."""
    print("\n" + "=" * 60)
    print("PUT/CALL TRIGGER TEST")
    print("=" * 60)

    # Import the function from app
    from app import find_putcall_events

    # Ensure CBOE data is loaded
    manager = get_putcall_manager()
    loaded = manager.load_cboe_historical(force_reload=False)
    print(f"\nCBOE data loaded: {manager.get_stats()['total_records']} records")

    # Test 1: Find high P/C events (fear spikes)
    print("\n[Test 1] Finding putcall_above events (P/C > 1.0)...")
    events_above = find_putcall_events(
        start_date='2008-01-01',
        end_date='2010-12-31',
        params={'putcall_threshold': 1.0},
        cross_above=True
    )
    print(f"  Found {len(events_above)} events where P/C crossed above 1.0")
    if events_above:
        print(f"  First 5 events: {[str(e.date()) for e in events_above[:5]]}")

    # Test 2: Find low P/C events (complacency)
    print("\n[Test 2] Finding putcall_below events (P/C < 0.7)...")
    events_below = find_putcall_events(
        start_date='2008-01-01',
        end_date='2010-12-31',
        params={'putcall_threshold': 0.7},
        cross_above=False
    )
    print(f"  Found {len(events_below)} events where P/C crossed below 0.7")
    if events_below:
        print(f"  First 5 events: {[str(e.date()) for e in events_below[:5]]}")

    # Test 3: 2008 financial crisis should have high P/C events
    print("\n[Test 3] Checking 2008 financial crisis period...")
    events_2008 = find_putcall_events(
        start_date='2008-09-01',
        end_date='2008-12-31',
        params={'putcall_threshold': 1.2},  # Higher threshold for crisis
        cross_above=True
    )
    print(f"  Found {len(events_2008)} extreme fear events (P/C > 1.2) during Sep-Dec 2008")
    if events_2008:
        print(f"  Events: {[str(e.date()) for e in events_2008]}")

    # Test 4: Different thresholds
    print("\n[Test 4] Testing different thresholds...")
    for threshold in [0.8, 0.9, 1.0, 1.1, 1.2]:
        events = find_putcall_events(
            start_date='2003-10-17',
            end_date='2019-10-04',
            params={'putcall_threshold': threshold},
            cross_above=True
        )
        print(f"  Threshold {threshold}: {len(events)} events")

    # Summary
    print("\n" + "=" * 60)
    all_passed = len(events_above) > 0 and len(events_below) > 0
    print(f"TEST {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


def test_api_endpoint():
    """Test the API endpoint (requires running server)."""
    import requests

    print("\n" + "=" * 60)
    print("API ENDPOINT TEST")
    print("=" * 60)

    try:
        # Test put/call stats endpoint
        print("\n[Test] Fetching put/call stats...")
        response = requests.get('http://localhost:5000/api/putcall/stats', timeout=10)

        if response.status_code == 200:
            stats = response.json()
            print(f"  Total records: {stats.get('total_records', 'N/A')}")
            print(f"  Date range: {stats.get('start_date')} to {stats.get('end_date')}")
            print("  API endpoint working correctly!")
            return 0
        else:
            print(f"  Error: {response.status_code} - {response.text}")
            return 1

    except requests.exceptions.ConnectionError:
        print("  Server not running - skipping API test")
        print("  (Start server with: python app.py)")
        return 0  # Not a failure if server isn't running


if __name__ == "__main__":
    result1 = test_find_putcall_events()
    result2 = test_api_endpoint()
    exit(result1 or result2)
