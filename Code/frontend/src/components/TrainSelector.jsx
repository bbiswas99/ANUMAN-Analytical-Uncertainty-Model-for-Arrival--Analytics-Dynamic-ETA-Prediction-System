import { useState, useEffect, useRef } from 'react';
import trainList from '../assets/train-list.json';
import styles from './TrainSelector.module.css';

/**
 * TrainSelector — autocomplete search or inline train list over the bundled train list (8,730 trains).
 * Supports search by train number, train name, route codes, station names, and train type.
 */
export function TrainSelector({ onSelect, selectedTrainNo, inlineList = false }) {
  const [query, setQuery]         = useState('');
  const [open, setOpen]           = useState(false);
  const [focused, setFocused]     = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [visibleLimit, setLimit]  = useState(60);
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const listRef = useRef(null);

  // Reset limit when query changes
  useEffect(() => {
    setLimit(60);
  }, [query]);

  // For dropdown mode: populate query text when a train is selected externally
  useEffect(() => {
    if (!inlineList) {
      if (selectedTrainNo) {
        const found = trainList.find(t => t.train_no === selectedTrainNo);
        if (found) setQuery(`${found.train_no} — ${found.train_name}`);
      } else {
        setQuery('');
      }
    }
  }, [selectedTrainNo, inlineList]);

  // Close dropdown on outside click (only in dropdown mode)
  useEffect(() => {
    if (inlineList) return;
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setFocused(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [inlineList]);

  // Infinite scroll loader for large dataset
  function handleListScroll(e) {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    if (scrollHeight - scrollTop - clientHeight < 150) {
      setLimit(prev => Math.min(prev + 60, filtered.length));
    }
  }

  // Filter matching trains
  const filtered = query.trim().length === 0
    ? (inlineList ? trainList : trainList.slice(0, 10))
    : trainList.filter(t => {
        const q = query.trim().toLowerCase();
        return (
          String(t.train_no).includes(q) ||
          (t.train_name && t.train_name.toLowerCase().includes(q)) ||
          (t.route && t.route.toLowerCase().includes(q)) ||
          (t.origin && t.origin.toLowerCase().includes(q)) ||
          (t.destination && t.destination.toLowerCase().includes(q)) ||
          (t.origin_name && t.origin_name.toLowerCase().includes(q)) ||
          (t.destination_name && t.destination_name.toLowerCase().includes(q)) ||
          (t.type_code && t.type_code.toLowerCase().includes(q))
        );
      });

  const displayedTrains = inlineList ? filtered.slice(0, visibleLimit) : filtered.slice(0, 15);

  function handleSelect(train) {
    if (!inlineList) {
      setQuery(`${train.train_no} — ${train.train_name}`);
      setOpen(false);
      setFocused(false);
    }
    onSelect(train.train_no);
  }

  function handleInputChange(e) {
    setQuery(e.target.value);
    if (!inlineList) {
      setOpen(true);
      if (e.target.value === '') onSelect(null);
    }
  }

  function handleClear() {
    setQuery('');
    if (!inlineList) {
      setOpen(false);
      onSelect(null);
    }
    inputRef.current?.focus();
  }

  const typeColors = {
    'RAJ-TRAINS': '#dc2626',
    'T18-TRAINS': '#0284c7',
    'SHT-TRAINS': '#2563eb',
    'SF-TRAINS':  '#0891b2',
    'EXP-TRAINS': '#7c3aed',
    'PRM-TRAINS': '#d97706',
    'GRB-TRAINS': '#16a34a',
    'PASS-TRAINS':'#059669',
  };

  const typeLabels = {
    'RAJ-TRAINS': 'RAJ',
    'T18-TRAINS': 'VANDE BHARAT',
    'SHT-TRAINS': 'SHATABDI',
    'SF-TRAINS':  'SUPERFAST',
    'EXP-TRAINS': 'EXP',
    'PRM-TRAINS': 'PREMIUM',
    'GRB-TRAINS': 'GARIB RATH',
    'PASS-TRAINS':'PASS',
  };

  const selectedTrain = trainList.find(t => t.train_no === selectedTrainNo);

  // ── INLINE LIST MODE (Passenger tab) ──────────────────────────────
  if (inlineList) {
    return (
      <div className={styles.inlineSection}>
        <div className={styles.inlineHeaderRow}>
          <p className="section-label" style={{ marginBottom: 0 }}>Search Train</p>
          {selectedTrain && (
            <span className={styles.selectedBadge}>
              Active: <strong>#{selectedTrain.train_no}</strong>
              <button
                className={styles.deselectBtn}
                onClick={() => onSelect(null)}
                title="Deselect train"
                aria-label="Deselect"
              >✕</button>
            </span>
          )}
        </div>

        {/* Search Bar */}
        <div className={`${styles.inputWrap} ${focused ? styles.focused : ''}`}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            ref={inputRef}
            id="train-selector-input"
            className={styles.input}
            type="text"
            placeholder="Search 8,700+ trains by no, name, city, station…"
            value={query}
            onChange={handleInputChange}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            autoComplete="off"
          />
          {query && (
            <button
              className={styles.clearBtn}
              onClick={handleClear}
              aria-label="Clear filter"
            >✕</button>
          )}
        </div>

        {/* Trains List directly under Search Bar */}
        <div className={styles.inlineListCard}>
          <div className={styles.listCardHeader}>
            <div className={styles.listCardHeaderLeft}>
              <span className={styles.listTitle}>
                {query.trim() ? 'Matching Trains' : 'Indian Railways Trains'}
              </span>
              <span className={styles.countBadge}>{filtered.length.toLocaleString()}</span>
            </div>
            <button
              type="button"
              className={styles.collapseBtn}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? '▾ Show list' : '▴ Hide list'}
            </button>
          </div>

          {!collapsed && (
            <div
              className={styles.inlineListScroll}
              ref={listRef}
              onScroll={handleListScroll}
            >
              {filtered.length === 0 ? (
                <div className={styles.noResult}>
                  <span>No matching train found</span>
                  <button type="button" className={styles.resetBtn} onClick={handleClear}>
                    Clear search filter
                  </button>
                </div>
              ) : (
                <>
                  {displayedTrains.map(train => {
                    const isSelected = train.train_no === selectedTrainNo;
                    return (
                      <button
                        key={train.train_no}
                        type="button"
                        className={`${styles.inlineItem} ${isSelected ? styles.inlineItemSelected : ''}`}
                        onClick={() => handleSelect(train)}
                      >
                        <div className={styles.inlineItemMain}>
                          <div className={styles.itemTopRow}>
                            <span className={styles.trainNoBadge}>#{train.train_no}</span>
                            <span className={styles.trainNameText}>{train.train_name}</span>
                          </div>
                          <div className={styles.itemBottomRow}>
                            <span className={styles.routeText}>
                              {train.route !== '--' ? train.route : 'Indian Railways'}
                            </span>
                            {train.origin_name && train.destination_name && (
                              <span className={styles.routeDetailText}>
                                {train.origin_name} → {train.destination_name}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className={styles.inlineItemRight}>
                          <span
                            className={styles.typePill}
                            style={{
                              background: (typeColors[train.type_code] || '#64748b') + '1a',
                              color: typeColors[train.type_code] || '#64748b'
                            }}
                          >
                            {typeLabels[train.type_code] || train.type_code?.replace('-TRAINS', '') || 'IR'}
                          </span>
                          {isSelected && (
                            <span className={styles.activePill}>Selected</span>
                          )}
                        </div>
                      </button>
                    );
                  })}

                  {visibleLimit < filtered.length && (
                    <div className={styles.loadMoreRow}>
                      <span>
                        Showing {visibleLimit} of {filtered.length.toLocaleString()} trains • Scroll for more
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── DROPDOWN AUTOCOMPLETE MODE (Operations tab) ───────────────────
  return (
    <div className={styles.container} ref={containerRef}>
      <p className="section-label">Search Train</p>
      <div className={`${styles.inputWrap} ${focused ? styles.focused : ''}`}>
        <span className={styles.searchIcon}>🔍</span>
        <input
          ref={inputRef}
          id="train-selector-input"
          className={styles.input}
          type="text"
          placeholder="Train number, name, station…"
          value={query}
          onChange={handleInputChange}
          onFocus={() => { setFocused(true); setOpen(true); }}
          autoComplete="off"
        />
        {query && (
          <button
            className={styles.clearBtn}
            onClick={handleClear}
            aria-label="Clear"
          >✕</button>
        )}
      </div>

      {open && (
        <div className={styles.dropdown}>
          {filtered.length === 0 ? (
            <div className={styles.noResult}>
              <span>No matching train found</span>
              <span className={styles.noResultHint}>Try a train number or part of the name</span>
            </div>
          ) : (
            displayedTrains.map(train => (
              <button
                key={train.train_no}
                type="button"
                className={`${styles.item} ${train.train_no === selectedTrainNo ? styles.selected : ''}`}
                onClick={() => handleSelect(train)}
              >
                <div className={styles.itemLeft}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className={styles.trainNo}>#{train.train_no}</span>
                    <span className={styles.trainName}>{train.train_name}</span>
                  </div>
                  <span className={styles.route}>{train.route}</span>
                </div>
                <span
                  className={styles.typePill}
                  style={{
                    background: (typeColors[train.type_code] || '#64748b') + '1a',
                    color: typeColors[train.type_code] || '#64748b'
                  }}
                >
                  {typeLabels[train.type_code] || train.type_code?.replace('-TRAINS', '') || 'IR'}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}


