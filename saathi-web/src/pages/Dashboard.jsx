import React, { useState, useEffect, useRef } from 'react';
import {
  Send, Clock, Settings, BookOpen, Mic, MicOff,
  Volume2, VolumeX, Search, Code, Sparkles, X,
  Loader2, Moon, Sun, Plus, AlignLeft, Calendar
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ── simple code block formatter ──────────────────────────────────────────────
function formatMessage(text) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (part.startsWith('```')) {
      const lines = part.split('\n');
      const lang = lines[0].replace('```', '').trim() || 'code';
      const code = lines.slice(1, lines.length - 1).join('\n');
      return (
        <pre key={i}>
          <div style={{ fontSize: 10, color: '#888', marginBottom: 8, fontFamily: 'sans-serif', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{lang}</div>
          {code}
        </pre>
      );
    }
    // inline code
    const inlineParts = part.split(/(`[^`]+`)/g);
    return (
      <span key={i}>
        {inlineParts.map((ip, j) =>
          ip.startsWith('`') && ip.endsWith('`')
            ? <code key={j}>{ip.slice(1, -1)}</code>
            : ip
        )}
      </span>
    );
  });
}

export default function Dashboard() {
  const [query, setQuery]       = useState('');
  const [mode, setMode]         = useState('chat');
  const [sessionId, setSessionId] = useState(null);
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', text: 'Peace and welcome. How may I assist you today?' }
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
  const chatEndRef = useRef(null);

  // ── helpers ──────────────────────────────────────────────────────────────
  const toggleDark = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle('dark', next);
    setUserSettings(s => ({ ...s, theme: next ? 'dark' : 'light' }));
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
    setChatHistory([]);
    try {
      const r = await fetch(`http://localhost:8000/api/sessions/${id}`);
      const d = await r.json();
      setChatHistory(d.messages?.length
        ? d.messages
        : [{ role: 'ai', text: 'Peace and welcome. How may I assist you today?' }]
      );
    } catch {}
  };

  const createNewChat = async () => {
    try {
      const r = await fetch('http://localhost:8000/api/sessions', { method: 'POST' });
      const d = await r.json();
      setSessionId(d.session_id);
      setChatHistory([{ role: 'ai', text: 'New channel open. What shall we explore?' }]);
      fetchSessions();
    } catch {}
  };

  const loadAll = () => {
    fetch('http://localhost:8000/api/settings')
      .then(r => r.json()).then(d => {
        setUserSettings(d);
        const dark = d.theme === 'dark';
        setIsDark(dark);
        document.documentElement.classList.toggle('dark', dark);
      }).catch(() => {});

    fetch('http://localhost:8000/api/calendar')
      .then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {});

    fetch('http://localhost:8000/api/research')
      .then(r => r.json()).then(d => setResearch(d.papers || [])).catch(() => {});

    fetchSessions();
  };

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isTyping]);

  const saveSettings = async (e) => {
    e.preventDefault();
    setShowSettings(false);
    try {
      await fetch('http://localhost:8000/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
      });
      loadAll();
    } catch {}
  };

  const toggleListen = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Voice not supported in this browser.'); return; }
    const rec = new SR();
    rec.lang = userSettings.language === 'Hindi' ? 'hi-IN' : 'en-US';
    if (isListening) { setIsListening(false); return; }
    setIsListening(true);
    rec.start();
    rec.onresult = (e) => { setQuery(e.results[0][0].transcript); setIsListening(false); };
    rec.onerror = () => setIsListening(false);
  };

  const speak = (text) => {
    if (!voiceEnabled || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text.replace(/```[\s\S]*?```/g, 'code block'));
    if (userSettings.language === 'Hindi') u.lang = 'hi-IN';
    window.speechSynthesis.speak(u);
  };

  const handleSend = async (override) => {
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
      setChatHistory(h => [...h, { role: 'ai', text: 'Connection lost. Please check the backend.' }]);
    }
    setIsTyping(false);
  };

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="layout">

      {/* ── LEFT SIDEBAR ── */}
      <aside className="sidebar">
        <div className="sb-header">
          <span className="sb-logo">saathi</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="icon-btn" onClick={toggleDark} title="Toggle theme">
              {isDark ? <Sun size={16}/> : <Moon size={16}/>}
            </button>
            <button className="icon-btn" onClick={() => setShowSettings(true)} title="Settings">
              <Settings size={16}/>
            </button>
          </div>
        </div>

        <button className="sb-btn" onClick={createNewChat}>
          <Plus size={15}/> New chat
        </button>

        <div className="sb-section">
          <span className="sb-label">Recent</span>
          {sessions.length === 0
            ? <p style={{ fontSize: 12, color: 'var(--muted)', padding: '4px 8px' }}>No history yet.</p>
            : sessions.map(s => (
              <button
                key={s.session_id}
                className={`sb-item ${sessionId === s.session_id ? 'active' : ''}`}
                onClick={() => loadSession(s.session_id)}
              >
                <AlignLeft size={13} style={{ flexShrink: 0, opacity: 0.5 }}/>
                <span>{s.title || 'New Chat'}</span>
              </button>
            ))
          }
        </div>
      </aside>

      {/* ── MAIN CHAT ── */}
      <main className="chat-area">

        {/* top-right controls */}
        <div style={{ position: 'absolute', top: 16, right: 20, display: 'flex', gap: 6, zIndex: 10 }}>
          <button className="icon-btn" onClick={() => setVoiceEnabled(v => !v)} title="Toggle voice">
            {voiceEnabled ? <Volume2 size={16}/> : <VolumeX size={16}/>}
          </button>
        </div>

        {/* messages */}
        <div className="messages">
          <AnimatePresence>
            {chatHistory.map((msg, i) => (
              <motion.div
                key={i}
                className={`msg-row ${msg.role}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
              >
                {msg.role === 'ai' ? (
                  <div className="bubble-ai">{formatMessage(msg.text)}</div>
                ) : (
                  <div className="bubble-user">{msg.text}</div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div className="msg-row ai" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="typing">
                <span/><span/><span/>
              </div>
            </motion.div>
          )}

          <div ref={chatEndRef}/>
        </div>

        {/* input dock */}
        <div className="input-dock">
          <div className="input-bar">
            <div className="mode-select">
              {mode === 'chat'   && <Sparkles size={13} style={{ color: 'var(--muted)' }}/>}
              {mode === 'agent'  && <Code     size={13} style={{ color: 'var(--muted)' }}/>}
              {mode === 'search' && <Search   size={13} style={{ color: 'var(--muted)' }}/>}
              <select value={mode} onChange={e => setMode(e.target.value)}>
                <option value="chat">Chat</option>
                <option value="agent">Agent</option>
                <option value="search">Search</option>
              </select>
            </div>

            <input
              className="chat-input"
              autoFocus
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder={
                mode === 'agent'  ? 'Describe what to automate…' :
                mode === 'search' ? 'Search the live web…' :
                'Message Saathi…'
              }
            />

            <button className="icon-btn" onClick={toggleListen} style={{ marginRight: 4 }}>
              {isListening
                ? <Mic size={16} style={{ color: '#ef4444' }}/>
                : <MicOff size={16}/>
              }
            </button>

            <button
              className="send-btn"
              onClick={() => handleSend()}
              disabled={!query.trim()}
            >
              <Send size={16}/>
            </button>
          </div>
        </div>
      </main>

      {/* ── RIGHT PANEL ── */}
      <aside className="sidebar-r">
        {/* Schedule */}
        <div style={{ marginBottom: 28 }}>
          <p className="panel-label"><Calendar size={12}/> Schedule</p>
          {events.length === 0
            ? <p style={{ fontSize: 12, color: 'var(--muted)' }}>Syncing…</p>
            : events.map(ev => (
              <div className="panel-card" key={ev.id}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <Clock size={13} style={{ color: 'var(--muted)', marginTop: 2, flexShrink: 0 }}/>
                  <div>
                    <h4>{ev.title}</h4>
                    <p className="meta">{ev.time}</p>
                  </div>
                </div>
              </div>
            ))
          }
        </div>

        {/* Research Radar */}
        <div>
          <p className="panel-label">
            <BookOpen size={12}/>
            {userSettings?.interests?.split(' ')[0] || 'Research'} radar
          </p>
          {research.length === 0
            ? <Loader2 size={14} style={{ color: 'var(--muted)', animation: 'spin 1s linear infinite' }}/>
            : research.map((r, i) => (
              <a
                href={r.link}
                target="_blank"
                rel="noreferrer"
                key={i}
                className="panel-card"
                style={{ display: 'block', textDecoration: 'none' }}
              >
                <h4>{r.title}</h4>
                <p className="meta">arxiv · open access</p>
              </a>
            ))
          }
        </div>
      </aside>

      {/* ── SETTINGS MODAL ── */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            className="modal-bg"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setShowSettings(false); }}
          >
            <motion.div
              className="modal-box"
              initial={{ scale: 0.97, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.97, opacity: 0 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <h2>Settings</h2>
                <button className="icon-btn" onClick={() => setShowSettings(false)}><X size={16}/></button>
              </div>
              <form onSubmit={saveSettings}>
                <div className="form-group">
                  <label className="form-label">Your name</label>
                  <input className="form-input" type="text" value={userSettings.name}
                    onChange={e => setUserSettings(s => ({ ...s, name: e.target.value }))}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Research interests</label>
                  <input className="form-input" type="text" value={userSettings.interests}
                    onChange={e => setUserSettings(s => ({ ...s, interests: e.target.value }))}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Reply language</label>
                  <select className="form-input" value={userSettings.language}
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
