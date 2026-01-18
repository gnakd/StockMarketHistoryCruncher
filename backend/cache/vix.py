"""
VIX (Volatility Index) Data Module

Fetches VIX data from FRED (Federal Reserve Economic Data).
- Historical data from 1990 to present
- Free, no API key required for basic access
- Daily closing values
"""

import sqlite3
import requests
import pandas as pd
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple
import time

logger = logging.getLogger(__name__)

# FRED VIX data URL
FRED_VIX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"


class VIXManager:
    """Manages VIX data from FRED."""

    def __init__(self, db_path: str = "data/vix.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vix_data (
                    date TEXT PRIMARY KEY,
                    value REAL,
                    source TEXT DEFAULT 'fred',
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vix_date
                ON vix_data(date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
        logger.info("VIX database initialized")

    def load_fred_data(self, force_reload: bool = False) -> int:
        """
        Download and load VIX data from FRED.

        Args:
            force_reload: If True, reload even if data exists

        Returns:
            Number of records loaded
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if already loaded recently (within 1 day)
            if not force_reload:
                cursor = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'fred_loaded_at'"
                )
                row = cursor.fetchone()
                if row:
                    loaded_at = datetime.fromisoformat(row[0])
                    if (datetime.now() - loaded_at).days < 1:
                        logger.info("VIX data loaded recently, skipping (use force_reload=True to reload)")
                        return 0

        try:
            logger.info(f"Downloading VIX data from FRED...")
            response = requests.get(FRED_VIX_URL, timeout=30)
            response.raise_for_status()

            # Parse CSV
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            # Normalize column names
            df.columns = [c.strip().upper() for c in df.columns]

            # Find date and value columns
            date_col = 'DATE' if 'DATE' in df.columns else df.columns[0]
            value_col = 'VIXCLS' if 'VIXCLS' in df.columns else df.columns[1]

            records = []
            for _, row in df.iterrows():
                try:
                    date_str = str(row[date_col]).strip()
                    value_str = str(row[value_col]).strip()

                    # Skip missing values (FRED uses "." for missing)
                    if value_str == '.' or value_str == '' or value_str.lower() == 'nan':
                        continue

                    # Parse date
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    value = float(value_str)

                    records.append((
                        parsed_date.isoformat(),
                        value,
                        'fred',
                        datetime.now().isoformat()
                    ))
                except Exception as e:
                    continue

            # Insert into database
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO vix_data
                    (date, value, source, updated_at)
                    VALUES (?, ?, ?, ?)
                """, records)

                # Update metadata
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('fred_loaded_at', ?)",
                    (datetime.now().isoformat(),)
                )
                conn.commit()

            logger.info(f"Loaded {len(records)} VIX records from FRED")
            return len(records)

        except Exception as e:
            logger.error(f"Error loading FRED VIX data: {e}")
            return 0

    def get_value(self, target_date: date) -> Optional[float]:
        """Get VIX value for a specific date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM vix_data WHERE date = ?",
                (target_date.isoformat(),)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_series(self, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Get VIX time series.

        Returns:
            DataFrame with columns: date (index), value
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date, value
                FROM vix_data
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """, conn, params=(start_date.isoformat(), end_date.isoformat()))

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

        return df

    def get_data_range(self) -> Tuple[Optional[date], Optional[date]]:
        """Get the date range of available data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT MIN(date), MAX(date) FROM vix_data
            """)
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return (
                    date.fromisoformat(row[0]),
                    date.fromisoformat(row[1])
                )
        return None, None

    def get_stats(self) -> Dict:
        """Get statistics about VIX data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_records,
                    MIN(date) as start_date,
                    MAX(date) as end_date,
                    AVG(value) as avg_vix,
                    MIN(value) as min_vix,
                    MAX(value) as max_vix
                FROM vix_data
            """)
            row = cursor.fetchone()

            if row:
                return {
                    'total_records': row[0],
                    'start_date': row[1],
                    'end_date': row[2],
                    'avg_vix': round(row[3], 2) if row[3] else None,
                    'min_vix': round(row[4], 2) if row[4] else None,
                    'max_vix': round(row[5], 2) if row[5] else None
                }
            return {}


# Singleton instance
_vix_manager: Optional[VIXManager] = None


def get_vix_manager(db_path: str = "data/vix.db") -> VIXManager:
    """Get or create the global VIX manager."""
    global _vix_manager
    if _vix_manager is None:
        _vix_manager = VIXManager(db_path=db_path)
    return _vix_manager
