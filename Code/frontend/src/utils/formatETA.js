/**
 * formatETA.js — Date/time formatting helpers for the dashboard.
 */

/**
 * Format an ISO datetime string to a human-readable time (HH:MM).
 * Returns '--:--' if the input is null/invalid.
 */
export function formatTime(isoString) {
  if (!isoString) return '--:--';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '--:--';
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '--:--';
  }
}

/**
 * Format an ISO datetime string to "14 Sep, 08:35".
 */
export function formatDateTime(isoString) {
  if (!isoString) return '--';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '--';
    return d.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch {
    return '--';
  }
}

/**
 * Format a delay value in minutes to a human-readable string.
 * e.g. 0 → "On Time", 14 → "+14 min late", -3 → "3 min early"
 */
export function formatDelay(minutes) {
  if (minutes === null || minutes === undefined) return '--';
  const m = Math.round(minutes);
  if (m === 0) return 'On Time';
  if (m > 0) return `+${m} min late`;
  return `${Math.abs(m)} min early`;
}

/**
 * Return a CSS class name for delay severity.
 */
export function delayClass(minutes) {
  if (minutes === null || minutes === undefined) return '';
  if (minutes <= 0)  return 'on-time';
  if (minutes <= 15) return 'slight';
  return 'late';
}

/**
 * Return a badge class for model_used field.
 */
export function modelBadgeClass(modelUsed) {
  if (!modelUsed) return 'badge-baseline';
  if (modelUsed.startsWith('model_b')) return 'badge-model-b';
  if (modelUsed.startsWith('model')) return 'badge-model-a';
  return 'badge-baseline';
}

/**
 * Return a human label for model_used field.
 */
export function modelLabel(modelUsed) {
  if (!modelUsed) return 'Baseline estimate';
  if (modelUsed === 'model_b') return 'Model B (Precedence-Aware)';
  if (modelUsed === 'model_b_whatif') return 'Model B What-If';
  if (modelUsed === 'model_a') return 'Model A (Section Delay)';
  if (modelUsed === 'model_a_static') return 'Model A (static data)';
  if (modelUsed === 'model_a_whatif') return 'Model A What-If';
  if (modelUsed === 'baseline') return 'Baseline estimate';
  return 'Baseline estimate';
}

/**
 * Parse a scheduled time string "HH:MM" into a Date object on today's date.
 * Returns null if unparseable.
 */
export function parseScheduledTime(timeStr) {
  if (!timeStr || timeStr === '--:--') return null;
  const [h, m] = timeStr.split(':').map(Number);
  if (isNaN(h) || isNaN(m)) return null;
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d;
}
