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
    <div className="wabi-shell">
      <header style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '80px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
          <Brain size={32} />
          <h2 className="serif" style={{ fontSize: '2.5rem' }}>Saathi</h2>
        </div>
        <div className="hero-tag">Identity: {profile.full_name} — Neural Core</div>
        <button className="pill-btn secondary" onClick={onBack} style={{ padding: '8px 24px', marginTop: '20px', fontSize: '0.8rem' }}>
          <ArrowLeft size={14} style={{ marginRight: '8px' }} />
          Return to Session
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '40px' }}>
        <section>
          <div className="hero-tag">Long-Term Memory</div>
          <div className="wabi-card" style={{ marginBottom: '32px', display: 'flex', gap: '16px', padding: '12px 24px' }}>
            <input 
              className="wabi-input" 
              placeholder="Anchor a new snippet..." 
              style={{ background: 'none' }}
              value={newMemory}
              onChange={(e) => setNewMemory(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddMemory()}
            />
            <button className="pill-btn" onClick={handleAddMemory} style={{ padding: '12px' }}>
              <Plus size={18} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {memories.map(m => (
              <div key={m.id} className="wabi-card" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <p style={{ fontSize: '1.1rem' }}>{m.text}</p>
                <button 
                  onClick={() => handleDeleteMemory(m.id)} 
                  style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer' }}
                >
                  <Trash size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="hero-tag">Active Priorities</div>
          
          <div className="wabi-card" style={{ marginBottom: '32px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input 
              className="wabi-input" 
              placeholder="Priority Title (e.g. Maths Test)" 
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
              <button className="pill-btn" onClick={handleAddDeadline}>
                <Plus size={18} />
                <span>Anchor</span>
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {deadlines.map((d, i) => (
              <div key={i} className="wabi-card" style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
                <div style={{ padding: '12px', background: '#e7e5e4', borderRadius: '12px' }}>
                  <Calendar size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 className="serif" style={{ fontSize: '1.2rem', marginBottom: '4px' }}>{d.title}</h4>
                  <p style={{ color: '#78716c', fontSize: '0.85rem' }}>
                    {d.status === "critical" ? "🚨 " : "⏰ "} 
                    {d.due_date} • {d.source_email_id === 'manual' ? 'Manual' : 'Workspace'}
                  </p>
                </div>
                <button 
                  onClick={() => handleDeleteDeadline(d.id)} 
                  style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: '4px' }}
                >
                  <Trash size={14} />
                </button>
              </div>
            ))}
            {deadlines.length === 0 && (
              <div className="wabi-card" style={{ textAlign: 'center', opacity: 0.5, padding: '60px' }}>
                <CheckCircle2 size={32} style={{ margin: '0 auto 16px' }} />
                <p>All Workspace goals achieved.</p>
              </div>
            )}
          </div>
        </section>
      </div>

      <footer style={{ marginTop: 'auto', paddingTop: '80px', textAlign: 'center', color: '#a8a29e', fontSize: '0.8rem' }}>
        <p className="serif" style={{ fontStyle: 'italic' }}>Made by Khushi and Sharon.</p>
        <p style={{ opacity: 0.6 }}>They both fought the great Antigravity to make it. ⚔️</p>
      </footer>
    </div>
  );
};

export default BrainRoom;


