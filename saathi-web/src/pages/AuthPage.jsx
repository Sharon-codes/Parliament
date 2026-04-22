import { motion } from "framer-motion";
import { Brain, ChevronRight, Zap, Globe, LayoutDashboard, Mic2 } from "lucide-react";

export default function AuthPage({ loading, onGoogleAuth, onProceed }) {
  const isMobile = window.innerWidth < 1024;
  const hasSession = !!window.localStorage.getItem("saathi-session-v2");

  return (
    <div className="wabi-shell">
      <nav className="nav-brand">
        <Brain size={32} />
        <h2>Saathi</h2>
      </nav>
      <main className="landing-hero">
        <motion.div
           initial={{ opacity: 0, y: 30 }}
           animate={{ opacity: 1, y: 0 }}
           transition={{ duration: 1, ease: [0.23, 1, 0.32, 1] }}
        >
          <div className="hero-tag">Session v38.0 — Neural Wabi-Sabi</div>
          <h1 className="hero-title">
            The soul of your <br />
            <span className="serif" style={{ fontStyle: 'italic' }}>digital day.</span>
          </h1>
          <p className="hero-subtitle">
            Saathi is an organic intelligence layer that simplifies your Gmail, 
            Calendar, and Local Desktop into a single, breathing interface.
          </p>

          <div style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
            {hasSession ? (
              <button className="pill-btn" onClick={() => window.location.href = "/dashboard"}>
                <span>Enter Dashboard</span>
                <ChevronRight size={18} />
              </button>
            ) : (
              <>
                <button className="pill-btn" onClick={() => onGoogleAuth("signup")} disabled={loading}>
                  <span>{loading ? "Waking..." : "Begin Session"}</span>
                  <ChevronRight size={18} />
                </button>
                <button className="pill-btn secondary" onClick={() => onGoogleAuth("login")}>
                  Sign In
                </button>
              </>
            )}
          </div>
        </motion.div>
      </main>

      <section style={{ maxWidth: '1200px', margin: '120px auto 0', width: '100%' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '32px' }}>
          <div className="wabi-card">
            <Zap size={24} style={{ marginBottom: '20px', color: '#78716c' }} />
            <h4 className="serif" style={{ fontSize: '1.4rem', marginBottom: '12px' }}>Contextual Stillness</h4>
            <p style={{ color: '#78716c', fontSize: '0.95rem' }}>Saathi anchors your tasks and memories, nudging you only when it matters.</p>
          </div>
          <div className="wabi-card">
            <Globe size={24} style={{ marginBottom: '20px', color: '#78716c' }} />
            <h4 className="serif" style={{ fontSize: '1.4rem', marginBottom: '12px' }}>Infinite Insight</h4>
            <p style={{ color: '#78716c', fontSize: '0.95rem' }}>Direct bridge to web intelligence and research, distilled instantly.</p>
          </div>
          <div className="wabi-card">
            <Mic2 size={24} style={{ marginBottom: '20px', color: '#78716c' }} />
            <h4 className="serif" style={{ fontSize: '1.4rem', marginBottom: '12px' }}>Human Resonance</h4>
            <p style={{ color: '#78716c', fontSize: '0.95rem' }}>Voice-first interaction that feels like a conversation, not a command.</p>
          </div>
        </div>
      </section>

      <footer style={{ marginTop: 'auto', paddingTop: '80px', textAlign: 'center', color: '#a8a29e', fontSize: '0.85rem' }}>
        <p className="serif" style={{ fontStyle: 'italic', marginBottom: '8px' }}>
          Made with resonance by Khushi and Sharon.
        </p>
        <p style={{ opacity: 0.7 }}>
          They both fought the great Antigravity to bring this soul to life. ⚔️
        </p>
        <p style={{ marginTop: '20px', fontSize: '0.7rem' }}>SAATHI v38.1 • 2026</p>
      </footer>
    </div>
  );
}
