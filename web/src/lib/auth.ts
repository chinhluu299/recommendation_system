export type AuthUser = {
  name: string;
  email: string;
  token: string;
  userId: number;
  externalUserId: string | null;
};

export const AUTH_STORAGE_KEY = "vibe.auth.user";
export const AUTH_STATE_CHANGE_EVENT = "vibe-auth-state-change";

const isBrowser = () => typeof window !== "undefined";

export const readStoredAuthUser = (): AuthUser | null => {
  if (!isBrowser()) {
    return null;
  }

  const storedValue =
    window.localStorage.getItem(AUTH_STORAGE_KEY) ??
    window.sessionStorage.getItem(AUTH_STORAGE_KEY);

  if (!storedValue) {
    return null;
  }

  try {
    return JSON.parse(storedValue) as AuthUser;
  } catch {
    return null;
  }
};

export const writeStoredAuthUser = (
  user: AuthUser,
  rememberMe: boolean = true,
): void => {
  if (!isBrowser()) {
    return;
  }

  const storage = rememberMe ? window.localStorage : window.sessionStorage;
  const fallbackStorage = rememberMe
    ? window.sessionStorage
    : window.localStorage;

  storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
  fallbackStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT));
};

export const clearStoredAuthUser = (): void => {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT));
};

export const getAuthToken = (): string | null => {
  return readStoredAuthUser()?.token ?? null;
};

export const getUserInitials = (user: AuthUser): string => {
  const parts = user.name.trim().split(/\s+/).filter(Boolean);

  if (parts.length === 0) {
    return (user.email || user.externalUserId || "U").slice(0, 2).toUpperCase();
  }

  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
};
