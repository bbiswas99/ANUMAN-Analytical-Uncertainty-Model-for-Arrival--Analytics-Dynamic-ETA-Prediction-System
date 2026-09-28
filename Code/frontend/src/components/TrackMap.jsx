import { useEffect, useRef, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, CircleMarker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import trainList from '../assets/train-list.json';
import stationCoords from '../assets/station-coordinates.json';
import railwayNetwork from '../assets/railway-network.json';
import { buildFullRouteTrackCoords } from '../utils/trackRouting';
import styles from './TrackMap.module.css';

// Fix Leaflet default icon path issues with Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const TRAIN_ICON = L.divIcon({
  className: '',
  html: `<div style="
    width:30px;height:30px;
    background:#1e3a5f;
    border:3px solid #fff;
    border-radius:50%;
    box-shadow:0 3px 10px rgba(0,0,0,0.45);
    display:flex;align-items:center;justify-content:center;
    font-size:15px;
    cursor:pointer;
  ">🚂</div>`,
  iconSize:   [30, 30],
  iconAnchor: [15, 15],
});

// Default Centre of India
const DEFAULT_CENTER = [22.8, 79.5];
const DEFAULT_ZOOM   = 5;

/**
 * Helper component that auto-animates map bounds whenever the route changes.
 * When a train is deselected (coords empty), smoothly returns to the all-India overview.
 */
function MapBoundsUpdater({ coords }) {
  const map = useMap();
  const prevHasCoords = useRef(false);

  useEffect(() => {
    if (coords && coords.length >= 2) {
      prevHasCoords.current = true;
      try {
        const bounds = L.latLngBounds(coords);
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10, animate: true, duration: 1.2 });
      } catch {
        // Fallback gracefully
      }
    } else if (prevHasCoords.current) {
      prevHasCoords.current = false;
      map.flyTo(DEFAULT_CENTER, DEFAULT_ZOOM, { animate: true, duration: 1.2 });
    }
  }, [coords, map]);
  return null;
}

/**
 * TrackMap — Dynamic Leaflet map that renders the route and stops for ANY selected train.
 * If trainNo is given, pulls stops and coordinates, draws route polyline, and auto-zooms.
 * If no train is selected, renders the clean national railway map without overlays.
 */
export function TrackMap({ trainNo, trainPosition, activeStop, delaySpikeMarkers = [] }) {
  const mapRef = useRef(null);
  const [_mapReady, setMapReady] = useState(false);

  // Find selected train details
  const selectedTrain = useMemo(() => {
    if (!trainNo) return null;
    return trainList.find(t => t.train_no === trainNo) || null;
  }, [trainNo]);

  // Build dynamic stations along route
  const dynamicStations = useMemo(() => {
    if (!selectedTrain) return [];
    const stops = selectedTrain.stops && selectedTrain.stops.length > 0
      ? selectedTrain.stops
      : [selectedTrain.origin, selectedTrain.destination].filter(Boolean);

    return stops.map((code, idx) => {
      const coords = stationCoords[code];
      if (!coords) return null;
      const isOrigin = idx === 0 || code === selectedTrain.origin;
      const isDest   = idx === stops.length - 1 || code === selectedTrain.destination;
      return {
        code,
        name: isOrigin
          ? (selectedTrain.origin_name || code)
          : (isDest ? (selectedTrain.destination_name || code) : code),
        lat: coords[0],
        lon: coords[1],
        isOrigin,
        isDest,
        stopIndex: idx + 1,
      };
    }).filter(Boolean);
  }, [selectedTrain]);

  // Active route polyline coordinates following real physical railway tracks across India
  const activeRouteCoords = useMemo(() => {
    if (!selectedTrain || dynamicStations.length < 2) return [];
    return buildFullRouteTrackCoords(dynamicStations);
  }, [selectedTrain, dynamicStations]);

  // Stations to render (only when a train is selected)
  const stationsToRender = selectedTrain ? dynamicStations : [];

  // Compute train marker location (null if no train selected)
  const markerPosition = useMemo(() => {
    if (!selectedTrain) return null;
    if (trainPosition) return [trainPosition.lat, trainPosition.lon];
    if (activeStop && dynamicStations.length > 0) {
      const found = dynamicStations.find(s => s.code === activeStop);
      if (found) return [found.lat, found.lon];
    }
    if (dynamicStations.length > 0) {
      // Place marker at first station
      return [dynamicStations[0].lat, dynamicStations[0].lon];
    }
    return null;
  }, [selectedTrain, trainPosition, activeStop, dynamicStations]);

  return (
    <div className={styles.mapWrap}>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        className={styles.map}
        whenReady={() => setMapReady(true)}
        ref={mapRef}
        zoomControl={true}
      >
        {/* Dynamic camera updater */}
        <MapBoundsUpdater coords={activeRouteCoords} />

        {/* Base: OpenStreetMap Standard — 100% free, no API key required, no watermarks */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        {/* National Indian Railways Physical Track Network — 100% client-side vector layer, zero external tile APIs */}
        {railwayNetwork?.tracks && (
          <Polyline
            positions={railwayNetwork.tracks}
            pathOptions={{
              color: '#334155',
              weight: 2,
              opacity: 0.7,
            }}
          />
        )}

        {/* Background glow polyline for route */}
        {activeRouteCoords.length >= 2 && (
          <Polyline
            positions={activeRouteCoords}
            pathOptions={{ color: '#1d4ed8', weight: 8, opacity: 0.35 }}
          />
        )}

        {/* Foreground active route polyline */}
        {activeRouteCoords.length >= 2 && (
          <Polyline
            positions={activeRouteCoords}
            pathOptions={{
              color: '#2563eb',
              weight: 4,
              opacity: 0.95,
              dashArray: '8 4',
            }}
          />
        )}

        {/* Station markers along route */}
        {stationsToRender.map(stn => {
          const isCurrent = activeStop === stn.code;
          const isOrigin = stn.isOrigin;
          const isDest = stn.isDest;
          const radius = isCurrent ? 10 : (isOrigin || isDest ? 8 : 5);
          const color = isCurrent ? '#2563eb' : (isOrigin ? '#10b981' : (isDest ? '#dc2626' : '#1e3a5f'));
          const fill = isCurrent ? '#2563eb' : (isOrigin ? '#ecfdf5' : (isDest ? '#fef2f2' : '#ffffff'));

          return (
            <CircleMarker
              key={`${stn.code}-${stn.stopIndex || 0}`}
              center={[stn.lat, stn.lon]}
              radius={radius}
              pathOptions={{
                color: color,
                fillColor: fill,
                fillOpacity: 1,
                weight: isOrigin || isDest || isCurrent ? 3 : 2,
              }}
            >
              <Popup>
                <div className={styles.popup}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <strong>{stn.code}</strong>
                    {isOrigin && <span className="badge badge-on-time" style={{ fontSize: 9 }}>Origin</span>}
                    {isDest && <span className="badge badge-late" style={{ fontSize: 9 }}>Destination</span>}
                    {isCurrent && <span className="badge badge-demo" style={{ fontSize: 9 }}>Current Stop</span>}
                  </div>
                  <span>{stn.name || stn.code}</span>
                  {stn.stopIndex && (
                    <span style={{ fontSize: 10, color: 'var(--clr-text-3)' }}>
                      Stop #{stn.stopIndex}
                    </span>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {/* Moving / current train marker */}
        {markerPosition && (
          <Marker position={markerPosition} icon={TRAIN_ICON}>
            <Popup>
              <div className={styles.popup}>
                <strong>#{selectedTrain?.train_no || trainNo || 'Train'}</strong>
                <span>{selectedTrain?.train_name || 'Live Train Location'}</span>
                <span style={{ fontSize: 11, color: 'var(--clr-primary)' }}>
                  {activeStop ? `At / near ${activeStop}` : 'En route'}
                </span>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Delay spike markers */}
        {delaySpikeMarkers.map((marker, i) => (
          <CircleMarker
            key={i}
            center={[marker.lat, marker.lon]}
            radius={7}
            pathOptions={{ color: '#ef4444', fillColor: '#fca5a5', fillOpacity: 0.8, weight: 2 }}
          >
            <Popup>
              <div className={styles.popup}>
                <span>Delay spike observed near this junction</span>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Map legend */}
      <div className={styles.legend}>
        {selectedTrain ? (
          <>
            <div className={styles.legendItem}>
              <span style={{ display:'inline-block', width:18, height:3, background:'#2563eb', borderRadius:2, borderTop:'2px dashed #2563eb' }} />
              <span>{selectedTrain.route || `${selectedTrain.origin} → ${selectedTrain.destination}`}</span>
            </div>
            <div className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: '#10b981' }} />
              <span>Origin</span>
            </div>
            <div className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: '#dc2626' }} />
              <span>Destination</span>
            </div>
            <div className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: '#1e3a5f' }} />
              <span>Stop</span>
            </div>
            {markerPosition && (
              <div className={styles.legendItem}>
                <span>🚂</span>
                <span>Train</span>
              </div>
            )}
            <div className={styles.legendDivider} />
          </>
        ) : (
          <>
            <div className={styles.legendItem} style={{ color: 'var(--clr-text-3)', fontStyle: 'italic' }}>
              <span>Select a train to view route</span>
            </div>
            <div className={styles.legendDivider} />
          </>
        )}
        <div className={styles.legendItem} style={{ opacity: 0.85 }}>
          <span style={{ fontSize: 10 }}>🛤️ IR Track Network</span>
        </div>
      </div>
    </div>
  );
}

