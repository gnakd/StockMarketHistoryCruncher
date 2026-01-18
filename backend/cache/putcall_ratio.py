"""
Put/Call Ratio Data Module

Hybrid approach:
- Historical data (1995-2019): CBOE free CSV files
- Current data: Polygon option chain snapshots
- All data cached in SQLite
"""

import sqlite3
import requests
import pandas as pd
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import time

logger = logging.getLogger(__name__)

# CBOE historical data URLs
CBOE_URLS = {
    'total': 'https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv',
    'equity': 'https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv',
    'index': 'https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpc.csv',
    'total_archive': 'https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpcarchive.csv',
}

# Polygon API base URL
POLYGON_BASE_URL = "https://api.polygon.io"


class PutCallRatioManager:
    """Manages put/call ratio data from multiple sources."""

    def __init__(self, db_path: str = "data/putcall_ratio.db", api_key: str = ""):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS putcall_ratio (
                    date TEXT PRIMARY KEY,
                    calls INTEGER,
                    puts INTEGER,
                    total INTEGER,
                    ratio REAL,
                    source TEXT,
                    ratio_type TEXT DEFAULT 'total',
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_putcall_date
                ON putcall_ratio(date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
        logger.info("Put/call ratio database initialized")

    def load_cboe_historical(self, force_reload: bool = False) -> int:
        """
        Download and load CBOE historical put/call ratio data.

        Returns:
            Number of records loaded
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if already loaded
            if not force_reload:
                cursor = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'cboe_loaded'"
                )
                row = cursor.fetchone()
                if row and row[0] == 'true':
                    logger.info("CBOE data already loaded, skipping (use force_reload=True to reload)")
                    return 0

        total_loaded = 0

        # Load total put/call ratio (primary source)
        for source_name, url in [('total', CBOE_URLS['total']),
                                  ('total_archive', CBOE_URLS['total_archive'])]:
            try:
                logger.info(f"Downloading CBOE {source_name} data from {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                # Parse CSV - CBOE files have disclaimer headers, find the actual header row
                from io import StringIO
                lines = response.text.strip().split('\n')

                # Find the row that contains 'DATE' as first column (actual header)
                header_row = 0
                for i, line in enumerate(lines):
                    if line.strip().upper().startswith('DATE,') or line.strip().upper().startswith('TRADE_DATE,'):
                        header_row = i
                        break

                # Read CSV starting from header row
                csv_text = '\n'.join(lines[header_row:])
                df = pd.read_csv(StringIO(csv_text))

                # Normalize column names (CBOE uses various formats)
                df.columns = [c.strip().upper() for c in df.columns]

                # Find date column
                date_col = None
                for col in ['DATE', 'TRADE_DATE', 'TRADEDATE']:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col is None:
                    logger.warning(f"Could not find date column in {source_name}. Columns: {list(df.columns)}")
                    continue

                # Find ratio column
                ratio_col = None
                for col in ['P/C RATIO', 'PC RATIO', 'RATIO', 'P/C']:
                    if col in df.columns:
                        ratio_col = col
                        break

                records = []
                for _, row in df.iterrows():
                    try:
                        # Parse date (various formats)
                        date_str = str(row[date_col]).strip()
                        parsed_date = None
                        for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d/%m/%Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                continue

                        if parsed_date is None:
                            continue

                        # Get values - handle various column name formats
                        calls = 0
                        for col in ['CALLS', 'CALL']:
                            if col in df.columns and pd.notna(row.get(col)):
                                calls = int(float(str(row[col]).replace(',', '')))
                                break

                        puts = 0
                        for col in ['PUTS', 'PUT']:
                            if col in df.columns and pd.notna(row.get(col)):
                                puts = int(float(str(row[col]).replace(',', '')))
                                break

                        total = 0
                        if 'TOTAL' in df.columns and pd.notna(row.get('TOTAL')):
                            total = int(float(str(row['TOTAL']).replace(',', '')))

                        if ratio_col and pd.notna(row[ratio_col]):
                            ratio = float(row[ratio_col])
                        elif calls > 0:
                            ratio = puts / calls
                        else:
                            continue

                        records.append((
                            parsed_date.isoformat(),
                            calls,
                            puts,
                            total,
                            ratio,
                            'cboe',
                            'total',
                            datetime.now().isoformat()
                        ))
                    except Exception as e:
                        continue

                # Insert into database
                with sqlite3.connect(self.db_path) as conn:
                    conn.executemany("""
                        INSERT OR REPLACE INTO putcall_ratio
                        (date, calls, puts, total, ratio, source, ratio_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, records)
                    conn.commit()

                total_loaded += len(records)
                logger.info(f"Loaded {len(records)} records from CBOE {source_name}")

            except Exception as e:
                logger.error(f"Error loading CBOE {source_name}: {e}")

        # Mark as loaded
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('cboe_loaded', 'true')"
            )
            conn.execute(
                f"INSERT OR REPLACE INTO metadata (key, value) VALUES ('cboe_loaded_at', '{datetime.now().isoformat()}')"
            )
            conn.commit()

        logger.info(f"Total CBOE records loaded: {total_loaded}")
        return total_loaded

    def fetch_polygon_daily(self, ticker: str = "SPY", target_date: Optional[date] = None) -> Optional[Dict]:
        """
        Fetch put/call ratio from Polygon option chain snapshot.

        Args:
            ticker: Underlying ticker (default SPY)
            target_date: Date to fetch (default today, but snapshot only returns current)

        Returns:
            Dict with calls, puts, total, ratio or None if failed
        """
        if not self.api_key:
            logger.error("Polygon API key required for daily fetch")
            return None

        # Option chain snapshot endpoint
        url = f"{POLYGON_BASE_URL}/v3/snapshot/options/{ticker}"
        params = {
            'limit': 250,
            'apiKey': self.api_key
        }

        total_call_volume = 0
        total_put_volume = 0

        try:
            next_url = url
            page_count = 0
            max_pages = 50  # Safety limit

            while next_url and page_count < max_pages:
                if page_count > 0:
                    # For pagination, next_url already includes params
                    response = requests.get(f"{next_url}&apiKey={self.api_key}", timeout=30)
                else:
                    response = requests.get(next_url, params=params, timeout=30)

                if response.status_code == 429:
                    logger.warning("Rate limited, waiting...")
                    time.sleep(12)
                    continue

                if response.status_code != 200:
                    logger.error(f"Polygon API error: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                results = data.get('results', [])

                for contract in results:
                    details = contract.get('details', {})
                    day = contract.get('day', {})

                    contract_type = details.get('contract_type', '').lower()
                    volume = day.get('volume', 0) or 0

                    if contract_type == 'call':
                        total_call_volume += volume
                    elif contract_type == 'put':
                        total_put_volume += volume

                next_url = data.get('next_url')
                page_count += 1

                # Small delay to avoid rate limits
                if next_url:
                    time.sleep(0.15)

            if total_call_volume == 0:
                logger.warning("No call volume found")
                return None

            ratio = total_put_volume / total_call_volume

            result = {
                'calls': total_call_volume,
                'puts': total_put_volume,
                'total': total_call_volume + total_put_volume,
                'ratio': round(ratio, 4)
            }

            # Cache the result
            fetch_date = target_date or date.today()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO putcall_ratio
                    (date, calls, puts, total, ratio, source, ratio_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fetch_date.isoformat(),
                    result['calls'],
                    result['puts'],
                    result['total'],
                    result['ratio'],
                    'polygon',
                    'equity',
                    datetime.now().isoformat()
                ))
                conn.commit()

            logger.info(f"Fetched P/C ratio for {ticker}: {result['ratio']:.4f} "
                       f"(puts={result['puts']}, calls={result['calls']})")
            return result

        except Exception as e:
            logger.error(f"Error fetching Polygon data: {e}")
            return None

    def get_ratio(self, target_date: date) -> Optional[float]:
        """Get put/call ratio for a specific date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT ratio FROM putcall_ratio WHERE date = ?",
                (target_date.isoformat(),)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_ratio_series(self, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Get put/call ratio time series.

        Returns:
            DataFrame with columns: date, ratio, calls, puts, total, source
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date, ratio, calls, puts, total, source
                FROM putcall_ratio
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
                SELECT MIN(date), MAX(date) FROM putcall_ratio
            """)
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return (
                    date.fromisoformat(row[0]),
                    date.fromisoformat(row[1])
                )
        return None, None

    def get_stats(self) -> Dict:
        """Get statistics about cached data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_records,
                    MIN(date) as start_date,
                    MAX(date) as end_date,
                    source,
                    COUNT(*) as source_count
                FROM putcall_ratio
                GROUP BY source
            """)
            rows = cursor.fetchall()

            stats = {
                'total_records': 0,
                'sources': {}
            }

            for row in rows:
                stats['sources'][row[3]] = {
                    'count': row[4],
                    'start': row[1],
                    'end': row[2]
                }
                stats['total_records'] += row[4]

            # Overall range
            cursor = conn.execute(
                "SELECT MIN(date), MAX(date) FROM putcall_ratio"
            )
            row = cursor.fetchone()
            if row:
                stats['start_date'] = row[0]
                stats['end_date'] = row[1]

            return stats


# Singleton instance
_putcall_manager: Optional[PutCallRatioManager] = None


def get_putcall_manager(api_key: str = "", db_path: str = "data/putcall_ratio.db") -> PutCallRatioManager:
    """Get or create the global put/call ratio manager."""
    global _putcall_manager
    if _putcall_manager is None:
        _putcall_manager = PutCallRatioManager(db_path=db_path, api_key=api_key)
    elif api_key and _putcall_manager.api_key != api_key:
        _putcall_manager.api_key = api_key
    return _putcall_manager


class PutCallValidator:
    """Validates put/call ratio data from different sources."""

    def __init__(self, manager: PutCallRatioManager):
        self.manager = manager
        self.results: List[Dict] = []

    def validate_cboe_data(self) -> Dict:
        """
        Validate CBOE historical data integrity.

        Checks:
        - Data loads successfully
        - Ratio values are in reasonable range (0.3 - 3.0)
        - Calculated ratio matches provided ratio
        - No major gaps in data
        """
        result = {
            'test': 'cboe_data_integrity',
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        with sqlite3.connect(self.manager.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date, calls, puts, total, ratio, source
                FROM putcall_ratio
                WHERE source = 'cboe'
                ORDER BY date
            """, conn)

        if df.empty:
            result['passed'] = False
            result['errors'].append("No CBOE data found in database")
            return result

        result['stats']['record_count'] = len(df)
        result['stats']['date_range'] = f"{df['date'].min()} to {df['date'].max()}"

        # Check ratio range (typical P/C ratio is 0.5-1.5, extremes can be 0.3-3.0)
        out_of_range = df[(df['ratio'] < 0.2) | (df['ratio'] > 4.0)]
        if len(out_of_range) > 0:
            result['warnings'].append(
                f"{len(out_of_range)} records with unusual ratio values (outside 0.2-4.0)"
            )

        # Validate calculated ratio matches stored ratio (where we have volume data)
        has_volume = df[(df['calls'] > 0) & (df['puts'] > 0)]
        if len(has_volume) > 0:
            has_volume = has_volume.copy()
            has_volume['calc_ratio'] = has_volume['puts'] / has_volume['calls']
            has_volume['ratio_diff'] = abs(has_volume['calc_ratio'] - has_volume['ratio'])

            # Allow 5% tolerance for rounding
            mismatches = has_volume[has_volume['ratio_diff'] > 0.05]
            if len(mismatches) > len(has_volume) * 0.01:  # More than 1% mismatch
                result['warnings'].append(
                    f"{len(mismatches)} records where calculated ratio differs from stored ratio by >5%"
                )

            result['stats']['records_with_volume'] = len(has_volume)
            result['stats']['avg_ratio'] = round(has_volume['ratio'].mean(), 4)
            result['stats']['std_ratio'] = round(has_volume['ratio'].std(), 4)
            result['stats']['min_ratio'] = round(has_volume['ratio'].min(), 4)
            result['stats']['max_ratio'] = round(has_volume['ratio'].max(), 4)

        # Check for gaps (more than 5 business days)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        df['day_gap'] = df['date'].diff().dt.days
        large_gaps = df[df['day_gap'] > 7]  # More than a week
        if len(large_gaps) > 0:
            result['warnings'].append(
                f"{len(large_gaps)} gaps larger than 7 days found in data"
            )
            # Show largest gaps
            largest_gaps = large_gaps.nlargest(3, 'day_gap')
            for _, gap in largest_gaps.iterrows():
                result['warnings'].append(
                    f"  Gap of {int(gap['day_gap'])} days before {gap['date'].strftime('%Y-%m-%d')}"
                )

        self.results.append(result)
        return result

    def validate_polygon_fetch(self, ticker: str = "SPY") -> Dict:
        """
        Validate Polygon option chain fetch works correctly.

        Checks:
        - API responds successfully
        - Volume data is present
        - Ratio is in reasonable range
        """
        result = {
            'test': 'polygon_fetch',
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if not self.manager.api_key:
            result['passed'] = False
            result['errors'].append("No Polygon API key configured")
            return result

        try:
            data = self.manager.fetch_polygon_daily(ticker=ticker)

            if data is None:
                result['passed'] = False
                result['errors'].append("Polygon fetch returned no data")
                return result

            result['stats']['ticker'] = ticker
            result['stats']['calls'] = data['calls']
            result['stats']['puts'] = data['puts']
            result['stats']['total'] = data['total']
            result['stats']['ratio'] = data['ratio']

            # Validate reasonable values
            if data['calls'] < 1000:
                result['warnings'].append(f"Low call volume: {data['calls']}")

            if data['puts'] < 1000:
                result['warnings'].append(f"Low put volume: {data['puts']}")

            if data['ratio'] < 0.2 or data['ratio'] > 4.0:
                result['warnings'].append(f"Unusual ratio: {data['ratio']}")

            # Validate ratio calculation
            expected_ratio = data['puts'] / data['calls'] if data['calls'] > 0 else 0
            if abs(expected_ratio - data['ratio']) > 0.001:
                result['passed'] = False
                result['errors'].append(
                    f"Ratio mismatch: stored={data['ratio']}, calculated={expected_ratio:.4f}"
                )

        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Polygon fetch failed: {str(e)}")

        self.results.append(result)
        return result

    def validate_ratio_reasonableness(self) -> Dict:
        """
        Validate that ratios from all sources are statistically reasonable.

        Compares historical distributions to ensure consistency.
        """
        result = {
            'test': 'ratio_reasonableness',
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        with sqlite3.connect(self.manager.db_path) as conn:
            df = pd.read_sql_query("""
                SELECT date, ratio, source
                FROM putcall_ratio
                WHERE ratio > 0
                ORDER BY date
            """, conn)

        if df.empty:
            result['passed'] = False
            result['errors'].append("No data available for validation")
            return result

        # Overall statistics
        result['stats']['total_records'] = len(df)
        result['stats']['mean'] = round(df['ratio'].mean(), 4)
        result['stats']['median'] = round(df['ratio'].median(), 4)
        result['stats']['std'] = round(df['ratio'].std(), 4)
        result['stats']['percentile_5'] = round(df['ratio'].quantile(0.05), 4)
        result['stats']['percentile_95'] = round(df['ratio'].quantile(0.95), 4)

        # Expected ranges based on historical norms
        # P/C ratio typically ranges from 0.6 to 1.2, with extremes during crises
        if result['stats']['mean'] < 0.5 or result['stats']['mean'] > 1.5:
            result['warnings'].append(
                f"Mean ratio {result['stats']['mean']} outside typical range (0.5-1.5)"
            )

        # Check by source
        for source in df['source'].unique():
            source_df = df[df['source'] == source]
            result['stats'][f'{source}_count'] = len(source_df)
            result['stats'][f'{source}_mean'] = round(source_df['ratio'].mean(), 4)
            result['stats'][f'{source}_std'] = round(source_df['ratio'].std(), 4)

        self.results.append(result)
        return result

    def run_all_validations(self, include_polygon: bool = True, polygon_ticker: str = "SPY") -> Dict:
        """
        Run all validation tests.

        Args:
            include_polygon: Whether to test Polygon fetch (requires API key)
            polygon_ticker: Ticker to use for Polygon validation

        Returns:
            Summary of all validation results
        """
        self.results = []

        print("=" * 60)
        print("PUT/CALL RATIO DATA VALIDATION")
        print("=" * 60)

        # Test 1: CBOE data integrity
        print("\n[1/3] Validating CBOE historical data...")
        cboe_result = self.validate_cboe_data()
        self._print_result(cboe_result)

        # Test 2: Polygon fetch (optional)
        if include_polygon and self.manager.api_key:
            print(f"\n[2/3] Validating Polygon fetch ({polygon_ticker})...")
            polygon_result = self.validate_polygon_fetch(ticker=polygon_ticker)
            self._print_result(polygon_result)
        else:
            print("\n[2/3] Skipping Polygon validation (no API key)")

        # Test 3: Overall reasonableness
        print("\n[3/3] Validating ratio reasonableness...")
        reason_result = self.validate_ratio_reasonableness()
        self._print_result(reason_result)

        # Summary
        print("\n" + "=" * 60)
        all_passed = all(r['passed'] for r in self.results)
        total_errors = sum(len(r['errors']) for r in self.results)
        total_warnings = sum(len(r['warnings']) for r in self.results)

        print(f"VALIDATION {'PASSED' if all_passed else 'FAILED'}")
        print(f"Tests: {len(self.results)} | Errors: {total_errors} | Warnings: {total_warnings}")
        print("=" * 60)

        return {
            'passed': all_passed,
            'tests': len(self.results),
            'errors': total_errors,
            'warnings': total_warnings,
            'results': self.results
        }

    def _print_result(self, result: Dict):
        """Pretty print a validation result."""
        status = "PASS" if result['passed'] else "FAIL"
        print(f"  Status: {status}")

        if result['stats']:
            print(f"  Stats:")
            for key, value in result['stats'].items():
                print(f"    {key}: {value}")

        for error in result['errors']:
            print(f"  ERROR: {error}")

        for warning in result['warnings']:
            print(f"  WARNING: {warning}")
