import React, { useState, useEffect } from 'react';
import axios from 'axios';

function DiscoveredTriggers({ onSelectTrigger, apiKey }) {
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [dataRange, setDataRange] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [sortColumn, setSortColumn] = useState('score');
  const [sortDirection, setSortDirection] = useState('desc');

  useEffect(() => {
    fetchTriggers();
    fetchDataRange();
  }, [apiKey]);

  // Auto-refresh trigger activity on initial load
  useEffect(() => {
    if (triggers.length > 0 && apiKey && !metadata?.activity_refreshed_at) {
      refreshTriggerActivity();
    }
  }, [triggers.length, apiKey]);

  const fetchTriggers = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/discovered_triggers');
      if (response.data.status === 'ok') {
        setTriggers(response.data.triggers || []);
        setMetadata({
          updated_at: response.data.updated_at,
          activity_refreshed_at: response.data.activity_refreshed_at,
          total_tested: response.data.total_tested,
          total_valid: response.data.total_valid,
          total_passed_filters: response.data.total_passed_filters,
          date_range: response.data.date_range,
          scoring_mode: response.data.scoring_mode,
          filter_thresholds: response.data.filter_thresholds,
          filter_stats: response.data.filter_stats,
        });
      } else {
        setTriggers([]);
        setError(response.data.message);
      }
    } catch (err) {
      setError('Failed to load discovered triggers');
      setTriggers([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchDataRange = async () => {
    try {
      const params = apiKey ? { api_key: apiKey } : {};
      const response = await axios.get('/api/data_range', { params });
      if (response.data.status === 'ok') {
        setDataRange(response.data);
      }
    } catch (err) {
      console.error('Failed to fetch data range:', err);
    }
  };

  const refreshTriggerActivity = async () => {
    if (!apiKey) {
      setError('API key required to refresh trigger activity');
      return;
    }
    setRefreshing(true);
    try {
      const response = await axios.post('/api/triggers/refresh', { api_key: apiKey });
      if (response.data.status === 'ok') {
        setTriggers(response.data.triggers || []);
        setMetadata(prev => ({
          ...prev,
          activity_refreshed_at: response.data.refreshed_at,
        }));
        setError(null);
      } else {
        setError(response.data.error || 'Failed to refresh');
      }
    } catch (err) {
      setError('Failed to refresh trigger activity: ' + (err.response?.data?.error || err.message));
    } finally {
      setRefreshing(false);
    }
  };

  const handleSelectTrigger = (trigger) => {
    const { criteria } = trigger;
    onSelectTrigger({
      condition_tickers: criteria.condition_tickers,
      target_ticker: criteria.target_ticker,
      condition_type: criteria.condition_type,
      condition_params: Object.fromEntries(
        Object.entries(criteria).filter(([k]) =>
          !['condition_type', 'condition_tickers', 'target_ticker'].includes(k)
        )
      ),
    });
  };

  const formatPercent = (val) => {
    if (val === null || val === undefined) return 'N/A';
    return `${(val * 100).toFixed(1)}%`;
  };

  const formatScore = (val) => {
    if (val === null || val === undefined) return 'N/A';
    return val.toFixed(1);
  };

  const getSignalDirection = (trigger) => {
    // Use signal field if present, otherwise derive from condition_type
    if (trigger.signal) return trigger.signal;

    const conditionType = trigger.criteria?.condition_type;
    const bullishTypes = ['rsi_above', 'rsi_below', 'momentum_above', 'momentum_below', 'ma_crossover', 'single_ath', 'dual_ath', 'vix_above', 'putcall_above', 'feargreed_below'];
    const bearishTypes = ['ma_crossunder', 'vix_below', 'putcall_below', 'feargreed_above'];

    if (bullishTypes.includes(conditionType)) return 'bullish';
    if (bearishTypes.includes(conditionType)) return 'bearish';
    return null;
  };

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const getSortedTriggers = () => {
    return [...triggers].sort((a, b) => {
      let aVal, bVal;

      switch (sortColumn) {
        case 'score':
          aVal = a.score ?? 0;
          bVal = b.score ?? 0;
          break;
        case 'target':
          aVal = a.criteria?.target_ticker || '';
          bVal = b.criteria?.target_ticker || '';
          break;
        case 'signal':
          aVal = getSignalDirection(a) || '';
          bVal = getSignalDirection(b) || '';
          break;
        case 'criteria':
          aVal = getCriteriaDescription(a.criteria);
          bVal = getCriteriaDescription(b.criteria);
          break;
        case 'events':
          aVal = a.event_count ?? 0;
          bVal = b.event_count ?? 0;
          break;
        case 'avgReturn':
          aVal = a.avg_return ?? a.avg_return_1y ?? 0;
          bVal = b.avg_return ?? b.avg_return_1y ?? 0;
          break;
        case 'winRate':
          aVal = a.avg_win_rate ?? a.win_rate_1y ?? 0;
          bVal = b.avg_win_rate ?? b.win_rate_1y ?? 0;
          break;
        case 'avgDD':
          aVal = a.avg_drawdown ?? a.max_drawdown ?? a.avg_max_dd ?? 0;
          bVal = b.avg_drawdown ?? b.max_drawdown ?? b.avg_max_dd ?? 0;
          break;
        case 'recent':
          aVal = a.recent_trigger_count ?? 0;
          bVal = b.recent_trigger_count ?? 0;
          break;
        case 'latest':
          aVal = a.latest_trigger_date || '';
          bVal = b.latest_trigger_date || '';
          break;
        default:
          aVal = a.score ?? 0;
          bVal = b.score ?? 0;
      }

      if (typeof aVal === 'string') {
        const cmp = aVal.localeCompare(bVal);
        return sortDirection === 'asc' ? cmp : -cmp;
      }
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    });
  };

  const SortHeader = ({ column, children, style }) => (
    <th
      style={{ ...style, cursor: 'pointer', userSelect: 'none' }}
      onClick={() => handleSort(column)}
      title={`Sort by ${children}`}
    >
      {children}
      {sortColumn === column && (
        <span className="ms-1">{sortDirection === 'asc' ? '▲' : '▼'}</span>
      )}
    </th>
  );

  const getCriteriaDescription = (criteria) => {
    const { condition_type, condition_tickers } = criteria;

    switch (condition_type) {
      case 'rsi_above':
        return `RSI(${criteria.rsi_period}) > ${criteria.rsi_threshold}`;
      case 'rsi_below':
        return `RSI(${criteria.rsi_period}) < ${criteria.rsi_threshold}`;
      case 'ma_crossover':
        return `${criteria.ma_short}MA crosses above ${criteria.ma_long}MA`;
      case 'ma_crossunder':
        return `${criteria.ma_short}MA crosses below ${criteria.ma_long}MA`;
      case 'momentum_above':
        return `Momentum(${criteria.momentum_period}) > ${(criteria.momentum_threshold * 100).toFixed(0)}%`;
      case 'momentum_below':
        return `Momentum(${criteria.momentum_period}) < ${(criteria.momentum_threshold * 100).toFixed(0)}%`;
      case 'single_ath':
        return `ATH (gap > ${criteria.days_gap} days)`;
      case 'dual_ath':
        return `Dual ATH: ${condition_tickers?.join(' & ')} (gap > ${criteria.days_gap})`;
      case 'vix_above':
        return `VIX > ${criteria.vix_threshold}`;
      case 'vix_below':
        return `VIX < ${criteria.vix_threshold}`;
      case 'putcall_above':
        return `P/C > ${criteria.putcall_threshold}`;
      case 'putcall_below':
        return `P/C < ${criteria.putcall_threshold}`;
      case 'feargreed_above':
        return `F&G > ${criteria.feargreed_threshold}`;
      case 'feargreed_below':
        return `F&G < ${criteria.feargreed_threshold}`;
      case 'sp500_pct_above_200ma':
        return `S&P breadth ≤${criteria.breadth_threshold}%`;
      default:
        return condition_type;
    }
  };

  if (loading) {
    return (
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Discovered Triggers</h5>
        </div>
        <div className="card-body text-center">
          <div className="spinner-border spinner-border-sm" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <span className="ms-2">Loading triggers...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card mb-4">
      <div
        className="card-header d-flex justify-content-between align-items-center"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <h5 className="mb-0">
          Discovered Triggers
          {triggers.length > 0 && (
            <span className="badge bg-success ms-2">{triggers.length}</span>
          )}
        </h5>
        <div className="d-flex align-items-center">
          <button
            className="btn btn-sm btn-outline-secondary me-2"
            onClick={(e) => { e.stopPropagation(); fetchTriggers(); }}
          >
            Refresh
          </button>
          <span>{expanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {expanded && (
        <div className="card-body p-0">
          {error && triggers.length === 0 ? (
            <div className="alert alert-info m-3 mb-0">
              {error}
            </div>
          ) : triggers.length === 0 ? (
            <div className="alert alert-info m-3 mb-0">
              No discovered triggers yet. Run CriteriaTriggerDiscovery to find high-signal triggers.
            </div>
          ) : (
            <>
              {(metadata || dataRange) && (
                <div className="px-3 py-2 bg-light border-bottom small">
                  <div className="d-flex justify-content-between align-items-center flex-wrap">
                    <div>
                      <span className="text-muted">
                        {metadata && (
                          <>
                            Discovery: {new Date(metadata.updated_at).toLocaleDateString()} |
                            Tested: {metadata.total_tested} | Valid: {metadata.total_valid}
                            {metadata.total_passed_filters !== undefined && (
                              <> | Passed: {metadata.total_passed_filters}</>
                            )}
                          </>
                        )}
                      </span>
                      {metadata?.scoring_mode && (
                        <span className="ms-2 badge bg-primary">{metadata.scoring_mode}</span>
                      )}
                      {dataRange?.overall && (
                        <span className="ms-2 badge bg-info">
                          Data: {dataRange.overall.first_date} to {dataRange.overall.last_date}
                        </span>
                      )}
                      {metadata?.activity_refreshed_at && (
                        <span className="ms-2 text-success small">
                          Activity updated: {new Date(metadata.activity_refreshed_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <button
                      className="btn btn-sm btn-outline-primary"
                      onClick={(e) => { e.stopPropagation(); refreshTriggerActivity(); }}
                      disabled={refreshing || !apiKey}
                      title={!apiKey ? 'Enter API key to refresh' : 'Refresh recent trigger activity'}
                    >
                      {refreshing ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                          Refreshing...
                        </>
                      ) : (
                        'Refresh Activity'
                      )}
                    </button>
                  </div>
                  {metadata?.filter_thresholds && (
                    <div className="mt-1 text-muted" style={{ fontSize: '0.75rem' }}>
                      Filters: Win Rate ≥{(metadata.filter_thresholds.min_win_rate * 100).toFixed(0)}% |
                      Max Drawdown ≥{metadata.filter_thresholds.max_drawdown}% |
                      Min Events ≥{metadata.filter_thresholds.min_events}
                    </div>
                  )}
                </div>
              )}
              <div className="table-responsive" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                <table className="table table-hover table-sm mb-0">
                  <thead className="sticky-top bg-white">
                    <tr>
                      <th style={{ width: '45px' }}>#</th>
                      <SortHeader column="score" style={{ width: '55px' }}>Score</SortHeader>
                      <SortHeader column="target" style={{ width: '60px' }}>Target</SortHeader>
                      <SortHeader column="signal" style={{ width: '70px' }}>Signal</SortHeader>
                      <SortHeader column="criteria">Criteria</SortHeader>
                      <SortHeader column="events" style={{ width: '60px' }}>Events</SortHeader>
                      <SortHeader column="avgReturn" style={{ width: '70px' }}>Avg Ret</SortHeader>
                      <SortHeader column="winRate" style={{ width: '70px' }}>Avg WR</SortHeader>
                      <SortHeader column="avgDD" style={{ width: '65px' }}>Avg DD</SortHeader>
                      <SortHeader column="recent" style={{ width: '55px' }}>Recent</SortHeader>
                      <SortHeader column="latest" style={{ width: '85px' }}>Latest</SortHeader>
                      <th style={{ width: '60px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getSortedTriggers().map((trigger, idx) => {
                      // Support both old format (avg_return_1y) and new format (avg_return)
                      const avgReturn = trigger.avg_return ?? trigger.avg_return_1y;
                      const avgWinRate = trigger.avg_win_rate ?? trigger.win_rate_1y;
                      // avg_max_dd is stored as decimal (e.g., -0.13), convert to percentage
                      const avgDrawdownRaw = trigger.avg_drawdown ?? trigger.max_drawdown ?? trigger.avg_max_dd;
                      const avgDrawdown = avgDrawdownRaw != null ? avgDrawdownRaw * 100 : null;

                      return (
                        <tr key={idx}>
                          <td className="text-muted">{idx + 1}</td>
                          <td>
                            <span className={`badge ${trigger.score >= 70 ? 'bg-success' : trigger.score >= 50 ? 'bg-warning' : 'bg-secondary'}`}>
                              {formatScore(trigger.score)}
                            </span>
                          </td>
                          <td>
                            <span className="badge bg-dark">{trigger.criteria?.target_ticker || 'SPY'}</span>
                          </td>
                          <td>
                            {(() => {
                              const signal = getSignalDirection(trigger);
                              if (!signal) return <span className="text-muted">-</span>;
                              return (
                                <span
                                  className={`badge ${signal === 'bullish' ? 'bg-success' : 'bg-danger'}`}
                                  style={{ fontSize: '0.7rem' }}
                                >
                                  {signal === 'bullish' ? '▲ Bull' : '▼ Bear'}
                                </span>
                              );
                            })()}
                          </td>
                          <td className="small text-truncate" style={{ maxWidth: '200px' }} title={getCriteriaDescription(trigger.criteria)}>{getCriteriaDescription(trigger.criteria)}</td>
                          <td>{trigger.event_count}</td>
                          <td className={avgReturn > 0 ? 'text-success' : avgReturn < 0 ? 'text-danger' : ''}>
                            {formatPercent(avgReturn)}
                          </td>
                          <td className={avgWinRate >= 0.7 ? 'text-success' : ''}>
                            {formatPercent(avgWinRate)}
                          </td>
                          <td className={avgDrawdown != null ? (avgDrawdown > -5 ? 'text-success' : avgDrawdown > -10 ? 'text-warning' : 'text-danger') : ''}>
                            {avgDrawdown != null ? `${avgDrawdown.toFixed(1)}%` : '-'}
                          </td>
                          <td>
                            {trigger.recent_trigger_count > 0 ? (
                              <span className="badge bg-info">{trigger.recent_trigger_count}</span>
                            ) : (
                              <span className="text-muted">0</span>
                            )}
                          </td>
                          <td className="small">
                            {trigger.latest_trigger_date || 'N/A'}
                          </td>
                          <td>
                            <button
                              className="btn btn-sm btn-primary btn-xs"
                              onClick={() => handleSelectTrigger(trigger)}
                            >
                              Use
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default DiscoveredTriggers;
