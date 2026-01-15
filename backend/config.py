import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # Cache configuration
    CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'True').lower() == 'true'
    CACHE_DB_PATH = os.getenv('CACHE_DB_PATH', 'data/price_cache.db')

    # API rate limiting
    API_RATE_LIMIT_DELAY = float(os.getenv('API_RATE_LIMIT_DELAY', '0.25'))
    API_MAX_RETRIES = int(os.getenv('API_MAX_RETRIES', '3'))

    # Cache refresh policy
    CACHE_ROLLING_REFRESH_DAYS = int(os.getenv('CACHE_ROLLING_REFRESH_DAYS', '90'))
    CACHE_FULL_REFRESH_INTERVAL = int(os.getenv('CACHE_FULL_REFRESH_INTERVAL', '30'))

    # Trading day intervals for forward returns
    RETURN_INTERVALS = {
        '1_week': 5,
        '2_weeks': 10,
        '1_month': 21,
        '2_months': 42,
        '3_months': 63,
        '6_months': 126,
        '9_months': 189,
        '1_year': 252
    }

    # Condition types available
    CONDITION_TYPES = [
        'dual_ath',
        'single_ath',
        'rsi_above',
        'rsi_below',
        'ma_crossover',
        'ma_crossunder',
        'momentum_above',
        'momentum_below',
        'breadth_adv_dec',
        'sp500_pct_below_200ma'
    ]

    # Default condition parameters
    DEFAULT_PARAMS = {
        'dual_ath': {'days_gap': 365},
        'single_ath': {'days_gap': 365},
        'rsi_above': {'rsi_period': 14, 'rsi_threshold': 70},
        'rsi_below': {'rsi_period': 14, 'rsi_threshold': 30},
        'ma_crossover': {'ma_short': 50, 'ma_long': 200},
        'ma_crossunder': {'ma_short': 50, 'ma_long': 200},
        'momentum_above': {'momentum_period': 12, 'momentum_threshold': 0.05},
        'momentum_below': {'momentum_period': 12, 'momentum_threshold': -0.05},
        'breadth_adv_dec': {'breadth_threshold': 2.0},
        'sp500_pct_below_200ma': {'breadth_threshold': 30}
    }
