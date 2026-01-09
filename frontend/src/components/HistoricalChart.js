import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import annotationPlugin from 'chartjs-plugin-annotation';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  annotationPlugin
);

function HistoricalChart({ data, eventMarkers, title }) {
  const chartData = useMemo(() => {
    if (!data || !data.dates || !data.prices) {
      return { labels: [], datasets: [] };
    }

    return {
      labels: data.dates,
      datasets: [
        {
          label: title,
          data: data.prices,
          borderColor: '#4a90d9',
          backgroundColor: 'rgba(74, 144, 217, 0.1)',
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: false,
          tension: 0
        }
      ]
    };
  }, [data, title]);

  const annotations = useMemo(() => {
    if (!eventMarkers || !data || !data.dates) return {};

    const markers = {};
    eventMarkers.forEach((markerDate, idx) => {
      const dateIndex = data.dates.indexOf(markerDate);
      if (dateIndex !== -1) {
        markers[`event_${idx}`] = {
          type: 'line',
          xMin: markerDate,
          xMax: markerDate,
          borderColor: 'rgba(220, 53, 69, 0.7)',
          borderWidth: 1,
          borderDash: [4, 4],
          label: {
            display: false
          }
        };
      }
    });
    return markers;
  }, [eventMarkers, data]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        display: true,
        position: 'top'
      },
      title: {
        display: true,
        text: `${title} Historical Price`,
        font: {
          size: 16,
          weight: 'bold'
        },
        color: '#333'
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        callbacks: {
          title: (items) => {
            if (items.length > 0) {
              const date = items[0].label;
              const isEvent = eventMarkers && eventMarkers.includes(date);
              return isEvent ? `${date} (EVENT)` : date;
            }
            return '';
          },
          label: (item) => {
            return `Price: $${item.raw.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          }
        }
      },
      annotation: {
        annotations: annotations
      },
      zoom: {
        zoom: {
          wheel: {
            enabled: true
          },
          pinch: {
            enabled: true
          },
          mode: 'xy'
        },
        pan: {
          enabled: true,
          mode: 'xy'
        }
      }
    },
    scales: {
      x: {
        type: 'category',
        display: true,
        title: {
          display: true,
          text: 'Date',
          font: {
            size: 12
          }
        },
        ticks: {
          maxRotation: 45,
          minRotation: 45,
          autoSkip: true,
          maxTicksLimit: 20
        },
        grid: {
          display: false
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: 'Price',
          font: {
            size: 12
          }
        },
        ticks: {
          callback: (value) => '$' + value.toLocaleString()
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        }
      }
    }
  }), [title, eventMarkers, annotations]);

  if (!data || !data.dates || data.dates.length === 0) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100">
        <p className="text-muted">No data available</p>
      </div>
    );
  }

  return <Line data={chartData} options={options} />;
}

export default HistoricalChart;
