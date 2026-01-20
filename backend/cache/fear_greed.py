"""
CNN Fear & Greed Index Data Module

Hybrid approach:
- Historical data (2011-present): GitHub repo whit3rabbit/fear-greed-data
- Current/ongoing data: CNN endpoint for recent updates
- All data cached in SQLite
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

# Data source URLs
GITHUB_CSV_URL = "https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/fear-greed-2011-2023.csv"
CNN_API_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/"


class FearGreedManager:
    """Manages Fear & Greed Index data from multiple sources."""

    def __init__(self, db_path: str = "data/fear_greed.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fear_greed_data (
                    date TEXT PRIMARY KEY,
                    value REAL,
                    source TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feargreed_date
                ON fear_greed_data(date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
        logger.info("Fear & Greed database initialized")

    def load_github_historical(self, force_reload: bool = False) -> int:
        """
        Download and load historical Fear & Greed data from GitHub.

        Args:
            force_reload: If True, reload even if data exists

        Returns:
            Number of records loaded
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if already loaded recently (within 7 days)
            if not force_reload:
                cursor = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'github_loaded_at'"
                )
                row = cursor.fetchone()
                if row:
                    loaded_at = datetime.fromisoformat(row[0])
                    if (datetime.now() - loaded_at).days < 7:
                        logger.info("GitHub Fear & Greed data loaded recently, skipping (use force_reload=True to reload)")
                        return 0

        try:
            logger.info(f"Downloading Fear & Greed data from GitHub...")
            response = requests.get(GITHUB_CSV_URL, timeout=30)
            response.raise_for_status()

            # Parse CSV
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            # Normalize column names
            df.columns = [c.strip().lower() for c in df.columns]

            # Find date and value columns
            date_col = None
            value_col = None

            for col in df.columns:
                if 'date' in col:
                    date_col = col
                if 'value' in col or 'index' in col or 'score' in col or 'fear' in col:
                    if value_col is None:
                        value_col = col

            if date_col is None:
                date_col = df.columns[0]
            if value_col is None:
                value_col = df.columns[1]

            records = []
            for _, row in df.iterrows():
                try:
                    date_str = str(row[date_col]).strip()
                    value_str = str(row[value_col]).strip()

                    # Skip missing values
                    if value_str == '' or value_str.lower() == 'nan' or value_str == '.':
                        continue

                    # Parse date (try multiple formats)
                    parsed_date = None
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue

                    if parsed_date is None:
                        continue

                    value = float(value_str)

                    # Validate value is in expected range (0-100)
                    if value < 0 or value > 100:
                        continue

                    records.append((
                        parsed_date.isoformat(),
                        value,
                        'github',
                        datetime.now().isoformat()
                    ))
                except Exception as e:
                    continue

            # Insert into database
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO fear_greed_data
                    (date, value, source, updated_at)
                    VALUES (?, ?, ?, ?)
                """, records)

                # Update metadata
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('github_loaded_at', ?)",
                    (datetime.now().isoformat(),)
                )
                conn.commit()

            logger.info(f"Loaded {len(records)} Fear & Greed records from GitHub")
            return len(records)

        except Exception as e:
            logger.error(f"Error loading GitHub Fear & Greed data: {e}")
            return 0

    def fetch_cnn_current(self, start_date: Optional[date] = None) -> int:
        """
        Fetch recent Fear & Greed data from CNN API.

        Args:
            start_date: Start date for fetching (default: 30 days ago)

        Returns:
            Number of records loaded
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)

        try:
            url = f"{CNN_API_URL}{start_date.isoformat()}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            logger.info(f"Fetching CNN Fear & Greed data from {start_date}...")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            records = []

            # CNN returns data in 'fear_and_greed_historical' or similar structure
            historical_data = None
            if isinstance(data, dict):
                # Look for historical data in various possible keys
                for key in ['fear_and_greed_historical', 'fear_and_greed', 'data', 'historical']:
                    if key in data:
                        historical_data = data[key]
                        break

                # Also check for nested 'data' key
                if historical_data is None and 'data' in data:
                    historical_data = data['data']

            elif isinstance(data, list):
                historical_data = data

            if historical_data is None:
                logger.warning("Could not find historical data in CNN response")
                return 0

            # Handle different data structures
            if isinstance(historical_data, dict) and 'data' in historical_data:
                historical_data = historical_data['data']

            if isinstance(historical_data, list):
                for item in historical_data:
                    try:
                        # Handle different item formats
                        if isinstance(item, dict):
                            # Try various date field names
                            item_date = None
                            for date_key in ['x', 'date', 'timestamp', 't']:
                                if date_key in item:
                                    date_val = item[date_key]
                                    if isinstance(date_val, (int, float)):
                                        # Unix timestamp (milliseconds)
                                        item_date = datetime.fromtimestamp(date_val / 1000).date()
                                    else:
                                        item_date = datetime.fromisoformat(str(date_val).replace('Z', '')).date()
                                    break

                            # Try various value field names
                            value = None
                            for val_key in ['y', 'value', 'score', 'index']:
                                if val_key in item:
                                    value = float(item[val_key])
                                    break

                            if item_date and value is not None and 0 <= value <= 100:
                                records.append((
                                    item_date.isoformat(),
                                    value,
                                    'cnn',
                                    datetime.now().isoformat()
                                ))
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            # [timestamp, value] format
                            timestamp, value = item[0], item[1]
                            if isinstance(timestamp, (int, float)):
                                item_date = datetime.fromtimestamp(timestamp / 1000).date()
                            else:
                                item_date = datetime.fromisoformat(str(timestamp)).date()

                            if 0 <= float(value) <= 100:
                                records.append((
                                    item_date.isoformat(),
                                    float(value),
                                    'cnn',
                                    datetime.now().isoformat()
                                ))
                    except Exception as e:
                        continue

            if records:
                with sqlite3.connect(self.db_path) as conn:
                    conn.executemany("""
                        INSERT OR REPLACE INTO fear_greed_data
                        (date, value, source, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, records)

                    conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('cnn_loaded_at', ?)",
                        (datetime.now().isoformat(),)
                    )
                    conn.commit()

                logger.info(f"Loaded {len(records)} Fear & Greed records from CNN")

            return len(records)

        except Exception as e:
            logger.error(f"Error fetching CNN Fear & Greed data: {e}")
            return 0

    def load_data(self, force_reload: bool = False) -> int:
        """
        Load data from all sources.

        Args:
            force_reload: If True, force reload from all sources

        Returns:
            Total number of records loaded
        """
        total = 0

        # Load historical data from GitHub
        total += self.load_github_historical(force_reload=force_reload)

        # Update with recent data from CNN
        # Start from the last date in database or 30 days ago
        min_date, max_date = self.get_data_range()
        if max_date:
            start = max_date - timedelta(days=7)  # Overlap for safety
        else:
            start = date.today() - timedelta(days=365)

        total += self.fetch_cnn_current(start_date=start)

        return total

    def get_value(self, target_date: date) -> Optional[float]:
        """Get Fear & Greed Index value for a specific date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM fear_greed_data WHERE date = ?",
                (target_date.isoformat(),)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_series(self, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Get Fear & Greed Index time series.

        Returns:
            DataFrame with columns: date (index), value
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date, value
                FROM fear_greed_data
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
                SELECT MIN(date), MAX(date) FROM fear_greed_data
            """)
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return (
                    date.fromisoformat(row[0]),
                    date.fromisoformat(row[1])
                )
        return None, None

    def get_stats(self) -> Dict:
        """Get statistics about Fear & Greed data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_records,
                    MIN(date) as start_date,
                    MAX(date) as end_date,
                    AVG(value) as avg_value,
                    MIN(value) as min_value,
                    MAX(value) as max_value
                FROM fear_greed_data
            """)
            row = cursor.fetchone()

            if row:
                stats = {
                    'total_records': row[0],
                    'start_date': row[1],
                    'end_date': row[2],
                    'avg_value': round(row[3], 2) if row[3] else None,
                    'min_value': round(row[4], 2) if row[4] else None,
                    'max_value': round(row[5], 2) if row[5] else None
                }

                # Get source breakdown
                cursor = conn.execute("""
                    SELECT source, COUNT(*) FROM fear_greed_data GROUP BY source
                """)
                stats['sources'] = {row[0]: row[1] for row in cursor.fetchall()}

                return stats
            return {}


# Singleton instance
_feargreed_manager: Optional[FearGreedManager] = None


def get_feargreed_manager(db_path: str = "data/fear_greed.db") -> FearGreedManager:
    """Get or create the global Fear & Greed manager."""
    global _feargreed_manager
    if _feargreed_manager is None:
        _feargreed_manager = FearGreedManager(db_path=db_path)
    return _feargreed_manager
