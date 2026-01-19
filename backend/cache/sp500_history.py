"""
Historical S&P 500 constituent data manager.

Tracks which stocks were in the S&P 500 on any given date,
enabling accurate point-in-time breadth calculations.

Data source: https://github.com/fja05680/sp500
"""

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
import urllib.request

logger = logging.getLogger(__name__)

# URL for the historical S&P 500 constituent data
SP500_HISTORY_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"

# Local cache path
CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = CACHE_DIR / "sp500_history.csv"


def _parse_date(date_str: str) -> Optional[date]:
    """Parse a date string, returning None for empty strings."""
    if not date_str or date_str.strip() == '':
        return None
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except ValueError:
        logger.warning(f"Could not parse date: {date_str}")
        return None


def download_sp500_history(force: bool = False) -> bool:
    """
    Download the S&P 500 historical constituent data.

    Args:
        force: If True, re-download even if file exists

    Returns:
        True if successful, False otherwise
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        # Check if file is recent (less than 7 days old)
        file_age = datetime.now().timestamp() - CACHE_FILE.stat().st_mtime
        if file_age < 7 * 24 * 3600:  # 7 days in seconds
            logger.debug("S&P 500 history cache is recent, skipping download")
            return True

    logger.info(f"Downloading S&P 500 historical data from {SP500_HISTORY_URL}")
    try:
        urllib.request.urlretrieve(SP500_HISTORY_URL, CACHE_FILE)
        logger.info(f"Downloaded S&P 500 history to {CACHE_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to download S&P 500 history: {e}")
        return False


def load_sp500_history() -> List[dict]:
    """
    Load the S&P 500 historical constituent data.

    Returns:
        List of dicts with keys: ticker, start_date, end_date
    """
    # Ensure we have the data
    if not CACHE_FILE.exists():
        if not download_sp500_history():
            logger.error("Could not load S&P 500 history - no cached data and download failed")
            return []

    records = []
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    'ticker': row['ticker'].strip().upper(),
                    'start_date': _parse_date(row.get('start_date', '')),
                    'end_date': _parse_date(row.get('end_date', ''))
                })
        logger.info(f"Loaded {len(records)} S&P 500 membership records")
        return records
    except Exception as e:
        logger.error(f"Failed to load S&P 500 history: {e}")
        return []


# Cache the loaded data in memory
_sp500_history_cache: Optional[List[dict]] = None


def get_sp500_constituents_for_date(target_date: date) -> List[str]:
    """
    Get the list of S&P 500 constituents for a specific date.

    Args:
        target_date: The date to get constituents for

    Returns:
        List of ticker symbols that were in the S&P 500 on that date
    """
    global _sp500_history_cache

    if _sp500_history_cache is None:
        _sp500_history_cache = load_sp500_history()

    if not _sp500_history_cache:
        logger.warning("No S&P 500 history data available")
        return []

    constituents = []
    for record in _sp500_history_cache:
        start = record['start_date']
        end = record['end_date']

        # Skip if no start date
        if start is None:
            continue

        # Check if target_date is within the membership period
        # end_date of None means still in the index
        if start <= target_date:
            if end is None or target_date <= end:
                constituents.append(record['ticker'])

    return constituents


def get_sp500_constituents_range(start_date: date, end_date: date) -> dict:
    """
    Get all unique S&P 500 constituents across a date range,
    along with their membership periods.

    Args:
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Dict mapping ticker -> {'start': date, 'end': date or None}
        Only includes tickers that were in S&P 500 at some point during the range
    """
    global _sp500_history_cache

    if _sp500_history_cache is None:
        _sp500_history_cache = load_sp500_history()

    if not _sp500_history_cache:
        return {}

    result = {}
    for record in _sp500_history_cache:
        ticker = record['ticker']
        membership_start = record['start_date']
        membership_end = record['end_date']

        if membership_start is None:
            continue

        # Check if membership period overlaps with the requested range
        # Membership is [membership_start, membership_end] (inclusive)
        # Range is [start_date, end_date]
        # They overlap if: membership_start <= end_date AND (membership_end is None OR membership_end >= start_date)

        if membership_start <= end_date:
            if membership_end is None or membership_end >= start_date:
                # This ticker was in S&P 500 at some point during our range
                # Store the overlap period
                effective_start = max(membership_start, start_date)
                effective_end = min(membership_end, end_date) if membership_end else end_date

                if ticker not in result:
                    result[ticker] = {'start': effective_start, 'end': effective_end}
                else:
                    # Ticker might have multiple membership periods, extend the range
                    result[ticker]['start'] = min(result[ticker]['start'], effective_start)
                    result[ticker]['end'] = max(result[ticker]['end'], effective_end)

    return result


def refresh_sp500_history() -> bool:
    """Force refresh of the S&P 500 history data."""
    global _sp500_history_cache
    _sp500_history_cache = None
    return download_sp500_history(force=True)


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    # Force download
    download_sp500_history(force=True)

    # Test some dates
    test_dates = [
        date(2016, 1, 1),
        date(2020, 1, 1),
        date(2024, 1, 1),
    ]

    for d in test_dates:
        constituents = get_sp500_constituents_for_date(d)
        print(f"\n{d}: {len(constituents)} constituents")
        print(f"  Sample: {constituents[:10]}...")

        # Check specific stocks
        for ticker in ['AAPL', 'UBER', 'ABNB', 'META', 'GOOGL']:
            in_sp500 = ticker in constituents
            print(f"  {ticker}: {'YES' if in_sp500 else 'NO'}")
