/**
 * apiClient.js
 * Central HTTP wrapper with timeout, fallback, and error parsing.
 * Per spec 05: all responses use a defined schema. Error shapes follow 10 (stubbed).
 */

import fallbackData from '../assets/demo-fallback.json';

const API_BASE = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '')
  : '';
const HAS_API_BACKEND = Boolean(API_BASE && API_BASE.trim() !== '');
const DEFAULT_TIMEOUT_MS = 2500;

/**
 * Fetch with timeout. Rejects with a TimeoutError if the request takes too long.
 */
async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timer);
    return res;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') throw new Error('TIMEOUT');
    throw err;
  }
}

/**
 * Parse an error response from the API.
 * Standard shape (from errors.py): {error_code, message, detail}
 * Falls back to legacy `detail` field and then generic status string.
 */
async function parseApiError(res) {
  try {
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      return `HTTP ${res.status}`;
    }
    const body = await res.json();
    // New standard shape from errors.py
    if (body.message) return body.message;
    // Legacy FastAPI shape
    if (body.detail) return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    return `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

import trainList from '../assets/train-list.json';

/**
 * Synthesizes a realistic baseline prediction for any train in the dataset
 * when the live ML backend server is offline.
 */
function synthesizeBaselinePrediction(trainNo, whatIf = null) {
  const train = trainList.find(t => t.train_no === trainNo);
  if (!train) return null;

  const now = new Date();
  
  // Typical delay based on IR category
  const typeDelayMap = {
    'T18-TRAINS': 2,
    'RAJ-TRAINS': 4,
    'SHT-TRAINS': 6,
    'PRM-TRAINS': 8,
    'SF-TRAINS':  14,
    'EXP-TRAINS': 22,
    'GRB-TRAINS': 16,
    'PASS-TRAINS': 35,
  };

  let delayMin = typeDelayMap[train.type_code] ?? 15;
  if (whatIf && typeof whatIf.added_delay_min === 'number') {
    delayMin += whatIf.added_delay_min;
  }

  const travelMin = 85;
  const etaDate = new Date(now.getTime() + (travelMin + delayMin) * 60 * 1000);
  const baselineDate = new Date(now.getTime() + travelMin * 60 * 1000);
  const lowerDate = new Date(etaDate.getTime() - 10 * 60 * 1000);
  const upperDate = new Date(etaDate.getTime() + 15 * 60 * 1000);

  const stops = train.stops || [];
  const midStop = stops.length > 2 ? stops[Math.floor(stops.length / 2)] : (train.origin || 'STN');

  const confidenceScore = train.type_code === 'T18-TRAINS' || train.type_code === 'RAJ-TRAINS'
    ? 0.92
    : (train.type_code === 'SF-TRAINS' || train.type_code === 'SHT-TRAINS' ? 0.84 : 0.73);

  return {
    train_no: train.train_no,
    train_name: train.train_name,
    type_code: train.type_code,
    eta: etaDate.toISOString(),
    confidence_interval_lower: lowerDate.toISOString(),
    confidence_interval_upper: upperDate.toISOString(),
    baseline_eta: baselineDate.toISOString(),
    current_delay_min: delayMin,
    data_confidence_score: confidenceScore,
    model_used: 'baseline',
    last_station_code: midStop,
    last_station_name: midStop,
    _isFallback: true,
    _isDynamicBaseline: true,
  };
}

function synthesizeExplanation(trainNo) {
  const train = trainList.find(t => t.train_no === trainNo);
  if (!train) return null;
  const isPriority = train.type_code === 'T18-TRAINS' || train.type_code === 'RAJ-TRAINS' || train.type_code === 'SHT-TRAINS';
  return {
    train_no: train.train_no,
    top_delay_factors: isPriority ? [
      "High priority service with green corridor section clearance",
      "Nominal traffic density across intermediate block sectors",
      "Consistent historical schedule buffer maintained"
    ] : [
      "Moderate section density on approaching division corridor",
      "Junction interlocking and crossing precedence window",
      "Historical buffer recovery in progress"
    ],
    _isFallback: true
  };
}

/** GET /predict?train_no={trainNo}[&what_if={...}][&enable_model_b={bool}] */
export async function fetchPrediction(trainNo, whatIf = null, enableModelB = null) {
  if (!trainNo || !Number.isInteger(trainNo) || trainNo <= 0) {
    throw new Error('INVALID_TRAIN');
  }

  // Fast-path client-side mode when no external API base is configured
  if (!HAS_API_BACKEND) {
    const fb = fallbackData.predictions[String(trainNo)];
    if (fb) return { ...fb, _isFallback: true };
    const dynamic = synthesizeBaselinePrediction(trainNo, whatIf);
    if (dynamic) return dynamic;
    throw new Error(`Prediction unavailable for train ${trainNo}`);
  }

  let url = `${API_BASE}/predict?train_no=${trainNo}`;
  if (whatIf) url += `&what_if=${encodeURIComponent(JSON.stringify(whatIf))}`;
  if (enableModelB !== null && enableModelB !== undefined) {
    url += `&enable_model_b=${enableModelB}`;
  }

  try {
    const res = await fetchWithTimeout(url);
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok || !contentType.includes('application/json')) {
      const msg = await parseApiError(res);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.message === 'TIMEOUT' || err.message === 'Failed to fetch' || !err.status || err.status === 404 || err.status >= 500) {
      // Network/timeout/404 — use fallback
      const fb = fallbackData.predictions[String(trainNo)];
      if (fb) return { ...fb, _isFallback: true };

      // Dynamic fallback for all 8,730 dataset trains
      const dynamic = synthesizeBaselinePrediction(trainNo, whatIf);
      if (dynamic) return dynamic;

      throw new Error(`Live prediction unavailable for train ${trainNo} right now`);
    }
    throw err;
  }
}

/** GET /config/model-b — query global Model B operational status */
export async function fetchModelBStatus() {
  if (!HAS_API_BACKEND) return { model_b_enabled: false };
  try {
    const res = await fetchWithTimeout(`${API_BASE}/config/model-b`, {}, 2500);
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok || !contentType.includes('application/json')) return { model_b_enabled: false };
    return await res.json();
  } catch {
    return { model_b_enabled: false };
  }
}

/** POST /config/model-b — update global Model B operational status */
export async function setModelBStatus(enabled) {
  if (!HAS_API_BACKEND) {
    return { success: true, model_b_enabled: Boolean(enabled), _isFallback: true };
  }
  try {
    const res = await fetchWithTimeout(`${API_BASE}/config/model-b`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: Boolean(enabled) }),
    }, 2500);
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok || !contentType.includes('application/json')) {
      return { success: true, model_b_enabled: Boolean(enabled), _isFallback: true };
    }
    return await res.json();
  } catch {
    return { success: true, model_b_enabled: Boolean(enabled), _isFallback: true };
  }
}

/** GET /explain?train_no={trainNo} */
export async function fetchExplanation(trainNo) {
  if (!trainNo || !Number.isInteger(trainNo) || trainNo <= 0) {
    throw new Error('INVALID_TRAIN');
  }

  if (!HAS_API_BACKEND) {
    const fb = fallbackData.explanations[String(trainNo)];
    if (fb) return { ...fb, _isFallback: true };
    const dynamicExp = synthesizeExplanation(trainNo);
    if (dynamicExp) return dynamicExp;
    return null;
  }

  const url = `${API_BASE}/explain?train_no=${trainNo}`;
  try {
    const res = await fetchWithTimeout(url);
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok || !contentType.includes('application/json')) {
      const msg = await parseApiError(res);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.message === 'TIMEOUT' || err.message === 'Failed to fetch' || !err.status || err.status === 404 || err.status >= 500) {
      const fb = fallbackData.explanations[String(trainNo)];
      if (fb) return { ...fb, _isFallback: true };

      const dynamicExp = synthesizeExplanation(trainNo);
      if (dynamicExp) return dynamicExp;

      return null;
    }
    throw err;
  }
}

import stationCoords from '../assets/station-coordinates.json';
import stationNames from '../assets/station-names.json';

function synthesizeReplay(trainNo, date) {
  const train = trainList.find(t => t.train_no === trainNo);
  if (!train) return null;

  const rawStops = train.stops && train.stops.length > 0
    ? train.stops
    : [train.origin, train.destination].filter(Boolean);

  const validStops = [];
  let stationIndex = 1;
  let startHour = 6;
  let startMinute = 0;

  for (let i = 0; i < rawStops.length; i++) {
    const code = rawStops[i];
    const coords = stationCoords[code];
    if (!coords) continue;

    const totalMinutes = i * 40;
    const hour = (startHour + Math.floor((startMinute + totalMinutes) / 60)) % 24;
    const min = (startMinute + totalMinutes) % 60;
    const timeStr = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
    const delay = Math.max(0, Math.round(Math.sin(i * 0.8) * 6 + (i * 1.5) % 8));

    const isOrigin = i === 0;
    const isDest = i === rawStops.length - 1;
    const fullName = stationNames[code] || (isOrigin
      ? (train.origin_name || code)
      : (isDest ? (train.destination_name || code) : code));

    const depMinutes = totalMinutes + (isOrigin || isDest ? 0 : 4);
    const depHour = (startHour + Math.floor((startMinute + depMinutes) / 60)) % 24;
    const depMin = (startMinute + depMinutes) % 60;
    const depTimeStr = `${String(depHour).padStart(2, '0')}:${String(depMin).padStart(2, '0')}`;

    const expTotal = totalMinutes + delay;
    const expHour = (startHour + Math.floor((startMinute + expTotal) / 60)) % 24;
    const expMin = (startMinute + expTotal) % 60;
    const expTimeStr = `${String(expHour).padStart(2, '0')}:${String(expMin).padStart(2, '0')}`;

    const expDepTotal = depMinutes + delay;
    const expDepHour = (startHour + Math.floor((startMinute + expDepTotal) / 60)) % 24;
    const expDepMin = (startMinute + expDepTotal) % 60;
    const expDepTimeStr = `${String(expDepHour).padStart(2, '0')}:${String(expDepMin).padStart(2, '0')}`;

    validStops.push({
      station_no: stationIndex++,
      station_code: code,
      station_name: code,
      station_full_name: fullName,
      scheduled_time: timeStr,
      scheduled_arr: isOrigin ? 'Origin' : timeStr,
      scheduled_dep: isDest ? 'Destination' : depTimeStr,
      actual_delay_min: isOrigin ? 0 : delay,
      expected_arr: isOrigin ? 'Origin' : expTimeStr,
      expected_dep: isDest ? 'Destination' : expDepTimeStr,
      expected_delay_min: isOrigin ? 0 : delay,
      halt_duration: isOrigin ? 'Origin' : (isDest ? 'Destination' : '4 min'),
      distance_km: i * 45,
      lat: coords[0],
      lon: coords[1],
    });
  }

  if (validStops.length < 2) return null;

  return {
    train_no: train.train_no,
    train_name: train.train_name,
    date: date || '2025-11-15',
    stops: validStops,
    _isFallback: true,
  };
}

/** GET /replay?train_no={trainNo}&date={date} */
export async function fetchReplay(trainNo, date) {
  if (!trainNo || !Number.isInteger(trainNo) || trainNo <= 0) {
    throw new Error('INVALID_TRAIN');
  }
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error('date must be in YYYY-MM-DD format');
  }

  if (!HAS_API_BACKEND) {
    const fb = fallbackData.replays[String(trainNo)];
    if (fb) return { ...fb, _isFallback: true };
    const dynamicReplay = synthesizeReplay(trainNo, date);
    if (dynamicReplay) return dynamicReplay;
    throw new Error(`No recorded journey available for train ${trainNo} right now`);
  }

  const url = `${API_BASE}/replay?train_no=${trainNo}&date=${date}`;
  try {
    const res = await fetchWithTimeout(url, {}, 8000); // longer timeout for replay
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok || !contentType.includes('application/json')) {
      const msg = await parseApiError(res);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.message === 'TIMEOUT' || err.message === 'Failed to fetch' || !err.status || err.status === 404 || err.status >= 500) {
      const fb = fallbackData.replays[String(trainNo)];
      if (fb) return { ...fb, _isFallback: true };

      const dynamicReplay = synthesizeReplay(trainNo, date);
      if (dynamicReplay) return dynamicReplay;

      throw new Error(`No recorded journey available for train ${trainNo} right now`);
    }
    throw err;
  }
}

