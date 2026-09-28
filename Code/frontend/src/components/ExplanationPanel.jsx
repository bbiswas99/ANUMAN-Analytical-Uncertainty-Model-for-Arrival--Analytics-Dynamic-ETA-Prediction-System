import { useExplanation } from '../hooks/useExplanation';
import styles from './ExplanationPanel.module.css';

/**
 * ExplanationPanel — shows top_delay_factors as bullet points.
 * Per spec 06 §2: renders however many are present (not padded to 3).
 */
export function ExplanationPanel({ trainNo }) {
  const { data, loading, error } = useExplanation(trainNo);

  if (!trainNo) return null;

  if (loading) {
    return (
      <div className={`${styles.panel} card card-padded fade-in`}>
        <p className="section-label">Delay Factors</p>
        <p className={styles.loading}>Loading explanation…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${styles.panel} card card-padded fade-in`}>
        <p className="section-label">Delay Factors</p>
        <p className={styles.unavailable}>Detailed reasoning unavailable right now</p>
      </div>
    );
  }

  if (!data) return null;

  const factors = data.top_delay_factors || [];

  return (
    <div className={`${styles.panel} card card-padded fade-in`}>
      {data._isFallback && (
        <span className={`badge badge-demo ${styles.demoTag}`}>Demo</span>
      )}
      <p className="section-label">Likely Delay Factors</p>
      {factors.length === 0 ? (
        <p className={styles.unavailable}>No significant delay factors identified</p>
      ) : (
        <ul className={styles.list}>
          {factors.map((factor, i) => (
            <li key={i} className={styles.item}>
              <span className={styles.bullet} style={{ animationDelay: `${i * 80}ms` }}>
                {i === 0 ? '🔺' : i === 1 ? '📍' : '📊'}
              </span>
              <span className={styles.text}>{factor}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
