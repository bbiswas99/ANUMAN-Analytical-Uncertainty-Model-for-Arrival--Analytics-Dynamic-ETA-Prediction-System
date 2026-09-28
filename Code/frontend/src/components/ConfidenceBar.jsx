import styles from './ConfidenceBar.module.css';
import { formatTime } from '../utils/formatETA';

/**
 * ConfidenceBar — visual shaded confidence interval strip.
 * Shows lower bound → point ETA → upper bound as a timeline.
 */
export function ConfidenceBar({ eta, lower, upper, baselineEta }) {
  if (!eta) return null;

  const etaMs    = new Date(eta).getTime();
  const lowerMs  = new Date(lower).getTime();
  const upperMs  = new Date(upper).getTime();
  const rangeMs  = upperMs - lowerMs || 1;

  const etaPct   = ((etaMs - lowerMs) / rangeMs) * 100;
  const widthMin = Math.round((upperMs - lowerMs) / 60000);

  return (
    <div className={styles.container}>
      <div className={styles.labels}>
        <span className={styles.bound}>{formatTime(lower)}</span>
        <span className={styles.rangeLabel}>±{Math.ceil(widthMin / 2)} min window</span>
        <span className={styles.bound}>{formatTime(upper)}</span>
      </div>
      <div className={styles.track}>
        <div className={styles.band} />
        <div className={styles.marker} style={{ left: `${Math.min(95, Math.max(5, etaPct))}%` }}>
          <div className={styles.markerDot} />
          <div className={styles.markerLabel}>{formatTime(eta)}</div>
        </div>
      </div>
      {baselineEta && (
        <div className={styles.baseline}>
          <span className={styles.baselineDot} />
          <span>Baseline: {formatTime(baselineEta)}</span>
        </div>
      )}
    </div>
  );
}
