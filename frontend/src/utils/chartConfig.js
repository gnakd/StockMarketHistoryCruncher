import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

// Register all ChartJS components once
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler,
  annotationPlugin
);

// Shared base options for all charts
export const baseChartOptions = {
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
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleColor: '#fff',
      bodyColor: '#fff'
    }
  }
};

// Shared title configuration
export const createTitleConfig = (text) => ({
  display: true,
  text,
  font: { size: 16, weight: 'bold' },
  color: '#333'
});

// Shared axis title configuration
export const createAxisTitle = (text) => ({
  display: true,
  text,
  font: { size: 12 }
});

// Empty state component
export const ChartEmptyState = ({ message = 'No data available' }) => (
  <div className="d-flex align-items-center justify-content-center h-100">
    <p className="text-muted">{message}</p>
  </div>
);

export { ChartJS };
