"""
Local cache module for stock price data.

Provides SQLite-based caching to minimize Polygon.io API calls.
"""

from .db import init_db, get_connection, get_db_stats
from .manager import CacheManager
from .sp500_cacher import SP500Cacher, start_sp500_cache_job, get_job_status
from .refresh import RefreshPolicy, RefreshStrategy

__all__ = [
    'init_db',
    'get_connection',
    'get_db_stats',
    'CacheManager',
    'SP500Cacher',
    'start_sp500_cache_job',
    'get_job_status',
    'RefreshPolicy',
    'RefreshStrategy',
]
