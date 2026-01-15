"""Cache refresh strategies for handling adjusted prices."""

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, Dict
import logging

from .db import get_connection

logger = logging.getLogger(__name__)


class RefreshStrategy(Enum):
    """Available refresh strategies for cached data."""
    APPEND_ONLY = "append"       # Only fetch new data (fast, may miss adjustments)
    ROLLING_WINDOW = "rolling"   # Re-fetch recent N months (balanced)
    FULL_REFRESH = "full"        # Re-fetch everything (slow, accurate)


class RefreshPolicy:
    """
    Determines when and how to refresh cached price data.

    The challenge: Polygon's adjusted=true means historical prices can change
    after stock splits, dividends, etc. We need to balance:
    - Speed (don't re-fetch everything every time)
    - Accuracy (catch price adjustments when they happen)
    """

    # Recent data - always fetch from API (may not be final)
    ALWAYS_FETCH_DAYS = 2

    # Rolling window - re-fetch periodically to catch recent adjustments
    ROLLING_WINDOW_DAYS = 90
    ROLLING_REFRESH_INTERVAL_DAYS = 7

    # Full refresh - periodically verify all historical data
    FULL_REFRESH_INTERVAL_DAYS = 30

    def __init__(
        self,
        always_fetch_days: int = None,
        rolling_window_days: int = None,
        rolling_refresh_interval: int = None,
        full_refresh_interval: int = None
    ):
        """
        Initialize refresh policy with configurable parameters.

        Args:
            always_fetch_days: Days of recent data to always fetch fresh
            rolling_window_days: Size of rolling refresh window
            rolling_refresh_interval: Days between rolling refreshes
            full_refresh_interval: Days between full historical refreshes
        """
        if always_fetch_days is not None:
            self.ALWAYS_FETCH_DAYS = always_fetch_days
        if rolling_window_days is not None:
            self.ROLLING_WINDOW_DAYS = rolling_window_days
        if rolling_refresh_interval is not None:
            self.ROLLING_REFRESH_INTERVAL_DAYS = rolling_refresh_interval
        if full_refresh_interval is not None:
            self.FULL_REFRESH_INTERVAL_DAYS = full_refresh_interval

    def decide_strategy(
        self,
        ticker: str,
        metadata: Optional[Dict],
        force_full: bool = False
    ) -> RefreshStrategy:
        """
        Determine refresh strategy based on ticker's cache state.

        Args:
            ticker: Stock symbol
            metadata: Ticker metadata from cache (or None if not cached)
            force_full: If True, always return FULL_REFRESH

        Returns:
            RefreshStrategy to use
        """
        if force_full:
            return RefreshStrategy.FULL_REFRESH

        if metadata is None:
            # No cached data - need full fetch
            return RefreshStrategy.FULL_REFRESH

        last_updated = metadata.get('last_updated')
        last_full_refresh = metadata.get('last_full_refresh')

        now = datetime.now()

        # Check if full refresh is due
        if last_full_refresh:
            days_since_full = (now - last_full_refresh).days
            if days_since_full >= self.FULL_REFRESH_INTERVAL_DAYS:
                logger.debug(f"{ticker}: Full refresh due (last was {days_since_full} days ago)")
                return RefreshStrategy.FULL_REFRESH
        else:
            # Never had a full refresh
            return RefreshStrategy.FULL_REFRESH

        # Check if rolling refresh is due
        if last_updated:
            days_since_update = (now - last_updated).days
            if days_since_update >= self.ROLLING_REFRESH_INTERVAL_DAYS:
                logger.debug(f"{ticker}: Rolling refresh due (last update {days_since_update} days ago)")
                return RefreshStrategy.ROLLING_WINDOW

        # Default to append-only
        return RefreshStrategy.APPEND_ONLY

    def get_refresh_range(
        self,
        strategy: RefreshStrategy,
        start_date: date,
        end_date: date,
        cached_last_date: Optional[date]
    ) -> tuple[date, date]:
        """
        Get the date range to fetch based on strategy.

        Args:
            strategy: The refresh strategy to use
            start_date: Requested start date
            end_date: Requested end date
            cached_last_date: Last date in cache (or None)

        Returns:
            Tuple of (fetch_start, fetch_end)
        """
        today = date.today()

        if strategy == RefreshStrategy.FULL_REFRESH:
            # Fetch entire range
            return (start_date, end_date)

        elif strategy == RefreshStrategy.ROLLING_WINDOW:
            # Fetch from rolling window start to end
            rolling_start = today - timedelta(days=self.ROLLING_WINDOW_DAYS)
            # Don't go earlier than requested start
            fetch_start = max(rolling_start, start_date)
            return (fetch_start, end_date)

        else:  # APPEND_ONLY
            if cached_last_date is None:
                return (start_date, end_date)

            # Only fetch new data
            # But always re-fetch recent ALWAYS_FETCH_DAYS
            recent_cutoff = today - timedelta(days=self.ALWAYS_FETCH_DAYS)
            fetch_start = min(recent_cutoff, cached_last_date + timedelta(days=1))

            if fetch_start > end_date:
                # Nothing to fetch
                return (None, None)

            return (fetch_start, end_date)


def should_refresh_date(
    query_date: date,
    last_updated: Optional[datetime],
    policy: RefreshPolicy = None
) -> bool:
    """
    Determine if a specific date's data should be refreshed.

    This is useful for sampling during rolling refreshes to detect
    if historical prices have changed due to adjustments.

    Args:
        query_date: The date to check
        last_updated: When this ticker was last updated
        policy: RefreshPolicy to use (defaults to standard policy)

    Returns:
        True if the date should be refreshed
    """
    if policy is None:
        policy = RefreshPolicy()

    today = date.today()
    days_ago = (today - query_date).days

    # Always refresh recent data
    if days_ago <= policy.ALWAYS_FETCH_DAYS:
        return True

    # Within rolling window - check refresh interval
    if days_ago <= policy.ROLLING_WINDOW_DAYS:
        if last_updated is None:
            return True
        days_since_update = (datetime.now() - last_updated).days
        return days_since_update >= policy.ROLLING_REFRESH_INTERVAL_DAYS

    # Old data - only refresh periodically
    return False


def detect_adjustment_needed(
    cached_close: float,
    api_close: float,
    tolerance: float = 0.01
) -> bool:
    """
    Compare a cached price vs API price to detect adjustments.

    This can be called during rolling refresh on sample dates
    to determine if a full refresh is needed.

    Args:
        cached_close: Close price from cache
        api_close: Close price from fresh API call
        tolerance: Acceptable difference percentage (default 1%)

    Returns:
        True if prices differ enough to suggest an adjustment occurred
    """
    if cached_close == 0 or api_close == 0:
        return True

    diff_pct = abs(cached_close - api_close) / cached_close
    return diff_pct > tolerance


def mark_full_refresh(ticker: str) -> None:
    """Mark that a ticker has had a full refresh."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ticker_metadata
            SET last_full_refresh = ?
            WHERE ticker = ?
        """, (datetime.now(), ticker.upper()))
        conn.commit()


def get_tickers_needing_refresh(
    policy: RefreshPolicy = None,
    limit: int = 100
) -> list[str]:
    """
    Get list of tickers that need a refresh based on policy.

    Args:
        policy: RefreshPolicy to use
        limit: Maximum number of tickers to return

    Returns:
        List of ticker symbols needing refresh
    """
    if policy is None:
        policy = RefreshPolicy()

    now = datetime.now()
    full_refresh_cutoff = now - timedelta(days=policy.FULL_REFRESH_INTERVAL_DAYS)
    rolling_refresh_cutoff = now - timedelta(days=policy.ROLLING_REFRESH_INTERVAL_DAYS)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker FROM ticker_metadata
            WHERE (last_full_refresh IS NULL OR last_full_refresh < ?)
               OR (last_updated IS NULL OR last_updated < ?)
            ORDER BY last_updated ASC
            LIMIT ?
        """, (full_refresh_cutoff, rolling_refresh_cutoff, limit))

        return [row['ticker'] for row in cursor.fetchall()]
