import { supabase } from '@/lib/supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

let cachedToken: string | null = null;
let tokenExpiry = 0;
let tokenPromise: Promise<string | null> | null = null;

async function getValidToken(): Promise<string | null> {
  if (cachedToken && Date.now() < tokenExpiry) {
    return cachedToken;
  }
  
  if (tokenPromise) {
    return tokenPromise;
  }
  
  tokenPromise = supabase.auth.getSession().then(({ data }) => {
    cachedToken = data.session?.access_token || null;
    tokenExpiry = data.session?.expires_at ? (data.session.expires_at * 1000) - 10000 : 0;
    tokenPromise = null;
    return cachedToken;
  }).catch(() => {
    tokenPromise = null;
    return null;
  });
  
  return tokenPromise;
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const token = await getValidToken();

  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error?.message || `API error: ${response.statusText}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}
