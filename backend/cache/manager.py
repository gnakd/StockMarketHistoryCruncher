"""Cache manager for stock price data."""

from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple
import pandas as pd
import logging
import time

from .db import get_connection, init_db, get_db_path

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local SQLite cache for stock price data.

    Provides transparent caching layer that:
    - Returns cached data when available
    - Fetches only missing date ranges from API
    - Stores new data for future requests
    """

    def __init__(self, api_key: str, fetch_func=None, rate_limit_delay: float = 0):
        """
        Initialize cache manager.

        Args:
            api_key: Polygon.io API key
            fetch_func: Function to fetch bars from API (for dependency injection)
            rate_limit_delay: Delay between API calls in seconds (0 = no limit)
        """
        self.api_key = api_key
        self._fetch_func = fetch_func
        self.rate_limit_delay = rate_limit_delay
        self._last_api_call = 0
        init_db()

    def _get_fetch_func(self):
        """Lazy-load the fetch function to avoid circular imports."""
        if self._fetch_func is None:
            # Import here to avoid circular dependency
            from app import fetch_aggregate_bars
            self._fetch_func = fetch_aggregate_bars
        return self._fetch_func

    def get_bars(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Get daily bars for ticker, fetching from API only if needed.

        Args:
            ticker: Stock symbol (e.g., 'AAPL', 'SPY')
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            force_refresh: If True, bypass cache and fetch from API

        Returns:
            DataFrame with columns: date (index), open, high, low, close, volume
        """
        ticker = ticker.upper()

        if force_refresh:
            self._invalidate_range(ticker, start_date, end_date)

        # Determine what we need to fetch
        fetch_ranges = self._determine_fetch_ranges(ticker, start_date, end_date)

        if fetch_ranges:
            logger.info(f"Cache miss for {ticker}: fetching {len(fetch_ranges)} range(s)")
            for range_start, range_end in fetch_ranges:
                try:
                    self._fetch_and_store(ticker, range_start, range_end)
                except Exception as e:
                    # If partial range fetch fails (e.g., 403 for restricted dates),
                    # fall back to fetching the full range which Polygon handles gracefully
                    if '403' in str(e) or 'NOT_AUTHORIZED' in str(e):
                        logger.warning(f"Partial fetch failed for {ticker}, trying full range: {e}")
                        try:
                            self._fetch_and_store(ticker, start_date, end_date)
                            break  # Full range succeeded, no need to continue with other ranges
                        except Exception as e2:
                            logger.error(f"Full range fetch also failed for {ticker}: {e2}")
                            # Continue with cached data only
                    else:
                        raise  # Re-raise non-403 errors
        else:
            logger.debug(f"Cache hit for {ticker}: {start_date} to {end_date}")

        # Return data from cache
        return self._get_from_cache(ticker, start_date, end_date)

    def get_cache_status(self, ticker: str) -> Optional[Dict]:
        """
        Get cache metadata for a ticker.

        Args:
            ticker: Stock symbol

        Returns:
            Dict with first_date, last_date, last_updated, total_bars, or None
        """
        ticker = ticker.upper()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT first_date, last_date, last_updated, total_bars, is_sp500, status
                FROM ticker_metadata
                WHERE ticker = ?
            """, (ticker,))
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                'ticker': ticker,
                'first_date': row['first_date'],
                'last_date': row['last_date'],
                'last_updated': row['last_updated'],
                'total_bars': row['total_bars'],
                'is_sp500': bool(row['is_sp500']),
                'status': row['status']
            }

    def invalidate_ticker(self, ticker: str) -> int:
        """
        Remove all cached data for a ticker (for full refresh).

        Args:
            ticker: Stock symbol

        Returns:
            Number of bars removed
        """
        ticker = ticker.upper()

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM daily_bars WHERE ticker = ?", (ticker,))
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM daily_bars WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM ticker_metadata WHERE ticker = ?", (ticker,))

            conn.commit()
            logger.info(f"Invalidated cache for {ticker}: {count} bars removed")

            return count

    def _determine_fetch_ranges(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, date]]:
        """
        Determine what date ranges need to be fetched from API.

        Returns list of (start, end) tuples for ranges not in cache.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT first_date, last_date
                FROM ticker_metadata
                WHERE ticker = ?
            """, (ticker,))
            row = cursor.fetchone()

            if row is None or row['first_date'] is None:
                # No cache at all - fetch entire range
                return [(start_date, end_date)]

            cached_first = self._parse_date(row['first_date'])
            cached_last = self._parse_date(row['last_date'])

            ranges = []

            # Need earlier data?
            if start_date < cached_first:
                # Fetch up to day before cached start
                ranges.append((start_date, cached_first - timedelta(days=1)))

            # Need later data?
            if end_date > cached_last:
                # Fetch from day after cached end
                ranges.append((cached_last + timedelta(days=1), end_date))

            return ranges

    def _parse_date(self, d) -> date:
        """Parse a date from various formats."""
        if isinstance(d, date):
            return d
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, str):
            return date.fromisoformat(d)
        raise ValueError(f"Cannot parse date: {d}")

    def _fetch_and_store(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> int:
        """
        Fetch from API and store in cache.

        Args:
            ticker: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            Count of bars stored
        """
        # Rate limiting (skip if delay is 0)
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self._last_api_call
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)

        fetch_func = self._get_fetch_func()

        self._last_api_call = time.time()
        bars = fetch_func(
            ticker,
            start_date.isoformat(),
            end_date.isoformat(),
            self.api_key
        )

        if not bars:
            logger.warning(f"No data returned from API for {ticker} ({start_date} to {end_date})")
            return 0

        # Store in database
        count = self._store_bars(ticker, bars)

        # Update metadata
        self._update_metadata(ticker)

        logger.info(f"Stored {count} bars for {ticker} ({start_date} to {end_date})")
        return count

    def _store_bars(self, ticker: str, bars: list) -> int:
        """Store bars in database, handling duplicates with REPLACE."""
        with get_connection() as conn:
            cursor = conn.cursor()

            for bar in bars:
                # Handle both Polygon format (t in ms) and other formats
                if 't' in bar:
                    bar_date = datetime.fromtimestamp(bar['t'] / 1000).date()
                elif 'date' in bar:
                    bar_date = self._parse_date(bar['date'])
                else:
                    continue

                cursor.execute("""
                    INSERT OR REPLACE INTO daily_bars
                    (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker,
                    bar_date,
                    bar.get('o', bar.get('open')),
                    bar.get('h', bar.get('high')),
                    bar.get('l', bar.get('low')),
                    bar.get('c', bar.get('close')),
                    bar.get('v', bar.get('volume', 0))
                ))

            conn.commit()
            return len(bars)

    def _update_metadata(self, ticker: str) -> None:
        """Update ticker metadata after storing new bars."""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get date range and count
            cursor.execute("""
                SELECT MIN(date) as first_date, MAX(date) as last_date, COUNT(*) as total
                FROM daily_bars
                WHERE ticker = ?
            """, (ticker,))
            row = cursor.fetchone()

            if row and row['first_date']:
                cursor.execute("""
                    INSERT INTO ticker_metadata (ticker, first_date, last_date, last_updated, total_bars)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        first_date = excluded.first_date,
                        last_date = excluded.last_date,
                        last_updated = excluded.last_updated,
                        total_bars = excluded.total_bars
                """, (
                    ticker,
                    row['first_date'],
                    row['last_date'],
                    datetime.now(),
                    row['total']
                ))
                conn.commit()

    def _get_from_cache(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Retrieve bars from cache as DataFrame."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, open, high, low, close, volume
                FROM daily_bars
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """, (ticker, start_date, end_date))

            rows = cursor.fetchall()

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame([dict(row) for row in rows])
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            return df

    def _invalidate_range(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> int:
        """Remove cached data for a specific date range."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM daily_bars
                WHERE ticker = ? AND date >= ? AND date <= ?
            """, (ticker, start_date, end_date))
            count = cursor.rowcount
            conn.commit()

            # Update metadata
            self._update_metadata(ticker)

            return count

    def mark_sp500(self, tickers: List[str]) -> None:
        """Mark tickers as S&P 500 constituents."""
        with get_connection() as conn:
            cursor = conn.cursor()
            for ticker in tickers:
                cursor.execute("""
                    INSERT INTO ticker_metadata (ticker, is_sp500)
                    VALUES (?, 1)
                    ON CONFLICT(ticker) DO UPDATE SET is_sp500 = 1
                """, (ticker.upper(),))
            conn.commit()

    def get_all_cached_tickers(self) -> List[str]:
        """Get list of all tickers with cached data."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM ticker_metadata ORDER BY ticker")
            return [row['ticker'] for row in cursor.fetchall()]

    def get_sp500_coverage(self) -> Dict:
        """Get coverage statistics for S&P 500 tickers."""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as total
                FROM ticker_metadata
                WHERE is_sp500 = 1
            """)
            marked = cursor.fetchone()['total']

            cursor.execute("""
                SELECT COUNT(*) as total
                FROM ticker_metadata
                WHERE is_sp500 = 1 AND total_bars > 0
            """)
            with_data = cursor.fetchone()['total']

            return {
                'marked_sp500': marked,
                'with_data': with_data,
                'coverage_pct': round(with_data / 500 * 100, 1) if marked > 0 else 0
            }
