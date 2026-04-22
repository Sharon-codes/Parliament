const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_BASE =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") ||
  (isLocalHost
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin);

export const WEB_URL =
  import.meta.env.VITE_WEB_URL?.replace(/\/$/, "") ||
  window.location.origin;

export const SUPPORTED_LANGUAGES = ["English", "Hindi", "Tamil", "Kannada", "Telugu"];

export const LANGUAGE_LOCALES = {
  English: "en-IN",
  Hindi: "hi-IN",
  Tamil: "ta-IN",
  Kannada: "kn-IN",
  Telugu: "te-IN",
};

export const WAKE_PHRASES = ["hey saathi", "oh saathi", "hey sathi", "oh sathi"];
