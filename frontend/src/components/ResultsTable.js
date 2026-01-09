import React, { useState } from 'react';

const COLUMN_LABELS = {
  date: 'Date',
  '1_week': '1 Week Later',
  '2_weeks': '2 Weeks',
  '1_month': '1 Month',
  '2_months': '2 Months',
  '3_months': '3 Months',
  '6_months': '6 Months',
  '9_months': '9 Months',
  '1_year': '1 Year Later',
  'max_drawdown': '1 Year Max Drawdown'
};

const RETURN_COLUMNS = [
  '1_week', '2_weeks', '1_month', '2_months',
  '3_months', '6_months', '9_months', '1_year', 'max_drawdown'
];

const PERIOD_COLUMNS = [
  '1_week', '2_weeks', '1_month', '2_months',
  '3_months', '6_months', '9_months', '1_year'
];

function formatValue(value, isDrawdown = false) {
  if (value === null || value === undefined) {
    return { text: 'N/A', className: 'text-muted' };
  }

  const formatted = `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

  // For drawdown, negative is expected (and bad), positive would be unusual
  let className;
  if (isDrawdown) {
    className = value < -10 ? 'table-negative' : value < -5 ? 'text-warning' : 'table-positive';
  } else {
    className = value >= 0 ? 'table-positive' : 'table-negative';
  }

  return { text: formatted, className };
}

function formatPositive(value) {
  if (value === null || value === undefined) {
    return { text: 'N/A', className: 'text-muted' };
  }

  const formatted = `${value.toFixed(1)}%`;
  let className = value >= 50 ? 'table-positive' : 'table-negative';

  return { text: formatted, className };
}

function computeCounts(events, column) {
  const values = events.map(e => e[column]).filter(v => v !== null && v !== undefined);
  const positiveCount = values.filter(v => v >= 0).length;
  const negativeCount = values.filter(v => v < 0).length;
  return { positiveCount, negativeCount };
}

function ResultsTable({ events, averages, positives }) {
  const [highlightedCol, setHighlightedCol] = useState(null);

  const handleHeaderClick = (col) => {
    setHighlightedCol(highlightedCol === col ? null : col);
  };

  if (!events || events.length === 0) {
    return (
      <div className="p-4 text-center text-muted">
        No events to display
      </div>
    );
  }

  return (
    <>
      <table className="table table-striped table-hover results-table mb-0">
        <thead>
          <tr>
            <th className="sticky-top">{COLUMN_LABELS.date}</th>
            {RETURN_COLUMNS.map(col => (
              <th
                key={col}
                className={`sticky-top text-center ${highlightedCol === col ? 'highlighted' : ''}`}
                onClick={() => handleHeaderClick(col)}
                title="Click to highlight column"
              >
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {events.map((event, idx) => (
            <tr key={idx}>
              <td className="fw-medium">{event.date}</td>
              {RETURN_COLUMNS.map(col => {
                const { text, className } = formatValue(
                  event[col],
                  col === 'max_drawdown'
                );
                return (
                  <td key={col} className={`text-center ${className} ${highlightedCol === col ? 'highlighted' : ''}`}>
                    {text}
                  </td>
                );
              })}
            </tr>
          ))}

          {/* Average Row */}
          <tr className="avg-row">
            <td className="fw-bold">Average:</td>
            {RETURN_COLUMNS.map(col => {
              const { text, className } = formatValue(
                averages?.[col],
                col === 'max_drawdown'
              );
              return (
                <td key={col} className={`text-center ${className} ${highlightedCol === col ? 'highlighted' : ''}`}>
                  {text}
                </td>
              );
            })}
          </tr>

          {/* Positive Percentage Row */}
          <tr className="positive-row">
            <td className="fw-bold">% Positive:</td>
            {RETURN_COLUMNS.map(col => {
              const { text, className } = formatPositive(positives?.[col]);
              return (
                <td key={col} className={`text-center ${className} ${highlightedCol === col ? 'highlighted' : ''}`}>
                  {text}
                </td>
              );
            })}
          </tr>

          {/* Positive Count Row */}
          <tr className="positive-row">
            <td className="fw-bold"># Positive:</td>
            {RETURN_COLUMNS.map(col => {
              const { positiveCount } = computeCounts(events, col);
              return (
                <td key={col} className={`text-center table-positive ${highlightedCol === col ? 'highlighted' : ''}`}>
                  {positiveCount}
                </td>
              );
            })}
          </tr>

          {/* Negative Count Row */}
          <tr className="positive-row">
            <td className="fw-bold"># Negative:</td>
            {RETURN_COLUMNS.map(col => {
              const { negativeCount } = computeCounts(events, col);
              return (
                <td key={col} className={`text-center table-negative ${highlightedCol === col ? 'highlighted' : ''}`}>
                  {negativeCount}
                </td>
              );
            })}
          </tr>

          {/* Max Drawdown Per Period Row */}
          <tr className="avg-row">
            <td className="fw-bold">Avg Max DD:</td>
            {PERIOD_COLUMNS.map(col => {
              const ddKey = `${col}_max_dd`;
              const { text, className } = formatValue(averages?.[ddKey], true);
              return (
                <td key={col} className={`text-center ${className} ${highlightedCol === col ? 'highlighted' : ''}`}>
                  {text}
                </td>
              );
            })}
            {/* Last column is already max_drawdown (1 year) */}
            <td className={`text-center text-muted ${highlightedCol === 'max_drawdown' ? 'highlighted' : ''}`}>-</td>
          </tr>
        </tbody>
      </table>

      <div className="source-attribution p-2">
        Data source: Polygon.io | Analysis: Stock Market History Cruncher
      </div>
    </>
  );
}

export default ResultsTable;
