import { useState, useEffect, useRef } from 'react';
import { useReplay } from '../hooks/useReplay';
import { snapPositionToRoute } from '../utils/snapPositionToRoute';
import { getTrackCoordinatesBetween } from '../utils/trackRouting';
import styles from './LiveReplayControls.module.css';
import { formatDelay } from '../utils/formatETA';
import { RouteStationsList } from './RouteStationsList';

const SPEED_OPTIONS = [1, 2, 4, 8];

/**
 * LiveReplayControls — replays a historical journey on a simulated clock.
 * Calls onPositionChange with {lat, lon} and onStopChange with station code.
 * Per spec 06 §2: play/pause/speed controls, auto-retry on load failure.
 */
export function LiveReplayControls({ trainNo, date, onPositionChange, onStopChange }) {
  const { data, loading, error, load, reset } = useReplay();
  const [playing, setPlaying]   = useState(false);
  const [speed, setSpeed]       = useState(1);
  const [tickIdx, setTickIdx]   = useState(0);   // current stop index
  const [progress, setProgress] = useState(0);   // 0-1 within current leg
  const intervalRef = useRef(null);

  // Load replay data when trainNo/date change
  useEffect(() => {
    reset();
    setPlaying(false);
    setTickIdx(0);
    setProgress(0);
    onPositionChange && onPositionChange(null);
    onStopChange && onStopChange(null);

    if (trainNo && date) {
      load(trainNo, date);
    }
  }, [trainNo, date]);

  // Notify parent of position changes
  useEffect(() => {
    if (!data) return;
    const stops = data.stops || [];
    if (stops.length === 0) return;

    const current = stops[tickIdx];
    const next    = stops[tickIdx + 1];

    if (!next) {
      // End of journey
      onPositionChange && onPositionChange({ lat: current.lat, lon: current.lon });
      const finalCode = current.station_code || current.code || current.station_name;
      onStopChange && onStopChange(finalCode);
      return;
    }

    // Resolve accurate track coordinates (via OSM geometry or intermediate station network)
    const code1 = current.station_code || current.code || current.station_name;
    const code2 = next.station_code || next.code || next.station_name;
    const p1 = (current.lat && current.lon) ? [current.lat, current.lon] : null;
    const p2 = (next.lat && next.lon) ? [next.lat, next.lon] : null;

    const coords = getTrackCoordinatesBetween(code1, code2, p1, p2);

    const pos = snapPositionToRoute(coords, progress);
    if (pos && pos.lat > 5 && pos.lat < 40 && pos.lon > 60 && pos.lon < 100) {
      onPositionChange && onPositionChange(pos);
    }
    onStopChange && onStopChange(code1);
  }, [tickIdx, progress, data]);

  // Playback tick
  useEffect(() => {
    if (!playing || !data) return;
    const stops = data.stops || [];
    if (stops.length < 2) return;

    intervalRef.current = setInterval(() => {
      setProgress(prev => {
        const next = prev + 0.02 * speed;
        if (next >= 1) {
          // Advance to next stop
          setTickIdx(ti => {
            const nextIdx = ti + 1;
            // If next stop is the destination, stop playback upon arrival
            if (nextIdx >= stops.length - 1) {
              setPlaying(false);
              return stops.length - 1;
            }
            return nextIdx;
          });
          return 0;
        }
        return next;
      });
    }, 100);

    return () => clearInterval(intervalRef.current);
  }, [playing, speed, data]);

  const stops    = data?.stops || [];
  const current  = stops[tickIdx];
  const total    = stops.length;
  const isEnd    = total > 0 && tickIdx >= total - 1;

  function handlePlayPause() {
    if (isEnd) {
      handleRestart();
      setPlaying(true);
      return;
    }
    setPlaying(p => !p);
  }

  function handleRestart() {
    setTickIdx(0);
    setProgress(0);
    setPlaying(false);
  }

  // Loading state
  if (loading) {
    return (
      <div className={`${styles.panel} card card-padded`}>
        <div className={styles.loadingRow}>
          <div className="spinner" />
          <span className="text-sm text-muted">Loading journey data…</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`${styles.panel} card card-padded`}>
        <div className="alert-inline alert-error">
          <span>⚠️</span>
          <div className="flex-col gap-1">
            <span>{error}</span>
            <span style={{ fontSize: 12 }}>Try selecting a different date</span>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className={`${styles.panel} card card-padded`}>
        <p className="text-sm text-muted">Select a train and date to replay its journey.</p>
      </div>
    );
  }

  const overallProgress = total > 1 ? Math.min(1, (tickIdx + (isEnd ? 0 : progress)) / (total - 1)) : 1;


  return (
    <div className={`${styles.panel} card card-padded fade-in`}>
      {data._isFallback && (
        <span className={`badge badge-demo ${styles.demoTag}`}>Demo replay</span>
      )}

      {/* Progress bar */}
      <div className={styles.progressTrack}>
        <div className={styles.progressFill} style={{ width: `${overallProgress * 100}%` }} />
      </div>

      {/* Stop info */}
      <div className={styles.stopInfo}>
        <div className={styles.stopInfoLeft}>
          <span className={styles.stopLabel}>{isEnd ? 'Arrived at' : 'Currently at'}</span>
          <span className={styles.stopName}>
            {(() => {
              const cCode = current?.station_code || current?.station_name;
              const cFull = current?.station_full_name;
              return (cFull && cFull !== cCode) ? cFull : (stationNames[cCode] || cCode || '--');
            })()}
          </span>
        </div>
        <div className={styles.stopInfoRight}>
          {current && (
            <span className={`badge ${current.actual_delay_min <= 0 ? 'badge-on-time' : current.actual_delay_min <= 15 ? 'badge-slight' : 'badge-late'}`}>
              {formatDelay(current.actual_delay_min)}
            </span>
          )}
          <span className={styles.stopCount}>{tickIdx + 1} / {total}</span>
        </div>
      </div>

      {/* Controls */}
      <div className={styles.controls}>
        <button
          className={`btn btn-icon btn-secondary`}
          onClick={handleRestart}
          title="Restart"
        >↺</button>

        <button
          className={`btn btn-primary ${styles.playBtn}`}
          onClick={handlePlayPause}
          id="replay-play-pause"
        >
          {isEnd ? '↺ Replay journey' : playing ? '⏸ Pause' : '▶ Play'}
        </button>

        <div className={styles.speedWrap}>
          {SPEED_OPTIONS.map(s => (
            <button
              key={s}
              className={`btn btn-sm ${speed === s ? styles.speedActive : 'btn-secondary'}`}
              onClick={() => setSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* Station List with individual Dropdowns */}
      <RouteStationsList
        stops={stops}
        currentIndex={tickIdx}
        isReplay={true}
        onJumpToStation={(i) => {
          setTickIdx(i);
          setProgress(0);
          setPlaying(false);
        }}
      />
    </div>
  );
}
