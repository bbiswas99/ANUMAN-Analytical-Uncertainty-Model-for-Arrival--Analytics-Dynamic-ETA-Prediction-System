import { useState } from 'react';
import { ErrorBoundary } from './components/ErrorBoundary';
import { PassengerView } from './tabs/PassengerView';
import { OpsView } from './tabs/OpsView';
import styles from './App.module.css';

const TABS = [
  { id: 'passenger', label: '🚆 Passenger', desc: 'Live ETA & Station Schedule' },
  { id: 'ops',       label: '🎛️ Control Room', desc: 'Live Replay & Dispatch Operations' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('passenger');

  return (
    <ErrorBoundary>
      <div className={styles.app}>
        {/* ── Top bar ── */}
        <header className={styles.topbar}>
          <div className={styles.brand}>
            <span className={styles.logo}>🛤️</span>
            <div className={styles.brandText}>
              <span className={styles.brandName}>TrainETA</span>
              <span className={styles.brandSub}>Dynamic ETA Prediction · PS 26028</span>
            </div>
          </div>

          <nav className={styles.tabs}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
                onClick={() => setActiveTab(tab.id)}
                id={`tab-${tab.id}`}
              >
                <span>{tab.label}</span>
                <span className={styles.tabDesc}>{tab.desc}</span>
              </button>
            ))}
          </nav>

          <div className={styles.topbarRight}>
            <div className={styles.corridor}>
              <span className={styles.corridorDot} />
              <span className={styles.corridorLabel}>Indian Railways Network</span>
            </div>
          </div>
        </header>

        {/* ── Main content ── */}
        <ErrorBoundary>
          {activeTab === 'passenger' && <PassengerView />}
          {activeTab === 'ops'       && <OpsView />}
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
}
