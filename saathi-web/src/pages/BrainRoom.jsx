import React, { useState, useEffect } from "react";
import { 
  Plus, Brain, ArrowLeft, Trash, Calendar, Globe, 
  Settings, LoaderCircle, CheckCircle2, Clock, ShieldCheck
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { apiFetch } from "../lib/api";

const BrainRoom = ({ profile, session, onBack }) => {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newMemory, setNewMemory] = useState("");
  const [deadlines, setDeadlines] = useState([]);
  const [newDeadline, setNewDeadline] = useState({ title: "", date: "" });

  useEffect(() => {
    loadBrainData();
  }, []);

  const loadBrainData = async () => {
    try {
      const [mems, deads] = await Promise.all([
        apiFetch("/api/memory", { session }),
        apiFetch("/api/workspace/deadlines", { session }).catch(() => [])
      ]);
      setMemories(mems);
      setDeadlines(deads);
    } finally {
      setLoading(false);
    }
  };

  const handleAddDeadline = async () => {
    if (!newDeadline.title || !newDeadline.date) return;
    const res = await apiFetch("/api/workspace/deadlines", {
      session,
      method: "POST",
      body: newDeadline
    });
    setDeadlines([res, ...deadlines]);
    setNewDeadline({ title: "", date: "" });
  };

  const handleDeleteDeadline = async (id) => {
    await apiFetch(`/api/workspace/deadlines/${id}`, { session, method: "DELETE" });
    setDeadlines(deadlines.filter(d => d.id !== id));
  };

  const handleAddMemory = async () => {
    if (!newMemory.trim()) return;
    const res = await apiFetch("/api/memory", {
      session,
      method: "POST",
      body: { text: newMemory }
    });
    setMemories([res, ...memories]);
    setNewMemory("");
  };

  const handleDeleteMemory = async (id) => {
    await apiFetch(`/api/memory/${id}`, { session, method: "DELETE" });
    setMemories(memories.filter(m => m.id !== id));
  };

  return (
    <div className="wabi-shell sovereign-bg">
      <header style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '60px', paddingTop: '40px' }}>
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '16px' }}
        >
          <Brain size={48} className="neural-glow" />
          <h2 className="serif" style={{ fontSize: '3rem', color: 'white' }}>Saathi</h2>
        </motion.div>
        <div className="hero-tag" style={{ color: '#94a3b8', fontSize: '1rem' }}>
          <ShieldCheck size={16} /> Identity: {profile.full_name} — Secure Neural Core
        </div>
        <button className="pill-btn secondary glass-btn" onClick={onBack} style={{ padding: '12px 32px', marginTop: '24px' }}>
          <ArrowLeft size={16} style={{ marginRight: '10px' }} />
          Return to Command Center
        </button>
      </header>

      <div className="brain-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '32px', padding: '0 24px' }}>
        <motion.section initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <div className="hero-tag" style={{ color: 'var(--saathi-primary)' }}>Neural Synapses (Long-Term Memory)</div>
          <div className="wabi-card glass-card" style={{ marginBottom: '24px', display: 'flex', gap: '16px', padding: '16px 24px' }}>
            <input 
              className="wabi-input" 
              placeholder="Inject new knowledge..." 
              style={{ background: 'none' }}
              value={newMemory}
              onChange={(e) => setNewMemory(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddMemory()}
            />
            <button className="pill-btn primary-gradient" onClick={handleAddMemory} style={{ padding: '12px' }}>
              <Plus size={20} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {memories.map(m => (
              <motion.div layout key={m.id} className="wabi-card glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <p style={{ fontSize: '1.05rem', color: '#e2e8f0' }}>{m.text}</p>
                <button 
                  onClick={() => handleDeleteMemory(m.id)} 
                  style={{ background: 'none', border: 'none', color: '#64748b', transition: 'color 0.2s' }}
                  className="hover-danger"
                >
                  <Trash size={18} />
                </button>
              </motion.div>
            ))}
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
          <div className="hero-tag" style={{ color: 'var(--saathi-primary)' }}>Sovereign Priorities</div>
          
          <div className="wabi-card glass-card" style={{ marginBottom: '24px', display: 'flex', flexDirection: 'column', gap: '16px', padding: '24px' }}>
            <input 
              className="wabi-input" 
              placeholder="Priority Objective" 
              value={newDeadline.title}
              onChange={(e) => setNewDeadline({...newDeadline, title: e.target.value})}
            />
            <div style={{ display: 'flex', gap: '12px' }}>
              <input 
                type="date"
                className="wabi-input" 
                style={{ flex: 1 }}
                value={newDeadline.date}
                onChange={(e) => setNewDeadline({...newDeadline, date: e.target.value})}
              />
              <button className="pill-btn primary-gradient" onClick={handleAddDeadline}>
                <span>Anchor Objective</span>
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {deadlines.map((d, i) => (
              <motion.div layout key={i} className="wabi-card glass-card" style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ padding: '10px', background: 'rgba(99, 102, 241, 0.1)', color: 'var(--saathi-primary)', borderRadius: '12px' }}>
                  <Calendar size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 className="serif" style={{ fontSize: '1.15rem', color: 'white', marginBottom: '2px' }}>{d.title}</h4>
                  <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
                    {d.status === "critical" ? "🚨 " : "⏰ "} 
                    {d.due_date} • {d.source_email_id === 'manual' ? 'Manual' : 'System Sync'}
                  </p>
                </div>
                <button 
                  onClick={() => handleDeleteDeadline(d.id)} 
                  className="hover-danger"
                  style={{ background: 'none', border: 'none', color: '#64748b', padding: '8px' }}
                >
                  <Trash size={16} />
                </button>
              </motion.div>
            ))}
            {deadlines.length === 0 && (
              <div className="wabi-card glass-card" style={{ textAlign: 'center', opacity: 0.5, padding: '48px' }}>
                <CheckCircle2 size={32} style={{ margin: '0 auto 16px', color: '#10b981' }} />
                <p>Strategic goals clear. No pending priorities.</p>
              </div>
            )}
          </div>
        </motion.section>
      </div>

      <footer style={{ marginTop: 'auto', padding: '60px 0', textAlign: 'center', borderTop: '1px solid var(--saathi-border)' }}>
        <p className="serif" style={{ fontStyle: 'italic', color: '#94a3b8', fontSize: '0.95rem' }}>Forged by Khushi and Sharon.</p>
        <p style={{ opacity: 0.5, fontSize: '0.75rem', marginTop: '4px' }}>The Sovereign Core vs. The Void. ⚔️</p>
      </footer>

      <style>{`
        .sovereign-bg { background: #0f172a; min-height: 100vh; color: white; }
        .glass-card { background: rgba(30, 41, 59, 0.7) !important; backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1) !important; }
        .neural-glow { filter: drop-shadow(0 0 10px #6366f1); color: #6366f1; }
        .glass-btn { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); }
        .glass-btn:hover { background: rgba(255,255,255,0.1); border-color: #6366f1; }
        .primary-gradient { background: linear-gradient(135deg, #6366f1, #4f46e5) !important; color: white !important; }
        .hover-danger:hover { color: #f87171 !important; transform: scale(1.1); }
      `}</style>
    </div>
  );
};

export default BrainRoom;

