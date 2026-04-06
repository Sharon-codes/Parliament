import React, { useState, useEffect, useRef } from 'react';
import {
  Send, Clock, Settings, BookOpen, Mic, MicOff,
  Volume2, VolumeX, X, Moon, Sun, Plus, AlignLeft, Calendar
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ── Code block parser (no external deps) ─────────────────────────────────────
function FormattedMessage({ text }) {
  const segments = text.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {segments.map((seg, i) => {
        if (seg.startsWith('```')) {
          const raw = seg.slice(3, -3);
          const nl = raw.indexOf('\n');
          const lang = nl > -1 ? raw.slice(0, nl).trim() : '';
          const code = nl > -1 ? raw.slice(nl + 1) : raw;
          return (
            <pre key={i}>
              {lang && (
                <span style={{
                  display: 'block', fontSize: 9, letterSpacing: '0.14em',
                  textTransform: 'uppercase', color: 'var(--accent)',
                  marginBottom: 10, fontFamily: 'DM Sans, sans-serif'
                }}>{lang}</span>
              )}
              {code}
            </pre>
          );
        }
        // inline code pass
        const inline = seg.split(/(`[^`]+`)/g);
        return (
          <span key={i}>
            {inline.map((part, j) =>
              part.startsWith('`') && part.endsWith('`')
                ? <code key={j}>{part.slice(1, -1)}</code>
                : part
            )}
          </span>
        );
      })}
    </>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [query, setQuery]       = useState('');
  const [mode, setMode]         = useState('chat');
  const [sessionId, setSessionId] = useState(null);
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', text: 'Peace and welcome.\nHow may I assist you today?' }
  ]);
  const [sessions, setSessions] = useState([]);
  const [events, setEvents]     = useState([]);
  const [research, setResearch] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isDark, setIsDark]     = useState(false);
  const [userSettings, setUserSettings] = useState({
    name: 'Guest', interests: 'machine learning', language: 'English', theme: 'light'
  });
  const messagesEnd = useRef(null);

  // helpers
  const applyTheme = (dark) => {
    document.documentElement.classList.toggle('dark', dark);
    setIsDark(dark);
  };

  const fetchSessions = async () => {
    try {
      const r = await fetch('http://localhost:8000/api/sessions');
      const d = await r.json();
      setSessions(d.sessions || []);
    } catch {}
  };

  const loadSession = async (id) => {
    setSessionId(id);
    try {
      const r = await fetch(`http://localhost:8000/api/sessions/${id}`);
      const d = await r.json();
      setChatHistory(d.messages?.length
        ? d.messages
        : [{ role: 'ai', text: 'Peace and welcome.\nHow may I assist you today?' }]
      );
    } catch {}
  };

  const newChat = async () => {
    try {
      const r = await fetch('http://localhost:8000/api/sessions', { method: 'POST' });
      const d = await r.json();
      setSessionId(d.session_id);
      setChatHistory([{ role: 'ai', text: 'New session.\nWhat shall we explore?' }]);
      fetchSessions();
    } catch {}
  };

  const boot = () => {
    fetch('http://localhost:8000/api/settings')
      .then(r => r.json()).then(d => {
        setUserSettings(d);
        applyTheme(d.theme === 'dark');
      }).catch(() => {});
    fetch('http://localhost:8000/api/calendar')
      .then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {});
    fetch('http://localhost:8000/api/research')
      .then(r => r.json()).then(d => setResearch(d.papers || [])).catch(() => {});
    fetchSessions();
  };

  useEffect(() => { boot(); }, []);
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatHistory, isTyping]);

  const saveSettings = async (e) => {
    e.preventDefault();
    setShowSettings(false);
    try {
      await fetch('http://localhost:8000/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
      });
      boot();
    } catch {}
  };

  const toggleListen = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Voice not supported.'); return; }
    if (isListening) { setIsListening(false); return; }
    const rec = new SR();
    rec.lang = userSettings.language === 'Hindi' ? 'hi-IN' : 'en-US';
    setIsListening(true);
    rec.start();
    rec.onresult = e => { setQuery(e.results[0][0].transcript); setIsListening(false); };
    rec.onerror = () => setIsListening(false);
  };

  const speak = (text) => {
    if (!voiceEnabled || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text.replace(/```[\s\S]*?```/g, 'code block'));
    if (userSettings.language === 'Hindi') u.lang = 'hi-IN';
    window.speechSynthesis.speak(u);
  };

  const send = async (override) => {
    const text = override || query;
    if (!text.trim()) return;
    setChatHistory(h => [...h, { role: 'user', text }]);
    setQuery('');
    setIsTyping(true);
    try {
      const r = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, mode, session_id: sessionId })
      });
      const d = await r.json();
      if (d.session_id && d.session_id !== sessionId) setSessionId(d.session_id);
      setChatHistory(h => [...h, { role: 'ai', text: d.reply }]);
      speak(d.reply);
      fetchSessions();
    } catch {
      setChatHistory(h => [...h, { role: 'ai', text: 'Connection disrupted. Please verify the backend is running.' }]);
    }
    setIsTyping(false);
  };

  return (
    <div className="layout">

      {/* ── LEFT SIDEBAR ── */}
      <aside className="sidebar-l">
        <div className="sb-top">
          <div className="logo">
            साथी
            <span className="logo-kana">saathi</span>
          </div>

          <div className="sb-controls" style={{ marginTop: 16 }}>
            <button className="new-chat-btn" onClick={newChat}>
              <Plus size={13}/> New chat
            </button>
            <button className="icon-btn" onClick={() => applyTheme(!isDark)} title="Toggle theme">
              {isDark ? <Sun size={14}/> : <Moon size={14}/>}
            </button>
            <button className="icon-btn" onClick={() => setVoiceEnabled(v => !v)} title="Toggle voice"
              style={{ color: voiceEnabled ? 'var(--accent)' : undefined }}>
              {voiceEnabled ? <Volume2 size={14}/> : <VolumeX size={14}/>}
            </button>
            <button className="icon-btn" onClick={() => setShowSettings(true)} title="Settings">
              <Settings size={14}/>
            </button>
          </div>
        </div>

        <div className="sb-sessions">
          <span className="sb-section-title">History</span>
          {sessions.length === 0
            ? <p style={{ fontSize: 11, color: 'var(--dust)', padding: '4px 8px', fontStyle: 'italic' }}>
                No sessions yet.
              </p>
            : sessions.map(s => (
              <button
                key={s.session_id}
                className={`session-item ${sessionId === s.session_id ? 'active' : ''}`}
                onClick={() => loadSession(s.session_id)}
              >
                <AlignLeft size={11} style={{ flexShrink: 0, opacity: 0.4 }}/>
                <span>{s.title || 'Session'}</span>
              </button>
            ))
          }
        </div>
      </aside>

      {/* ── CENTER CHAT ── */}
      <main className="chat-main">

        {/* Top bar with mode switcher */}
        <div className="chat-topbar">
          <div className="mode-pill">
            {['chat', 'agent', 'search'].map(m => (
              <button
                key={m}
                className={`mode-opt ${mode === m ? 'active' : ''}`}
                onClick={() => setMode(m)}
              >
                {m === 'chat' ? 'Chat' : m === 'agent' ? 'Agent' : 'Search'}
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="messages">
          <AnimatePresence>
            {chatHistory.map((msg, i) => (
              <motion.div
                key={i}
                className={`msg-row ${msg.role}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
              >
                {msg.role === 'ai'
                  ? <div className="bubble-ai"><FormattedMessage text={msg.text}/></div>
                  : <div className="bubble-user">{msg.text}</div>
                }
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div className="typing-row" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="bubble-ai" style={{ paddingTop: 8 }}>
                <div className="typing"><span/><span/><span/></div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEnd}/>
        </div>

        {/* Input Dock */}
        <div className="input-dock">
          <div className="input-wrap">
            <input
              className="chat-input"
              autoFocus
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder={
                mode === 'agent'  ? 'Describe what to automate…' :
                mode === 'search' ? 'Search the live web…' :
                'Message Saathi…'
              }
            />
            <button
              className={`voice-btn ${isListening ? 'listening' : ''}`}
              onClick={toggleListen}
            >
              {isListening ? <Mic size={15}/> : <MicOff size={15}/>}
            </button>
            <button
              className="send-btn"
              onClick={() => send()}
              disabled={!query.trim()}
            >
              <Send size={15}/>
            </button>
          </div>
          <p style={{
            textAlign: 'center', marginTop: 12,
            fontSize: 10, color: 'var(--dust)', letterSpacing: '0.08em'
          }}>
            mode: {mode} · {userSettings.name}
          </p>
        </div>
      </main>

      {/* ── RIGHT PANEL ── */}
      <aside className="sidebar-r">

        {/* Schedule */}
        <div className="panel-section">
          <p className="panel-heading"><Calendar size={10}/> Schedule</p>
          {events.length === 0
            ? <p style={{ fontSize: 11, color: 'var(--dust)', fontStyle: 'italic' }}>Syncing…</p>
            : events.map(ev => (
              <div className="p-card" key={ev.id}>
                <h4>{ev.title}</h4>
                <p className="p-meta">
                  <span className="p-dot"/>
                  <Clock size={9}/> {ev.time}
                </p>
              </div>
            ))
          }
        </div>

        {/* Research Radar */}
        <div className="panel-section">
          <p className="panel-heading">
            <BookOpen size={10}/>
            {(userSettings?.interests || 'research').split(' ').slice(0, 2).join(' ')} radar
          </p>
          {research.length === 0
            ? <p style={{ fontSize: 11, color: 'var(--dust)', fontStyle: 'italic' }}>Scanning arXiv…</p>
            : research.map((r, i) => (
              <a href={r.link} target="_blank" rel="noreferrer" key={i} className="p-card">
                <h4>{r.title}</h4>
                <p className="p-meta">
                  <span className="p-dot"/>
                  arXiv · open access
                </p>
              </a>
            ))
          }
        </div>

      </aside>

      {/* ── SETTINGS MODAL ── */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setShowSettings(false); }}
          >
            <motion.div
              className="modal-panel"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h2>設定<br/><span style={{ fontFamily: 'DM Sans', fontSize: 13, fontWeight: 300, color: 'var(--stone)', letterSpacing: '0.06em' }}>preferences</span></h2>
                <button className="icon-btn" onClick={() => setShowSettings(false)}><X size={15}/></button>
              </div>

              <form onSubmit={saveSettings} style={{ marginTop: 28 }}>
                <div className="form-group">
                  <label className="form-label">Your name</label>
                  <input className="form-field" type="text" value={userSettings.name}
                    onChange={e => setUserSettings(s => ({ ...s, name: e.target.value }))}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Research field</label>
                  <input className="form-field" type="text" value={userSettings.interests}
                    onChange={e => setUserSettings(s => ({ ...s, interests: e.target.value }))}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Reply language</label>
                  <select className="form-field" value={userSettings.language}
                    onChange={e => setUserSettings(s => ({ ...s, language: e.target.value }))}>
                    <option>English</option>
                    <option>Hindi</option>
                    <option>Japanese</option>
                    <option>French</option>
                  </select>
                </div>
                <button type="submit" className="save-btn">Save changes</button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
