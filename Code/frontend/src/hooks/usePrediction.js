import { useState, useEffect, useRef } from 'react';
import { fetchPrediction } from '../utils/apiClient';

/**
 * usePrediction — fetches a prediction for the given trainNo.
 * Handles loading, error, fallback, and what-if overrides.
 */
export function usePrediction(trainNo, whatIf = null, enableModelB = null) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);
  const abortRef = useRef(false);

  useEffect(() => {
    if (!trainNo) { setData(null); setError(null); return; }
    abortRef.current = false;
    setLoading(true);
    setError(null);
    setData(null);

    fetchPrediction(trainNo, whatIf, enableModelB)
      .then(res => { if (!abortRef.current) setData(res); })
      .catch(err => { if (!abortRef.current) setError(err.message); })
      .finally(() => { if (!abortRef.current) setLoading(false); });

    return () => { abortRef.current = true; };
  }, [trainNo, JSON.stringify(whatIf), enableModelB]);

  return { data, loading, error };
}
