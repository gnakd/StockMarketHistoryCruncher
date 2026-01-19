from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import logging
from config import Config
from cache.putcall_ratio import get_putcall_manager, PutCallRatioManager
from cache.vix import get_vix_manager, VIXManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global cache manager instance (lazy initialized)
_cache_manager = None

# Polygon.io base URL
POLYGON_BASE_URL = "https://api.polygon.io"


def fetch_aggregate_bars(ticker, start_date, end_date, api_key):
    """Fetch daily aggregate bars from Polygon.io"""
    url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    params = {
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
        'apiKey': api_key
    }

    all_results = []
    while url:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"API error for {ticker}: {response.status_code} - {response.text}")

        data = response.json()
        if 'results' in data:
            all_results.extend(data['results'])

        # Handle pagination
        url = data.get('next_url')
        if url:
            params = {'apiKey': api_key}

    return all_results


def get_cache_manager(api_key: str):
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None or _cache_manager.api_key != api_key:
        from cache.manager import CacheManager
        _cache_manager = CacheManager(api_key, fetch_func=fetch_aggregate_bars)
    return _cache_manager


def dataframe_to_polygon_format(df: pd.DataFrame) -> list:
    """Convert a DataFrame back to Polygon-style dict list."""
    if df.empty:
        return []

    result = []
    for idx, row in df.iterrows():
        bar = {
            't': int(idx.timestamp() * 1000),  # milliseconds
            'o': row['open'],
            'h': row['high'],
            'l': row['low'],
            'c': row['close'],
            'v': int(row['volume']) if pd.notna(row['volume']) else 0
        }
        result.append(bar)
    return result


def fetch_aggregate_bars_cached(
    ticker: str,
    start_date: str,
    end_date: str,
    api_key: str,
    use_cache: bool = True
) -> list:
    """
    Fetch daily aggregate bars, using cache when available.

    This wraps the original fetch_aggregate_bars to add caching.

    Args:
        ticker: Stock symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        api_key: Polygon.io API key
        use_cache: If False, bypass cache and fetch directly from API

    Returns:
        List of bar dicts in Polygon format
    """
    if not use_cache or not Config.CACHE_ENABLED:
        return fetch_aggregate_bars(ticker, start_date, end_date, api_key)

    cache = get_cache_manager(api_key)
    df = cache.get_bars(
        ticker,
        date.fromisoformat(start_date),
        date.fromisoformat(end_date)
    )

    return dataframe_to_polygon_format(df)


def fetch_rsi(ticker, start_date, end_date, window, api_key):
    """Fetch RSI indicator from Polygon.io"""
    url = f"{POLYGON_BASE_URL}/v1/indicators/rsi/{ticker}"
    params = {
        'timespan': 'day',
        'adjusted': 'true',
        'window': window,
        'series_type': 'close',
        'order': 'asc',
        'timestamp.gte': start_date,
        'timestamp.lte': end_date,
        'limit': 5000,
        'apiKey': api_key
    }

    all_results = []
    next_url = url
    while next_url:
        response = requests.get(next_url, params=params if next_url == url else {'apiKey': api_key})
        if response.status_code != 200:
            return None  # RSI endpoint may not be available, fall back to manual calculation

        data = response.json()
        if 'results' in data and 'values' in data['results']:
            all_results.extend(data['results']['values'])

        next_url = data.get('next_url')

    return all_results


def fetch_sma(ticker, start_date, end_date, window, api_key):
    """Fetch SMA indicator from Polygon.io"""
    url = f"{POLYGON_BASE_URL}/v1/indicators/sma/{ticker}"
    params = {
        'timespan': 'day',
        'adjusted': 'true',
        'window': window,
        'series_type': 'close',
        'order': 'asc',
        'timestamp.gte': start_date,
        'timestamp.lte': end_date,
        'limit': 5000,
        'apiKey': api_key
    }

    all_results = []
    next_url = url
    while next_url:
        response = requests.get(next_url, params=params if next_url == url else {'apiKey': api_key})
        if response.status_code != 200:
            return None

        data = response.json()
        if 'results' in data and 'values' in data['results']:
            all_results.extend(data['results']['values'])

        next_url = data.get('next_url')

    return all_results


def compute_rsi(prices_df, period=14):
    """Compute RSI manually using pandas"""
    delta = prices_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_sma(prices_df, window):
    """Compute SMA manually"""
    return prices_df['close'].rolling(window=window).mean()


def compute_momentum(prices_df, period):
    """Compute momentum as percentage change over period"""
    return prices_df['close'].pct_change(periods=period)


def get_sp500_constituents():
    """Return the full list of S&P 500 constituents"""
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


def compute_breadth_pct_below_200ma(ticker_data_dict, target_df):
    """
    Compute the percentage of stocks below their 200-day moving average.
    Returns a DataFrame aligned to target_df dates with pct_below_200ma column.
    """
    # First, compute 200 DMA for each stock
    stock_below_200ma = {}

    for ticker, df in ticker_data_dict.items():
        if len(df) < 200:
            continue
        df = df.copy()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        df['below_200ma'] = df['close'] < df['sma_200']
        stock_below_200ma[ticker] = df['below_200ma']

    if not stock_below_200ma:
        return pd.DataFrame()

    # Combine all into a single DataFrame
    combined = pd.DataFrame(stock_below_200ma)

    # For each date, compute % of stocks below 200 DMA
    breadth_series = combined.sum(axis=1) / combined.count(axis=1) * 100

    breadth_df = pd.DataFrame({'pct_below_200ma': breadth_series})

    # Align to target_df dates
    breadth_df = breadth_df.reindex(target_df.index, method='ffill')

    return breadth_df


def find_breadth_below_threshold_events(breadth_df, params):
    """
    Find dates where % of stocks below 200 DMA falls at or below threshold.
    Triggers when breadth drops to or below the threshold from above.
    """
    threshold = params.get('breadth_threshold', 30)  # Default 30%

    events = []

    pct_col = breadth_df['pct_below_200ma']

    for i in range(1, len(breadth_df)):
        date = breadth_df.index[i]
        current_pct = pct_col.iloc[i]
        prev_pct = pct_col.iloc[i-1]

        if pd.isna(current_pct) or pd.isna(prev_pct):
            continue

        # Trigger when crossing at or below threshold from above
        if prev_pct > threshold and current_pct <= threshold:
            if not events or (date - events[-1]).days > 5:
                events.append(date)

    return events


def bars_to_dataframe(bars):
    """Convert Polygon bars to pandas DataFrame"""
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    df['date'] = pd.to_datetime(df['t'], unit='ms')
    df = df.rename(columns={
        'o': 'open',
        'h': 'high',
        'l': 'low',
        'c': 'close',
        'v': 'volume'
    })
    df = df.set_index('date')
    df = df.sort_index()
    return df[['open', 'high', 'low', 'close', 'volume']]


def find_dual_ath_events(condition_dfs, params):
    """Find dates where all condition tickers hit ATH after days_gap"""
    days_gap = params.get('days_gap', 365)

    if len(condition_dfs) < 2:
        raise ValueError("Dual ATH requires at least 2 condition tickers")

    # Align all DataFrames to common dates
    common_index = condition_dfs[0].index
    for df in condition_dfs[1:]:
        common_index = common_index.intersection(df.index)

    aligned_dfs = [df.loc[common_index] for df in condition_dfs]

    events = []

    for i, date in enumerate(common_index):
        if i < days_gap:
            continue

        all_at_ath = True
        all_gap_satisfied = True

        for df in aligned_dfs:
            current_close = df.loc[date, 'close']
            historical_max = df.iloc[:i]['close'].max()

            # Check if current is at or above ATH
            if current_close < historical_max:
                all_at_ath = False
                break

            # Find last ATH date
            ath_dates = df.iloc[:i][df.iloc[:i]['close'] >= historical_max * 0.9999].index
            if len(ath_dates) > 0:
                last_ath = ath_dates[-1]
                days_since_ath = len(df.loc[last_ath:date]) - 1
                if days_since_ath < days_gap:
                    all_gap_satisfied = False
                    break

        if all_at_ath and all_gap_satisfied:
            # Check this isn't consecutive to previous event
            if not events or (date - events[-1]).days > 5:
                events.append(date)

    return events


def find_single_ath_events(condition_dfs, params):
    """Find dates where first ticker hits ATH after days_gap"""
    days_gap = params.get('days_gap', 365)
    df = condition_dfs[0]

    events = []
    rolling_max = df['close'].expanding().max()

    for i in range(days_gap, len(df)):
        date = df.index[i]
        current = df.iloc[i]['close']
        prev_max = df.iloc[:i]['close'].max()

        if current >= prev_max:
            # Find last ATH
            ath_mask = df.iloc[:i]['close'] >= prev_max * 0.9999
            if ath_mask.any():
                last_ath_idx = df.iloc[:i][ath_mask].index[-1]
                days_since = len(df.loc[last_ath_idx:date]) - 1

                if days_since >= days_gap:
                    if not events or (date - events[-1]).days > 5:
                        events.append(date)

    return events


def find_rsi_crossover_events(condition_dfs, params, api_key, ticker, start_date, end_date):
    """Find dates where RSI crosses above/below threshold"""
    period = params.get('rsi_period', 14)
    threshold = params.get('rsi_threshold', 70)
    cross_above = params.get('cross_above', True)

    df = condition_dfs[0].copy()

    # Always use manual RSI calculation for consistency
    # (Polygon API uses different formula that gives different values)
    df['rsi'] = compute_rsi(df, period)

    events = []

    for i in range(1, len(df)):
        date = df.index[i]
        current_rsi = df.iloc[i]['rsi']
        prev_rsi = df.iloc[i-1]['rsi']

        if pd.isna(current_rsi) or pd.isna(prev_rsi):
            continue

        if cross_above:
            if prev_rsi < threshold and current_rsi >= threshold:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)
        else:
            if prev_rsi > threshold and current_rsi <= threshold:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)

    return events


def find_ma_crossover_events(condition_dfs, params, api_key, ticker, start_date, end_date):
    """Find dates where short MA crosses above long MA"""
    short_period = params.get('ma_short', 50)
    long_period = params.get('ma_long', 200)
    cross_above = params.get('cross_above', True)

    df = condition_dfs[0].copy()

    # Try API first for SMAs
    short_sma_data = fetch_sma(ticker, start_date, end_date, short_period, api_key)
    long_sma_data = fetch_sma(ticker, start_date, end_date, long_period, api_key)

    if short_sma_data and long_sma_data:
        short_df = pd.DataFrame(short_sma_data)
        short_df['date'] = pd.to_datetime(short_df['timestamp'], unit='ms')
        short_df = short_df.set_index('date')

        long_df = pd.DataFrame(long_sma_data)
        long_df['date'] = pd.to_datetime(long_df['timestamp'], unit='ms')
        long_df = long_df.set_index('date')

        df['sma_short'] = short_df['value']
        df['sma_long'] = long_df['value']
    else:
        df['sma_short'] = compute_sma(df, short_period)
        df['sma_long'] = compute_sma(df, long_period)

    events = []

    for i in range(1, len(df)):
        date = df.index[i]
        curr_short = df.iloc[i]['sma_short']
        curr_long = df.iloc[i]['sma_long']
        prev_short = df.iloc[i-1]['sma_short']
        prev_long = df.iloc[i-1]['sma_long']

        if any(pd.isna([curr_short, curr_long, prev_short, prev_long])):
            continue

        if cross_above:
            if prev_short <= prev_long and curr_short > curr_long:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)
        else:
            if prev_short >= prev_long and curr_short < curr_long:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)

    return events


def find_momentum_events(condition_dfs, params):
    """Find dates where momentum crosses threshold"""
    period = params.get('momentum_period', 12)
    threshold = params.get('momentum_threshold', 0.05)

    df = condition_dfs[0].copy()
    df['momentum'] = compute_momentum(df, period)

    events = []

    for i in range(1, len(df)):
        date = df.index[i]
        current_mom = df.iloc[i]['momentum']
        prev_mom = df.iloc[i-1]['momentum']

        if pd.isna(current_mom) or pd.isna(prev_mom):
            continue

        if threshold > 0:
            if prev_mom < threshold and current_mom >= threshold:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)
        else:
            if prev_mom > threshold and current_mom <= threshold:
                if not events or (date - events[-1]).days > 5:
                    events.append(date)

    return events


def find_putcall_events(start_date: str, end_date: str, params: dict, cross_above: bool = True):
    """
    Find dates where put/call ratio crosses threshold.

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        params: Dict with 'putcall_threshold' key
        cross_above: If True, find crosses above threshold (high fear = buy signal)
                    If False, find crosses below threshold (complacency = caution)

    Returns:
        List of datetime dates when crossover occurred
    """
    threshold = params.get('putcall_threshold', 1.0 if cross_above else 0.7)

    # Get put/call ratio manager (CBOE data should already be loaded)
    manager = get_putcall_manager()

    # Ensure CBOE data is loaded
    manager.load_cboe_historical(force_reload=False)

    # Get ratio series
    start_dt = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)
    df = manager.get_ratio_series(start_dt, end_dt)

    if df.empty:
        logger.warning(f"No put/call ratio data available for {start_date} to {end_date}")
        return []

    events = []

    for i in range(1, len(df)):
        current_date = df.index[i]
        current_ratio = df.iloc[i]['ratio']
        prev_ratio = df.iloc[i-1]['ratio']

        if pd.isna(current_ratio) or pd.isna(prev_ratio):
            continue

        # Convert to pandas Timestamp for consistent comparison
        current_ts = pd.Timestamp(current_date)

        if cross_above:
            # Crossing above threshold (e.g., P/C > 1.0 = fear spike)
            if prev_ratio < threshold and current_ratio >= threshold:
                # Avoid clustering events too close together (5 day minimum gap)
                if not events or (current_ts - events[-1]).days > 5:
                    events.append(current_ts)
        else:
            # Crossing below threshold (e.g., P/C < 0.7 = complacency)
            if prev_ratio > threshold and current_ratio <= threshold:
                if not events or (current_ts - events[-1]).days > 5:
                    events.append(current_ts)

    logger.info(f"Found {len(events)} put/call {'above' if cross_above else 'below'} {threshold} events")
    return events


def find_vix_events(start_date: str, end_date: str, params: dict, cross_above: bool = True):
    """
    Find dates where VIX crosses threshold.

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        params: Dict with 'vix_threshold' key
        cross_above: If True, find crosses above threshold (fear spike = buy signal)
                    If False, find crosses below threshold (complacency = caution)

    Returns:
        List of datetime dates when crossover occurred
    """
    threshold = params.get('vix_threshold', 30 if cross_above else 15)

    # Get VIX manager and ensure data is loaded
    manager = get_vix_manager()
    manager.load_fred_data(force_reload=False)

    # Get VIX series
    start_dt = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)
    df = manager.get_series(start_dt, end_dt)

    if df.empty:
        logger.warning(f"No VIX data available for {start_date} to {end_date}")
        return []

    events = []

    for i in range(1, len(df)):
        current_date = df.index[i]
        current_vix = df.iloc[i]['value']
        prev_vix = df.iloc[i-1]['value']

        if pd.isna(current_vix) or pd.isna(prev_vix):
            continue

        # Convert to pandas Timestamp for consistent comparison
        current_ts = pd.Timestamp(current_date)

        if cross_above:
            # Crossing above threshold (e.g., VIX > 30 = fear spike)
            if prev_vix < threshold and current_vix >= threshold:
                # Avoid clustering events too close together (5 day minimum gap)
                if not events or (current_ts - events[-1]).days > 5:
                    events.append(current_ts)
        else:
            # Crossing below threshold (e.g., VIX < 15 = complacency)
            if prev_vix > threshold and current_vix <= threshold:
                if not events or (current_ts - events[-1]).days > 5:
                    events.append(current_ts)

    logger.info(f"Found {len(events)} VIX {'above' if cross_above else 'below'} {threshold} events")
    return events


def compute_forward_returns(target_df, event_dates, intervals):
    """Compute forward returns for each event"""
    results = []

    for event_date in event_dates:
        if event_date not in target_df.index:
            # Find nearest trading day
            idx = target_df.index.get_indexer([event_date], method='nearest')[0]
            event_date = target_df.index[idx]

        event_idx = target_df.index.get_loc(event_date)
        event_price = target_df.iloc[event_idx]['close']

        event_result = {
            'date': event_date.strftime('%Y-%m-%d'),
            'price': float(event_price)
        }

        # Forward returns at each interval
        for name, days in intervals.items():
            future_idx = event_idx + days
            if future_idx < len(target_df):
                future_price = target_df.iloc[future_idx]['close']
                pct_return = ((future_price - event_price) / event_price) * 100
                event_result[name] = round(float(pct_return), 2)

                # Max drawdown for this period
                period_prices = target_df.iloc[event_idx:future_idx + 1]['close']
                running_max = period_prices.expanding().max()
                drawdowns = (period_prices - running_max) / running_max * 100
                period_max_dd = float(drawdowns.min())
                event_result[f'{name}_max_dd'] = round(period_max_dd, 2)
            else:
                event_result[name] = None
                event_result[f'{name}_max_dd'] = None

        # Max drawdown over next year (keep for backwards compatibility)
        year_end_idx = min(event_idx + 252, len(target_df))
        if year_end_idx > event_idx:
            future_prices = target_df.iloc[event_idx:year_end_idx]['close']
            running_max = future_prices.expanding().max()
            drawdowns = (future_prices - running_max) / running_max * 100
            max_drawdown = float(drawdowns.min())
            event_result['max_drawdown'] = round(max_drawdown, 2)
        else:
            event_result['max_drawdown'] = None

        results.append(event_result)

    return results


def compute_average_forward_curve(target_df, event_dates, days=252):
    """Compute forward returns statistics curve aligned by trading days.

    Returns a dict with:
    - avg: average return at each day
    - max: maximum return at each day (best case)
    - min: minimum return at each day (worst case)
    - std: standard deviation at each day
    """
    curves = []

    for event_date in event_dates:
        if event_date not in target_df.index:
            idx = target_df.index.get_indexer([event_date], method='nearest')[0]
            event_date = target_df.index[idx]

        event_idx = target_df.index.get_loc(event_date)
        event_price = target_df.iloc[event_idx]['close']

        curve = []
        for d in range(days + 1):
            future_idx = event_idx + d
            if future_idx < len(target_df):
                future_price = target_df.iloc[future_idx]['close']
                pct_return = ((future_price - event_price) / event_price) * 100
                curve.append(float(pct_return))
            else:
                curve.append(None)

        curves.append(curve)

    # Compute statistics at each day, ignoring None values
    avg_curve = []
    median_curve = []
    max_curve = []
    min_curve = []
    std_curve = []

    for d in range(days + 1):
        values = [c[d] for c in curves if c[d] is not None]
        if values:
            avg_val = sum(values) / len(values)
            avg_curve.append(round(avg_val, 2))
            max_curve.append(round(max(values), 2))
            min_curve.append(round(min(values), 2))
            # Median
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            if n % 2 == 0:
                median_val = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
            else:
                median_val = sorted_vals[n//2]
            median_curve.append(round(median_val, 2))
            # Standard deviation
            if len(values) > 1:
                variance = sum((v - avg_val) ** 2 for v in values) / len(values)
                std_curve.append(round(variance ** 0.5, 2))
            else:
                std_curve.append(0)
        else:
            avg_curve.append(None)
            median_curve.append(None)
            max_curve.append(None)
            min_curve.append(None)
            std_curve.append(None)

    return {
        'avg': avg_curve,
        'median': median_curve,
        'max': max_curve,
        'min': min_curve,
        'std': std_curve
    }


def compute_statistics(event_results, intervals):
    """Compute averages and positive percentages"""
    averages = {}
    positives = {}

    # Compute stats for returns and max_drawdown
    for name in list(intervals.keys()) + ['max_drawdown']:
        values = [r[name] for r in event_results if r.get(name) is not None]
        if values:
            averages[name] = round(sum(values) / len(values), 2)
            positives[name] = round(sum(1 for v in values if v > 0) / len(values) * 100, 1)
        else:
            averages[name] = None
            positives[name] = None

    # Compute stats for per-period max drawdowns
    for name in intervals.keys():
        dd_key = f'{name}_max_dd'
        values = [r[dd_key] for r in event_results if r.get(dd_key) is not None]
        if values:
            averages[dd_key] = round(sum(values) / len(values), 2)
            # For drawdown, count how many are "not too bad" (> -5%)
            positives[dd_key] = round(sum(1 for v in values if v > -5) / len(values) * 100, 1)
        else:
            averages[dd_key] = None
            positives[dd_key] = None

    return averages, positives


@app.route('/api/fetch_data', methods=['POST'])
def fetch_data():
    """Main endpoint to fetch and analyze stock data"""
    try:
        data = request.get_json()

        condition_tickers = data.get('condition_tickers', [])
        target_ticker = data.get('target_ticker', '^GSPC')
        start_date = data.get('start_date', '1990-01-01')
        end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        condition_type = data.get('condition_type', 'dual_ath')
        condition_params = data.get('condition_params', {})
        # Also check for top-level params (for backwards compatibility with discovery tool)
        for key in ['rsi_period', 'rsi_threshold', 'momentum_period', 'momentum_threshold',
                    'ma_short', 'ma_long', 'days_gap', 'breadth_threshold']:
            if key in data and key not in condition_params:
                condition_params[key] = data[key]
        api_key = data.get('api_key', '')

        if not api_key:
            return jsonify({'error': 'Polygon API key is required'}), 400

        # Some conditions don't require condition tickers
        no_ticker_conditions = ['sp500_pct_below_200ma', 'putcall_above', 'putcall_below', 'vix_above', 'vix_below']
        if not condition_tickers and condition_type not in no_ticker_conditions:
            return jsonify({'error': 'At least one condition ticker is required'}), 400

        # For no-ticker conditions, ignore any condition tickers passed
        if condition_type in no_ticker_conditions:
            condition_tickers = []

        # Fetch data for all tickers
        all_tickers = list(set(condition_tickers + [target_ticker]))
        ticker_data = {}

        for ticker in all_tickers:
            bars = fetch_aggregate_bars_cached(ticker, start_date, end_date, api_key)
            if not bars:
                return jsonify({'error': f'No data found for {ticker}'}), 400
            ticker_data[ticker] = bars_to_dataframe(bars)

        condition_dfs = [ticker_data[t] for t in condition_tickers] if condition_tickers else []
        target_df = ticker_data[target_ticker]

        # Find events based on condition type
        if condition_type == 'dual_ath':
            event_dates = find_dual_ath_events(condition_dfs, condition_params)
        elif condition_type == 'single_ath':
            event_dates = find_single_ath_events(condition_dfs, condition_params)
        elif condition_type == 'rsi_above':
            condition_params['cross_above'] = True
            event_dates = find_rsi_crossover_events(
                condition_dfs, condition_params, api_key,
                condition_tickers[0], start_date, end_date
            )
        elif condition_type == 'rsi_below':
            condition_params['cross_above'] = False
            event_dates = find_rsi_crossover_events(
                condition_dfs, condition_params, api_key,
                condition_tickers[0], start_date, end_date
            )
        elif condition_type == 'ma_crossover':
            condition_params['cross_above'] = True
            event_dates = find_ma_crossover_events(
                condition_dfs, condition_params, api_key,
                condition_tickers[0], start_date, end_date
            )
        elif condition_type == 'ma_crossunder':
            condition_params['cross_above'] = False
            event_dates = find_ma_crossover_events(
                condition_dfs, condition_params, api_key,
                condition_tickers[0], start_date, end_date
            )
        elif condition_type == 'momentum_above':
            event_dates = find_momentum_events(condition_dfs, condition_params)
        elif condition_type == 'momentum_below':
            condition_params['momentum_threshold'] = -abs(condition_params.get('momentum_threshold', 0.05))
            event_dates = find_momentum_events(condition_dfs, condition_params)
        elif condition_type == 'putcall_above':
            # High P/C ratio = fear/bearish sentiment = contrarian buy signal
            event_dates = find_putcall_events(start_date, end_date, condition_params, cross_above=True)
        elif condition_type == 'putcall_below':
            # Low P/C ratio = complacency/bullish sentiment = contrarian caution signal
            event_dates = find_putcall_events(start_date, end_date, condition_params, cross_above=False)
        elif condition_type == 'vix_above':
            # High VIX = fear/volatility spike = contrarian buy signal
            event_dates = find_vix_events(start_date, end_date, condition_params, cross_above=True)
        elif condition_type == 'vix_below':
            # Low VIX = complacency = potential caution signal
            event_dates = find_vix_events(start_date, end_date, condition_params, cross_above=False)
        elif condition_type == 'sp500_pct_below_200ma':
            # Fetch data for all S&P 500 constituents
            sp500_tickers = get_sp500_constituents()
            sp500_data = {}
            failed_tickers = []
            rate_limit_hits = 0

            # Fetch data for each constituent with rate limiting
            # Cache manager handles rate limiting, but we still handle errors
            for i, ticker in enumerate(sp500_tickers):
                try:
                    bars = fetch_aggregate_bars_cached(ticker, start_date, end_date, api_key)
                    if bars:
                        sp500_data[ticker] = bars_to_dataframe(bars)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'rate' in error_str or '429' in error_str:
                        rate_limit_hits += 1
                        # If we hit rate limit, wait longer and retry once
                        time.sleep(12)  # Wait 12 seconds for free tier
                        try:
                            bars = fetch_aggregate_bars_cached(ticker, start_date, end_date, api_key)
                            if bars:
                                sp500_data[ticker] = bars_to_dataframe(bars)
                        except Exception:
                            failed_tickers.append(ticker)
                    else:
                        failed_tickers.append(ticker)
                    continue

                # Progress logging every 50 stocks
                if (i + 1) % 50 == 0:
                    logger.info(f"Fetched {i + 1}/{len(sp500_tickers)} S&P 500 stocks...")

            print(f"Successfully fetched {len(sp500_data)} stocks, {len(failed_tickers)} failed")

            if len(sp500_data) < 50:
                error_msg = f'Could not fetch enough S&P 500 data. Only got {len(sp500_data)} stocks.'
                if rate_limit_hits > 0:
                    error_msg += f' Hit rate limit {rate_limit_hits} times. Consider using a paid Polygon.io plan for this feature.'
                return jsonify({'error': error_msg}), 400

            # Compute breadth
            breadth_df = compute_breadth_pct_below_200ma(sp500_data, target_df)

            if breadth_df.empty:
                return jsonify({'error': 'Could not compute breadth data'}), 400

            # Find events
            event_dates = find_breadth_below_threshold_events(breadth_df, condition_params)
        else:
            return jsonify({'error': f'Unknown condition type: {condition_type}'}), 400

        if not event_dates:
            return jsonify({
                'event_list': [],
                'averages': {},
                'positives': {},
                'historical_data': {
                    'dates': target_df.index.strftime('%Y-%m-%d').tolist(),
                    'prices': target_df['close'].tolist()
                },
                'event_markers': [],
                'average_forward_curve': [],
                'message': 'No events found matching the criteria'
            })

        # Compute forward returns
        intervals = Config.RETURN_INTERVALS
        event_results = compute_forward_returns(target_df, event_dates, intervals)

        # Compute statistics
        averages, positives = compute_statistics(event_results, intervals)

        # Compute average forward curve
        avg_curve = compute_average_forward_curve(target_df, event_dates)

        # Prepare historical data
        historical_data = {
            'dates': target_df.index.strftime('%Y-%m-%d').tolist(),
            'prices': target_df['close'].tolist()
        }

        # Event markers
        event_markers = [d.strftime('%Y-%m-%d') for d in event_dates]

        return jsonify({
            'event_list': event_results,
            'averages': averages,
            'positives': positives,
            'historical_data': historical_data,
            'event_markers': event_markers,
            'average_forward_curve': avg_curve,
            'total_events': len(event_dates)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/condition_types', methods=['GET'])
def get_condition_types():
    """Return available condition types and default parameters"""
    return jsonify({
        'types': Config.CONDITION_TYPES,
        'default_params': Config.DEFAULT_PARAMS
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


@app.route('/api/discovered_triggers', methods=['GET'])
def get_discovered_triggers():
    """Get triggers discovered by CriteriaTriggerDiscovery agent"""
    import json
    from pathlib import Path

    triggers_file = Path(__file__).parent / "discovered_triggers" / "triggers.json"

    if not triggers_file.exists():
        return jsonify({
            'status': 'no_data',
            'message': 'No discovered triggers yet. Run CriteriaTriggerDiscovery to find triggers.',
            'triggers': []
        })

    try:
        with open(triggers_file) as f:
            data = json.load(f)
        return jsonify({
            'status': 'ok',
            **data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'triggers': []
        }), 500


@app.route('/api/triggers/refresh', methods=['POST'])
def refresh_trigger_activity():
    """Refresh recent trigger counts using current cached data."""
    import json
    from pathlib import Path

    data = request.get_json() or {}
    api_key = data.get('api_key', Config.POLYGON_API_KEY)

    if not api_key:
        return jsonify({'error': 'API key required'}), 400

    triggers_file = Path(__file__).parent / "discovered_triggers" / "triggers.json"

    if not triggers_file.exists():
        return jsonify({'error': 'No triggers file found'}), 404

    try:
        with open(triggers_file) as f:
            triggers_data = json.load(f)

        triggers = triggers_data.get('triggers', [])
        updated_triggers = []

        for trigger in triggers:
            criteria = trigger.get('criteria', {})
            condition_type = criteria.get('condition_type')
            condition_tickers = criteria.get('condition_tickers', [])
            target_ticker = criteria.get('target_ticker', 'SPY')

            # Get cached data range for the condition ticker
            ticker = condition_tickers[0] if condition_tickers else target_ticker
            cache = get_cache_manager(api_key)
            cache_status = cache.get_cache_status(ticker)

            if not cache_status or not cache_status.get('first_date'):
                # No cached data, keep original values
                updated_triggers.append(trigger)
                continue

            # Get data from cache
            start_date = cache_status['first_date']
            end_date = cache_status['last_date']

            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
            elif hasattr(start_date, 'date'):
                start_date = start_date.date()

            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            elif hasattr(end_date, 'date'):
                end_date = end_date.date()

            try:
                df = cache._get_from_cache(ticker, start_date, end_date)
                if df.empty:
                    updated_triggers.append(trigger)
                    continue

                # Build condition params
                condition_params = {k: v for k, v in criteria.items()
                                   if k not in ['condition_type', 'condition_tickers', 'target_ticker']}

                # Find events using the same logic as main analysis
                event_dates = []
                if condition_type == 'rsi_above':
                    condition_params['cross_above'] = True
                    df_copy = df.copy()
                    df_copy['rsi'] = compute_rsi(df_copy, condition_params.get('rsi_period', 14))
                    threshold = condition_params.get('rsi_threshold', 70)
                    for i in range(1, len(df_copy)):
                        current_rsi = df_copy.iloc[i]['rsi']
                        prev_rsi = df_copy.iloc[i-1]['rsi']
                        if pd.notna(current_rsi) and pd.notna(prev_rsi):
                            if prev_rsi < threshold and current_rsi >= threshold:
                                event_date = df_copy.index[i]
                                if not event_dates or (event_date - event_dates[-1]).days > 5:
                                    event_dates.append(event_date)

                elif condition_type == 'rsi_below':
                    df_copy = df.copy()
                    df_copy['rsi'] = compute_rsi(df_copy, condition_params.get('rsi_period', 14))
                    threshold = condition_params.get('rsi_threshold', 30)
                    for i in range(1, len(df_copy)):
                        current_rsi = df_copy.iloc[i]['rsi']
                        prev_rsi = df_copy.iloc[i-1]['rsi']
                        if pd.notna(current_rsi) and pd.notna(prev_rsi):
                            if prev_rsi > threshold and current_rsi <= threshold:
                                event_date = df_copy.index[i]
                                if not event_dates or (event_date - event_dates[-1]).days > 5:
                                    event_dates.append(event_date)

                elif condition_type == 'momentum_above':
                    df_copy = df.copy()
                    period = condition_params.get('momentum_period', 12)
                    threshold = condition_params.get('momentum_threshold', 0.05)
                    df_copy['momentum'] = compute_momentum(df_copy, period)
                    for i in range(1, len(df_copy)):
                        current_mom = df_copy.iloc[i]['momentum']
                        prev_mom = df_copy.iloc[i-1]['momentum']
                        if pd.notna(current_mom) and pd.notna(prev_mom):
                            if prev_mom < threshold and current_mom >= threshold:
                                event_date = df_copy.index[i]
                                if not event_dates or (event_date - event_dates[-1]).days > 5:
                                    event_dates.append(event_date)

                elif condition_type == 'momentum_below':
                    df_copy = df.copy()
                    period = condition_params.get('momentum_period', 12)
                    threshold = -abs(condition_params.get('momentum_threshold', 0.05))
                    df_copy['momentum'] = compute_momentum(df_copy, period)
                    for i in range(1, len(df_copy)):
                        current_mom = df_copy.iloc[i]['momentum']
                        prev_mom = df_copy.iloc[i-1]['momentum']
                        if pd.notna(current_mom) and pd.notna(prev_mom):
                            if prev_mom > threshold and current_mom <= threshold:
                                event_date = df_copy.index[i]
                                if not event_dates or (event_date - event_dates[-1]).days > 5:
                                    event_dates.append(event_date)

                elif condition_type in ('putcall_above', 'putcall_below'):
                    cross_above = condition_type == 'putcall_above'
                    event_dates = find_putcall_events(
                        start_date.isoformat() if hasattr(start_date, 'isoformat') else str(start_date),
                        end_date.isoformat() if hasattr(end_date, 'isoformat') else str(end_date),
                        condition_params,
                        cross_above=cross_above
                    )

                # Calculate recent triggers (last 30 days)
                today = datetime.now().date()
                thirty_days_ago = today - timedelta(days=30)
                recent_events = [d for d in event_dates if d.date() >= thirty_days_ago]

                # Update trigger with fresh data
                updated_trigger = trigger.copy()
                updated_trigger['recent_trigger_count'] = len(recent_events)
                updated_trigger['latest_trigger_date'] = (
                    event_dates[-1].strftime('%Y-%m-%d') if event_dates else None
                )
                updated_triggers.append(updated_trigger)

            except Exception as e:
                logger.warning(f"Failed to refresh trigger {criteria}: {e}")
                updated_triggers.append(trigger)

        # Update the triggers file
        triggers_data['triggers'] = updated_triggers
        triggers_data['activity_refreshed_at'] = datetime.now().isoformat()

        with open(triggers_file, 'w') as f:
            json.dump(triggers_data, f, indent=2)

        return jsonify({
            'status': 'ok',
            'message': f'Refreshed {len(updated_triggers)} triggers',
            'triggers': updated_triggers,
            'refreshed_at': triggers_data['activity_refreshed_at']
        })

    except Exception as e:
        logger.error(f"Failed to refresh triggers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/data_range', methods=['GET'])
def get_data_range():
    """Get the date range of cached data for relevant tickers."""
    api_key = request.args.get('api_key', Config.POLYGON_API_KEY)

    if not api_key:
        return jsonify({'error': 'API key required'}), 400

    cache = get_cache_manager(api_key)

    # Get status for common tickers
    tickers_to_check = ['SPY', 'QQQ', 'IWM']
    ticker_ranges = {}

    for ticker in tickers_to_check:
        status = cache.get_cache_status(ticker)
        if status and status.get('first_date'):
            first_date = status['first_date']
            last_date = status['last_date']

            # Handle different date formats
            if hasattr(first_date, 'strftime'):
                first_date = first_date.strftime('%Y-%m-%d')
            elif isinstance(first_date, str) and 'GMT' in first_date:
                first_date = datetime.strptime(first_date, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d')

            if hasattr(last_date, 'strftime'):
                last_date = last_date.strftime('%Y-%m-%d')
            elif isinstance(last_date, str) and 'GMT' in last_date:
                last_date = datetime.strptime(last_date, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d')

            ticker_ranges[ticker] = {
                'first_date': first_date,
                'last_date': last_date,
                'total_bars': status.get('total_bars', 0)
            }

    # Calculate overall range
    if ticker_ranges:
        all_first = [r['first_date'] for r in ticker_ranges.values()]
        all_last = [r['last_date'] for r in ticker_ranges.values()]
        overall = {
            'first_date': min(all_first),
            'last_date': max(all_last)
        }
    else:
        overall = None

    return jsonify({
        'status': 'ok',
        'tickers': ticker_ranges,
        'overall': overall,
        'cache_enabled': Config.CACHE_ENABLED
    })


@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """Get cache statistics and status."""
    from cache.db import get_db_stats

    ticker = request.args.get('ticker')

    if ticker:
        # Get status for specific ticker
        api_key = request.args.get('api_key', Config.POLYGON_API_KEY)
        if not api_key:
            return jsonify({'error': 'API key required for ticker status'}), 400

        cache = get_cache_manager(api_key)
        status = cache.get_cache_status(ticker.upper())

        if status is None:
            return jsonify({
                'ticker': ticker.upper(),
                'cached': False,
                'message': 'No cached data for this ticker'
            })

        return jsonify({
            'ticker': ticker.upper(),
            'cached': True,
            **status
        })

    # General stats
    stats = get_db_stats()
    return jsonify({
        'cache_enabled': Config.CACHE_ENABLED,
        **stats
    })


@app.route('/api/cache/invalidate', methods=['POST'])
def invalidate_cache():
    """Invalidate (clear) cache for a specific ticker."""
    data = request.get_json()
    api_key = data.get('api_key', Config.POLYGON_API_KEY)
    ticker = data.get('ticker')

    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    if not api_key:
        return jsonify({'error': 'API key required'}), 400

    cache = get_cache_manager(api_key)
    count = cache.invalidate_ticker(ticker.upper())

    return jsonify({
        'success': True,
        'ticker': ticker.upper(),
        'bars_removed': count
    })


@app.route('/api/cache/sp500/start', methods=['POST'])
def start_sp500_cache():
    """Start S&P 500 caching job in background."""
    from cache.sp500_cacher import start_sp500_cache_job

    data = request.get_json() or {}
    api_key = data.get('api_key', Config.POLYGON_API_KEY)

    if not api_key:
        return jsonify({'error': 'API key required'}), 400

    start_date = data.get('start_date', Config.HISTORICAL_START_DATE)
    end_date = data.get('end_date')  # None means today

    result = start_sp500_cache_job(api_key, start_date, end_date)

    if result['status'] == 'already_running':
        return jsonify(result), 409  # Conflict

    return jsonify(result)


@app.route('/api/cache/sp500/status', methods=['GET'])
def sp500_cache_status():
    """Get status of S&P 500 caching job and coverage."""
    from cache.sp500_cacher import get_job_status, SP500Cacher, get_sp500_constituents

    job_id = request.args.get('job_id', type=int)

    # Get job status
    job_status = get_job_status(job_id)

    # Get coverage status
    api_key = request.args.get('api_key', Config.POLYGON_API_KEY)
    if api_key:
        cache = get_cache_manager(api_key)
        cacher = SP500Cacher(cache)
        coverage = cacher.get_caching_status()
    else:
        coverage = {'message': 'API key required for coverage stats'}

    return jsonify({
        'job': job_status,
        'coverage': coverage
    })


@app.route('/api/putcall', methods=['GET'])
def get_putcall_ratio():
    """
    Get put/call ratio data.

    Query params:
        start_date: Start date (YYYY-MM-DD), default: 2003-10-17
        end_date: End date (YYYY-MM-DD), default: today
        reload: If 'true', force reload CBOE data
    """
    start_date = request.args.get('start_date', '2003-10-17')
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    reload = request.args.get('reload', 'false').lower() == 'true'

    try:
        manager = get_putcall_manager()

        # Load CBOE data if needed
        manager.load_cboe_historical(force_reload=reload)

        # Get data range
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)

        # Get ratio series
        df = manager.get_ratio_series(start_dt, end_dt)

        if df.empty:
            return jsonify({
                'status': 'no_data',
                'message': f'No put/call ratio data available for {start_date} to {end_date}',
                'data': [],
                'stats': manager.get_stats()
            })

        # Convert to list of dicts
        data = []
        for idx, row in df.iterrows():
            data.append({
                'date': idx.strftime('%Y-%m-%d'),
                'ratio': row['ratio'],
                'calls': int(row['calls']) if pd.notna(row['calls']) else None,
                'puts': int(row['puts']) if pd.notna(row['puts']) else None,
                'source': row['source']
            })

        return jsonify({
            'status': 'ok',
            'count': len(data),
            'start_date': start_date,
            'end_date': end_date,
            'data': data,
            'stats': manager.get_stats()
        })

    except Exception as e:
        logger.error(f"Error fetching put/call ratio: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/putcall/stats', methods=['GET'])
def get_putcall_stats():
    """Get statistics about put/call ratio data."""
    try:
        manager = get_putcall_manager()
        manager.load_cboe_historical(force_reload=False)
        return jsonify(manager.get_stats())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize database on startup
    from cache.db import init_db
    init_db()
    app.run(debug=Config.DEBUG, port=5000)
