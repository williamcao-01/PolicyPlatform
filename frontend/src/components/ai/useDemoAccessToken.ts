import { useEffect, useState } from 'react';
import { api, type AuthResponse } from '../../api';

const DEMO_AUTH_STORAGE_KEY = 'policy_governance_demo_auth';

type TokenState = {
  accessToken: string;
  loading: boolean;
  error: string;
};

export function useDemoAccessToken(): TokenState {
  const [accessToken, setAccessToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    async function loadToken() {
      setLoading(true);
      setError('');
      try {
        const stored = readStoredAuth();
        if (stored?.access_token) {
          try {
            await api.me(stored.access_token);
            if (active) setAccessToken(stored.access_token);
            return;
          } catch {
            window.localStorage.removeItem(DEMO_AUTH_STORAGE_KEY);
          }
        }
        const next = await api.login('admin', 'admin123');
        window.localStorage.setItem(DEMO_AUTH_STORAGE_KEY, JSON.stringify(next));
        if (active) setAccessToken(next.access_token);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : '认证失败');
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadToken();
    return () => {
      active = false;
    };
  }, []);

  return { accessToken, loading, error };
}

function readStoredAuth(): AuthResponse | null {
  try {
    const raw = window.localStorage.getItem(DEMO_AUTH_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthResponse) : null;
  } catch {
    return null;
  }
}
