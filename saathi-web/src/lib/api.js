import { API_BASE } from "./config";

export async function apiFetch(path, { session, method = "GET", body, headers = {}, signal } = {}) {
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 1024;
  const finalHeaders = { 
    ...headers,
    "Bypass-Tunnel-Reminder": "true",
    "bypass-tunnel-reminder": "true",
    "X-Saathi-Origin": isMobile ? "mobile" : "laptop"
  };
  
  const isFormData = body instanceof FormData;
  if (body !== undefined && !isFormData) {
    finalHeaders["Content-Type"] = "application/json";
  }

  // Support both old object session and new string token
  const token = typeof session === "string" ? session : session?.access_token;
  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: finalHeaders,
    body: isFormData ? body : (body !== undefined ? JSON.stringify(body) : undefined),
    signal,
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (response.status === 401) {
    // Neural Guard: Force logout on invalid session
    console.warn("Session expired or invalid. Purging local state.");
    window.localStorage.removeItem("saathi-session-v2");
    // Only refresh if not already on the auth page to avoid loops
    if (!window.location.pathname.startsWith("/auth") && window.location.pathname !== "/") {
       window.location.href = "/";
    }
  }

  if (!response.ok) {
    const message = typeof data === "string" ? data : data?.detail || data?.message || "Request failed";
    throw new Error(message);
  }

  return data;
}

export function getAvatarUrl(name) {
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'Saathi')}&background=2e5145&color=fff`;
}

export function formatSessionDate(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true }).replace(',', '');
}
