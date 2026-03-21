export type AuthUser = {
  id: number;
  email: string;
  display_name: string;
  is_premium?: boolean;
  plan_code?: string | null;
  status?: string | null;
  access_source?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
};

const USER_KEY = 'sportlytics.auth.user';

export function getAuthToken(): string | null {
  return null;
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function setAuthSession(_token: string | null, user: AuthUser) {
  setStoredUser(user);
}

export function clearAuthSession() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(USER_KEY);
}
