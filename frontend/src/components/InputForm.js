import React, { useState, useEffect } from 'react';
import { saveCreatedTrigger, calculateScore, deriveSignal } from '../utils/createdTriggerStorage';

const CONDITION_TYPES = [
  { value: 'dual_ath', label: 'Dual All-Time High', description: 'Both tickers hit ATH after gap period' },
  { value: 'single_ath', label: 'Single All-Time High', description: 'First ticker hits ATH after gap period' },
  { value: 'rsi_above', label: 'RSI Crosses Above', description: 'RSI crosses above threshold' },
  { value: 'rsi_below', label: 'RSI Crosses Below', description: 'RSI crosses below threshold' },
  { value: 'ma_crossover', label: 'MA Golden Cross', description: 'Short MA crosses above long MA' },
  { value: 'ma_crossunder', label: 'MA Death Cross', description: 'Short MA crosses below long MA' },
  { value: 'momentum_above', label: 'Momentum Above', description: 'Momentum crosses above threshold' },
  { value: 'momentum_below', label: 'Momentum Below', description: 'Momentum crosses below threshold' },
  { value: 'putcall_above', label: 'Put/Call Ratio Above', description: 'P/C crosses above threshold (fear spike = contrarian buy)' },
  { value: 'putcall_below', label: 'Put/Call Ratio Below', description: 'P/C crosses below threshold (complacency = caution)' },
  { value: 'vix_above', label: 'VIX Above', description: 'VIX crosses above threshold (fear spike = contrarian buy)' },
  { value: 'vix_below', label: 'VIX Below', description: 'VIX crosses below threshold (complacency = caution)' },
  { value: 'sp500_pct_above_200ma', label: 'S&P 500 % Above 200 DMA', description: '% of S&P 500 stocks above 200-day MA drops to threshold (fear = buy signal)' }
];

const DEFAULT_PARAMS = {
  dual_ath: { days_gap: 365 },
  single_ath: { days_gap: 365 },
  rsi_above: { rsi_period: 14, rsi_threshold: 70 },
  rsi_below: { rsi_period: 14, rsi_threshold: 30 },
  ma_crossover: { ma_short: 50, ma_long: 200 },
  ma_crossunder: { ma_short: 50, ma_long: 200 },
  momentum_above: { momentum_period: 12, momentum_threshold: 0.05 },
  momentum_below: { momentum_period: 12, momentum_threshold: -0.05 },
  putcall_above: { putcall_threshold: 1.0 },
  putcall_below: { putcall_threshold: 0.7 },
  vix_above: { vix_threshold: 30 },
  vix_below: { vix_threshold: 15 },
  sp500_pct_above_200ma: { breadth_threshold: 30 }
};

function InputForm({ onSubmit, loading, selectedTrigger, onTriggerApplied, apiKey, onApiKeyChange, results, onTriggerSaved }) {
  const [conditionTickers, setConditionTickers] = useState(['^DJI', '^DJT']);
  const [targetTicker, setTargetTicker] = useState('^GSPC');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [conditionType, setConditionType] = useState('dual_ath');
  const [conditionParams, setConditionParams] = useState(DEFAULT_PARAMS.dual_ath);
  const [tickerInput, setTickerInput] = useState('');
  const [dataRangeLoaded, setDataRangeLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  // Track if we just applied a trigger to prevent param reset
  const [triggerApplied, setTriggerApplied] = React.useState(false);

  // Fetch earliest available date from cache on mount
  useEffect(() => {
    if (!apiKey || dataRangeLoaded) return;

    fetch(`/api/data_range?api_key=${encodeURIComponent(apiKey)}`)
      .then(res => res.json())
      .then(data => {
        if (data.overall && data.overall.first_date) {
          setStartDate(data.overall.first_date);
        } else {
          // Fallback if no cached data
          setStartDate('2016-01-18');
        }
        setDataRangeLoaded(true);
      })
      .catch(() => {
        // Fallback on error
        setStartDate('2016-01-18');
        setDataRangeLoaded(true);
      });
  }, [apiKey, dataRangeLoaded]);

  // Apply selected trigger from DiscoveredTriggers component
  useEffect(() => {
    if (selectedTrigger) {
      setTriggerApplied(true);
      setConditionTickers(selectedTrigger.condition_tickers || []);
      setTargetTicker(selectedTrigger.target_ticker || 'SPY');
      setConditionType(selectedTrigger.condition_type || 'rsi_below');
      setConditionParams(selectedTrigger.condition_params || {});
      if (onTriggerApplied) {
        onTriggerApplied();
      }
    }
  }, [selectedTrigger, onTriggerApplied]);

  useEffect(() => {
    // Only reset params when condition type changes manually (not from trigger)
    if (triggerApplied) {
      setTriggerApplied(false);
      return;
    }
    setConditionParams(DEFAULT_PARAMS[conditionType] || {});
  }, [conditionType]);

  const handleAddTicker = () => {
    if (tickerInput.trim() && !conditionTickers.includes(tickerInput.trim().toUpperCase())) {
      setConditionTickers([...conditionTickers, tickerInput.trim().toUpperCase()]);
      setTickerInput('');
    }
  };

  const handleRemoveTicker = (ticker) => {
    setConditionTickers(conditionTickers.filter(t => t !== ticker));
  };

  const handleParamChange = (key, value) => {
    setConditionParams(prev => ({
      ...prev,
      [key]: isNaN(value) ? value : Number(value)
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      condition_tickers: conditionTickers,
      target_ticker: targetTicker,
      start_date: startDate,
      end_date: endDate,
      condition_type: conditionType,
      condition_params: conditionParams,
      api_key: apiKey
    });
  };

  const handleSaveTrigger = async () => {
    const name = window.prompt('Enter a name for this trigger:');
    if (!name || !name.trim()) return;

    setSaving(true);
    try {
      // Build criteria object (same structure as discovered triggers)
      const criteria = {
        condition_type: conditionType,
        condition_tickers: conditionTickers,
        target_ticker: targetTicker,
        ...conditionParams
      };

      // Extract metrics from results
      // Keys are '1_year', '6_months', etc. Values are percentages (e.g., 12.5 = 12.5%)
      const eventCount = results?.total_events || 0;
      const avgReturnPct = results?.averages?.['1_year'];
      const avgReturn = avgReturnPct != null ? avgReturnPct / 100 : null; // Convert to decimal (0.125 = 12.5%)
      const winRatePct = results?.positives?.['1_year'];
      const avgWinRate = winRatePct != null ? winRatePct / 100 : null; // Convert to decimal (0.75 = 75%)
      const maxDrawdown = results?.averages?.max_drawdown || null;

      // Calculate recent trigger count (events in last 30 days)
      let recentCount = 0;
      let latestDate = null;
      if (results?.event_list && results.event_list.length > 0) {
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0];

        recentCount = results.event_list.filter(e => e.date >= thirtyDaysAgoStr).length;
        latestDate = results.event_list[results.event_list.length - 1]?.date;
      }

      // Calculate score
      const score = calculateScore({
        avg_return: avgReturn || 0,
        avg_win_rate: avgWinRate || 0,
        event_count: eventCount,
        max_drawdown: maxDrawdown || 0
      });

      // Derive signal
      const signal = deriveSignal(conditionType);

      const triggerData = {
        name: name.trim(),
        criteria,
        event_count: eventCount,
        avg_return: avgReturn,
        avg_win_rate: avgWinRate,
        max_drawdown: maxDrawdown,
        score,
        signal,
        recent_trigger_count: recentCount,
        latest_trigger_date: latestDate
      };

      await saveCreatedTrigger(triggerData);
      alert('Trigger saved successfully!');

      if (onTriggerSaved) {
        onTriggerSaved();
      }
    } catch (error) {
      alert('Failed to save trigger: ' + error.message);
    } finally {
      setSaving(false);
    }
  };

  const renderConditionParams = () => {
    switch (conditionType) {
      case 'dual_ath':
      case 'single_ath':
        return (
          <div className="col-md-4">
            <label className="form-label">Days Gap (min days since last ATH)</label>
            <input
              type="number"
              className="form-control"
              value={conditionParams.days_gap || 365}
              onChange={(e) => handleParamChange('days_gap', e.target.value)}
              min="1"
            />
          </div>
        );

      case 'rsi_above':
      case 'rsi_below':
        return (
          <>
            <div className="col-md-3">
              <label className="form-label">RSI Period</label>
              <input
                type="number"
                className="form-control"
                value={conditionParams.rsi_period || 14}
                onChange={(e) => handleParamChange('rsi_period', e.target.value)}
                min="2"
              />
            </div>
            <div className="col-md-3">
              <label className="form-label">RSI Threshold</label>
              <input
                type="number"
                className="form-control"
                value={conditionParams.rsi_threshold || (conditionType === 'rsi_above' ? 70 : 30)}
                onChange={(e) => handleParamChange('rsi_threshold', e.target.value)}
                min="0"
                max="100"
              />
            </div>
          </>
        );

      case 'ma_crossover':
      case 'ma_crossunder':
        return (
          <>
            <div className="col-md-3">
              <label className="form-label">Short MA Period</label>
              <input
                type="number"
                className="form-control"
                value={conditionParams.ma_short || 50}
                onChange={(e) => handleParamChange('ma_short', e.target.value)}
                min="1"
              />
            </div>
            <div className="col-md-3">
              <label className="form-label">Long MA Period</label>
              <input
                type="number"
                className="form-control"
                value={conditionParams.ma_long || 200}
                onChange={(e) => handleParamChange('ma_long', e.target.value)}
                min="1"
              />
            </div>
          </>
        );

      case 'momentum_above':
      case 'momentum_below':
        return (
          <>
            <div className="col-md-3">
              <label className="form-label">Momentum Period (days)</label>
              <input
                type="number"
                className="form-control"
                value={conditionParams.momentum_period || 12}
                onChange={(e) => handleParamChange('momentum_period', e.target.value)}
                min="1"
              />
            </div>
            <div className="col-md-3">
              <label className="form-label">Threshold (%)</label>
              <input
                type="number"
                className="form-control"
                value={(conditionParams.momentum_threshold || 0.05) * 100}
                onChange={(e) => handleParamChange('momentum_threshold', e.target.value / 100)}
                step="0.1"
              />
            </div>
          </>
        );

      case 'putcall_above':
      case 'putcall_below':
        return (
          <div className="col-md-4">
            <label className="form-label">Put/Call Ratio Threshold</label>
            <input
              type="number"
              className="form-control"
              value={conditionParams.putcall_threshold || (conditionType === 'putcall_above' ? 1.0 : 0.7)}
              onChange={(e) => handleParamChange('putcall_threshold', e.target.value)}
              min="0.1"
              max="3.0"
              step="0.05"
            />
            <small className="text-muted">
              {conditionType === 'putcall_above'
                ? 'High P/C (>1.0) = fear/bearish sentiment. Typical range: 0.8-1.5'
                : 'Low P/C (<0.7) = complacency/bullish. Typical range: 0.5-0.8'}
            </small>
          </div>
        );

      case 'vix_above':
      case 'vix_below':
        return (
          <div className="col-md-4">
            <label className="form-label">VIX Threshold</label>
            <input
              type="number"
              className="form-control"
              value={conditionParams.vix_threshold || (conditionType === 'vix_above' ? 30 : 15)}
              onChange={(e) => handleParamChange('vix_threshold', e.target.value)}
              min="5"
              max="80"
              step="1"
            />
            <small className="text-muted">
              {conditionType === 'vix_above'
                ? 'High VIX (>30) = extreme fear = contrarian buy signal. Crisis levels: 40+'
                : 'Low VIX (<15) = complacency = potential caution. Typical: 12-20'}
            </small>
          </div>
        );

      case 'sp500_pct_above_200ma':
        return (
          <div className="col-md-4">
            <label className="form-label">% Above 200 DMA Threshold</label>
            <input
              type="number"
              className="form-control"
              value={conditionParams.breadth_threshold || 30}
              onChange={(e) => handleParamChange('breadth_threshold', e.target.value)}
              min="0"
              max="100"
              step="1"
            />
            <small className="text-muted">Triggers when % drops at or below this value</small>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="row g-3">
        {/* Condition Tickers - hidden for conditions that don't need them */}
        {!['sp500_pct_above_200ma', 'putcall_above', 'putcall_below', 'vix_above', 'vix_below'].includes(conditionType) ? (
          <div className="col-md-6">
            <label className="form-label">Condition Tickers</label>
            <div className="input-group mb-2">
              <input
                type="text"
                className="form-control"
                placeholder="Add ticker (e.g., ^DJI)"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTicker())}
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={handleAddTicker}
              >
                Add
              </button>
            </div>
            <div className="d-flex flex-wrap gap-1">
              {conditionTickers.map((ticker, idx) => (
                <span key={idx} className="badge bg-primary d-flex align-items-center">
                  {ticker}
                  <button
                    type="button"
                    className="btn-close btn-close-white ms-1"
                    style={{ fontSize: '0.6rem' }}
                    onClick={() => handleRemoveTicker(ticker)}
                  />
                </span>
              ))}
            </div>
            <small className="text-muted">
              {conditionType === 'dual_ath' ? 'Add at least 2 tickers for dual ATH' : 'First ticker will be used for condition'}
            </small>
          </div>
        ) : (
          <div className="col-md-6">
            <label className="form-label">Condition Tickers</label>
            <div className="alert alert-info mb-0 py-2">
              <small>
                {conditionType === 'sp500_pct_above_200ma'
                  ? 'This condition automatically uses all S&P 500 constituents. No condition tickers needed.'
                  : conditionType.startsWith('vix_')
                  ? 'VIX data from FRED (1990-present). No condition tickers needed.'
                  : 'Put/Call ratio uses CBOE market-wide data (2003-2019). No condition tickers needed.'}
              </small>
            </div>
          </div>
        )}

        {/* Target Ticker */}
        <div className="col-md-6">
          <label className="form-label">Target Ticker (to analyze)</label>
          <input
            type="text"
            className="form-control"
            placeholder="^GSPC"
            value={targetTicker}
            onChange={(e) => setTargetTicker(e.target.value.toUpperCase())}
            required
          />
          <small className="text-muted">The ticker to calculate forward returns for</small>
        </div>

        {/* Date Range */}
        <div className="col-md-3">
          <label className="form-label">Start Date</label>
          <input
            type="date"
            className="form-control"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </div>

        <div className="col-md-3">
          <label className="form-label">End Date</label>
          <input
            type="date"
            className="form-control"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
          />
        </div>

        {/* Condition Type */}
        <div className="col-md-6">
          <label className="form-label">
            Condition Type{' '}
            <a
              href="/docs/condition-types.html"
              target="_blank"
              rel="noopener noreferrer"
              className="text-decoration-none"
              title="View documentation for all condition types"
            >
              <small>(docs)</small>
            </a>
          </label>
          <select
            className="form-select"
            value={conditionType}
            onChange={(e) => setConditionType(e.target.value)}
          >
            {CONDITION_TYPES.map(type => (
              <option key={type.value} value={type.value}>
                {type.label} - {type.description}
              </option>
            ))}
          </select>
        </div>

        {/* Dynamic Condition Parameters */}
        {renderConditionParams()}

        {/* API Key */}
        <div className="col-12">
          <label className="form-label">Polygon.io API Key</label>
          <input
            type="password"
            className="form-control"
            placeholder="Enter your Polygon.io API key"
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            required
          />
          <small className="text-muted">
            Get your free API key at <a href="https://polygon.io" target="_blank" rel="noopener noreferrer">polygon.io</a>
          </small>
        </div>

        {/* Submit and Save Buttons */}
        <div className="col-12 d-flex gap-2">
          <button
            type="submit"
            className="btn btn-analyze btn-lg"
            disabled={loading || (conditionTickers.length === 0 && !['sp500_pct_above_200ma', 'putcall_above', 'putcall_below', 'vix_above', 'vix_below'].includes(conditionType))}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Analyzing...
              </>
            ) : (
              'Analyze'
            )}
          </button>
          <button
            type="button"
            className="btn btn-outline-success btn-lg"
            disabled={loading || saving || !results || !results.event_list || results.event_list.length === 0}
            onClick={handleSaveTrigger}
            title={!results ? 'Run analysis first to save trigger' : 'Save this trigger configuration'}
          >
            {saving ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Saving...
              </>
            ) : (
              'Save Trigger'
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

export default InputForm;
