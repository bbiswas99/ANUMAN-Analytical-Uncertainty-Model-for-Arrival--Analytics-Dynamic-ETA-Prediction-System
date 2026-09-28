import { useState, useRef } from 'react';
import { fetchReplay } from '../utils/apiClient';

export function useReplay() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const retryCount = useRef(0);

  async function load(trainNo, date) {
    setLoading(true);
    setError(null);
    setData(null);
    retryCount.current = 0;

    const attempt = async () => {
      try {
        const res = await fetchReplay(trainNo, date);
        setData(res);
      } catch (err) {
        if (retryCount.current === 0) {
          retryCount.current = 1;
          await new Promise(r => setTimeout(r, 1500));
          try {
            const res = await fetchReplay(trainNo, date);
            setData(res);
          } catch (err2) {
            setError(err2.message);
          }
        } else {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    };
    await attempt();
  }

  function reset() { setData(null); setError(null); }

  return { data, loading, error, load, reset };
}
