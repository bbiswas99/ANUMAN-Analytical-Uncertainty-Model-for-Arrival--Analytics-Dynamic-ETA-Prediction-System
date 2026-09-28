import { useState, useEffect, useRef } from 'react';
import { fetchExplanation } from '../utils/apiClient';

export function useExplanation(trainNo) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const abortRef = useRef(false);

  useEffect(() => {
    if (!trainNo) { setData(null); setError(null); return; }
    abortRef.current = false;
    setLoading(true);
    setError(null);
    setData(null);

    fetchExplanation(trainNo)
      .then(res => { if (!abortRef.current) setData(res); })
      .catch(err => { if (!abortRef.current) setError(err.message); })
      .finally(() => { if (!abortRef.current) setLoading(false); });

    return () => { abortRef.current = true; };
  }, [trainNo]);

  return { data, loading, error };
}
