import { useState, useEffect } from 'react';
import { TrainSelector } from '../components/TrainSelector';
import { ETACard } from '../components/ETACard';
import { ExplanationPanel } from '../components/ExplanationPanel';
import { TrackMap } from '../components/TrackMap';
import { RouteStationsList } from '../components/RouteStationsList';
import { useReplay } from '../hooks/useReplay';
import styles from './PassengerView.module.css';

const DEMO_DATE = '2025-11-15';

export function PassengerView() {
  const [trainNo, setTrainNo]         = useState(null);
  const [activeStop, setActiveStop]   = useState(null);
  const { data: routeData, load: loadRoute, reset: resetRoute } = useReplay();

  useEffect(() => {
    setActiveStop(null);
    if (trainNo) {
      loadRoute(trainNo, DEMO_DATE);
    } else {
      resetRoute();
    }
  }, [trainNo]);

  return (
    <div className={styles.layout}>
      {/* ── Sidebar ── */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <span className={styles.passengerBadge}>🚆 Passenger Live View</span>
          <p className={styles.passengerSubtitle}>Real-time ETA, route delays & station schedule</p>
        </div>

        <TrainSelector
          onSelect={t => {
            setTrainNo(t);
            setActiveStop(null);
          }}
          selectedTrainNo={trainNo}
          inlineList
        />

        <ETACard trainNo={trainNo} />

        {trainNo && (
          <RouteStationsList
            stops={routeData?.stops || []}
            activeStop={activeStop}
            onSelectStation={(stop) => setActiveStop(stop.station_code || stop.station_name)}
            isReplay={false}
            title="Station-wise Live Delay & Schedule"
          />
        )}

        <ExplanationPanel trainNo={trainNo} />
      </aside>

      {/* ── Map ── */}
      <main className={styles.mapArea}>
        <TrackMap
          trainNo={trainNo}
          trainPosition={null}
          activeStop={activeStop}
          delaySpikeMarkers={[]}
        />
      </main>
    </div>
  );
}
