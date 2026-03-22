const GUEST_IDENTITY_KEY = "sportlytics.guest.identity";

export function getGuestIdentity(): string {
  if (typeof window === "undefined") return "user_00000";

  const existing = window.localStorage.getItem(GUEST_IDENTITY_KEY)?.trim();
  if (existing) return existing;

  const suffix = Math.floor(10000 + Math.random() * 90000);
  const identity = `user_${suffix}`;
  window.localStorage.setItem(GUEST_IDENTITY_KEY, identity);
  return identity;
}
