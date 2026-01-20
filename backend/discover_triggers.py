#!/usr/bin/env python3
"""
Trigger Discovery Script

Systematically tests various condition parameters to discover high-quality triggers
using 10-year historical data.
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from config import Config
from cache.db import init_db
from cache.manager import CacheManager
from app import (
    fetch_aggregate_bars,
    compute_rsi,
    compute_momentum,
    compute_sma,
    compute_forward_returns,
    compute_statistics,
    find_vix_events,
    find_feargreed_events,
    find_breadth_threshold_events,
    compute_breadth_pct_above_200ma,
)


# Minimum thresholds for a valid trigger
MIN_EVENTS = 5
MIN_WIN_RATE = 0.70
MIN_AVG_RETURN = 0.08  # 8% annual
MIN_SCORE = 55

# Signal direction mapping
# Bullish = expect price to go UP (buy signal)
# Bearish = expect price to go DOWN (sell/caution signal)
SIGNAL_DIRECTION = {
    'rsi_above': 'bullish',       # Strong momentum, trend continuation
    'rsi_below': 'bullish',       # Oversold contrarian buy
    'momentum_above': 'bullish',  # Strong upward momentum
    'momentum_below': 'bullish',  # Oversold contrarian buy (historically works as buy signal)
    'ma_crossover': 'bullish',    # Golden cross
    'ma_crossunder': 'bearish',   # Death cross
    'single_ath': 'bullish',      # Breakout to new highs
    'dual_ath': 'bullish',        # Confirmed breakout
    'vix_above': 'bullish',       # High fear = contrarian buy
    'vix_below': 'bearish',       # Complacency = caution
    'putcall_above': 'bullish',   # High fear = contrarian buy
    'putcall_below': 'bearish',   # Complacency = caution
    'feargreed_above': 'bearish', # Extreme greed = caution
    'feargreed_below': 'bullish', # Extreme fear = contrarian buy
}


def get_signal_direction(condition_type: str) -> str:
    """Get the signal direction (bullish/bearish) for a condition type."""
    return SIGNAL_DIRECTION.get(condition_type, 'neutral')


def find_rsi_events(df: pd.DataFrame, period: int, threshold: float, cross_above: bool) -> list:
    """Find RSI crossover events."""
    df = df.copy()
    df['rsi'] = compute_rsi(df, period)

    events = []
    for i in range(1, len(df)):
        current_rsi = df.iloc[i]['rsi']
        prev_rsi = df.iloc[i-1]['rsi']

        if pd.isna(current_rsi) or pd.isna(prev_rsi):
            continue

        if cross_above:
            if prev_rsi < threshold and current_rsi >= threshold:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)
        else:
            if prev_rsi > threshold and current_rsi <= threshold:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)

    return events


def find_momentum_events(df: pd.DataFrame, period: int, threshold: float) -> list:
    """Find momentum crossover events."""
    df = df.copy()
    df['momentum'] = compute_momentum(df, period)

    events = []
    for i in range(1, len(df)):
        current_mom = df.iloc[i]['momentum']
        prev_mom = df.iloc[i-1]['momentum']

        if pd.isna(current_mom) or pd.isna(prev_mom):
            continue

        if threshold > 0:
            if prev_mom < threshold and current_mom >= threshold:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)
        else:
            if prev_mom > threshold and current_mom <= threshold:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)

    return events


def find_ma_crossover_events(df: pd.DataFrame, short_period: int, long_period: int, cross_above: bool) -> list:
    """Find MA crossover events."""
    df = df.copy()
    df['sma_short'] = compute_sma(df, short_period)
    df['sma_long'] = compute_sma(df, long_period)

    events = []
    for i in range(1, len(df)):
        curr_short = df.iloc[i]['sma_short']
        curr_long = df.iloc[i]['sma_long']
        prev_short = df.iloc[i-1]['sma_short']
        prev_long = df.iloc[i-1]['sma_long']

        if any(pd.isna([curr_short, curr_long, prev_short, prev_long])):
            continue

        if cross_above:
            if prev_short <= prev_long and curr_short > curr_long:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 20:
                    events.append(event_date)
        else:
            if prev_short >= prev_long and curr_short < curr_long:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 20:
                    events.append(event_date)

    return events


def calculate_score(avg_return: float, win_rate: float, sharpe: float, num_events: int) -> float:
    """Calculate normalized 0-100 score."""
    if avg_return is None or win_rate is None:
        return 0

    return_score = min(avg_return / 0.40, 1.0)
    winrate_score = win_rate
    sharpe_score = min(sharpe / 2.5, 1.0) if sharpe else 0
    significance_score = min(num_events / 30, 1.0)

    score = (return_score * 30 +
             winrate_score * 30 +
             sharpe_score * 25 +
             significance_score * 15)

    return round(score, 2)


def analyze_condition(df: pd.DataFrame, target_df: pd.DataFrame, events: list) -> dict:
    """Analyze forward returns for a set of events."""
    if len(events) < MIN_EVENTS:
        return None

    intervals = Config.RETURN_INTERVALS
    event_results = compute_forward_returns(target_df, events, intervals)

    returns_1y = [r['1_year'] for r in event_results if r.get('1_year') is not None]
    max_drawdowns = [r['max_drawdown'] for r in event_results if r.get('max_drawdown') is not None]

    if not returns_1y or len(returns_1y) < MIN_EVENTS:
        return None

    avg_return = np.mean(returns_1y) / 100
    win_rate = sum(1 for r in returns_1y if r > 0) / len(returns_1y)
    std_return = np.std(returns_1y) / 100 if len(returns_1y) > 1 else None
    sharpe = (avg_return / std_return) if std_return and std_return > 0 else None
    avg_max_dd = np.mean(max_drawdowns) / 100 if max_drawdowns else None

    if win_rate < MIN_WIN_RATE or avg_return < MIN_AVG_RETURN:
        return None

    score = calculate_score(avg_return, win_rate, sharpe, len(events))

    if score < MIN_SCORE:
        return None

    # Recent trigger info
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    recent_events = [e for e in events if e.date() >= thirty_days_ago]

    return {
        'event_count': len(events),
        'avg_return_1y': round(avg_return, 4),
        'win_rate_1y': round(win_rate, 4),
        'avg_max_dd': round(avg_max_dd, 4) if avg_max_dd else None,
        'sharpe_like': round(sharpe, 2) if sharpe else None,
        'score': score,
        'recent_trigger_count': len(recent_events),
        'latest_trigger_date': events[-1].strftime('%Y-%m-%d') if events else None,
    }


def discover_rsi_triggers(df: pd.DataFrame, target_df: pd.DataFrame, ticker: str) -> list:
    """Discover RSI-based triggers."""
    triggers = []

    # RSI Above parameters to test
    rsi_periods = [7, 9, 11, 13, 14, 15, 21]
    rsi_above_thresholds = [55, 60, 65, 70, 75, 80]
    rsi_below_thresholds = [20, 25, 30, 35, 40, 45]

    print("  Testing RSI Above conditions...")
    for period, threshold in product(rsi_periods, rsi_above_thresholds):
        events = find_rsi_events(df, period, threshold, cross_above=True)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'rsi_above',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'rsi_period': period,
                    'rsi_threshold': threshold,
                },
                **result
            })

    print("  Testing RSI Below conditions...")
    for period, threshold in product(rsi_periods, rsi_below_thresholds):
        events = find_rsi_events(df, period, threshold, cross_above=False)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'rsi_below',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'rsi_period': period,
                    'rsi_threshold': threshold,
                },
                **result
            })

    return triggers


def discover_momentum_triggers(df: pd.DataFrame, target_df: pd.DataFrame, ticker: str) -> list:
    """Discover momentum-based triggers."""
    triggers = []

    momentum_periods = [5, 10, 15, 20, 30]
    momentum_above_thresholds = [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15]
    momentum_below_thresholds = [-0.03, -0.05, -0.07, -0.09, -0.12, -0.15]

    print("  Testing Momentum Above conditions...")
    for period, threshold in product(momentum_periods, momentum_above_thresholds):
        events = find_momentum_events(df, period, threshold)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'momentum_above',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'momentum_period': period,
                    'momentum_threshold': threshold,
                },
                **result
            })

    print("  Testing Momentum Below conditions...")
    for period, threshold in product(momentum_periods, momentum_below_thresholds):
        events = find_momentum_events(df, period, threshold)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'momentum_below',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'momentum_period': period,
                    'momentum_threshold': threshold,
                },
                **result
            })

    return triggers


def discover_ma_triggers(df: pd.DataFrame, target_df: pd.DataFrame, ticker: str) -> list:
    """Discover moving average crossover triggers."""
    triggers = []

    ma_combinations = [
        (10, 50), (20, 50), (20, 100), (50, 100), (50, 200), (100, 200)
    ]

    print("  Testing MA Crossover conditions...")
    for short, long in ma_combinations:
        # Golden Cross
        events = find_ma_crossover_events(df, short, long, cross_above=True)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'ma_crossover',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'ma_short': short,
                    'ma_long': long,
                },
                **result
            })

        # Death Cross (for potential short signals or caution)
        events = find_ma_crossover_events(df, short, long, cross_above=False)
        result = analyze_condition(df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'ma_crossunder',
                    'condition_tickers': [ticker],
                    'target_ticker': ticker,
                    'ma_short': short,
                    'ma_long': long,
                },
                **result
            })

    return triggers


def discover_vix_triggers(target_df: pd.DataFrame, target_ticker: str, start_date: str, end_date: str) -> list:
    """Discover VIX-based triggers."""
    triggers = []

    # VIX thresholds to test
    vix_above_thresholds = [20, 25, 30, 35, 40, 45, 50]
    vix_below_thresholds = [12, 13, 14, 15, 16, 17, 18]

    print("  Testing VIX Above conditions...")
    for threshold in vix_above_thresholds:
        params = {'vix_threshold': threshold}
        events = find_vix_events(start_date, end_date, params, cross_above=True)
        result = analyze_condition(target_df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'vix_above',
                    'condition_tickers': [],
                    'target_ticker': target_ticker,
                    'vix_threshold': threshold,
                },
                **result
            })

    print("  Testing VIX Below conditions...")
    for threshold in vix_below_thresholds:
        params = {'vix_threshold': threshold}
        events = find_vix_events(start_date, end_date, params, cross_above=False)
        result = analyze_condition(target_df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'vix_below',
                    'condition_tickers': [],
                    'target_ticker': target_ticker,
                    'vix_threshold': threshold,
                },
                **result
            })

    return triggers


def discover_feargreed_triggers(target_df: pd.DataFrame, target_ticker: str, start_date: str, end_date: str) -> list:
    """Discover Fear & Greed Index-based triggers."""
    triggers = []

    # Fear & Greed thresholds to test
    # Above thresholds (extreme greed = caution)
    feargreed_above_thresholds = [70, 75, 80, 85, 90]
    # Below thresholds (extreme fear = buy signal)
    feargreed_below_thresholds = [10, 15, 20, 25, 30]

    print("  Testing Fear & Greed Above conditions...")
    for threshold in feargreed_above_thresholds:
        params = {'feargreed_threshold': threshold}
        events = find_feargreed_events(start_date, end_date, params, cross_above=True)
        result = analyze_condition(target_df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'feargreed_above',
                    'condition_tickers': [],
                    'target_ticker': target_ticker,
                    'feargreed_threshold': threshold,
                },
                **result
            })

    print("  Testing Fear & Greed Below conditions...")
    for threshold in feargreed_below_thresholds:
        params = {'feargreed_threshold': threshold}
        events = find_feargreed_events(start_date, end_date, params, cross_above=False)
        result = analyze_condition(target_df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'feargreed_below',
                    'condition_tickers': [],
                    'target_ticker': target_ticker,
                    'feargreed_threshold': threshold,
                },
                **result
            })

    return triggers


def discover_breadth_triggers(target_df: pd.DataFrame, ticker_data_dict: dict, membership_dict: dict, target_ticker: str) -> list:
    """Discover S&P 500 breadth triggers (% above/below 200 DMA)."""
    triggers = []

    # Calculate breadth series
    breadth_df = compute_breadth_pct_above_200ma(ticker_data_dict, target_df, membership_dict)
    if breadth_df is None or breadth_df.empty:
        print("  No breadth data available, skipping...")
        return triggers

    # Breadth thresholds to test (% above 200 DMA crossing below threshold = bearish breadth = buy signal)
    breadth_below_thresholds = [15, 20, 25, 30, 35]  # Low % above = most stocks below 200 DMA = oversold

    print("  Testing S&P 500 Breadth conditions...")
    for threshold in breadth_below_thresholds:
        params = {'breadth_threshold': threshold}
        events = find_breadth_threshold_events(breadth_df, params)
        result = analyze_condition(target_df, target_df, events)
        if result:
            triggers.append({
                'criteria': {
                    'condition_type': 'sp500_pct_above_200ma',
                    'condition_tickers': [],
                    'target_ticker': target_ticker,
                    'breadth_threshold': threshold,
                },
                **result
            })

    return triggers


def deduplicate_triggers(triggers: list) -> list:
    """Remove near-duplicate triggers, keeping the best scoring one."""
    if not triggers:
        return []

    # Sort by score descending
    sorted_triggers = sorted(triggers, key=lambda x: x['score'], reverse=True)

    unique = []
    for trigger in sorted_triggers:
        criteria = trigger['criteria']
        is_duplicate = False

        for existing in unique:
            existing_criteria = existing['criteria']

            # Check if same type and similar parameters
            if criteria['condition_type'] == existing_criteria['condition_type']:
                if criteria['condition_type'] in ['rsi_above', 'rsi_below']:
                    period_diff = abs(criteria.get('rsi_period', 0) - existing_criteria.get('rsi_period', 0))
                    threshold_diff = abs(criteria.get('rsi_threshold', 0) - existing_criteria.get('rsi_threshold', 0))
                    if period_diff <= 2 and threshold_diff <= 5:
                        is_duplicate = True
                        break
                elif criteria['condition_type'] in ['momentum_above', 'momentum_below']:
                    period_diff = abs(criteria.get('momentum_period', 0) - existing_criteria.get('momentum_period', 0))
                    threshold_diff = abs(criteria.get('momentum_threshold', 0) - existing_criteria.get('momentum_threshold', 0))
                    if period_diff <= 2 and threshold_diff <= 0.02:
                        is_duplicate = True
                        break

        if not is_duplicate:
            unique.append(trigger)

    return unique


def load_existing_triggers(min_score: float = 60.0) -> list:
    """Load existing triggers with score >= min_score."""
    triggers_file = Path(__file__).parent / "discovered_triggers" / "triggers.json"

    if not triggers_file.exists():
        return []

    try:
        with open(triggers_file) as f:
            data = json.load(f)

        existing = [t for t in data.get('triggers', []) if t.get('score', 0) >= min_score]
        print(f"  Loaded {len(existing)} existing triggers with score >= {min_score}")
        return existing
    except Exception as e:
        print(f"  Warning: Could not load existing triggers: {e}")
        return []


def triggers_match(t1: dict, t2: dict) -> bool:
    """Check if two triggers are effectively the same (same ticker + same params)."""
    c1 = t1.get('criteria', {})
    c2 = t2.get('criteria', {})

    if c1.get('condition_type') != c2.get('condition_type'):
        return False

    # Must be same ticker to be considered a match
    if c1.get('target_ticker') != c2.get('target_ticker'):
        return False

    # Must also have same condition_tickers
    if c1.get('condition_tickers') != c2.get('condition_tickers'):
        return False

    ctype = c1.get('condition_type')

    if 'rsi' in ctype:
        return (c1.get('rsi_period') == c2.get('rsi_period') and
                c1.get('rsi_threshold') == c2.get('rsi_threshold'))
    elif 'momentum' in ctype:
        return (c1.get('momentum_period') == c2.get('momentum_period') and
                c1.get('momentum_threshold') == c2.get('momentum_threshold'))
    elif 'ma' in ctype:
        return (c1.get('ma_short') == c2.get('ma_short') and
                c1.get('ma_long') == c2.get('ma_long'))
    elif 'vix' in ctype:
        return c1.get('vix_threshold') == c2.get('vix_threshold')
    elif 'feargreed' in ctype:
        return c1.get('feargreed_threshold') == c2.get('feargreed_threshold')
    elif 'breadth' in ctype or 'sp500_pct' in ctype:
        return c1.get('breadth_threshold') == c2.get('breadth_threshold')

    return False


def main():
    print("=" * 70)
    print("TRIGGER DISCOVERY - 10 Year Historical Data")
    print("=" * 70)

    # Initialize
    init_db()
    api_key = Config.POLYGON_API_KEY
    if not api_key:
        print("Error: POLYGON_API_KEY not set")
        sys.exit(1)

    cache_manager = CacheManager(api_key, fetch_func=fetch_aggregate_bars, rate_limit_delay=0)

    # Date range
    start_date = date.fromisoformat(Config.HISTORICAL_START_DATE)
    end_date = date.today()

    print(f"\nConfiguration:")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Min events: {MIN_EVENTS}")
    print(f"  Min win rate: {MIN_WIN_RATE:.0%}")
    print(f"  Min avg return: {MIN_AVG_RETURN:.0%}")
    print(f"  Min score: {MIN_SCORE}")

    # Load existing triggers to preserve
    existing_triggers = load_existing_triggers(min_score=60.0)

    # Tickers to analyze
    tickers = ['SPY', 'QQQ', 'IWM']

    all_triggers = []

    for ticker in tickers:
        print(f"\n{'='*50}")
        print(f"Analyzing {ticker}...")
        print("=" * 50)

        df = cache_manager.get_bars(ticker, start_date, end_date)
        if df.empty:
            print(f"  No data for {ticker}, skipping...")
            continue

        print(f"  Loaded {len(df)} bars")

        # Discover RSI triggers
        rsi_triggers = discover_rsi_triggers(df, df, ticker)
        print(f"  Found {len(rsi_triggers)} valid RSI triggers")
        all_triggers.extend(rsi_triggers)

        # Discover momentum triggers
        momentum_triggers = discover_momentum_triggers(df, df, ticker)
        print(f"  Found {len(momentum_triggers)} valid momentum triggers")
        all_triggers.extend(momentum_triggers)

        # Discover MA triggers
        ma_triggers = discover_ma_triggers(df, df, ticker)
        print(f"  Found {len(ma_triggers)} valid MA triggers")
        all_triggers.extend(ma_triggers)

    # Discover VIX triggers (only need to run once with SPY as target)
    print(f"\n{'='*50}")
    print("Analyzing VIX triggers...")
    print("=" * 50)

    spy_df = cache_manager.get_bars('SPY', start_date, end_date)
    if not spy_df.empty:
        vix_triggers = discover_vix_triggers(spy_df, 'SPY', start_date.isoformat(), end_date.isoformat())
        print(f"  Found {len(vix_triggers)} valid VIX triggers")
        all_triggers.extend(vix_triggers)

    # Discover Fear & Greed triggers (only need to run once with SPY as target)
    print(f"\n{'='*50}")
    print("Analyzing Fear & Greed triggers...")
    print("=" * 50)

    if not spy_df.empty:
        feargreed_triggers = discover_feargreed_triggers(spy_df, 'SPY', start_date.isoformat(), end_date.isoformat())
        print(f"  Found {len(feargreed_triggers)} valid Fear & Greed triggers")
        all_triggers.extend(feargreed_triggers)

    # Deduplicate and sort
    print(f"\n{'='*50}")
    print("Processing results...")
    print("=" * 50)

    print(f"  Total new triggers before dedup: {len(all_triggers)}")
    unique_new_triggers = deduplicate_triggers(all_triggers)
    print(f"  Unique new triggers after dedup: {len(unique_new_triggers)}")

    # Merge with existing triggers (keep existing if same, add new otherwise)
    merged_triggers = list(existing_triggers)  # Start with existing

    for new_trigger in unique_new_triggers:
        # Check if this trigger already exists
        is_duplicate = False
        for i, existing in enumerate(merged_triggers):
            if triggers_match(new_trigger, existing):
                # Update existing with new data if new score is higher
                if new_trigger['score'] > existing.get('score', 0):
                    merged_triggers[i] = new_trigger
                is_duplicate = True
                break

        if not is_duplicate:
            merged_triggers.append(new_trigger)

    print(f"  Merged triggers (existing + new): {len(merged_triggers)}")

    # Sort by score
    merged_triggers.sort(key=lambda x: x['score'], reverse=True)

    # Take top triggers
    top_triggers = merged_triggers[:50]

    # Display results
    print(f"\n{'='*85}")
    print("TOP DISCOVERED TRIGGERS")
    print("=" * 85)
    print(f"{'Rank':<5} {'Ticker':<7} {'Type':<18} {'Params':<22} {'Events':<8} {'Return':<9} {'WinRate':<9} {'Score':<7}")
    print("-" * 85)

    for i, trigger in enumerate(top_triggers, 1):
        criteria = trigger['criteria']
        ctype = criteria['condition_type']
        ticker = criteria.get('target_ticker', 'SPY')

        if 'rsi' in ctype:
            params = f"p={criteria['rsi_period']}, t={criteria['rsi_threshold']}"
        elif 'momentum' in ctype:
            params = f"p={criteria['momentum_period']}, t={criteria['momentum_threshold']:.0%}"
        elif 'ma' in ctype:
            params = f"s={criteria['ma_short']}, l={criteria['ma_long']}"
        elif 'vix' in ctype:
            params = f"threshold={criteria['vix_threshold']}"
        elif 'feargreed' in ctype:
            params = f"threshold={criteria['feargreed_threshold']}"
        elif 'breadth' in ctype or 'sp500_pct' in ctype:
            params = f"pct<={criteria['breadth_threshold']}%"
        else:
            params = ""

        print(f"{i:<5} {ticker:<7} {ctype:<18} {params:<22} {trigger['event_count']:<8} "
              f"{trigger['avg_return_1y']:.1%}    {trigger['win_rate_1y']:.1%}    {trigger['score']:<7}")

    # Add signal direction to each trigger
    for trigger in top_triggers:
        condition_type = trigger.get('criteria', {}).get('condition_type', '')
        trigger['signal'] = get_signal_direction(condition_type)

    # Save to triggers.json
    triggers_file = Path(__file__).parent / "discovered_triggers" / "triggers.json"
    triggers_file.parent.mkdir(exist_ok=True)

    output = {
        'version': '1.1',
        'updated_at': datetime.now().isoformat(),
        'total_tested': len(all_triggers),
        'total_valid': len(merged_triggers),
        'date_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'triggers': top_triggers,
        'activity_refreshed_at': datetime.now().isoformat()
    }

    with open(triggers_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Saved {len(top_triggers)} triggers to {triggers_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
