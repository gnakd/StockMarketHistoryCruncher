import React, { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { baseChartOptions, createTitleConfig, createAxisTitle, ChartEmptyState } from '../utils/chartConfig';

function HistoricalChart({ data, eventMarkers, title }) {
  const chartData = useMemo(() => {
    if (!data?.dates?.length) return { labels: [], datasets: [] };

    return {
      labels: data.dates,
      datasets: [{
        label: title,
        data: data.prices,
        borderColor: '#4a90d9',
        backgroundColor: 'rgba(74, 144, 217, 0.1)',
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: false,
        tension: 0
      }]
    };
  }, [data, title]);

  const annotations = useMemo(() => {
    if (!eventMarkers?.length || !data?.dates) return {};

    return eventMarkers.reduce((markers, markerDate, idx) => {
      if (data.dates.includes(markerDate)) {
        markers[`event_${idx}`] = {
          type: 'line',
          xMin: markerDate,
          xMax: markerDate,
          borderColor: 'rgba(220, 53, 69, 0.7)',
          borderWidth: 1,
          borderDash: [4, 4],
          label: { display: false }
        };
      }
      return markers;
    }, {});
  }, [eventMarkers, data]);

  const options = useMemo(() => ({
    ...baseChartOptions,
    plugins: {
      ...baseChartOptions.plugins,
      title: createTitleConfig(`${title} Historical Price`),
      tooltip: {
        ...baseChartOptions.plugins.tooltip,
        callbacks: {
          title: (items) => {
            if (!items.length) return '';
            const date = items[0].label;
            return eventMarkers?.includes(date) ? `${date} (EVENT)` : date;
          },
          label: (item) => `Price: $${item.raw.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        }
      },
      annotation: { annotations },
      zoom: {
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' },
        pan: { enabled: true, mode: 'xy' }
      }
    },
    scales: {
      x: {
        type: 'category',
        display: true,
        title: createAxisTitle('Date'),
        ticks: { maxRotation: 45, minRotation: 45, autoSkip: true, maxTicksLimit: 20 },
        grid: { display: false }
      },
      y: {
        display: true,
        title: createAxisTitle('Price'),
        ticks: { callback: (value) => '$' + value.toLocaleString() },
        grid: { color: 'rgba(0, 0, 0, 0.05)' }
      }
    }
  }), [title, eventMarkers, annotations]);

  if (!data?.dates?.length) {
    return <ChartEmptyState message="No data available" />;
  }

  return <Line data={chartData} options={options} />;
}

export default HistoricalChart;
