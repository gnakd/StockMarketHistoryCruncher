import React, { useState, useEffect } from 'react';
import axios from 'axios';

function DiscoveredTriggers({ onSelectTrigger }) {
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    fetchTriggers();
  }, []);

  const fetchTriggers = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/discovered_triggers');
      if (response.data.status === 'ok') {
        setTriggers(response.data.triggers || []);
        setMetadata({
          updated_at: response.data.updated_at,
          total_tested: response.data.total_tested,
          total_valid: response.data.total_valid,
          date_range: response.data.date_range,
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
              {metadata && (
                <div className="px-3 py-2 bg-light border-bottom small">
                  <span className="text-muted">
                    Last updated: {new Date(metadata.updated_at).toLocaleString()} |
                    Tested: {metadata.total_tested} | Valid: {metadata.total_valid} |
                    Range: {metadata.date_range?.start} to {metadata.date_range?.end}
                  </span>
                </div>
              )}
              <div className="table-responsive" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                <table className="table table-hover table-sm mb-0">
                  <thead className="sticky-top bg-white">
                    <tr>
                      <th style={{ width: '50px' }}>Rank</th>
                      <th style={{ width: '60px' }}>Score</th>
                      <th>Criteria</th>
                      <th style={{ width: '70px' }}>Events</th>
                      <th style={{ width: '80px' }}>Avg Ret</th>
                      <th style={{ width: '70px' }}>Win %</th>
                      <th style={{ width: '65px' }}>Recent</th>
                      <th style={{ width: '90px' }}>Latest</th>
                      <th style={{ width: '80px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {triggers.map((trigger, idx) => (
                      <tr key={idx}>
                        <td className="text-muted">{idx + 1}</td>
                        <td>
                          <span className={`badge ${trigger.score >= 70 ? 'bg-success' : trigger.score >= 50 ? 'bg-warning' : 'bg-secondary'}`}>
                            {formatScore(trigger.score)}
                          </span>
                        </td>
                        <td className="small">{getCriteriaDescription(trigger.criteria)}</td>
                        <td>{trigger.event_count}</td>
                        <td className={trigger.avg_return_1y > 0 ? 'text-success' : trigger.avg_return_1y < 0 ? 'text-danger' : ''}>
                          {formatPercent(trigger.avg_return_1y)}
                        </td>
                        <td>{formatPercent(trigger.win_rate_1y)}</td>
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
                            className="btn btn-sm btn-primary"
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
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default DiscoveredTriggers;
