import React, { useMemo, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { baseChartOptions, createTitleConfig, createAxisTitle, ChartEmptyState } from '../utils/chartConfig';

function ForwardReturnsChart({ data, title }) {
  const [showBands, setShowBands] = useState(true);
  const [bandType, setBandType] = useState('minmax'); // 'minmax' or 'stddev'

  // Handle both old format (array) and new format (object with avg, max, min, std)
  const curveData = useMemo(() => {
    if (!data) return null;

    // Old format: just an array of averages
    if (Array.isArray(data)) {
      return { avg: data, max: null, min: null, std: null };
    }

    // New format: object with curves
    return data;
  }, [data]);

  const chartData = useMemo(() => {
    if (!curveData?.avg?.length) return { labels: [], datasets: [] };

    const labels = curveData.avg.map((_, idx) => idx);
    const datasets = [];

    // Main average line
    datasets.push({
      label: 'Average Return',
      data: curveData.avg,
      borderColor: '#28a745',
      backgroundColor: 'transparent',
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      fill: false,
      tension: 0.1,
      order: 1
    });

    // Median line (thinner dotted green)
    if (curveData.median) {
      datasets.push({
        label: 'Median Return',
        data: curveData.median,
        borderColor: 'rgba(40, 167, 69, 0.7)',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [2, 2],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.1,
        order: 1
      });
    }

    if (showBands && bandType === 'minmax' && curveData.max && curveData.min) {
      // Max gains line (dashed)
      datasets.push({
        label: 'Best Case',
        data: curveData.max,
        borderColor: 'rgba(40, 167, 69, 0.5)',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [5, 5],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.1,
        order: 2
      });

      // Min returns line (dashed) - worst case / max drawdown
      datasets.push({
        label: 'Worst Case',
        data: curveData.min,
        borderColor: 'rgba(220, 53, 69, 0.5)',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [5, 5],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.1,
        order: 3
      });

      // Shaded area between min and max
      datasets.push({
        label: 'Range',
        data: curveData.max,
        borderColor: 'transparent',
        backgroundColor: 'rgba(40, 167, 69, 0.08)',
        borderWidth: 0,
        pointRadius: 0,
        fill: '+1', // Fill to next dataset (min)
        tension: 0.1,
        order: 4
      });
      datasets.push({
        label: '_min_fill',
        data: curveData.min,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        borderWidth: 0,
        pointRadius: 0,
        fill: false,
        tension: 0.1,
        order: 5
      });
    } else if (showBands && bandType === 'stddev' && curveData.std) {
      // +1 std dev band
      const upperBand = curveData.avg.map((avg, i) =>
        avg !== null && curveData.std[i] !== null ? avg + curveData.std[i] : null
      );
      // -1 std dev band
      const lowerBand = curveData.avg.map((avg, i) =>
        avg !== null && curveData.std[i] !== null ? avg - curveData.std[i] : null
      );

      datasets.push({
        label: '+1 Std Dev',
        data: upperBand,
        borderColor: 'rgba(23, 162, 184, 0.4)',
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderDash: [3, 3],
        pointRadius: 0,
        fill: false,
        tension: 0.1,
        order: 2
      });

      datasets.push({
        label: '-1 Std Dev',
        data: lowerBand,
        borderColor: 'rgba(23, 162, 184, 0.4)',
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderDash: [3, 3],
        pointRadius: 0,
        fill: false,
        tension: 0.1,
        order: 3
      });

      // Shaded area for std dev
      datasets.push({
        label: '±1σ Range',
        data: upperBand,
        borderColor: 'transparent',
        backgroundColor: 'rgba(23, 162, 184, 0.1)',
        borderWidth: 0,
        pointRadius: 0,
        fill: '+1',
        tension: 0.1,
        order: 4
      });
      datasets.push({
        label: '_lower_fill',
        data: lowerBand,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        borderWidth: 0,
        pointRadius: 0,
        fill: false,
        tension: 0.1,
        order: 5
      });
    }

    return { labels, datasets };
  }, [curveData, showBands, bandType]);

  const options = useMemo(() => ({
    ...baseChartOptions,
    plugins: {
      ...baseChartOptions.plugins,
      title: createTitleConfig(title || 'Forward Returns Distribution'),
      legend: {
        display: true,
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 15,
          filter: (item) => !item.text.startsWith('_') && item.text !== 'Range' && item.text !== '±1σ Range'
        }
      },
      tooltip: {
        ...baseChartOptions.plugins.tooltip,
        callbacks: {
          title: (items) => items.length ? `Day ${items[0].label} after event` : '',
          label: (item) => {
            const value = item.raw;
            if (value === null || value === undefined) return null;
            const label = item.dataset.label;
            if (label.startsWith('_')) return null;
            return `${label}: ${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
          }
        },
        filter: (item) => !item.dataset.label.startsWith('_')
      },
      annotation: {
        annotations: {
          zeroLine: {
            type: 'line',
            yMin: 0,
            yMax: 0,
            borderColor: 'rgba(128, 128, 128, 0.6)',
            borderWidth: 1
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        title: createAxisTitle('Trading Days After Event'),
        ticks: { autoSkip: true, maxTicksLimit: 13, callback: (value) => value },
        grid: { display: false }
      },
      y: {
        display: true,
        title: createAxisTitle('Return (%)'),
        ticks: { callback: (value) => (value >= 0 ? '+' : '') + value.toFixed(1) + '%' },
        grid: { color: 'rgba(0, 0, 0, 0.05)' }
      }
    }
  }), [title]);

  if (!curveData?.avg?.length) {
    return <ChartEmptyState message="No forward returns data available" />;
  }

  const hasBandData = curveData.max && curveData.min && curveData.std;

  return (
    <div>
      {hasBandData && (
        <div className="d-flex justify-content-end gap-2 mb-2">
          <div className="btn-group btn-group-sm">
            <button
              type="button"
              className={`btn ${showBands ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => setShowBands(!showBands)}
            >
              {showBands ? 'Hide Bands' : 'Show Bands'}
            </button>
          </div>
          {showBands && (
            <div className="btn-group btn-group-sm">
              <button
                type="button"
                className={`btn ${bandType === 'minmax' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setBandType('minmax')}
              >
                Min/Max
              </button>
              <button
                type="button"
                className={`btn ${bandType === 'stddev' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setBandType('stddev')}
              >
                ±1 Std Dev
              </button>
            </div>
          )}
        </div>
      )}
      <div style={{ height: '300px' }}>
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
}

export default ForwardReturnsChart;
