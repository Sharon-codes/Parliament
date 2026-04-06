import React, { useState, useEffect, useRef } from 'react';
import {
  Send, Home, MessageSquarePlus, History, Settings,
  Mic, MicOff, Volume2, VolumeX, X, Moon, Sun, ChevronUp, BookOpen
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// thumbnail emoji set for research cards
const THUMBS = ['🧬','🤖','🔬','🧠','⚛️','📡','🌿','💡','🕹️','📊'];

// ── Inline code formatter (no external deps) ─────────────────────────────────
function Msg({ text }) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith('```')) {
          const raw  = p.slice(3, -3);
          const nl   = raw.indexOf('\n');
          const lang = nl > -1 ? raw.slice(0, nl).trim() : '';
          const code = nl > -1 ? raw.slice(nl + 1) : raw;
          return (
            <pre key={i}>
              {lang && <span style={{ fontSize: 9, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--accent)', display: 'block', marginBottom: 8 }}>{lang}</span>}
              {code}
            </pre>
          );
        }
        return (
          <span key={i}>
            {p.split(/(`[^`]+`)/g).map((s, j) =>
              s.startsWith('`') && s.endsWith('`')
                ? <code key={j}>{s.slice(1, -1)}</code>
                : s
            )}
          </span>
        );
      })}
    </>
  );
}

export default function Dashboard() {
  const [query, setQuery]         = useState('');
  const [mode, setMode]           = useState('chat');
  const [view, setView]           = useState('home'); // home | history
  const [sessionId, setSessionId] = useState(null);
  const [chat, setChat]           = useState([
    { role: 'ai', text: 'Peace and welcome.\nHow may I assist you today?' }
  ]);
  const [sessions, setSessions]   = useState([]);
  const [events, setEvents]       = useState([]);
  const [research, setResearch]   = useState([]);
  const [isTyping, setIsTyping]   = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceOn, setVoiceOn]     = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isDark, setIsDark]       = useState(false);
  const [ffOpen, setFfOpen]       = useState(true);
  const [ifOpen, setIfOpen]       = useState(true);
  const [userSettings, setUserSettings] = useState({
    name: 'Guest', interests: 'machine learning', language: 'English', theme: 'light'
  });
  const endRef = useRef(null);

  const applyDark = (d) => { document.documentElement.classList.toggle('dark', d); setIsDark(d); };

  const fetchSessions = async () => {
    try { const r = await fetch('http://localhost:8000/api/sessions'); const d = await r.json(); setSessions(d.sessions || []); } catch {}
  };

  const loadSession = async (id) => {
    setSessionId(id); setView('home');
    try {
      const r = await fetch(`http://localhost:8000/api/sessions/${id}`);
      const d = await r.json();
      setChat(d.messages?.length ? d.messages : [{ role: 'ai', text: 'What shall we explore?' }]);
    } catch {}
  };

  const newChat = async () => {
    setView('home');
    try {
      const r = await fetch('http://localhost:8000/api/sessions', { method: 'POST' });
      const d = await r.json();
      setSessionId(d.session_id);
      setChat([{ role: 'ai', text: 'New session. What shall we explore?' }]);
      fetchSessions();
    } catch {}
  };

  const boot = () => {
    fetch('http://localhost:8000/api/settings').then(r => r.json()).then(d => {
      setUserSettings(d);
      applyDark(d.theme === 'dark');
    }).catch(() => {});
    fetch('http://localhost:8000/api/calendar').then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {});
    fetch('http://localhost:8000/api/research').then(r => r.json()).then(d => setResearch(d.papers || [])).catch(() => {});
    fetchSessions();
  };

  useEffect(() => { boot(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chat, isTyping]);

  const saveSettings = async (e) => {
    e.preventDefault(); setShowSettings(false);
    try {
      await fetch('http://localhost:8000/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(userSettings) });
      boot();
    } catch {}
  };

  const toggleListen = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Voice unsupported.'); return; }
    if (isListening) { setIsListening(false); return; }
    const rec = new SR();
    rec.lang = userSettings.language === 'Hindi' ? 'hi-IN' : 'en-US';
    setIsListening(true); rec.start();
    rec.onresult = e => { setQuery(e.results[0][0].transcript); setIsListening(false); };
    rec.onerror = () => setIsListening(false);
  };

  const speak = (text) => {
    if (!voiceOn || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text.replace(/```[\s\S]*?```/g, 'code block'));
    window.speechSynthesis.speak(u);
  };

  const sendMsg = async (override) => {
    const text = override || query;
    if (!text.trim()) return;
    setChat(h => [...h, { role: 'user', text }]);
    setQuery(''); setIsTyping(true);
    try {
      const r = await fetch('http://localhost:8000/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, mode, session_id: sessionId })
      });
      const d = await r.json();
      if (d.session_id && d.session_id !== sessionId) setSessionId(d.session_id);
      setChat(h => [...h, { role: 'ai', text: d.reply }]);
      speak(d.reply); fetchSessions();
    } catch {
      setChat(h => [...h, { role: 'ai', text: 'Connection lost. Check backend.' }]);
    }
    setIsTyping(false);
  };

  return (
    <div className="app">

      {/* ────────── LEFT SIDEBAR ────────── */}
      <aside className="sb-left">
        <div className="sb-logo-area">
          <div className="sb-logo-main">
            साथी <span className="sb-logo-sub">(saathi)</span>
          </div>
        </div>

        <nav className="sb-nav">
          <button className={`nav-item ${view === 'home' ? 'active' : ''}`} onClick={() => setView('home')}>
            <Home size={15}/> Home
          </button>
          <button className="nav-item" onClick={newChat}>
            <MessageSquarePlus size={15}/> New Chat
          </button>
          <button className={`nav-item ${view === 'history' ? 'active' : ''}`} onClick={() => setView('history')}>
            <History size={15}/> History
          </button>

          {/* Session list when history view */}
          <AnimatePresence>
            {view === 'history' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                style={{ overflow: 'hidden' }}
              >
                <div className="sb-session-list">
                  {sessions.length === 0
                    ? <span className="s-section-label" style={{ color: 'var(--mist)', fontStyle: 'italic', fontWeight: 300 }}>No history yet.</span>
                    : sessions.map(s => (
                      <button key={s.session_id} className={`s-item ${sessionId === s.session_id ? 's-active' : ''}`} onClick={() => loadSession(s.session_id)}>
                        <span>{s.title || 'Session'}</span>
                      </button>
                    ))
                  }
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </nav>

        <div className="sb-bottom">
          <button className="nav-item" onClick={() => setShowSettings(true)}>
            <Settings size={15}/> Settings
          </button>
        </div>
      </aside>

      {/* ────────── CENTER CHAT ────────── */}
      <main className="chat-col">

        {/* Top bar */}
        <div className="chat-topbar">
          <button className="theme-btn" onClick={() => applyDark(!isDark)}>
            {isDark ? <Sun size={16}/> : <Moon size={16}/>}
          </button>
          <button className="theme-btn" onClick={() => setVoiceOn(v => !v)} style={{ color: voiceOn ? 'var(--accent)' : undefined }}>
            {voiceOn ? <Volume2 size={16}/> : <VolumeX size={16}/>}
          </button>
          <div className="mode-pills">
            {['chat','agent','search'].map(m => (
              <button key={m} className={`mode-pill ${mode === m ? 'mp-on' : ''}`} onClick={() => setMode(m)}>
                {m === 'chat' ? 'Chat' : m === 'agent' ? 'Agent' : 'Search'}
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="messages-area">
          {/* Watercolor crane */}
          <div className="crane-bg"/>

          <div className="messages-inner">
            <AnimatePresence>
              {chat.map((msg, i) => (
                <motion.div key={i} className={`msg-row ${msg.role}`}
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28, ease: [0.4,0,0.2,1] }}
                >
                  {msg.role === 'ai' ? (
                    <div className="bubble-ai">
                      <div className="ai-sender">SAATHI</div>
                      <Msg text={msg.text}/>
                    </div>
                  ) : (
                    <div className="bubble-user">{msg.text}</div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {isTyping && (
              <motion.div className="msg-row ai" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="bubble-ai">
                  <div className="ai-sender">SAATHI</div>
                  <div className="typing"><span/><span/><span/></div>
                </div>
              </motion.div>
            )}
            <div ref={endRef}/>
          </div>
        </div>

        {/* Input Dock */}
        <div className="input-dock">
          <div className="input-bar">
            <input
              className="chat-input" autoFocus
              type="text" value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMsg()}
              placeholder={mode === 'agent' ? 'Automate something…' : mode === 'search' ? 'Search the live web…' : 'Message Saathi…'}
            />
            <button className={`voice-btn ${isListening ? 'on' : ''}`} onClick={toggleListen}>
              {isListening ? <Mic size={16}/> : <Mic size={16} style={{ opacity: 0.5 }}/>}
            </button>
            <button className="send-btn-circle" onClick={() => sendMsg()} disabled={!query.trim()}>
              <Send size={14}/>
            </button>
          </div>
          <p className="dock-meta">mode: {mode} | {userSettings.name}</p>
        </div>
      </main>

      {/* ────────── RIGHT PANEL ────────── */}
      <aside className="sb-right">
        <div className="rp-header">
          <h2>Context &amp; Insights</h2>
        </div>

        <div className="rp-scroll">

          {/* Focus Flow */}
          <div className="rp-section">
            <div className="rp-section-hd">
              Focus Flow
              <button onClick={() => setFfOpen(v => !v)}>
                <ChevronUp size={13} style={{ transform: ffOpen ? 'rotate(0)' : 'rotate(180deg)', transition: 'transform .2s' }}/>
              </button>
            </div>

            <AnimatePresence>
              {ffOpen && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                  {events.length === 0
                    ? <div className="ff-tag"><span className="ff-tag-dot"/> Syncing…</div>
                    : events.map(ev => (
                      <div className="ff-tag" key={ev.id}>
                        <span className="ff-tag-dot"/>
                        <span>{ev.title}</span>
                        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--mist)' }}>{ev.time}</span>
                      </div>
                    ))
                  }
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Insight Feed */}
          <div className="rp-section">
            <div className="rp-section-hd">
              Insight Feed
              <button onClick={() => setIfOpen(v => !v)}>
                <ChevronUp size={13} style={{ transform: ifOpen ? 'rotate(0)' : 'rotate(180deg)', transition: 'transform .2s' }}/>
              </button>
            </div>

            <AnimatePresence>
              {ifOpen && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                  {research.length === 0
                    ? <div className="if-card" style={{ opacity: 0.5 }}>
                        <div className="if-card-body"><h4>Scanning arXiv…</h4></div>
                      </div>
                    : research.map((r, i) => (
                      <a href={r.link} target="_blank" rel="noreferrer" key={i} className="if-card">
                        <div className="if-card-body">
                          <h4>{r.title}</h4>
                          <p className="if-meta">arXiv</p>
                        </div>
                        <div className="if-thumb">
                          <span className="if-thumb-placeholder">{THUMBS[i % THUMBS.length]}</span>
                        </div>
                      </a>
                    ))
                  }
                </motion.div>
              )}
            </AnimatePresence>
          </div>

        </div>
      </aside>

      {/* ────────── SETTINGS MODAL ────────── */}
      <AnimatePresence>
        {showSettings && (
          <motion.div className="modal-ov"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setShowSettings(false); }}
          >
            <motion.div className="modal-box"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.24 }}
            >
              <div className="modal-row" style={{ marginBottom: 0 }}>
                <h2>設定<br/><span style={{ fontFamily: 'DM Sans', fontSize: 12, fontWeight: 300, color: 'var(--stone)', letterSpacing: '.06em' }}>preferences</span></h2>
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--stone)', padding: 6, borderRadius: 6 }} onClick={() => setShowSettings(false)}><X size={16}/></button>
              </div>
              <form onSubmit={saveSettings} style={{ marginTop: 28 }}>
                <div className="form-grp">
                  <label className="form-lbl">Your name</label>
                  <input className="form-fld" type="text" value={userSettings.name}
                    onChange={e => setUserSettings(s => ({ ...s, name: e.target.value }))}/>
                </div>
                <div className="form-grp">
                  <label className="form-lbl">Research field</label>
                  <input className="form-fld" type="text" value={userSettings.interests}
                    onChange={e => setUserSettings(s => ({ ...s, interests: e.target.value }))}/>
                </div>
                <div className="form-grp">
                  <label className="form-lbl">Reply language</label>
                  <select className="form-fld" value={userSettings.language}
                    onChange={e => setUserSettings(s => ({ ...s, language: e.target.value }))}>
                    <option>English</option><option>Hindi</option><option>Japanese</option><option>French</option>
                  </select>
                </div>
                <div className="form-grp">
                  <label className="form-lbl">Theme</label>
                  <select className="form-fld" value={userSettings.theme}
                    onChange={e => { setUserSettings(s => ({...s, theme: e.target.value})); applyDark(e.target.value === 'dark'); }}>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </select>
                </div>
                <button type="submit" className="save-cta">Save changes</button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
