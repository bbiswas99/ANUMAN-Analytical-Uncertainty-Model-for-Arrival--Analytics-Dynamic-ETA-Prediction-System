import { usePrediction } from '../hooks/usePrediction';
import { ConfidenceBar } from './ConfidenceBar';
import { formatTime, formatDelay, modelBadgeClass, modelLabel } from '../utils/formatETA';
import styles from './ETACard.module.css';

/**
 * ETACard — shows ETA, confidence band, delay status, and model used.
 * Per spec 06 §2: all three error states implemented.
 */
export function ETACard({ trainNo, whatIf = null, compact = false }) {
  const { data, loading, error } = usePrediction(trainNo, whatIf);

  if (!trainNo) return null;

  // Loading state
  if (loading) {
    return (
      <div className={`${styles.card} card card-padded fade-in`}>
        <div className={styles.skeletonHeader}>
          <div className="skeleton" style={{ width: 120, height: 14 }} />
          <div className="skeleton" style={{ width: 60, height: 20 }} />
        </div>
        <div className="skeleton" style={{ height: 64, marginTop: 16 }} />
        <div className={styles.skeletonRow}>
          <div className="skeleton" style={{ width: '45%', height: 12 }} />
          <div className="skeleton" style={{ width: '30%', height: 12 }} />
        </div>
      </div>
    );
  }

  // Error / unrecoverable state
  if (error) {
    return (
      <div className={`${styles.card} card card-padded fade-in`}>
        <div className="alert-inline alert-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const delay = data.current_delay_min ?? 0;
  const statusClass = delay <= 0 ? 'badge-on-time' : delay <= 15 ? 'badge-slight' : 'badge-late';
  const statusLabel = delay <= 0 ? '🟢 On Time' : delay <= 15 ? '🟡 Slight Delay' : '🔴 Delayed';

  return (
    <div className={`${styles.card} card card-padded fade-in`}>
      {/* Fallback indicator */}
      {data._isFallback && (
        <div className={`badge badge-demo ${styles.demoTag}`}>⚡ Demo data</div>
      )}

      {/* Header row */}
      <div className={styles.header}>
        <div className={styles.trainInfo}>
          <span className={styles.trainNo}>#{data.train_no}</span>
          <span className={styles.trainName}>{data.train_name}</span>
        </div>
        <span className={`badge ${statusClass}`}>{statusLabel}</span>
      </div>

      {/* Big ETA display */}
      <div className={styles.etaBlock}>
        <span className={styles.etaLabel}>Predicted Arrival</span>
        <span className={styles.etaTime}>{formatTime(data.eta)}</span>
        <span className={styles.delayText}>{formatDelay(delay)}</span>
      </div>

      {/* Confidence interval bar */}
      {!compact && data.confidence_interval_lower && (
        <div className={styles.section}>
          <p className="section-label">Prediction Window</p>
          <ConfidenceBar
            eta={data.eta}
            lower={data.confidence_interval_lower}
            upper={data.confidence_interval_upper}
            baselineEta={data.baseline_eta}
          />
        </div>
      )}

      <div className="divider" />

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.footerItem}>
          <span className={styles.footerLabel}>Last at</span>
          <span className={styles.footerValue}>{data.last_station_name || '--'}</span>
        </div>
        <div className={styles.footerItem}>
          <span className={styles.footerLabel}>Confidence</span>
          <span className={styles.footerValue}>
            {data.data_confidence_score != null
              ? `${Math.round(data.data_confidence_score * 100)}%`
              : '--'}
          </span>
        </div>
        <span className={`badge ${modelBadgeClass(data.model_used)}`}>
          {modelLabel(data.model_used)}
        </span>
      </div>
    </div>
  );
}
