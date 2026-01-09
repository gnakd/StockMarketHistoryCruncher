import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

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
        'breadth_adv_dec'
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
        'breadth_adv_dec': {'breadth_threshold': 2.0}
    }
