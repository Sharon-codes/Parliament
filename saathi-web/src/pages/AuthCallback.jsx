import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    
    if (token) {
      // Neural Injection: Save the sovereign token
      localStorage.setItem("saathi-session-v2", token);
      
      // Navigate to welcome to trigger the routing logic in App.jsx
      // App.jsx will automatically send them to /dashboard if they are a returning user
      // due to the backend markings we added in main.py.
      setTimeout(() => {
        navigate("/welcome", { replace: true });
        window.location.reload(); // Hard reset to ensure App.jsx reads the new token
      }, 500);
    } else {
      // No token found, portal failure
      navigate("/", { replace: true });
    }
  }, [searchParams, navigate]);

  return (
    <div className="connect-shell immersive-zen">
      <div className="zen-bg-mesh" />
      <section className="connect-card glass-panel">
        <div className="brand-pill">Neural Bridge v3.6</div>
        <h1>Completing Identity Link</h1>
        <p>Restoring your sovereign session and preparing the orchestrator.</p>
        <div className="loading-spinner-zen" style={{ marginTop: '20px' }} />
      </section>
    </div>
  );
}
