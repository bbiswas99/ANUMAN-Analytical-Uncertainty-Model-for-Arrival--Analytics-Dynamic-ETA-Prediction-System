import { useState } from 'react';
import { fetchPrediction } from '../utils/apiClient';
import styles from './WhatIfForm.module.css';

const DELAY_MIN = -60, DELAY_MAX = 600;
const OCC_MIN = 0,   OCC_MAX = 200;  // Matches server-side apply_what_if_overrides() range

/**
 * WhatIfForm — per spec 06 §2.
 * Allowlist: reported_delay_min, section_occupancy_count.
 * Client-side range validation mirrors server-side apply_what_if_overrides() limits.
 */
export function WhatIfForm({ trainNo, onResult }) {
  const [delayVal, setDelayVal]   = useState(0);
  const [occVal, setOccVal]       = useState(0);
  const [riskVal, setRiskVal]     = useState(0);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  function validate() {
    const errs = {};
    if (delayVal < DELAY_MIN || delayVal > DELAY_MAX)
      errs.delay = `Must be between ${DELAY_MIN} and ${DELAY_MAX} minutes`;
    if (occVal < OCC_MIN || occVal > OCC_MAX)
      errs.occ = `Must be between ${OCC_MIN} and ${OCC_MAX}`;
    if (riskVal < 0 || riskVal > 100)
      errs.risk = 'Precedence risk must be between 0% and 100%';
    return errs;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setLoading(true);
    setError(null);
    try {
      const payload = {
        reported_delay_min: Number(delayVal),
        section_occupancy_count: Number(occVal),
      };
      if (riskVal > 0) {
        payload.precedence_risk_score_next_section = Number((riskVal / 100).toFixed(2));
      }
      const result = await fetchPrediction(trainNo, payload);
      onResult(result);
    } catch (err) {
      if (err.status === 422) {
        setFieldErrors({ server: err.message });
      } else {
        setError(err.message || 'Could not compute scenario — try again');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`${styles.panel} card card-padded`}>
      <p className="section-label">What-If Scenario</p>
      <p className={styles.subtitle}>
        Override hypothetical values and see the recomputed ETA instantly.
      </p>

      {!trainNo && (
        <div className="alert-inline alert-info" style={{ marginTop: 8 }}>
          <span>ℹ️</span>
          <span>Select a train first to run a What-If scenario.</span>
        </div>
      )}

      <form className={styles.form} onSubmit={handleSubmit}>
        {/* Delay input */}
        <div className={styles.field}>
          <label className={styles.label} htmlFor="whatif-delay">
            Assume current delay (minutes)
          </label>
          <div className={styles.inputRow}>
            <input
              id="whatif-delay"
              type="range"
              min={DELAY_MIN} max={DELAY_MAX} step={1}
              value={delayVal}
              onChange={e => setDelayVal(Number(e.target.value))}
              className={styles.range}
              disabled={!trainNo || loading}
            />
            <span className={`${styles.rangeValue} ${delayVal > 0 ? styles.late : delayVal < 0 ? styles.early : ''}`}>
              {delayVal > 0 ? `+${delayVal}` : delayVal} min
            </span>
          </div>
          <div className={styles.rangeTicks}>
            <span>{DELAY_MIN}</span>
            <span>0</span>
            <span>{DELAY_MAX}</span>
          </div>
          {fieldErrors.delay && <p className={styles.fieldError}>{fieldErrors.delay}</p>}
        </div>

        {/* Congestion input */}
        <div className={styles.field}>
          <label className={styles.label} htmlFor="whatif-occ">
            Assume congestion level (trains in section ±30 min)
          </label>
          <div className={styles.inputRow}>
            <input
              id="whatif-occ"
              type="range"
              min={OCC_MIN} max={OCC_MAX} step={1}
              value={occVal}
              onChange={e => setOccVal(Number(e.target.value))}
              className={styles.range}
              disabled={!trainNo || loading}
            />
            <span className={styles.rangeValue}>{occVal} trains</span>
          </div>
          <div className={styles.rangeTicks}>
            <span>{OCC_MIN}</span>
            <span>{OCC_MAX}</span>
          </div>
          {fieldErrors.occ && <p className={styles.fieldError}>{fieldErrors.occ}</p>}
        </div>

        {/* Precedence conflict risk input */}
        <div className={styles.field}>
          <label className={styles.label} htmlFor="whatif-risk">
            Simulate precedence conflict risk (Model B)
          </label>
          <div className={styles.inputRow}>
            <input
              id="whatif-risk"
              type="range"
              min={0} max={100} step={5}
              value={riskVal}
              onChange={e => setRiskVal(Number(e.target.value))}
              className={styles.range}
              disabled={!trainNo || loading}
            />
            <span className={`${styles.rangeValue} ${riskVal > 0 ? styles.late : ''}`}>
              {riskVal}%
            </span>
          </div>
          <div className={styles.rangeTicks}>
            <span>0% (Clear)</span>
            <span>50%</span>
            <span>100% (High Risk)</span>
          </div>
          {fieldErrors.risk && <p className={styles.fieldError}>{fieldErrors.risk}</p>}
        </div>

        {fieldErrors.server && (
          <div className="alert-inline alert-error">
            <span>⚠️</span>
            <span>{fieldErrors.server}</span>
          </div>
        )}

        {error && (
          <div className="alert-inline alert-warn">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          className={`btn btn-primary w-full`}
          disabled={!trainNo || loading}
          id="whatif-submit"
        >
          {loading ? (
            <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Computing…</>
          ) : (
            '⚡ Compute Scenario'
          )}
        </button>
      </form>
    </div>
  );
}
