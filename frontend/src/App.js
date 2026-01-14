import React, { useState, useCallback } from 'react';
import axios from 'axios';
import InputForm from './components/InputForm';
import HistoricalChart from './components/HistoricalChart';
import ForwardReturnsChart from './components/ForwardReturnsChart';
import ResultsTable from './components/ResultsTable';
import DiscoveredTriggers from './components/DiscoveredTriggers';
import RecentTriggers from './components/RecentTriggers';
import { exportToCSV } from './utils/export';

function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [formData, setFormData] = useState(null);
  const [selectedTrigger, setSelectedTrigger] = useState(null);

  const handleSubmit = useCallback(async (data) => {
    setLoading(true);
    setError(null);
    setFormData(data);

    try {
      const response = await axios.post('/api/fetch_data', data);
      setResults(response.data);
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.message || 'An error occurred';
      setError(errorMsg);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleExport = useCallback(() => {
    if (results && results.event_list) {
      exportToCSV(results, formData);
    }
  }, [results, formData]);

  const handleSelectTrigger = useCallback((trigger) => {
    setSelectedTrigger(trigger);
    // Clear previous results when selecting a new trigger
    setResults(null);
    setError(null);
  }, []);

  const generateTitle = () => {
    if (!formData) return 'Stock Market History Cruncher';

    const { target_ticker, condition_tickers, condition_type, condition_params } = formData;
    const conditionNames = {
      'dual_ath': `Both ${condition_tickers.join(' & ')} hit ATH (>${condition_params.days_gap || 365} days)`,
      'single_ath': `${condition_tickers[0]} hits ATH (>${condition_params.days_gap || 365} days)`,
      'rsi_above': `RSI crosses above ${condition_params.rsi_threshold || 70} on ${condition_tickers[0]}`,
      'rsi_below': `RSI crosses below ${condition_params.rsi_threshold || 30} on ${condition_tickers[0]}`,
      'ma_crossover': `${condition_params.ma_short || 50}MA crosses above ${condition_params.ma_long || 200}MA on ${condition_tickers[0]}`,
      'ma_crossunder': `${condition_params.ma_short || 50}MA crosses below ${condition_params.ma_long || 200}MA on ${condition_tickers[0]}`,
      'momentum_above': `Momentum > ${(condition_params.momentum_threshold || 0.05) * 100}% on ${condition_tickers[0]}`,
      'momentum_below': `Momentum < ${(condition_params.momentum_threshold || -0.05) * 100}% on ${condition_tickers[0]}`,
      'sp500_pct_below_200ma': `S&P 500 % below 200 DMA drops to ≤${condition_params.breadth_threshold || 30}%`
    };

    return `${target_ticker}: ${conditionNames[condition_type] || condition_type}`;
  };

  return (
    <div className="min-vh-100">
      {/* Header */}
      <div className="header-bar">
        <div className="container">
          <h1 className="h3 mb-0">Stock Market History Cruncher</h1>
          <small>Analyze historical market performance after trigger conditions</small>
        </div>
      </div>

      <div className="container pb-5">
        {/* Recent Triggers - criteria that fired in the past 30 days */}
        <RecentTriggers onSelectTrigger={handleSelectTrigger} />

        {/* All Discovered Triggers */}
        <DiscoveredTriggers onSelectTrigger={handleSelectTrigger} />

        {/* Input Form */}
        <div className="card">
          <div className="card-header">
            <h5 className="mb-0">Analysis Parameters</h5>
          </div>
          <div className="card-body">
            <InputForm
              onSubmit={handleSubmit}
              loading={loading}
              selectedTrigger={selectedTrigger}
              onTriggerApplied={() => setSelectedTrigger(null)}
            />
          </div>
        </div>

        {/* Loading Overlay */}
        {loading && (
          <div className="loading-overlay">
            <div className="text-center">
              <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                <span className="visually-hidden">Loading...</span>
              </div>
              <p className="mt-3">Fetching and analyzing data...</p>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="alert alert-danger" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Results */}
        {results && !loading && (
          <>
            {/* Dynamic Title */}
            <div className="header-bar" style={{ borderRadius: '0.375rem' }}>
              <h4 className="mb-0">{generateTitle()}</h4>
              <small>{results.total_events || 0} events found</small>
            </div>

            {results.event_list && results.event_list.length > 0 ? (
              <>
                {/* Historical Chart */}
                <div className="card">
                  <div className="card-header d-flex justify-content-between align-items-center">
                    <h5 className="mb-0">Historical Price with Event Markers</h5>
                  </div>
                  <div className="card-body">
                    <div className="chart-container">
                      <HistoricalChart
                        data={results.historical_data}
                        eventMarkers={results.event_markers}
                        title={formData?.target_ticker || 'Target Index'}
                      />
                    </div>
                  </div>
                </div>

                {/* Results Table */}
                <div className="card">
                  <div className="card-header d-flex justify-content-between align-items-center">
                    <h5 className="mb-0">Forward Returns by Event</h5>
                    <button className="btn btn-sm btn-outline-secondary" onClick={handleExport}>
                      Export CSV
                    </button>
                  </div>
                  <div className="card-body p-0">
                    <div className="table-responsive">
                      <ResultsTable
                        events={results.event_list}
                        averages={results.averages}
                        positives={results.positives}
                      />
                    </div>
                  </div>
                </div>

                {/* Average Forward Returns Chart */}
                <div className="card">
                  <div className="card-header">
                    <h5 className="mb-0">Average Forward Returns (Next 252 Trading Days)</h5>
                  </div>
                  <div className="card-body">
                    <div className="chart-container">
                      <ForwardReturnsChart
                        data={results.average_forward_curve}
                        title="Average Return After Event"
                      />
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="alert alert-info">
                {results.message || 'No events found matching the specified criteria.'}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-dark text-white py-3 mt-auto">
        <div className="container text-center">
          <small>Stock Market History Cruncher | Data provided by Polygon.io</small>
        </div>
      </footer>
    </div>
  );
}

export default App;
