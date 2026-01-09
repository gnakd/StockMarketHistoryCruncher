import { saveAs } from 'file-saver';

const RETURN_COLUMNS = [
  '1_week', '2_weeks', '1_month', '2_months',
  '3_months', '6_months', '9_months', '1_year', 'max_drawdown'
];

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

export function exportToCSV(results, formData) {
  if (!results || !results.event_list) return;

  const { event_list, averages, positives } = results;

  // Build CSV header
  const headers = ['Date', ...RETURN_COLUMNS.map(col => COLUMN_LABELS[col])];

  // Build data rows
  const rows = event_list.map(event => {
    return [
      event.date,
      ...RETURN_COLUMNS.map(col => {
        const val = event[col];
        return val !== null && val !== undefined ? val.toFixed(2) + '%' : 'N/A';
      })
    ];
  });

  // Add average row
  rows.push([
    'Average',
    ...RETURN_COLUMNS.map(col => {
      const val = averages?.[col];
      return val !== null && val !== undefined ? val.toFixed(2) + '%' : 'N/A';
    })
  ]);

  // Add positive percentage row
  rows.push([
    '% Positive',
    ...RETURN_COLUMNS.map(col => {
      const val = positives?.[col];
      return val !== null && val !== undefined ? val.toFixed(1) + '%' : 'N/A';
    })
  ]);

  // Convert to CSV string
  const csvContent = [
    // Metadata
    `# Stock Market History Cruncher Analysis`,
    `# Target Ticker: ${formData?.target_ticker || 'N/A'}`,
    `# Condition Tickers: ${formData?.condition_tickers?.join(', ') || 'N/A'}`,
    `# Condition Type: ${formData?.condition_type || 'N/A'}`,
    `# Date Range: ${formData?.start_date || 'N/A'} to ${formData?.end_date || 'N/A'}`,
    `# Total Events: ${event_list.length}`,
    `# Generated: ${new Date().toISOString()}`,
    '',
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  // Create and save file
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
  const filename = `stock_analysis_${formData?.target_ticker || 'data'}_${new Date().toISOString().split('T')[0]}.csv`;
  saveAs(blob, filename);
}

export function exportForwardCurve(forwardCurve, formData) {
  if (!forwardCurve || forwardCurve.length === 0) return;

  const headers = ['Trading Day', 'Average Return (%)'];
  const rows = forwardCurve.map((val, idx) => [
    idx,
    val !== null && val !== undefined ? val.toFixed(2) : 'N/A'
  ]);

  const csvContent = [
    `# Average Forward Returns Curve`,
    `# Target Ticker: ${formData?.target_ticker || 'N/A'}`,
    `# Generated: ${new Date().toISOString()}`,
    '',
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
  const filename = `forward_curve_${formData?.target_ticker || 'data'}_${new Date().toISOString().split('T')[0]}.csv`;
  saveAs(blob, filename);
}
