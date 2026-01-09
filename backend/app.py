from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import Config

app = Flask(__name__)
CORS(app)

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

    # Try to fetch RSI from API first
    rsi_data = fetch_rsi(ticker, start_date, end_date, period, api_key)

    if rsi_data:
        rsi_df = pd.DataFrame(rsi_data)
        rsi_df['date'] = pd.to_datetime(rsi_df['timestamp'], unit='ms')
        rsi_df = rsi_df.set_index('date')
        df['rsi'] = rsi_df['value']
    else:
        # Compute manually
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
    """Compute average forward returns curve aligned by trading days"""
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

    # Compute average, ignoring None values
    avg_curve = []
    for d in range(days + 1):
        values = [c[d] for c in curves if c[d] is not None]
        if values:
            avg_curve.append(round(sum(values) / len(values), 2))
        else:
            avg_curve.append(None)

    return avg_curve


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
        api_key = data.get('api_key', '')

        if not api_key:
            return jsonify({'error': 'Polygon API key is required'}), 400

        if not condition_tickers:
            return jsonify({'error': 'At least one condition ticker is required'}), 400

        # Fetch data for all tickers
        all_tickers = list(set(condition_tickers + [target_ticker]))
        ticker_data = {}

        for ticker in all_tickers:
            bars = fetch_aggregate_bars(ticker, start_date, end_date, api_key)
            if not bars:
                return jsonify({'error': f'No data found for {ticker}'}), 400
            ticker_data[ticker] = bars_to_dataframe(bars)

        condition_dfs = [ticker_data[t] for t in condition_tickers]
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


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=5000)
