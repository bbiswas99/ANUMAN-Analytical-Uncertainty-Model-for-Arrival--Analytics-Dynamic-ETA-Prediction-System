import { useState, useEffect, useRef } from 'react';
import stationNames from '../assets/station-names.json';
import { formatDelay } from '../utils/formatETA';
import styles from './RouteStationsList.module.css';

function computeClientExpectedTime(timeStr, delayMin) {
  if (!timeStr || timeStr === '--:--' || timeStr === 'Origin' || timeStr === 'Destination') return timeStr;
  if (!timeStr.includes(':')) return timeStr;
  const parts = timeStr.split(':');
  const h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  if (isNaN(h) || isNaN(m)) return timeStr;
  const tot = (h * 60 + m + Math.round(delayMin || 0)) % (24 * 60);
  const hh = Math.floor(tot / 60);
  const mm = tot % 60;
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}

function computeClientHaltDuration(arr, dep) {
  if (!arr || !dep || arr === 'Origin' || dep === 'Destination' || !arr.includes(':') || !dep.includes(':')) {
    return null;
  }
  const aParts = arr.split(':');
  const dParts = dep.split(':');
  const aMin = parseInt(aParts[0], 10) * 60 + parseInt(aParts[1], 10);
  const dMin = parseInt(dParts[0], 10) * 60 + parseInt(dParts[1], 10);
  if (isNaN(aMin) || isNaN(dMin)) return null;
  const diff = (dMin - aMin + 24 * 60) % (24 * 60);
  return `${diff} min`;
}

/**
 * RouteStationsList — renders the full station-by-station route breakdown with delays,
 * scheduled & expected times, and expandable detail cards.
 * Used across both Live ETA (Passenger View) and Live Replay (Control Room View).
 */
export function RouteStationsList({
  stops = [],
  currentIndex = -1,
  activeStop = null,
  onSelectStation = null,
  onJumpToStation = null,
  isReplay = false,
  title = 'Route Stations',
}) {
  const [expandedStops, setExpandedStops] = useState({});
  const activeCardRef = useRef(null);

  // Auto-scroll active card into view during replay
  useEffect(() => {
    if (isReplay && activeCardRef.current) {
      activeCardRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentIndex, isReplay]);

  // Auto-expand current stop during replay
  useEffect(() => {
    if (isReplay && currentIndex >= 0) {
      setExpandedStops(prev => ({
        ...prev,
        [currentIndex]: true,
      }));
    }
  }, [currentIndex, isReplay]);

  if (!stops || stops.length === 0) {
    return (
      <div className={styles.emptyNotice}>
        No intermediate station schedule available for this train.
      </div>
    );
  }

  const allExpanded = stops.every((_, i) => expandedStops[i]);

  const handleToggleAll = () => {
    const next = {};
    stops.forEach((_, i) => { next[i] = !allExpanded; });
    setExpandedStops(next);
  };

  return (
    <div className={styles.stationSection}>
      <div className={styles.stationSectionHeader}>
        <div className={styles.sectionTitleWrap}>
          <span className={styles.sectionTitle}>{title}</span>
          <span className={styles.sectionBadge}>{stops.length} Stops</span>
        </div>
        <button
          type="button"
          className={styles.toggleAllBtn}
          onClick={handleToggleAll}
        >
          {allExpanded ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      <div className={styles.stationList}>
        {stops.map((stop, i) => {
          const isCurrent = isReplay && i === currentIndex;
          const isPast = isReplay && i < currentIndex;
          const isExpanded = !!expandedStops[i];
          const isOrigin = i === 0;
          const isDest = i === stops.length - 1;

          const rawCode = stop.station_code || stop.station_name;
          const rawFull = stop.station_full_name;
          const fullName = (rawFull && rawFull !== rawCode) ? rawFull : (stationNames[rawCode] || rawCode);

          const delayMin = stop.actual_delay_min ?? stop.expected_delay_min ?? 0;
          const delayClass = delayMin <= 0 ? styles.delayOnTime : delayMin <= 15 ? styles.delaySlight : styles.delayLate;

          const schedArr = stop.scheduled_arr && stop.scheduled_arr !== 'nan' ? stop.scheduled_arr : (isOrigin ? 'Origin' : (stop.scheduled_time || '--:--'));
          const schedDep = stop.scheduled_dep && stop.scheduled_dep !== 'nan' ? stop.scheduled_dep : (isDest ? 'Destination' : '--:--');
          const expArr = stop.expected_arr && stop.expected_arr !== 'nan' ? stop.expected_arr : (isOrigin ? 'Origin' : computeClientExpectedTime(schedArr, delayMin));
          const expDep = stop.expected_dep && stop.expected_dep !== 'nan' ? stop.expected_dep : (isDest ? 'Destination' : computeClientExpectedTime(schedDep, delayMin));
          const haltDuration = stop.halt_duration || (isOrigin ? 'Origin' : (isDest ? 'Destination' : computeClientHaltDuration(schedArr, schedDep) || '--'));

          const isHighlight = activeStop && (activeStop === rawCode || activeStop === stop.station_name);

          return (
            <div
              key={`${rawCode}-${i}`}
              ref={isCurrent ? activeCardRef : null}
              className={`
                ${styles.stationCard}
                ${isCurrent ? styles.stationCardCurrent : ''}
                ${isHighlight && !isCurrent ? styles.stationCardActiveHighlight : ''}
                ${isPast ? styles.stationCardPast : ''}
              `}
            >
              {/* Station Card Header (Toggle Dropdown) */}
              <div
                className={styles.stationCardHeader}
                onClick={() => {
                  setExpandedStops(prev => ({ ...prev, [i]: !prev[i] }));
                  onSelectStation && onSelectStation(stop, i);
                }}
              >
                <div className={styles.stnHeaderLeft}>
                  <span className={`
                    ${styles.stnNum}
                    ${isCurrent ? styles.stnNumActive : isOrigin ? styles.stnNumOrigin : isDest ? styles.stnNumDest : ''}
                  `}>
                    {isPast ? '✓' : i + 1}
                  </span>
                  <div className={styles.stnTitleBlock}>
                    <span className={styles.stnNameText} title={fullName}>
                      {fullName}
                    </span>
                    <span className={styles.stnCodePill}>{rawCode}</span>
                  </div>
                </div>

                <div className={styles.stnHeaderRight}>
                  <span className={`${styles.delayPill} ${delayClass}`}>
                    {formatDelay(delayMin)}
                  </span>
                  <button
                    type="button"
                    className={`${styles.chevronBtn} ${isExpanded ? styles.chevronRotated : ''}`}
                    aria-label="Toggle details"
                  >
                    ▾
                  </button>
                </div>
              </div>

              {/* Dropdown Details Drawer */}
              {isExpanded && (
                <div className={styles.stationDropdown}>
                  <div className={styles.detailGrid}>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Station Name</span>
                      <span className={styles.detailValBold} title={fullName}>{fullName}</span>
                    </div>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Station Code</span>
                      <span className={styles.detailValBold}>{rawCode}</span>
                    </div>

                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Scheduled Arrival</span>
                      <span className={styles.detailVal}>{schedArr}</span>
                    </div>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Scheduled Departure</span>
                      <span className={styles.detailVal}>{schedDep}</span>
                    </div>

                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Expected Arrival</span>
                      <span className={`${styles.detailVal} ${delayMin > 15 ? styles.textLate : ''}`}>{expArr}</span>
                    </div>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Expected Departure</span>
                      <span className={styles.detailVal}>{expDep}</span>
                    </div>

                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Current Delay</span>
                      <span className={`${styles.detailVal} ${delayClass}`}>{formatDelay(delayMin)}</span>
                    </div>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Expected Delay</span>
                      <span className={`${styles.detailVal} ${delayClass}`}>{formatDelay(delayMin)}</span>
                    </div>

                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Scheduled Halt</span>
                      <span className={styles.detailVal}>{haltDuration}</span>
                    </div>
                    <div className={styles.detailBox}>
                      <span className={styles.detailLabel}>Distance</span>
                      <span className={styles.detailVal}>{stop.distance_km != null ? `${stop.distance_km} km` : '--'}</span>
                    </div>
                  </div>

                  <div className={styles.actionRow}>
                    {isReplay && onJumpToStation ? (
                      <button
                        type="button"
                        className={styles.jumpBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          onJumpToStation(i);
                        }}
                      >
                        📍 Jump Replay to this Station
                      </button>
                    ) : (
                      <button
                        type="button"
                        className={styles.jumpBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectStation && onSelectStation(stop, i);
                        }}
                      >
                        📍 Highlight on Map
                      </button>
                    )}
                    <span className={styles.statusIndicator}>
                      {isCurrent ? '🚂 Current Location' : isPast ? '✓ Visited' : isOrigin ? '🚩 Origin' : isDest ? '🏁 Destination' : `Stop ${i + 1} of ${stops.length}`}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
