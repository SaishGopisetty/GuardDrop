import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const SESSION_STORAGE_KEY = "gd_session";
export const LEGACY_USER_STORAGE_KEY = "gd_user";

const api = axios.create({
  baseURL: API_BASE_URL,
});

function canUseStorage() {
  return typeof window !== "undefined" && !!window.localStorage;
}

export function readStoredSession() {
  if (!canUseStorage()) return null;

  const savedSession = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!savedSession) {
    window.localStorage.removeItem(LEGACY_USER_STORAGE_KEY);
    return null;
  }

  try {
    const parsed = JSON.parse(savedSession);
    if (!parsed?.access_token || !parsed?.user?.id) {
      clearStoredSession();
      return null;
    }
    return parsed;
  } catch {
    clearStoredSession();
    return null;
  }
}

export function writeStoredSession(session) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  window.localStorage.removeItem(LEGACY_USER_STORAGE_KEY);
}

export function clearStoredSession() {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_USER_STORAGE_KEY);
}

export function getWebSocketUrl(userId, accessToken) {
  const url = new URL(`/ws/${userId}`, API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", accessToken);
  return url.toString();
}

api.interceptors.request.use((config) => {
  const session = readStoredSession();
  if (session?.access_token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredSession();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("guarddrop:unauthorized"));
      }
    }
    return Promise.reject(error);
  }
);

export default api;
