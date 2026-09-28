/**
 * snapPositionToRoute.js
 * Arc-length-parameterized interpolation along an ordered coordinate array.
 * Per spec 06 §2: used ONLY for map display, never as a model input.
 *
 * @param {Array<[number,number]>} coords  Ordered [lat, lon] points along the section
 * @param {number}                 ratio   Progress 0→1 along the section
 * @returns {{lat:number, lon:number}|null}
 */
export function snapPositionToRoute(coords, ratio) {
  if (!coords || coords.length === 0) return null;

  // Filter out any null, undefined, or coordinates outside India (e.g. Null Island [0,0] off Africa)
  const valid = coords.filter(
    pt => Array.isArray(pt) && pt.length >= 2 &&
          typeof pt[0] === 'number' && !isNaN(pt[0]) &&
          typeof pt[1] === 'number' && !isNaN(pt[1]) &&
          pt[0] > 5 && pt[0] < 40 && pt[1] > 60 && pt[1] < 100
  );

  if (valid.length === 0) return null;
  if (valid.length === 1) return { lat: valid[0][0], lon: valid[0][1] };

  const r = Math.max(0, Math.min(1, ratio));

  // Compute segment lengths
  const segments = [];
  let totalLen = 0;
  for (let i = 0; i < valid.length - 1; i++) {
    const d = haversine(valid[i], valid[i + 1]);
    segments.push(d);
    totalLen += d;
  }

  if (totalLen === 0) return { lat: valid[0][0], lon: valid[0][1] };

  const target = r * totalLen;
  let cumulative = 0;

  for (let i = 0; i < segments.length; i++) {
    if (cumulative + segments[i] >= target) {
      const t = segments[i] === 0 ? 0 : (target - cumulative) / segments[i];
      const a = valid[i];
      const b = valid[i + 1];
      return {
        lat: a[0] + t * (b[0] - a[0]),
        lon: a[1] + t * (b[1] - a[1]),
      };
    }
    cumulative += segments[i];
  }

  // Clamp to end
  const last = valid[valid.length - 1];
  return { lat: last[0], lon: last[1] };
}

/** Haversine distance in km between two [lat,lon] points */
function haversine([lat1, lon1], [lat2, lon2]) {
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function toRad(deg) { return (deg * Math.PI) / 180; }
