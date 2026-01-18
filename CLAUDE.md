# Stock Market History Cruncher

## Project Overview
Analyzes historical market performance after trigger conditions. Integrates with CriteriaTriggerDiscovery agent to display high-signal triggers.

## Architecture
- **Backend**: Flask API (`backend/app.py`) - fetches data from Polygon.io, calculates forward returns
- **Frontend**: React app (`frontend/`) - displays charts, tables, and discovered triggers
- **Integration**: `backend/discovered_triggers/triggers.json` - shared file written by CriteriaTriggerDiscovery

## Recent Changes (2026-01-18)

### VIX Trigger (NEW)
- Added `vix_above` and `vix_below` condition types
- Historical data from FRED (1990-present, ~9100 records)
- Contrarian fear gauge indicator:
  - High VIX (>30) = extreme fear = contrarian buy signal
  - Low VIX (<15) = complacency = potential caution signal
- New files:
  - `backend/cache/vix.py` - VIX data manager, FRED loader
  - `backend/tests/test_vix.py` - validation tests
- Free data, no API key required

### Put/Call Ratio Trigger
- Added `putcall_above` and `putcall_below` condition types
- Historical data from CBOE (2003-2019, ~4000 records)
- Contrarian sentiment indicator:
  - High P/C (>1.0) = fear/bearish sentiment = potential buy signal
  - Low P/C (<0.7) = complacency = potential caution signal
- New files:
  - `backend/cache/putcall_ratio.py` - data manager, CBOE loader, Polygon fetcher
  - `backend/tests/test_putcall_ratio.py` - validation tests
  - `backend/tests/test_putcall_trigger.py` - trigger integration tests
- API endpoints: `/api/putcall`, `/api/putcall/stats`
- **Note**: Polygon options API requires paid plan for real-time data

## Recent Changes (2026-01-17)

### Dynamic S&P 500 Constituents
- S&P 500 list now fetched from Wikipedia instead of hardcoded
- Cached in SQLite with 7-day auto-refresh
- Tracks additions/removals automatically
- `sync_sp500_flags()` updates `is_sp500` in ticker_metadata

### DiscoveredTriggers UI Updates
- Added columns: Type (Long/Short), Avg WR, Max DD
- Shows scoring mode badge and filter thresholds
- Backward compatible with old trigger format

## Unstaged Changes
There are other modified files not yet committed:
- `backend/app.py` - review before committing
- `frontend/src/components/ForwardReturnsChart.js`
- `frontend/src/components/HistoricalChart.js`
- `frontend/src/components/InputForm.js`
- `frontend/src/components/RecentTriggers.js`
- `frontend/src/utils/chartConfig.js` (new file)

## Next Session TODO

### 1. Bullish vs Bearish Trigger Distinction
- Add a field to categorize triggers as "Bullish" or "Bearish"
- Bullish: momentum_above, rsi_above, ma_crossover, rsi_below (contrarian buy)
- Bearish: momentum_below (if used as sell signal), ma_crossunder
- Display in UI with color-coded badges (green/red)

### 2. Scoring Documentation
- Add link to documentation explaining how trigger scores are calculated
- Document the 0-100 scoring formula:
  - Return score: 30% weight (capped at 40% annual return)
  - Win rate score: 30% weight
  - Sharpe ratio: 25% weight (capped at 2.5)
  - Statistical significance: 15% weight (30+ events = full credit)
- Add to `/docs/condition-types.html` or create separate `/docs/scoring.html`

### 3. YCharts Put/Call Ratio Data
- Explore scraping put/call ratio data from YCharts
- Current CBOE data only goes to 2019
- YCharts may have more recent data: https://ycharts.com/indicators/cboe_equity_put_call_ratio
- Consider web scraping or API options
- Alternative: Check if FRED has updated P/C ratio data

### 4. Conservative Scoring (CriteriaTriggerDiscovery)
The conservative scoring plan was implemented but reverted. If re-implementing:
- Multi-period win rate filters (70%+ across all periods)
- Drawdown filters (max -10%)
- Trigger type categorization (long-term vs short-term)
- The frontend already supports the new fields

### 5. Review Unstaged Changes
Several frontend files have modifications - review and commit or discard.

### 6. Dynamic Start Date Based on Available Data
- Update the default Start Date to the earliest available data for SPY, QQQ, IWM
- Query cache to find the furthest back date with data for each ticker
- Set form default to the oldest common date across selected tickers
- Currently hardcoded to 2016-01-18 (10-year Polygon subscription)

### 7. Enhanced Forward Returns Chart
- Add series showing **maximum drawdowns** at each time interval
- Add series showing **maximum positive gains** at each time interval
- Consider adding **standard deviation bands** (e.g., +/- 1 std dev)
- Would help visualize the range of outcomes, not just the average
- Could use shaded area or dashed lines for the bands

### 8. Future Ideas
- Real-time trigger alerts/notifications
- Trigger comparison view (overlay multiple triggers on same chart)
- Backtest date range selector in UI
- Sector rotation signals using S&P 500 stock data
