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
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

function ForwardReturnsChart({ data, title }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return { labels: [], datasets: [] };
    }

    // Create labels for trading days (0 to length-1)
    const labels = data.map((_, idx) => idx);

    return {
      labels: labels,
      datasets: [
        {
          label: 'Average Return (%)',
          data: data,
          borderColor: '#28a745',
          backgroundColor: 'rgba(40, 167, 69, 0.2)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
          tension: 0.1
        }
      ]
    };
  }, [data]);

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
        text: title || 'Average Forward Returns',
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
              const day = items[0].label;
              return `Day ${day} after event`;
            }
            return '';
          },
          label: (item) => {
            const value = item.raw;
            if (value === null || value === undefined) return 'N/A';
            return `Return: ${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: 'Trading Days After Event',
          font: {
            size: 12
          }
        },
        ticks: {
          autoSkip: true,
          maxTicksLimit: 13,
          callback: (value) => value
        },
        grid: {
          display: false
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: 'Return (%)',
          font: {
            size: 12
          }
        },
        ticks: {
          callback: (value) => (value >= 0 ? '+' : '') + value.toFixed(1) + '%'
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        }
      }
    }
  }), [title]);

  if (!data || data.length === 0) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100">
        <p className="text-muted">No forward returns data available</p>
      </div>
    );
  }

  return <Line data={chartData} options={options} />;
}

export default ForwardReturnsChart;
