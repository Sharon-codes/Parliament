import { useEffect, useMemo, useState } from "react";
import { BrowserRouter as Router, Navigate, Route, Routes } from "react-router-dom";

import AuthPage from "./pages/AuthPage";
import AuthCallback from "./pages/AuthCallback";
import ConnectPage from "./pages/ConnectPage";
import Dashboard from "./pages/Dashboard";
import WelcomePage from "./pages/WelcomePage";
import { apiFetch } from "./lib/api";
import { supabase, supabaseConfigured } from "./lib/supabase";

function LoadingScreen({ text }) {
  return (
    <div className="connect-shell">
      <section className="connect-card">
        <div className="brand-pill">Saathi</div>
        <h1>{text}</h1>
        <p>Getting your workspace, preferences, and sessions ready.</p>
      </section>
    </div>
  );
}

function buildDemoSession() {
  return {
    access_token: "demo-token",
    user: {
      id: "demo-user",
      email: "demo@saathi.local",
      user_metadata: {
        full_name: "Demo User",
      },
    },
    demo: true,
  };
}

export default function App() {
  const [session, setSession] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [welcomeForm, setWelcomeForm] = useState({
    full_name: "",
    language: "English",
    voice_gender: "female",
  });
  const [welcomeSaving, setWelcomeSaving] = useState(false);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [workspaceStatus, setWorkspaceStatus] = useState(null);
  const [mobileLandingSeen, setMobileLandingSeen] = useState(false);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 1024;

  useEffect(() => {
    // Check for session token in URL (from Google Callback)
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      const sessionData = { access_token: urlToken, user: {} };
      setSession(sessionData);
      window.localStorage.setItem("saathi-session-v2", JSON.stringify(sessionData));
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
      setAuthReady(true);
      return;
    }

    const saved = window.localStorage.getItem("saathi-session-v2");
    if (saved) {
      setSession(JSON.parse(saved));
    }
    setAuthReady(true);
  }, []);

  useEffect(() => {
    if (!session) {
      setProfile(null);
      return;
    }

    if (profile) return;

    setProfileLoading(true);
    Promise.all([
      apiFetch("/api/profile", { session }),
      apiFetch("/api/workspace/status", { session }).catch(() => ({ connected: false })),
    ])
      .then(([profileData, workspaceData]) => {
        setProfile(profileData);
        setWorkspaceStatus(workspaceData);
        setWelcomeForm({
          full_name: profileData.full_name || profileData.name || "",
          language: profileData.language || "English",
          voice_gender: profileData.voice_gender || "female",
        });
      })
      .finally(() => setProfileLoading(false));
  }, [session]);

  const nextRoute = useMemo(() => {
    if (isMobile && !mobileLandingSeen) return "/";
    if (!session) return "/";
    if (!profile?.onboarding_completed) return "/welcome";
    return "/dashboard";
  }, [isMobile, mobileLandingSeen, session, profile]);

  async function handleGoogleAuth(mode = "signup") {
    setAuthLoading(true);
    try {
      const { url } = await apiFetch(`/api/auth/google/url?mode=${mode}`, { session });
      if (url) window.location.href = url;
    } catch (err) {
      console.error("AUTH URL ERROR:", err);
      alert("Failed to reach Neural Gateway. Start the API first.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleSignOut() {
    window.localStorage.removeItem("saathi-session-v2");
    setSession(null);
    setProfile(null);
  }

  async function handleSaveWelcome() {
    setWelcomeSaving(true);
    try {
      const updated = await apiFetch("/api/profile", {
        session,
        method: "POST",
        body: {
          ...welcomeForm,
          onboarding_completed: true,
        },
      });
      setProfile(updated);
    } catch (error) {
      console.error(error);
    } finally {
      setWelcomeSaving(false);
    }
  }

  async function handleConnectWorkspace() {
    setWorkspaceLoading(true);
    try {
      const data = await apiFetch("/api/workspace/connect", { session });
      window.location.href = data.url;
    } catch (error) {
      setWorkspaceStatus((current) => ({ ...(current || {}), error: error.message }));
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function handleSkipWelcome() {
    await handleSaveWelcome();
  }

  if (!authReady) {
    return <LoadingScreen text="Restoring your session…" />;
  }

  return (
    <Router>
      <div className="app-root">
        <Routes>
          <Route
            path="/"
            element={
              <AuthPage 
                loading={authLoading} 
                onGoogleAuth={handleGoogleAuth} 
                session={session}
                profile={profile}
                onProceed={() => { 
                  if(isMobile) setMobileLandingSeen(true); 
                  // If we have a session and profile is done, we can allow manual entry to dashboard via a button in AuthPage
                }}
              />
            }
          />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route
            path="/welcome"
            element={
              !session ? (
                <Navigate to="/" replace />
              ) : profileLoading && !profile ? (
                <LoadingScreen text="Loading your welcome setup…" />
              ) : profile?.onboarding_completed ? (
                <Navigate to="/dashboard" replace />
              ) : (
                <WelcomePage
                  profile={profile}
                  saving={welcomeSaving}
                  workspaceLoading={workspaceLoading}
                  workspaceStatus={workspaceStatus}
                  form={welcomeForm}
                  setForm={setWelcomeForm}
                  onSave={handleSaveWelcome}
                  onConnectWorkspace={handleConnectWorkspace}
                  onSkip={handleSkipWelcome}
                />
              )
            }
          />
          <Route
            path="/dashboard"
            element={
              !session ? (
                <Navigate to="/" replace />
              ) : profileLoading && !profile ? (
                <LoadingScreen text="Opening your dashboard…" />
              ) : !profile?.onboarding_completed ? (
                <Navigate to="/welcome" replace />
              ) : (
                <Dashboard session={session} profile={profile} setProfile={setProfile} onSignOut={handleSignOut} />
              )
            }
          />
          <Route
            path="/connect"
            element={
              !session ? (
                <AuthPage loading={authLoading} onGoogleAuth={handleGoogleAuth} supabaseConfigured={supabaseConfigured} />
              ) : profileLoading && !profile ? (
                <LoadingScreen text="Opening mobile access…" />
              ) : !profile?.onboarding_completed ? (
                <Navigate to="/welcome" replace />
              ) : (
                <ConnectPage
                  shareSessionId={new URLSearchParams(window.location.search).get("session")}
                  onOpenDashboard={() => {
                    const suffix = window.location.search || "";
                    window.location.href = `/dashboard${suffix}`;
                  }}
                />
              )
            }
          />
        </Routes>
      </div>
    </Router>
  );
}
