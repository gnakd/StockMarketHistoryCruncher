# Stock Market History Cruncher

A web application that analyzes historical stock market performance after specific trigger conditions are met. Visualize how markets have performed historically following various technical signals.

## Features

- **Multiple Condition Types:**
  - Dual All-Time High (ATH) - Both tickers hit ATH after a gap period
  - Single ATH - One ticker hits ATH after a gap period
  - RSI Crosses - RSI crossing above/below thresholds
  - MA Crossovers - Golden Cross / Death Cross signals
  - Momentum thresholds - Price momentum above/below levels

- **Visualizations:**
  - Historical price chart with event markers
  - Forward returns table with color-coded values
  - Average forward returns curve

- **Data Analysis:**
  - Forward returns at 1w, 2w, 1m, 2m, 3m, 6m, 9m, 1y intervals
  - Maximum drawdown calculation
  - Average returns and positive percentage statistics
  - CSV export functionality

## Prerequisites

- Python 3.9+
- Node.js 18+
- Polygon.io API key (get free at https://polygon.io)

## Installation

### Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API key
```

### Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend Server

```bash
cd backend
python app.py
```

The API server will start at http://localhost:5000

### Start Frontend Development Server

```bash
cd frontend
npm start
```

The React app will start at http://localhost:3000

## Usage

1. Enter your Polygon.io API key
2. Add condition tickers (e.g., QQQ, AAPL)
3. Set the target ticker to analyze (e.g., SPY for S&P 500)
4. Select date range
5. Choose condition type and parameters
6. Click "Analyze"

### Example Analysis: Dow Theory Confirmation

- **Condition Tickers:** DJI, DJT
- **Target Ticker:** SPY
- **Condition Type:** Dual All-Time High
- **Days Gap:** 365

This analyzes S&P 500 performance after both Dow Industrials and Dow Transports hit new all-time highs for the first time in over a year.

## API Endpoints

### POST /api/fetch_data

Fetches and analyzes stock data.

**Request Body:**
```json
{
  "condition_tickers": ["QQQ", "AAPL"],
  "target_ticker": "SPY",
  "start_date": "1990-01-01",
  "end_date": "2024-01-01",
  "condition_type": "dual_ath",
  "condition_params": {"days_gap": 365},
  "api_key": "your_api_key"
}
```

**Response:**
```json
{
  "event_list": [...],
  "averages": {...},
  "positives": {...},
  "historical_data": {...},
  "event_markers": [...],
  "average_forward_curve": [...],
  "total_events": 10
}
```

### GET /api/condition_types

Returns available condition types and default parameters.

### GET /api/health

Health check endpoint.

## Condition Types Reference

| Type | Description | Parameters |
|------|-------------|------------|
| `dual_ath` | Both tickers at ATH | `days_gap` |
| `single_ath` | First ticker at ATH | `days_gap` |
| `rsi_above` | RSI crosses above threshold | `rsi_period`, `rsi_threshold` |
| `rsi_below` | RSI crosses below threshold | `rsi_period`, `rsi_threshold` |
| `ma_crossover` | Short MA crosses above long MA | `ma_short`, `ma_long` |
| `ma_crossunder` | Short MA crosses below long MA | `ma_short`, `ma_long` |
| `momentum_above` | Momentum exceeds threshold | `momentum_period`, `momentum_threshold` |
| `momentum_below` | Momentum below threshold | `momentum_period`, `momentum_threshold` |

## Project Structure

```
StockMarketHistoryCruncher/
├── backend/
│   ├── app.py              # Flask application
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment template
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── InputForm.js
│   │   │   ├── HistoricalChart.js
│   │   │   ├── ForwardReturnsChart.js
│   │   │   └── ResultsTable.js
│   │   ├── utils/
│   │   │   └── export.js
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
└── README.md
```

## Deployment

### Production Build

```bash
# Build frontend
cd frontend
npm run build

# Serve with Flask or nginx
```

### Gunicorn (Production)

```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Notes

- Polygon.io free tier has rate limits. For extensive historical data, consider a paid plan.
- API key is: zQiPSof8ubDKNiVGTNVKCPKqM6xoQYWu
- Historical data availability varies by ticker. Index data may start from different dates.
- The 5-day cooldown between events prevents duplicate triggers from consecutive days.

## License

MIT
