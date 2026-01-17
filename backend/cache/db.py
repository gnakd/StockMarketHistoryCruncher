"""Database connection and schema initialization for price cache."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
import logging

logger = logging.getLogger(__name__)

# Default database path relative to backend directory
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "price_cache.db"


def get_db_path() -> Path:
    """Return the database path, creating parent directory if needed."""
    db_path = _DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def get_connection(db_path: Path = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.

    Args:
        db_path: Optional custom path to database file

    Yields:
        SQLite connection with Row factory enabled
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path = None) -> None:
    """
    Initialize database schema if tables don't exist.

    Args:
        db_path: Optional custom path to database file
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Daily OHLCV bars table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        """)

        # Indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_bars_ticker
            ON daily_bars(ticker)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_bars_date
            ON daily_bars(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_bars_ticker_date
            ON daily_bars(ticker, date)
        """)

        # Ticker metadata for cache management
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_metadata (
                ticker TEXT PRIMARY KEY,
                first_date DATE,
                last_date DATE,
                last_updated TIMESTAMP,
                last_full_refresh TIMESTAMP,
                total_bars INTEGER DEFAULT 0,
                is_sp500 BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_metadata_sp500
            ON ticker_metadata(is_sp500)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_metadata_last_updated
            ON ticker_metadata(last_updated)
        """)

        # Background job tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                tickers_total INTEGER,
                tickers_processed INTEGER DEFAULT 0,
                tickers_failed INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # S&P 500 constituent list cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sp500_constituents (
                ticker TEXT PRIMARY KEY,
                company_name TEXT,
                sector TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Track when the constituent list was last refreshed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sp500_list_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_refreshed TIMESTAMP,
                source TEXT,
                ticker_count INTEGER
            )
        """)

        conn.commit()
        logger.info("Database schema initialized successfully")


def get_db_stats(db_path: Path = None) -> dict:
    """
    Get database statistics.

    Returns:
        Dict with total_tickers, total_bars, database_size_mb
    """
    if db_path is None:
        db_path = get_db_path()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT ticker) FROM daily_bars")
        total_tickers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM daily_bars")
        total_bars = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM ticker_metadata WHERE is_sp500 = 1")
        sp500_cached = cursor.fetchone()[0]

    # Get file size
    size_mb = 0
    if db_path.exists():
        size_mb = round(db_path.stat().st_size / (1024 * 1024), 2)

    return {
        'total_tickers': total_tickers,
        'total_bars': total_bars,
        'sp500_cached': sp500_cached,
        'database_size_mb': size_mb
    }
