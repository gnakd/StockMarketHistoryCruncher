import React, { useState, useEffect, useCallback } from 'react';
import { loadCreatedTriggers, deleteCreatedTrigger, updateCreatedTrigger } from '../utils/createdTriggerStorage';

function CreatedTriggers({ onSelectTrigger, onTriggersChange }) {
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);

  const fetchTriggers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await loadCreatedTriggers();
      setTriggers(data || []);
      setError(null);
    } catch (err) {
      setError('Failed to load created triggers');
      setTriggers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTriggers();
  }, [fetchTriggers]);

  // Expose refresh function to parent
  useEffect(() => {
    if (onTriggersChange) {
      onTriggersChange(fetchTriggers);
    }
  }, [onTriggersChange, fetchTriggers]);

  const handleSelectTrigger = (trigger) => {
    const { criteria } = trigger;
    onSelectTrigger({
      condition_tickers: criteria.condition_tickers || [],
      target_ticker: criteria.target_ticker,
      condition_type: criteria.condition_type,
      condition_params: Object.fromEntries(
        Object.entries(criteria).filter(([k]) =>
          !['condition_type', 'condition_tickers', 'target_ticker'].includes(k)
        )
      ),
    });
  };

  const handleDelete = async (e, triggerId, triggerName) => {
    e.stopPropagation();
    if (!window.confirm(`Delete trigger "${triggerName}"?`)) {
      return;
    }

    setDeletingId(triggerId);
    try {
      await deleteCreatedTrigger(triggerId);
      setTriggers(prev => prev.filter(t => t.id !== triggerId));
    } catch (err) {
      setError('Failed to delete trigger');
    } finally {
      setDeletingId(null);
    }
  };

  const handleRename = async (e, triggerId, currentName) => {
    e.stopPropagation();
    const newName = window.prompt('Enter new name:', currentName);
    if (!newName || !newName.trim() || newName.trim() === currentName) {
      return;
    }

    setRenamingId(triggerId);
    try {
      const updated = await updateCreatedTrigger(triggerId, { name: newName.trim() });
      setTriggers(prev => prev.map(t => t.id === triggerId ? updated : t));
    } catch (err) {
      setError('Failed to rename trigger');
    } finally {
      setRenamingId(null);
    }
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
    if (trigger.signal) return trigger.signal;

    const conditionType = trigger.criteria?.condition_type;
    const bullishTypes = ['rsi_above', 'rsi_below', 'momentum_above', 'momentum_below',
                          'ma_crossover', 'single_ath', 'dual_ath', 'vix_above',
                          'putcall_above', 'sp500_pct_above_200ma'];
    const bearishTypes = ['ma_crossunder', 'vix_below', 'putcall_below'];

    if (bullishTypes.includes(conditionType)) return 'bullish';
    if (bearishTypes.includes(conditionType)) return 'bearish';
    return null;
  };

  const getCriteriaDescription = (criteria) => {
    const { condition_type } = criteria;

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
        return `Dual ATH (gap > ${criteria.days_gap})`;
      case 'vix_above':
        return `VIX > ${criteria.vix_threshold}`;
      case 'vix_below':
        return `VIX < ${criteria.vix_threshold}`;
      case 'putcall_above':
        return `P/C > ${criteria.putcall_threshold}`;
      case 'putcall_below':
        return `P/C < ${criteria.putcall_threshold}`;
      case 'sp500_pct_above_200ma':
        return `S&P breadth drops to ≤${criteria.breadth_threshold}%`;
      default:
        return condition_type;
    }
  };

  if (loading) {
    return (
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Saved Triggers</h5>
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
          Saved Triggers
          {triggers.length > 0 && (
            <span className="badge bg-primary ms-2">{triggers.length}</span>
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
            <div className="alert alert-warning m-3 mb-0">
              {error}
            </div>
          ) : triggers.length === 0 ? (
            <div className="alert alert-info m-3 mb-0">
              No saved triggers yet. Run an analysis and click "Save Trigger" to save your configuration.
            </div>
          ) : (
            <div className="table-responsive" style={{ maxHeight: '300px', overflowY: 'auto' }}>
              <table className="table table-hover table-sm mb-0">
                <thead className="sticky-top bg-white">
                  <tr>
                    <th style={{ width: '120px' }}>Name</th>
                    <th style={{ width: '55px' }}>Score</th>
                    <th style={{ width: '60px' }}>Target</th>
                    <th style={{ width: '70px' }}>Signal</th>
                    <th>Criteria</th>
                    <th style={{ width: '60px' }}>Events</th>
                    <th style={{ width: '70px' }}>Avg Ret</th>
                    <th style={{ width: '70px' }}>Win Rate</th>
                    <th style={{ width: '65px' }}>Avg DD</th>
                    <th style={{ width: '85px' }}>Latest</th>
                    <th style={{ width: '140px' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {triggers.map((trigger, idx) => {
                    const avgReturn = trigger.avg_return;
                    const avgWinRate = trigger.avg_win_rate;
                    const maxDrawdown = trigger.max_drawdown;

                    return (
                      <tr key={trigger.id || idx}>
                        <td className="fw-medium text-truncate" style={{ maxWidth: '120px' }} title={trigger.name}>
                          {trigger.name}
                        </td>
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
                        <td className="small">{getCriteriaDescription(trigger.criteria)}</td>
                        <td>{trigger.event_count}</td>
                        <td className={avgReturn > 0 ? 'text-success' : avgReturn < 0 ? 'text-danger' : ''}>
                          {formatPercent(avgReturn)}
                        </td>
                        <td className={avgWinRate >= 0.7 ? 'text-success' : ''}>
                          {formatPercent(avgWinRate)}
                        </td>
                        <td className={maxDrawdown !== undefined ? (maxDrawdown > -5 ? 'text-success' : maxDrawdown > -10 ? 'text-warning' : 'text-danger') : ''}>
                          {maxDrawdown !== undefined ? `${maxDrawdown.toFixed(1)}%` : 'N/A'}
                        </td>
                        <td className="small">
                          {trigger.latest_trigger_date || 'N/A'}
                        </td>
                        <td>
                          <button
                            className="btn btn-sm btn-primary btn-xs me-1"
                            onClick={() => handleSelectTrigger(trigger)}
                          >
                            Use
                          </button>
                          <button
                            className="btn btn-sm btn-outline-secondary btn-xs me-1"
                            onClick={(e) => handleRename(e, trigger.id, trigger.name)}
                            disabled={renamingId === trigger.id}
                            title="Rename trigger"
                          >
                            {renamingId === trigger.id ? '...' : 'Edit'}
                          </button>
                          <button
                            className="btn btn-sm btn-outline-danger btn-xs"
                            onClick={(e) => handleDelete(e, trigger.id, trigger.name)}
                            disabled={deletingId === trigger.id}
                            title="Delete trigger"
                          >
                            {deletingId === trigger.id ? '...' : 'Del'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default CreatedTriggers;
