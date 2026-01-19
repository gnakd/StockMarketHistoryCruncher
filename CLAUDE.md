# Stock Market History Cruncher

## Project Overview
Analyzes historical market performance after trigger conditions. Integrates with CriteriaTriggerDiscovery agent to display high-signal triggers.

## Architecture
- **Backend**: Flask API (`backend/app.py`) - fetches data from Polygon.io, calculates forward returns
- **Frontend**: React app (`frontend/`) - displays charts, tables, and discovered triggers
- **Integration**: `backend/discovered_triggers/triggers.json` - shared file written by CriteriaTriggerDiscovery

## Recent Changes (2026-01-18)

### Historical S&P 500 Constituent Tracking (NEW)
- Fixed survivorship bias in S&P 500 breadth calculations
- Tracks which stocks were in S&P 500 on any given historical date
- Data source: https://github.com/fja05680/sp500 (membership start/end dates)
- `get_sp500_constituents_for_date(date)` - returns list of tickers for a specific date
- `get_sp500_constituents_range(start, end)` - returns all tickers with membership periods
- `compute_breadth_pct_below_200ma()` now uses point-in-time membership
- New file: `backend/cache/sp500_history.py`
- Auto-downloads and caches data with 7-day refresh

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

### 1. Bullish vs Bearish Trigger Distinction - DONE
- Added `signal` field to triggers (bullish/bearish) in discover_triggers.py
- Signal mapping: bullish (rsi_above/below, momentum_above/below, ma_crossover, ath, vix_above, putcall_above)
- Signal mapping: bearish (ma_crossunder, vix_below, putcall_below)
- UI shows color-coded badges: green "▲ Bull" / red "▼ Bear"
- Frontend has fallback logic for triggers without signal field

### 2. Scoring Documentation - DONE
- Created `/docs/scoring.html` with detailed scoring formula documentation
- Added link from `/docs/condition-types.html` to scoring docs
- Documents all four components: Return (30%), Win Rate (30%), Sharpe (25%), Significance (15%)

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

### 6. Dynamic Start Date Based on Available Data - DONE
- InputForm now fetches `/api/data_range` on mount to get earliest cached date
- Start date defaults to `overall.first_date` from the API response
- Falls back to 2016-01-18 if no cached data or API error

### 7. Enhanced Forward Returns Chart - DONE
- Backend `compute_average_forward_curve` now returns `{avg, max, min, std}` for each day
- Frontend chart shows:
  - Best Case (dashed green) - maximum return at each day
  - Worst Case (dashed red) - minimum return at each day
  - Shaded area between min/max for visual range
  - Toggle buttons to show/hide bands and switch between Min/Max vs ±1 Std Dev views
- Backward compatible with old array format

### 8. Created Triggers Table
- Add a "Created Triggers" table similar to the "Discovered Triggers" table
- Display triggers from the Condition Type dropdown (user-configured triggers)
- Allow users to save/name their custom trigger configurations
- Show same metrics as Discovered Triggers: score, events, avg return, win rate, etc.
- Persist saved triggers (localStorage or backend)

### 9. Rolling Period Return Trigger (Wayne Whaley Style)
- Add condition type for measuring forward returns based on historic rolling period performance
- Inspired by Wayne Whaley's seasonal analysis (e.g., Turn-of-Year Barometer)
- Parameters:
  - Period start (month/day, e.g., November 19)
  - Period end (month/day, e.g., January 19)
  - Return threshold (e.g., >3%)
- Example: "Turn-of-Year Barometer" - if Nov 19 to Jan 19 return exceeds 3%, S&P 500 was up 12 months later almost every time
- Could support multiple preset periods (Turn-of-Year, January Barometer, Santa Claus Rally, etc.)
- Calculate historical instances and forward returns for each year

### 10. New Highs Minus New Lows Trigger
- Add condition type based on NYSE/S&P 500 new 52-week highs minus new 52-week lows
- Classic market breadth indicator showing underlying market health
- Parameters:
  - Threshold (e.g., drops below -500, or rises above +500)
  - Smoothing period (optional moving average)
- Extreme negative readings = capitulation/fear = contrarian buy signal
- Extreme positive readings = broad participation = bullish confirmation
- Data sources: Could calculate from S&P 500 constituent data already cached, or fetch from external source

### 11. Future Ideas
- Real-time trigger alerts/notifications
- Trigger comparison view (overlay multiple triggers on same chart)
- Backtest date range selector in UI
- Sector rotation signals using S&P 500 stock data
