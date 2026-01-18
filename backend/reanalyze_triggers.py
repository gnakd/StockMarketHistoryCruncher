#!/usr/bin/env python3
"""Re-analyze discovered triggers using full 10-year historical data."""

import json
import sys
from datetime import date, datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from config import Config
from cache.db import init_db
from cache.manager import CacheManager
from app import (
    fetch_aggregate_bars,
    bars_to_dataframe,
    compute_rsi,
    compute_momentum,
    compute_sma,
    compute_forward_returns,
    compute_statistics,
    compute_average_forward_curve,
)


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
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)
        else:
            if prev_short >= prev_long and curr_short < curr_long:
                event_date = df.index[i]
                if not events or (event_date - events[-1]).days > 5:
                    events.append(event_date)

    return events


def analyze_trigger(criteria: dict, cache_manager: CacheManager, start_date: date, end_date: date) -> dict:
    """Analyze a single trigger with full historical data."""
    condition_type = criteria['condition_type']
    condition_tickers = criteria.get('condition_tickers', [])
    target_ticker = criteria.get('target_ticker', 'SPY')

    # Fetch data for condition ticker
    ticker = condition_tickers[0] if condition_tickers else target_ticker
    df = cache_manager.get_bars(ticker, start_date, end_date)

    if df.empty:
        return None

    # Also fetch target ticker data if different
    if target_ticker != ticker:
        target_df = cache_manager.get_bars(target_ticker, start_date, end_date)
    else:
        target_df = df

    # Find events based on condition type
    events = []
    if condition_type == 'rsi_above':
        period = criteria.get('rsi_period', 14)
        threshold = criteria.get('rsi_threshold', 70)
        events = find_rsi_events(df, period, threshold, cross_above=True)
    elif condition_type == 'rsi_below':
        period = criteria.get('rsi_period', 14)
        threshold = criteria.get('rsi_threshold', 30)
        events = find_rsi_events(df, period, threshold, cross_above=False)
    elif condition_type == 'momentum_above':
        period = criteria.get('momentum_period', 12)
        threshold = criteria.get('momentum_threshold', 0.05)
        events = find_momentum_events(df, period, threshold)
    elif condition_type == 'momentum_below':
        period = criteria.get('momentum_period', 12)
        threshold = -abs(criteria.get('momentum_threshold', 0.05))
        events = find_momentum_events(df, period, threshold)
    elif condition_type == 'ma_crossover':
        short = criteria.get('ma_short', 50)
        long = criteria.get('ma_long', 200)
        events = find_ma_crossover_events(df, short, long, cross_above=True)
    elif condition_type == 'ma_crossunder':
        short = criteria.get('ma_short', 50)
        long = criteria.get('ma_long', 200)
        events = find_ma_crossover_events(df, short, long, cross_above=False)

    if not events:
        return {
            'event_count': 0,
            'avg_return_1y': None,
            'win_rate_1y': None,
            'sharpe_like': None,
        }

    # Calculate forward returns
    intervals = Config.RETURN_INTERVALS
    event_results = compute_forward_returns(target_df, events, intervals)
    averages, positives = compute_statistics(event_results, intervals)

    # Calculate 1-year statistics
    returns_1y = [r['1_year'] for r in event_results if r.get('1_year') is not None]

    if returns_1y:
        avg_return = np.mean(returns_1y) / 100  # Convert from percentage
        win_rate = sum(1 for r in returns_1y if r > 0) / len(returns_1y)
        std_return = np.std(returns_1y) / 100 if len(returns_1y) > 1 else None
        sharpe = (avg_return / std_return) if std_return and std_return > 0 else None
    else:
        avg_return = None
        win_rate = None
        sharpe = None

    # Calculate normalized score (0-100 scale)
    # Each component normalized to 0-1, then weighted to sum to 100
    if avg_return is not None and win_rate is not None:
        return_score = min(avg_return / 0.40, 1.0)       # Cap at 40% annual return
        winrate_score = win_rate                          # Already 0-1
        sharpe_score = min(sharpe / 2.5, 1.0) if sharpe else 0  # Cap at 2.5 Sharpe
        significance_score = min(len(events) / 30, 1.0)  # 30+ events = full credit

        # Weighted score (weights sum to 100)
        score = (return_score * 30 +       # 30% weight: returns
                 winrate_score * 30 +      # 30% weight: consistency
                 sharpe_score * 25 +       # 25% weight: risk-adjusted quality
                 significance_score * 15)  # 15% weight: statistical significance
    else:
        score = 0

    # Recent trigger info
    from datetime import timedelta
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    recent_events = [e for e in events if e.date() >= thirty_days_ago]

    return {
        'event_count': len(events),
        'avg_return_1y': round(avg_return, 4) if avg_return else None,
        'win_rate_1y': round(win_rate, 4) if win_rate else None,
        'sharpe_like': round(sharpe, 2) if sharpe else None,
        'score': round(score, 2),
        'recent_trigger_count': len(recent_events),
        'latest_trigger_date': events[-1].strftime('%Y-%m-%d') if events else None,
        'averages': averages,
        'positives': positives,
    }


def main():
    print("=" * 60)
    print("Re-analyzing triggers with 10-year historical data")
    print("=" * 60)

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
    print(f"\nDate range: {start_date} to {end_date}")

    # Load existing triggers
    triggers_file = Path(__file__).parent / "discovered_triggers" / "triggers.json"
    if not triggers_file.exists():
        print("Error: No triggers.json found")
        sys.exit(1)

    with open(triggers_file) as f:
        data = json.load(f)

    triggers = data.get('triggers', [])
    print(f"Found {len(triggers)} triggers to analyze\n")

    # Re-analyze each trigger
    updated_triggers = []
    for i, trigger in enumerate(triggers):
        criteria = trigger['criteria']
        print(f"[{i+1}/{len(triggers)}] Analyzing {criteria['condition_type']} "
              f"(period={criteria.get('rsi_period') or criteria.get('momentum_period')}, "
              f"threshold={criteria.get('rsi_threshold') or criteria.get('momentum_threshold')})...")

        result = analyze_trigger(criteria, cache_manager, start_date, end_date)

        if result:
            updated_trigger = {
                'criteria': criteria,
                'score': result['score'],
                'event_count': result['event_count'],
                'avg_return_1y': result['avg_return_1y'],
                'win_rate_1y': result['win_rate_1y'],
                'sharpe_like': result['sharpe_like'],
                'recent_trigger_count': result['recent_trigger_count'],
                'latest_trigger_date': result['latest_trigger_date'],
            }
            updated_triggers.append(updated_trigger)

            print(f"    Events: {result['event_count']} (was {trigger['event_count']})")
            print(f"    Avg 1Y Return: {result['avg_return_1y']:.2%}" if result['avg_return_1y'] else "    Avg 1Y Return: N/A")
            print(f"    Win Rate: {result['win_rate_1y']:.1%}" if result['win_rate_1y'] else "    Win Rate: N/A")
        else:
            print("    Failed to analyze")

    # Sort by score
    updated_triggers.sort(key=lambda x: x['score'], reverse=True)

    # Update triggers.json
    data['triggers'] = updated_triggers
    data['date_range'] = {
        'start': start_date.isoformat(),
        'end': end_date.isoformat()
    }
    data['updated_at'] = datetime.now().isoformat()
    data['activity_refreshed_at'] = datetime.now().isoformat()

    with open(triggers_file, 'w') as f:
        json.dump(data, f, indent=2)

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print(f"Updated {len(updated_triggers)} triggers in triggers.json")
    print(f"Date range: {start_date} to {end_date}")
    print("=" * 60)


if __name__ == "__main__":
    main()
