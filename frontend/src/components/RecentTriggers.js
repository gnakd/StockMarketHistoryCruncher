import React, { useState, useEffect } from 'react';
import axios from 'axios';

function RecentTriggers({ onSelectTrigger, apiKey }) {
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [dataRange, setDataRange] = useState(null);

  useEffect(() => {
    fetchTriggers();
    fetchDataRange();
  }, [apiKey]);

  const fetchTriggers = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/discovered_triggers');
      if (response.data.status === 'ok') {
        // Filter to only show triggers with recent activity
        const recentTriggers = (response.data.triggers || []).filter(
          t => t.recent_trigger_count > 0
        );
        // Sort by recent_trigger_count descending, then by latest_trigger_date
        recentTriggers.sort((a, b) => {
          if (b.recent_trigger_count !== a.recent_trigger_count) {
            return b.recent_trigger_count - a.recent_trigger_count;
          }
          return (b.latest_trigger_date || '').localeCompare(a.latest_trigger_date || '');
        });
        setTriggers(recentTriggers);
      } else {
        setTriggers([]);
        setError(response.data.message);
      }
    } catch (err) {
      setError('Failed to load triggers');
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

  const getCriteriaDescription = (criteria) => {
    const { condition_type, condition_tickers } = criteria;
    const ticker = condition_tickers?.[0] || 'SPY';

    switch (condition_type) {
      case 'rsi_above':
        return `RSI(${criteria.rsi_period}) > ${criteria.rsi_threshold} on ${ticker}`;
      case 'rsi_below':
        return `RSI(${criteria.rsi_period}) < ${criteria.rsi_threshold} on ${ticker}`;
      case 'ma_crossover':
        return `${criteria.ma_short}MA crosses above ${criteria.ma_long}MA on ${ticker}`;
      case 'ma_crossunder':
        return `${criteria.ma_short}MA crosses below ${criteria.ma_long}MA on ${ticker}`;
      case 'momentum_above':
        return `Momentum(${criteria.momentum_period}) > ${(criteria.momentum_threshold * 100).toFixed(0)}%`;
      case 'momentum_below':
        return `Momentum(${criteria.momentum_period}) < ${(criteria.momentum_threshold * 100).toFixed(0)}%`;
      case 'single_ath':
        return `${ticker} ATH (gap > ${criteria.days_gap} days)`;
      case 'dual_ath':
        return `Dual ATH: ${condition_tickers?.join(' & ')} (gap > ${criteria.days_gap})`;
      default:
        return condition_type;
    }
  };

  const getDaysAgo = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    const today = new Date();
    const diffTime = today - date;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <div className="card mb-4 border-warning">
        <div className="card-header bg-warning bg-opacity-10">
          <h5 className="mb-0">Recent Triggers (Past 30 Days)</h5>
        </div>
        <div className="card-body text-center">
          <div className="spinner-border spinner-border-sm" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <span className="ms-2">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card mb-4 border-warning">
      <div
        className="card-header bg-warning bg-opacity-10 d-flex justify-content-between align-items-center"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <h5 className="mb-0">
          Recent Triggers (Past 30 Days)
          {triggers.length > 0 && (
            <span className="badge bg-warning text-dark ms-2">{triggers.length}</span>
          )}
        </h5>
        <div className="d-flex align-items-center">
          <button
            className="btn btn-sm btn-outline-warning me-2"
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
            <div className="alert alert-secondary m-3 mb-0">
              No criteria have triggered in the past 30 days.
              {dataRange?.overall && (
                <small className="d-block mt-1 text-muted">
                  Data available: {dataRange.overall.first_date} to {dataRange.overall.last_date}
                </small>
              )}
            </div>
          ) : (
            <div className="table-responsive" style={{ maxHeight: '250px', overflowY: 'auto' }}>
              <table className="table table-hover table-sm mb-0">
                <thead className="sticky-top bg-white">
                  <tr>
                    <th style={{ width: '60px' }}>Score</th>
                    <th>Criteria</th>
                    <th style={{ width: '70px' }}>Recent</th>
                    <th style={{ width: '100px' }}>Latest</th>
                    <th style={{ width: '80px' }}>Avg Ret</th>
                    <th style={{ width: '70px' }}>Win %</th>
                    <th style={{ width: '80px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {triggers.map((trigger, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className={`badge ${trigger.score >= 70 ? 'bg-success' : trigger.score >= 50 ? 'bg-warning' : 'bg-secondary'}`}>
                          {formatScore(trigger.score)}
                        </span>
                      </td>
                      <td className="small">{getCriteriaDescription(trigger.criteria)}</td>
                      <td>
                        <span className="badge bg-info">{trigger.recent_trigger_count}</span>
                      </td>
                      <td className="small">
                        <div>{trigger.latest_trigger_date}</div>
                        <small className="text-muted">{getDaysAgo(trigger.latest_trigger_date)}</small>
                      </td>
                      <td className={trigger.avg_return_1y > 0 ? 'text-success' : trigger.avg_return_1y < 0 ? 'text-danger' : ''}>
                        {formatPercent(trigger.avg_return_1y)}
                      </td>
                      <td>{formatPercent(trigger.win_rate_1y)}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-warning"
                          onClick={() => handleSelectTrigger(trigger)}
                        >
                          Use
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default RecentTriggers;
