import { useState, useEffect } from 'react';
import { TrainSelector } from '../components/TrainSelector';
import { WhatIfForm } from '../components/WhatIfForm';
import { TrackMap } from '../components/TrackMap';
import { LiveReplayControls } from '../components/LiveReplayControls';
import { usePrediction } from '../hooks/usePrediction';
import { fetchModelBStatus, setModelBStatus } from '../utils/apiClient';
import { modelBadgeClass, modelLabel } from '../utils/formatETA';
import styles from './OpsView.module.css';

const DEMO_DATE = '2025-11-15';

/**
 * OpsView — Control Room tab.
 * Hosts Live Journey Replay, What-If scenario dispatch, Model B precedence switches, and track animation.
 */
export function OpsView() {
  const [trainNo, setTrainNo]         = useState(null);
  const [controlMode, setControlMode] = useState('replay'); // 'replay' | 'whatif'
  const [whatIfResult, setResult]     = useState(null);
  const [modelBEnabled, setModelBEnabled] = useState(false);
  const [updatingSwitch, setUpdatingSwitch] = useState(false);

  // Live Replay state
  const [replayPos, setReplayPos]     = useState(null);
  const [replayStop, setReplayStop]   = useState(null);
  const [replayDate, setReplayDate]   = useState(DEMO_DATE);

  // Sync initial switch status from backend on load
  useEffect(() => {
    fetchModelBStatus()
      .then(cfg => {
        if (cfg && typeof cfg.model_b_enabled === 'boolean') {
          setModelBEnabled(cfg.model_b_enabled);
        }
      })
      .catch(() => {});
  }, []);

  const { data: liveData } = usePrediction(trainNo, null, modelBEnabled);

  const displayData = whatIfResult || liveData;

  const handleToggleModelB = async () => {
    const nextVal = !modelBEnabled;
    setModelBEnabled(nextVal);
    setResult(null); // Reset what-if so prediction refreshes with new model mode
    setUpdatingSwitch(true);
    try {
      await setModelBStatus(nextVal);
    } catch (err) {
      console.warn('Backend sync failed, client override active:', err);
    } finally {
      setUpdatingSwitch(false);
    }
  };

  return (
    <div className={styles.layout}>
      {/* ── Left panel ── */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <span className={styles.opsBadge}>🎛️ Control Room</span>
          <p className={styles.opsSubtitle}>Dispatch, live journey replay & precedence operations</p>
        </div>

        {/* ── Control Room Mode Switcher ── */}
        <div className={styles.controlModeTabs}>
          <button
            type="button"
            className={`${styles.controlModeTab} ${controlMode === 'replay' ? styles.controlModeTabActive : ''}`}
            onClick={() => { setControlMode('replay'); setReplayPos(null); setReplayStop(null); }}
          >
            🎬 Live Journey Replay
          </button>
          <button
            type="button"
            className={`${styles.controlModeTab} ${controlMode === 'whatif' ? styles.controlModeTabActive : ''}`}
            onClick={() => setControlMode('whatif')}
          >
            🧪 What-If & Model B
          </button>
        </div>

        <TrainSelector
          onSelect={t => {
            setTrainNo(t);
            setResult(null);
            setReplayPos(null);
            setReplayStop(null);
          }}
          selectedTrainNo={trainNo}
          inlineList
        />

        {/* ── REPLAY MODE ── */}
        {controlMode === 'replay' && (
          <>
            <div className={styles.datePicker}>
              <p className="section-label">Journey Date</p>
              <input
                type="date"
                className="input"
                value={replayDate}
                max={new Date().toISOString().split('T')[0]}
                onChange={e => setReplayDate(e.target.value)}
              />
            </div>

            <LiveReplayControls
              trainNo={trainNo}
              date={replayDate}
              onPositionChange={setReplayPos}
              onStopChange={setReplayStop}
            />
          </>
        )}

        {/* ── WHAT-IF & MODEL B MODE ── */}
        {controlMode === 'whatif' && (
          <>
            {/* ── Model B Operational Switch ── */}
            <div className={`card card-padded ${styles.modelBSwitchCard} ${modelBEnabled ? styles.modelBSwitchCardActive : ''}`}>
              <div className={styles.switchTopRow}>
                <div className={styles.switchTitleGroup}>
                  <span className={styles.switchTitle}>Model B Precedence</span>
                  <span className={`badge ${modelBEnabled ? 'badge-precedence' : 'badge-model-a'}`}>
                    {modelBEnabled ? '⚡ Active (ON)' : '🛡️ Standard (OFF)'}
                  </span>
                </div>
                <button
                  type="button"
                  id="model-b-toggle-btn"
                  className={`${styles.toggleButton} ${modelBEnabled ? styles.toggleActive : ''}`}
                  onClick={handleToggleModelB}
                  disabled={updatingSwitch}
                  title={modelBEnabled ? "Switch Model B OFF (revert to Model A)" : "Switch Model B ON (enable precedence adjustments)"}
                  aria-label="Toggle Model B Precedence Mode"
                >
                  <span className={styles.toggleThumb} />
                </button>
              </div>
              <p className={styles.switchDescription}>
                {modelBEnabled
                  ? "Phase 2 active: applying priority conflict corrections from inferred overtakes."
                  : "Phase 2 disabled pending live scraped dataset. Running Model A congestion baseline."}
              </p>
            </div>

            <WhatIfForm trainNo={trainNo} onResult={setResult} />
          </>
        )}

        {/* Raw model details panel */}
        {displayData && (
          <div className={`card card-padded ${styles.modelDetails} fade-in`}>
            <p className="section-label">Model Details</p>
            <table className={styles.detailTable}>
              <tbody>
                <DetailRow label="Model used"        value={displayData.model_used || '--'} mono />
                <DetailRow label="Model B Switch"    value={modelBEnabled ? "ON (Precedence Active)" : "OFF (Model A Baseline)"} highlight={modelBEnabled} />
                <DetailRow label="Data confidence"   value={displayData.data_confidence_score != null ? `${Math.round(displayData.data_confidence_score * 100)}%` : '--'} />
                <DetailRow label="Baseline ETA"      value={formatRawTime(displayData.baseline_eta)} />
                <DetailRow label="ML ETA"            value={formatRawTime(displayData.eta)} />
                <DetailRow label="Current delay"     value={displayData.current_delay_min != null ? `${displayData.current_delay_min} min` : '--'} />
                <DetailRow label="Precedence risk"   value={displayData.precedence_risk_score != null ? `${Math.round(displayData.precedence_risk_score * 100)}%` : '--'} />
                <DetailRow label="Active conflicts"  value={displayData.precedence_conflicts_count ?? 0} />
                <DetailRow label="Last station"      value={displayData.last_station_code || '--'} mono />
                <DetailRow label="Train type"        value={displayData.type_code || '--'} mono />
                {whatIfResult && <DetailRow label="Scenario" value="What-If override active" highlight />}
              </tbody>
            </table>

            {/* Confidence gauge */}
            {displayData.data_confidence_score != null && (
              <div className={styles.confidenceGauge}>
                <div className={styles.gaugeLabel}>
                  <span className="text-sm text-muted">Data Confidence</span>
                  <span className={`text-sm font-semibold ${getConfidenceClass(displayData.data_confidence_score)}`}>
                    {getConfidenceLabel(displayData.data_confidence_score)}
                  </span>
                </div>
                <div className={styles.gaugeTrack}>
                  <div
                    className={styles.gaugeFill}
                    style={{
                      width: `${displayData.data_confidence_score * 100}%`,
                      background: getConfidenceColor(displayData.data_confidence_score),
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Precedence Conflicts Card */}
        {displayData && displayData.precedence_conflicts && displayData.precedence_conflicts.length > 0 && (
          <div className={`card card-padded ${styles.conflictCard} fade-in`}>
            <div className={styles.conflictHeader}>
              <span className="section-label" style={{ color: '#b91c1c' }}>⚠️ Precedence Conflicts</span>
              <span className="badge badge-precedence">{displayData.precedence_conflicts.length} active</span>
            </div>

            {!modelBEnabled && (
              <div className={styles.precedenceAdvisoryCard}>
                <div className={styles.advisoryHeader}>
                  <span className={styles.advisoryIcon}>🛡️</span>
                  <span className={styles.advisoryTitle}>Advisory Only (Model B OFF)</span>
                </div>
                <p className={styles.advisoryText}>
                  Priority crossings detected along route. Predicted ETA is calculated using <strong>Model A standard</strong>. Flip the switch above to apply Model B precedence adjustments.
                </p>
                <button
                  type="button"
                  className={styles.advisoryActionBtn}
                  onClick={handleToggleModelB}
                >
                  Enable Model B now
                </button>
              </div>
            )}

            <div className={styles.conflictList}>
              {displayData.precedence_conflicts.map((c, idx) => (
                <div key={idx} className={styles.conflictItem}>
                  <div className={styles.conflictTop}>
                    <span className={styles.conflictSection}>Section {c.section_id}</span>
                    <span className={`badge ${c.role === 'delayed' ? 'badge-late' : 'badge-on-time'}`}>
                      {c.role === 'delayed' ? 'Held Behind' : 'Priority Pass'}
                    </span>
                  </div>
                  <p className={styles.conflictDesc}>{c.description}</p>
                  <div className={styles.conflictMeta}>
                    <span>Confidence: {Math.round(c.confidence_score * 100)}%</span>
                    {c.estimated_hold_min > 0 && <span>Est. Hold: +{c.estimated_hold_min}m</span>}
                    <span>Observed: {c.total_crossings_observed}x</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* ── Right: slim ETA strip + map ── */}
      <main className={styles.main}>
        {displayData && (
          <div className={`${styles.etaStrip} fade-in`}>
            <div className={styles.stripLeft}>
              <span className={styles.stripTrainNo}>#{displayData.train_no}</span>
              <span className={styles.stripTrainName}>{displayData.train_name}</span>
            </div>
            <div className={styles.stripDivider} />
            <div className={styles.stripItem}>
              <span className={styles.stripLabel}>ETA</span>
              <span className={styles.stripValue}>{formatRawTime(displayData.eta)}</span>
            </div>
            <div className={styles.stripDivider} />
            <div className={styles.stripItem}>
              <span className={styles.stripLabel}>Delay</span>
              <span className={`${styles.stripValue} ${displayData.current_delay_min > 15 ? styles.late : displayData.current_delay_min > 0 ? styles.slight : styles.onTime}`}>
                {displayData.current_delay_min > 0 ? `+${displayData.current_delay_min} min` : displayData.current_delay_min < 0 ? `${displayData.current_delay_min} min` : 'On Time'}
              </span>
            </div>
            <div className={styles.stripDivider} />
            <div className={styles.stripItem}>
              <span className={styles.stripLabel}>Confidence</span>
              <span className={styles.stripValue}>
                {displayData.data_confidence_score != null ? `${Math.round(displayData.data_confidence_score * 100)}%` : '--'}
              </span>
            </div>
            <div className={styles.stripDivider} />
            <div className={styles.stripItem}>
              <span className={styles.stripLabel}>Baseline</span>
              <span className={styles.stripValue}>{formatRawTime(displayData.baseline_eta)}</span>
            </div>
            <div className={styles.stripSpacer} />
            <span className={`badge ${modelBadgeClass(displayData.model_used)}`}>
              {modelLabel(displayData.model_used)}
            </span>
            <span
              className={`badge ${modelBEnabled ? 'badge-precedence' : 'badge-model-a'}`}
              title={modelBEnabled ? "Model B precedence adjustments active" : "Model B switched OFF (using Model A)"}
            >
              {modelBEnabled ? '⚡ Model B: ON' : '🛡️ Model B: OFF'}
            </span>
            {displayData.precedence_active && (
              <span className="badge badge-precedence" title="Precedence conflict risk detected">
                ⚠️ Precedence Risk ({Math.round((displayData.precedence_risk_score || 0) * 100)}%)
              </span>
            )}
            {displayData.live_data_used && (
              <span className="badge badge-model-a" title="Using live scraper data">📡 Live</span>
            )}
            {whatIfResult && (
              <span className="badge badge-demo">⚡ What-If active</span>
            )}
          </div>
        )}

        {/* Side-by-side What-If comparison card */}
        {whatIfResult && liveData && (
          <div className={`${styles.whatIfCompareCard} fade-in`}>
            <div className={styles.compareHeader}>
              <span className={styles.compareTitle}>⚡ Scenario Impact Analysis</span>
              <button
                type="button"
                className={styles.resetBtn}
                onClick={() => setResult(null)}
                title="Reset to live prediction"
              >
                ✕ Reset to Live
              </button>
            </div>
            <div className={styles.compareGrid}>
              <div className={styles.compareCol}>
                <span className={styles.compareLabel}>Live Baseline ETA</span>
                <span className={styles.compareVal}>{formatRawTime(liveData.eta)}</span>
                <span className={styles.compareSub}>
                  {liveData.current_delay_min > 0 ? `+${liveData.current_delay_min} min delay` : 'On Time'}
                </span>
              </div>
              <div className={styles.compareArrow}>➔</div>
              <div className={styles.compareCol}>
                <span className={styles.compareLabel}>What-If Recomputed ETA</span>
                <span className={styles.compareVal}>{formatRawTime(whatIfResult.eta)}</span>
                <span className={styles.compareSub}>
                  {whatIfResult.current_delay_min > 0 ? `+${whatIfResult.current_delay_min} min delay` : 'On Time'}
                </span>
              </div>
              <div className={styles.compareDelta}>
                <span className={styles.compareLabel}>Delay Delta</span>
                {(() => {
                  const delta = Math.round((whatIfResult.current_delay_min ?? 0) - (liveData.current_delay_min ?? 0));
                  return (
                    <span className={`${styles.compareDeltaVal} ${delta > 0 ? styles.late : delta < 0 ? styles.onTime : ''}`}>
                      {delta > 0 ? `+${delta} min` : delta < 0 ? `${delta} min` : '0 min'}
                    </span>
                  );
                })()}
              </div>
            </div>
          </div>
        )}

        {!displayData && trainNo && (
          <div className={styles.etaStripEmpty}>
            <div className="spinner" />
            <span className="text-sm text-muted">Loading train data…</span>
          </div>
        )}
        {!trainNo && (
          <div className={styles.etaStripEmpty}>
            <span className="text-sm text-muted">Select a train to see live data</span>
          </div>
        )}
        <div className={styles.mapArea}>
          <TrackMap
            trainNo={trainNo}
            trainPosition={controlMode === 'replay' ? replayPos : null}
            activeStop={controlMode === 'replay' ? replayStop : displayData?.last_station_code}
            delaySpikeMarkers={[]}
          />
        </div>
      </main>
    </div>
  );
}

function DetailRow({ label, value, mono, highlight }) {
  return (
    <tr>
      <td style={{ color: 'var(--clr-text-3)', fontSize: 12, paddingBottom: 8, paddingRight: 16, whiteSpace: 'nowrap' }}>{label}</td>
      <td style={{
        fontSize: 13, fontWeight: 600,
        fontFamily: mono ? 'monospace' : 'inherit',
        color: highlight ? 'var(--clr-accent)' : 'var(--clr-text)',
      }}>{value}</td>
    </tr>
  );
}

function formatRawTime(iso) {
  if (!iso) return '--';
  try { return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }); }
  catch { return '--'; }
}

function getConfidenceColor(score) {
  if (score >= 0.7) return 'var(--clr-on-time)';
  if (score >= 0.3) return 'var(--clr-slight)';
  return 'var(--clr-late)';
}
function getConfidenceClass(score) {
  if (score >= 0.7) return 'text-primary';
  if (score >= 0.3) return 'text-accent';
  return '';
}
function getConfidenceLabel(score) {
  if (score >= 0.7) return 'High';
  if (score >= 0.3) return 'Moderate — baseline active';
  return 'Low — baseline only';
}
