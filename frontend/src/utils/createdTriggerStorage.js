import axios from 'axios';

const STORAGE_KEY = 'created_triggers_cache';

/**
 * Load created triggers from backend, using localStorage as cache
 */
export async function loadCreatedTriggers() {
  try {
    const response = await axios.get('/api/created_triggers');
    if (response.data.status === 'ok') {
      const triggers = response.data.triggers || [];
      // Update localStorage cache
      localStorage.setItem(STORAGE_KEY, JSON.stringify(triggers));
      return triggers;
    }
    // Fall back to localStorage cache on error
    return getLocalCache();
  } catch (error) {
    console.error('Failed to load created triggers:', error);
    // Fall back to localStorage cache
    return getLocalCache();
  }
}

/**
 * Save a new trigger to backend and update localStorage cache
 */
export async function saveCreatedTrigger(trigger) {
  const response = await axios.post('/api/created_triggers', trigger);
  if (response.data.status === 'ok') {
    const savedTrigger = response.data.trigger;
    // Update localStorage cache
    const cache = getLocalCache();
    cache.push(savedTrigger);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
    return savedTrigger;
  }
  throw new Error(response.data.error || 'Failed to save trigger');
}

/**
 * Delete a trigger from backend and update localStorage cache
 */
export async function deleteCreatedTrigger(triggerId) {
  const response = await axios.delete(`/api/created_triggers/${triggerId}`);
  if (response.data.status === 'ok') {
    // Update localStorage cache
    const cache = getLocalCache();
    const filtered = cache.filter(t => t.id !== triggerId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    return true;
  }
  throw new Error(response.data.error || 'Failed to delete trigger');
}

/**
 * Update a trigger (e.g., rename)
 */
export async function updateCreatedTrigger(triggerId, updates) {
  const response = await axios.put(`/api/created_triggers/${triggerId}`, updates);
  if (response.data.status === 'ok') {
    const updatedTrigger = response.data.trigger;
    // Update localStorage cache
    const cache = getLocalCache();
    const index = cache.findIndex(t => t.id === triggerId);
    if (index !== -1) {
      cache[index] = updatedTrigger;
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
    return updatedTrigger;
  }
  throw new Error(response.data.error || 'Failed to update trigger');
}

/**
 * Get triggers from localStorage cache
 */
function getLocalCache() {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    return cached ? JSON.parse(cached) : [];
  } catch {
    return [];
  }
}

/**
 * Calculate score for a trigger based on metrics
 * Uses similar formula to discovered triggers
 *
 * @param {Object} metrics
 * @param {number} metrics.avg_return - Average return as decimal (0.12 = 12%)
 * @param {number} metrics.avg_win_rate - Win rate as decimal (0.75 = 75%)
 * @param {number} metrics.event_count - Number of events
 * @param {number} metrics.max_drawdown - Max drawdown as percentage (-11.5 = -11.5%)
 */
export function calculateScore(metrics) {
  const {
    avg_return = 0,
    avg_win_rate = 0,
    event_count = 0,
    max_drawdown = 0
  } = metrics;

  // Convert decimal return to percentage for calculation (0.12 -> 12)
  const returnPct = avg_return * 100;

  // Return component (30%): normalize return to 0-100 range
  // Range: -10% to +30% maps to 0-100
  const returnScore = Math.min(Math.max((returnPct + 10) / 40 * 100, 0), 100);

  // Win rate component (30%): convert decimal to 0-100 scale
  const winRateScore = avg_win_rate * 100;

  // Sharpe-like component (25%): return relative to drawdown
  const drawdownAbs = Math.abs(max_drawdown) || 1;
  const sharpeScore = Math.min(Math.max((returnPct / drawdownAbs + 1) * 50, 0), 100);

  // Significance component (15%): more events = more reliable
  const significanceScore = Math.min(event_count / 50 * 100, 100);

  // Weighted average
  const score = (
    returnScore * 0.30 +
    winRateScore * 0.30 +
    sharpeScore * 0.25 +
    significanceScore * 0.15
  );

  return Math.round(score * 10) / 10;
}

/**
 * Derive signal direction from condition type
 */
export function deriveSignal(conditionType) {
  const bullishTypes = ['rsi_above', 'rsi_below', 'momentum_above', 'momentum_below',
                        'ma_crossover', 'single_ath', 'dual_ath', 'vix_above',
                        'putcall_above', 'sp500_pct_above_200ma', 'feargreed_below'];
  const bearishTypes = ['ma_crossunder', 'vix_below', 'putcall_below', 'feargreed_above'];

  if (bullishTypes.includes(conditionType)) return 'bullish';
  if (bearishTypes.includes(conditionType)) return 'bearish';
  return null;
}
