import { Smartphone, ArrowLeft, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

export default function ConnectPage({ onBack }) {
  const currentUrl = window.location.origin;

  return (
    <div className="wabi-shell" style={{ alignItems: 'center', justifyContent: 'center', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <button className="pill-btn secondary" onClick={onBack} style={{ position: 'absolute', top: '40px', left: '40px', padding: '12px 24px' }}>
        <ArrowLeft size={18} style={{ marginRight: '8px' }} />
        Back
      </button>

      <motion.section 
        className="wabi-card"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ maxWidth: '500px', width: '100%', padding: '60px', textAlign: 'center' }}
      >
        <div style={{ marginBottom: '32px', color: '#1c1917' }}>
          <Smartphone size={64} style={{ margin: '0 auto' }} />
        </div>
        
        <h1 className="serif" style={{ fontSize: '3rem', marginBottom: '16px' }}>Saathi Sync</h1>
        <p className="hero-subtitle" style={{ fontSize: '1rem', marginBottom: '40px' }}>
          Your Neural Brain, now in your pocket. Scan to link your smartphone instantly.
        </p>

        <div style={{ background: '#f5f5f4', padding: '30px', borderRadius: '32px', border: '1px solid #e7e5e4', display: 'inline-block', marginBottom: '40px' }}>
          <img 
            src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(currentUrl)}`} 
            alt="Mobile Link QR" 
            style={{ borderRadius: '12px' }}
          />
          <div style={{ marginTop: '20px', fontWeight: '800', textTransform: 'uppercase', fontSize: '0.7rem', color: '#78716c', letterSpacing: '0.1em' }}>
            {currentUrl.replace("https://", "")}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'center', opacity: 0.6, fontSize: '0.8rem' }}>
          <CheckCircle2 size={14} />
          <span>Sovereign Bridge v38.8 Active</span>
        </div>
      </motion.section>

      <footer style={{ marginTop: '80px', textAlign: 'center', color: '#a8a29e', fontSize: '0.8rem' }}>
        <p className="serif" style={{ fontStyle: 'italic' }}>Made by Khushi and Sharon.</p>
        <p style={{ opacity: 0.6 }}>They both fought the great Antigravity to make it. ⚔️</p>
      </footer>
    </div>
  );
}
