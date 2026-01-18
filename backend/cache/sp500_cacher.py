"""S&P 500 pre-caching utilities."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional, Dict, List
import time
import logging
import threading

from .db import get_connection, init_db
from .manager import CacheManager

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

logger = logging.getLogger(__name__)

# Wikipedia URL for S&P 500 constituents
SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# How often to refresh the constituent list (in days)
SP500_LIST_REFRESH_DAYS = 7


def _get_fallback_sp500_list() -> List[str]:
    """Fallback static list if Wikipedia fetch fails."""
    return [
        'A', 'AAL', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI',
        'ADM', 'ADP', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG',
        'AKAM', 'ALB', 'ALGN', 'ALL', 'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN',
        'AMP', 'AMT', 'AMZN', 'ANET', 'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH',
        'APTV', 'ARE', 'ATO', 'AVB', 'AVGO', 'AVY', 'AWK', 'AXON', 'AXP', 'AZO',
        'BA', 'BAC', 'BALL', 'BAX', 'BBWI', 'BBY', 'BDX', 'BEN', 'BF.B', 'BG',
        'BIIB', 'BIO', 'BK', 'BKNG', 'BKR', 'BLDR', 'BLK', 'BMY', 'BR', 'BRK.B',
        'BRO', 'BSX', 'BWA', 'BX', 'BXP', 'C', 'CAG', 'CAH', 'CARR', 'CAT',
        'CB', 'CBOE', 'CBRE', 'CCI', 'CCL', 'CDNS', 'CDW', 'CE', 'CEG', 'CF',
        'CFG', 'CHD', 'CHRW', 'CHTR', 'CI', 'CINF', 'CL', 'CLX', 'CMCSA', 'CME',
        'CMG', 'CMI', 'CMS', 'CNC', 'CNP', 'COF', 'COO', 'COP', 'COR', 'COST',
        'CPAY', 'CPB', 'CPRT', 'CPT', 'CRL', 'CRM', 'CRWD', 'CSCO', 'CSGP', 'CSX',
        'CTAS', 'CTLT', 'CTRA', 'CTSH', 'CTVA', 'CVS', 'CVX', 'CZR', 'D', 'DAL',
        'DAY', 'DD', 'DE', 'DECK', 'DFS', 'DG', 'DGX', 'DHI', 'DHR', 'DIS',
        'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ', 'DRI', 'DTE', 'DUK', 'DVA',
        'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED', 'EFX', 'EG', 'EIX', 'EL',
        'ELV', 'EMN', 'EMR', 'ENPH', 'EOG', 'EPAM', 'EQIX', 'EQR', 'EQT', 'ES',
        'ESS', 'ETN', 'ETR', 'ETSY', 'EVRG', 'EW', 'EXC', 'EXPD', 'EXPE', 'EXR',
        'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX', 'FE', 'FFIV', 'FI', 'FICO',
        'FIS', 'FITB', 'FLT', 'FMC', 'FOX', 'FOXA', 'FRT', 'FSLR', 'FTNT', 'FTV',
        'GD', 'GDDY', 'GE', 'GEHC', 'GEN', 'GEV', 'GILD', 'GIS', 'GL', 'GLW',
        'GM', 'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN', 'GS', 'GWW', 'HAL',
        'HAS', 'HBAN', 'HCA', 'HD', 'HES', 'HIG', 'HII', 'HLT', 'HOLX', 'HON',
        'HPE', 'HPQ', 'HRL', 'HSIC', 'HST', 'HSY', 'HUBB', 'HUM', 'HWM', 'IBM',
        'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY', 'INTC', 'INTU', 'INVH', 'IP',
        'IPG', 'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW', 'IVZ', 'J', 'JBHT',
        'JBL', 'JCI', 'JKHY', 'JNJ', 'JNPR', 'JPM', 'K', 'KDP', 'KEY', 'KEYS',
        'KHC', 'KIM', 'KKR', 'KLAC', 'KMB', 'KMI', 'KMX', 'KO', 'KR', 'KVUE',
        'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ', 'LLY', 'LMT', 'LNT',
        'LOW', 'LRCX', 'LULU', 'LUV', 'LVS', 'LW', 'LYB', 'LYV', 'MA', 'MAA',
        'MAR', 'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT', 'MET', 'META',
        'MGM', 'MHK', 'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST', 'MO', 'MOH',
        'MOS', 'MPC', 'MPWR', 'MRK', 'MRNA', 'MRO', 'MS', 'MSCI', 'MSFT', 'MSI',
        'MTB', 'MTCH', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE', 'NEM', 'NFLX',
        'NI', 'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA',
        'NVR', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OKE', 'OMC', 'ON', 'ORCL',
        'ORLY', 'OTIS', 'OXY', 'PANW', 'PARA', 'PAYC', 'PAYX', 'PCAR', 'PCG', 'PEG',
        'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG', 'PLD', 'PM',
        'PNC', 'PNR', 'PNW', 'PODD', 'POOL', 'PPG', 'PPL', 'PRU', 'PSA', 'PSX',
        'PTC', 'PWR', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'REG', 'REGN', 'RF', 'RJF',
        'RL', 'RMD', 'ROK', 'ROL', 'ROP', 'ROST', 'RSG', 'RTX', 'RVTY', 'SBAC',
        'SBUX', 'SCHW', 'SHW', 'SJM', 'SLB', 'SMCI', 'SNA', 'SNPS', 'SO', 'SOLV',
        'SPG', 'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ', 'SWK', 'SWKS',
        'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH', 'TEL', 'TER',
        'TFC', 'TFX', 'TGT', 'TJX', 'TMO', 'TMUS', 'TPR', 'TRGP', 'TRMB', 'TROW',
        'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO', 'TXN', 'TXT', 'TYL', 'UAL',
        'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI', 'USB', 'V',
        'VFC', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRTX', 'VST', 'VTR',
        'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WBD', 'WDC', 'WEC', 'WELL', 'WFC',
        'WM', 'WMB', 'WMT', 'WRB', 'WST', 'WTW', 'WY', 'WYNN', 'XEL', 'XOM',
        'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZTS'
    ]


def fetch_sp500_from_wikipedia() -> List[Dict]:
    """
    Fetch current S&P 500 constituents from Wikipedia.

    Returns:
        List of dicts with 'ticker', 'company_name', 'sector' keys.
        Returns empty list on failure.
    """
    try:
        import pandas as pd
        import requests
        from io import StringIO
    except ImportError as e:
        logger.error(f"Missing dependency for Wikipedia fetching: {e}")
        return []

    try:
        logger.info(f"Fetching S&P 500 constituents from Wikipedia...")

        # Use requests with proper user agent to avoid 403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(SP500_WIKIPEDIA_URL, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        # First table contains the constituents
        df = tables[0]

        # Find the symbol/ticker column (usually 'Symbol' or 'Ticker')
        symbol_col = None
        for col in df.columns:
            if 'symbol' in str(col).lower() or 'ticker' in str(col).lower():
                symbol_col = col
                break

        if symbol_col is None:
            # Fallback: assume first column is the symbol
            symbol_col = df.columns[0]
            logger.warning(f"Could not find Symbol column, using: {symbol_col}")

        # Find company name and sector columns
        name_col = None
        sector_col = None
        for col in df.columns:
            col_lower = str(col).lower()
            if 'security' in col_lower or 'company' in col_lower or 'name' in col_lower:
                name_col = col
            if 'sector' in col_lower or 'gics' in col_lower:
                sector_col = col

        constituents = []
        for _, row in df.iterrows():
            ticker = str(row[symbol_col]).strip()
            # Clean ticker: some have footnotes or extra characters
            ticker = ticker.split('[')[0].strip()
            # Replace '.' with '-' for Polygon compatibility (e.g., BRK.B -> BRK-B)
            # Actually, keep as-is since Polygon uses '.' format
            if ticker:
                constituents.append({
                    'ticker': ticker.upper(),
                    'company_name': str(row[name_col]).strip() if name_col else None,
                    'sector': str(row[sector_col]).strip() if sector_col else None,
                })

        logger.info(f"Fetched {len(constituents)} S&P 500 constituents from Wikipedia")
        return constituents

    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 from Wikipedia: {e}")
        return []


def get_sp500_list_metadata() -> Optional[Dict]:
    """Get metadata about the cached S&P 500 list."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sp500_list_metadata WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return {
                'last_refreshed': row['last_refreshed'],
                'source': row['source'],
                'ticker_count': row['ticker_count'],
            }
        return None


def get_cached_sp500_constituents() -> List[str]:
    """Get S&P 500 tickers from local cache."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM sp500_constituents ORDER BY ticker")
        return [row['ticker'] for row in cursor.fetchall()]


def refresh_sp500_constituents(force: bool = False) -> Dict:
    """
    Refresh the S&P 500 constituent list from Wikipedia.

    Args:
        force: If True, refresh even if cache is fresh.

    Returns:
        Dict with 'success', 'ticker_count', 'added', 'removed' keys.
    """
    init_db()

    # Check if refresh is needed
    if not force:
        metadata = get_sp500_list_metadata()
        if metadata and metadata['last_refreshed']:
            last_refresh = metadata['last_refreshed']
            if isinstance(last_refresh, str):
                last_refresh = datetime.fromisoformat(last_refresh)
            age_days = (datetime.now() - last_refresh).days
            if age_days < SP500_LIST_REFRESH_DAYS:
                logger.info(f"S&P 500 list is fresh ({age_days} days old), skipping refresh")
                return {
                    'success': True,
                    'skipped': True,
                    'ticker_count': metadata['ticker_count'],
                    'message': f'List is {age_days} days old, refresh not needed'
                }

    # Fetch from Wikipedia
    constituents = fetch_sp500_from_wikipedia()
    if not constituents:
        logger.warning("Wikipedia fetch failed, keeping existing list")
        return {'success': False, 'error': 'Failed to fetch from Wikipedia'}

    new_tickers = {c['ticker'] for c in constituents}

    with get_connection() as conn:
        cursor = conn.cursor()

        # Get existing tickers
        cursor.execute("SELECT ticker FROM sp500_constituents")
        old_tickers = {row['ticker'] for row in cursor.fetchall()}

        # Calculate changes
        added = new_tickers - old_tickers
        removed = old_tickers - new_tickers

        # Clear and repopulate
        cursor.execute("DELETE FROM sp500_constituents")
        for c in constituents:
            cursor.execute("""
                INSERT INTO sp500_constituents (ticker, company_name, sector)
                VALUES (?, ?, ?)
            """, (c['ticker'], c['company_name'], c['sector']))

        # Update metadata
        cursor.execute("""
            INSERT INTO sp500_list_metadata (id, last_refreshed, source, ticker_count)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_refreshed = excluded.last_refreshed,
                source = excluded.source,
                ticker_count = excluded.ticker_count
        """, (datetime.now(), 'wikipedia', len(constituents)))

        conn.commit()

    # Log changes
    if added:
        logger.info(f"S&P 500 additions: {sorted(added)}")
    if removed:
        logger.info(f"S&P 500 removals: {sorted(removed)}")

    return {
        'success': True,
        'ticker_count': len(constituents),
        'added': sorted(added),
        'removed': sorted(removed),
    }


def sync_sp500_flags() -> Dict:
    """
    Sync is_sp500 flags in ticker_metadata with current constituent list.

    Sets is_sp500=True for current constituents, False for removed ones.

    Returns:
        Dict with 'marked', 'unmarked' counts.
    """
    init_db()
    current_tickers = set(get_sp500_constituents())

    with get_connection() as conn:
        cursor = conn.cursor()

        # Mark current constituents
        marked = 0
        for ticker in current_tickers:
            cursor.execute("""
                INSERT INTO ticker_metadata (ticker, is_sp500)
                VALUES (?, 1)
                ON CONFLICT(ticker) DO UPDATE SET is_sp500 = 1
            """, (ticker,))
            marked += 1

        # Unmark removed constituents
        cursor.execute("""
            UPDATE ticker_metadata
            SET is_sp500 = 0
            WHERE is_sp500 = 1 AND ticker NOT IN ({})
        """.format(','.join('?' * len(current_tickers))), tuple(current_tickers))
        unmarked = cursor.rowcount

        conn.commit()

    logger.info(f"Synced S&P 500 flags: {marked} marked, {unmarked} unmarked")
    return {'marked': marked, 'unmarked': unmarked}


def get_sp500_constituents(refresh_if_stale: bool = True) -> List[str]:
    """
    Get the current S&P 500 constituent tickers.

    Fetches from Wikipedia and caches locally. Falls back to static list
    if fetch fails and no cache exists.

    Args:
        refresh_if_stale: If True, refresh from Wikipedia if cache is old.

    Returns:
        List of ticker symbols.
    """
    init_db()

    # Try to refresh if needed
    if refresh_if_stale:
        try:
            refresh_sp500_constituents(force=False)
        except Exception as e:
            logger.warning(f"Failed to refresh S&P 500 list: {e}")

    # Get from cache
    cached = get_cached_sp500_constituents()
    if cached:
        return cached

    # Fallback to static list
    logger.warning("No cached S&P 500 list, using fallback static list")
    return _get_fallback_sp500_list()


class SP500Cacher:
    """Handles batch caching of S&P 500 constituents."""

    def __init__(
        self,
        cache_manager: CacheManager,
        rate_limit_delay: float = 0,  # No rate limiting with unlimited API calls
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Initialize S&P 500 cacher.

        Args:
            cache_manager: CacheManager instance
            rate_limit_delay: Delay between API calls in seconds (0 = no limit)
            on_progress: Optional callback(processed, total, ticker) for progress updates
        """
        self.cache_manager = cache_manager
        self.rate_limit_delay = rate_limit_delay
        self.on_progress = on_progress

    def cache_all(
        self,
        start_date: date,
        end_date: date,
        incremental: bool = True
    ) -> Dict:
        """
        Cache data for all S&P 500 constituents.

        Args:
            start_date: Start of historical range
            end_date: End date (typically today)
            incremental: If True, only fetch missing data (uses cache)

        Returns:
            Dict with success_count, fail_count, failed_tickers, duration_seconds
        """
        tickers = get_sp500_constituents()
        start_time = time.time()

        success_count = 0
        fail_count = 0
        failed_tickers = []

        # Mark all as S&P 500 constituents
        self.cache_manager.mark_sp500(tickers)

        for i, ticker in enumerate(tickers):
            try:
                # Use force_refresh if not incremental
                self.cache_manager.get_bars(
                    ticker,
                    start_date,
                    end_date,
                    force_refresh=not incremental
                )
                success_count += 1

            except Exception as e:
                error_str = str(e).lower()
                # If rate limited, wait longer and retry once
                if '429' in error_str or 'rate' in error_str:
                    logger.info(f"Rate limited on {ticker}, waiting 60s and retrying...")
                    time.sleep(60)
                    try:
                        self.cache_manager.get_bars(ticker, start_date, end_date, force_refresh=not incremental)
                        success_count += 1
                    except Exception as retry_e:
                        logger.warning(f"Failed to cache {ticker} after retry: {retry_e}")
                        fail_count += 1
                        failed_tickers.append(ticker)
                else:
                    logger.warning(f"Failed to cache {ticker}: {e}")
                    fail_count += 1
                    failed_tickers.append(ticker)

            # Progress callback
            if self.on_progress:
                self.on_progress(i + 1, len(tickers), ticker)

            # Log progress every 50 tickers
            if (i + 1) % 50 == 0:
                logger.info(f"S&P 500 caching progress: {i + 1}/{len(tickers)}")

            # Rate limit delay between requests (skip if delay is 0)
            if self.rate_limit_delay > 0 and i < len(tickers) - 1:
                time.sleep(self.rate_limit_delay)

        duration = time.time() - start_time

        return {
            'success_count': success_count,
            'fail_count': fail_count,
            'failed_tickers': failed_tickers,
            'duration_seconds': round(duration, 2)
        }

    def update_stale_tickers(self, max_age_days: int = 1) -> Dict:
        """
        Update tickers that haven't been refreshed recently.

        Args:
            max_age_days: Update tickers older than this many days

        Returns:
            Dict with updated_count, failed_count
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        today = date.today()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticker FROM ticker_metadata
                WHERE is_sp500 = 1
                AND (last_updated IS NULL OR last_updated < ?)
            """, (cutoff,))

            stale_tickers = [row['ticker'] for row in cursor.fetchall()]

        if not stale_tickers:
            logger.info("No stale S&P 500 tickers to update")
            return {'updated_count': 0, 'failed_count': 0}

        logger.info(f"Updating {len(stale_tickers)} stale S&P 500 tickers")

        updated = 0
        failed = 0

        for ticker in stale_tickers:
            try:
                # Fetch just the recent data (last 30 days)
                start = today - timedelta(days=30)
                self.cache_manager.get_bars(ticker, start, today)
                updated += 1
            except Exception as e:
                logger.warning(f"Failed to update {ticker}: {e}")
                failed += 1

        return {'updated_count': updated, 'failed_count': failed}

    def get_caching_status(self) -> Dict:
        """Get current cache coverage for S&P 500."""
        tickers = get_sp500_constituents()

        with get_connection() as conn:
            cursor = conn.cursor()

            # Get tickers with cached data
            cursor.execute("""
                SELECT ticker, first_date, last_date, total_bars, last_updated
                FROM ticker_metadata
                WHERE is_sp500 = 1 AND total_bars > 0
            """)
            cached = {row['ticker']: dict(row) for row in cursor.fetchall()}

        # Calculate coverage
        cached_count = len(cached)
        total_count = len(tickers)
        missing = [t for t in tickers if t not in cached]

        # Find date range
        if cached:
            min_first = min(c['first_date'] for c in cached.values() if c['first_date'])
            max_last = max(c['last_date'] for c in cached.values() if c['last_date'])
            oldest_update = min(c['last_updated'] for c in cached.values() if c['last_updated'])
        else:
            min_first = max_last = oldest_update = None

        return {
            'total_sp500': total_count,
            'cached_count': cached_count,
            'missing_count': len(missing),
            'coverage_pct': round(cached_count / total_count * 100, 1),
            'earliest_data': str(min_first) if min_first else None,
            'latest_data': str(max_last) if max_last else None,
            'oldest_cache_update': str(oldest_update) if oldest_update else None,
            'missing_tickers': missing[:20] if len(missing) > 20 else missing  # Truncate if too many
        }


# Background job infrastructure
_job_thread: Optional[threading.Thread] = None
_current_job_id: Optional[int] = None


def create_cache_job(job_type: str, tickers_total: int) -> int:
    """Create a new cache job record and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cache_jobs (job_type, status, tickers_total, started_at)
            VALUES (?, 'running', ?, ?)
        """, (job_type, tickers_total, datetime.now()))
        conn.commit()
        return cursor.lastrowid


def update_job_progress(job_id: int, processed: int, failed: int = 0) -> None:
    """Update job progress in database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cache_jobs
            SET tickers_processed = ?, tickers_failed = ?
            WHERE id = ?
        """, (processed, failed, job_id))
        conn.commit()


def complete_job(job_id: int, status: str = 'completed', error_message: str = None) -> None:
    """Mark job as completed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cache_jobs
            SET status = ?, completed_at = ?, error_message = ?
            WHERE id = ?
        """, (status, datetime.now(), error_message, job_id))
        conn.commit()


def get_job_status(job_id: int = None) -> Dict:
    """Get status of a specific job or the most recent job."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if job_id:
            cursor.execute("SELECT * FROM cache_jobs WHERE id = ?", (job_id,))
        else:
            cursor.execute("""
                SELECT * FROM cache_jobs
                ORDER BY created_at DESC LIMIT 1
            """)

        row = cursor.fetchone()

        if not row:
            return {'status': 'no_jobs', 'message': 'No caching jobs found'}

        return {
            'job_id': row['id'],
            'job_type': row['job_type'],
            'status': row['status'],
            'tickers_total': row['tickers_total'],
            'tickers_processed': row['tickers_processed'],
            'tickers_failed': row['tickers_failed'],
            'started_at': str(row['started_at']) if row['started_at'] else None,
            'completed_at': str(row['completed_at']) if row['completed_at'] else None,
            'error_message': row['error_message'],
            'progress_pct': round(row['tickers_processed'] / row['tickers_total'] * 100, 1) if row['tickers_total'] else 0
        }


def run_sp500_cache_job(
    api_key: str,
    start_date: str,
    end_date: str,
    job_id: int
) -> None:
    """
    Background job to cache all S&P 500 data.

    This runs in a separate thread.
    """
    global _current_job_id

    try:
        _current_job_id = job_id

        # Import here to avoid circular imports
        from app import fetch_aggregate_bars

        cache_manager = CacheManager(api_key, fetch_func=fetch_aggregate_bars)

        failed_count = 0

        def on_progress(processed: int, total: int, ticker: str):
            nonlocal failed_count
            update_job_progress(job_id, processed, failed_count)

        cacher = SP500Cacher(cache_manager, on_progress=on_progress)

        result = cacher.cache_all(
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
            incremental=True
        )

        failed_count = result['fail_count']

        if result['fail_count'] > 0:
            error_msg = f"Failed tickers: {', '.join(result['failed_tickers'][:10])}"
            if len(result['failed_tickers']) > 10:
                error_msg += f" and {len(result['failed_tickers']) - 10} more"
            complete_job(job_id, 'completed_with_errors', error_msg)
        else:
            complete_job(job_id, 'completed')

        logger.info(f"S&P 500 cache job completed: {result['success_count']} success, {result['fail_count']} failed")

    except Exception as e:
        logger.error(f"S&P 500 cache job failed: {e}")
        complete_job(job_id, 'failed', str(e))

    finally:
        _current_job_id = None


def start_sp500_cache_job(
    api_key: str,
    start_date: str = None,  # Defaults to Config.HISTORICAL_START_DATE
    end_date: str = None
) -> Dict:
    """
    Start a background job to cache all S&P 500 data.

    Returns immediately with job_id that can be used to check progress.
    """
    global _job_thread

    if _job_thread is not None and _job_thread.is_alive():
        return {
            'status': 'already_running',
            'job_id': _current_job_id,
            'message': 'A caching job is already running'
        }

    if start_date is None:
        start_date = Config.HISTORICAL_START_DATE
    if end_date is None:
        end_date = date.today().isoformat()

    tickers = get_sp500_constituents()
    job_id = create_cache_job('sp500_full', len(tickers))

    _job_thread = threading.Thread(
        target=run_sp500_cache_job,
        args=(api_key, start_date, end_date, job_id),
        daemon=True
    )
    _job_thread.start()

    return {
        'status': 'started',
        'job_id': job_id,
        'tickers_total': len(tickers),
        'message': f'Started caching {len(tickers)} S&P 500 tickers in background'
    }
