import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Home, MessageSquarePlus, History, Settings,
  Mic, MicOff, Volume2, VolumeX, X, Moon, Sun, ChevronUp,
  Brain, Bell, BellOff, Search, Check, Sparkles, Radio, FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API = 'http://localhost:8000';
const THUMBS = ['🧬','🤖','🔬','🧠','⚛️','📡','🌿','💡','🕹️','📊'];

// ── Inline code/markdown formatter ───────────────────────────────────────────
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
                : s.split('\n').map((line, k) => <span key={k}>{line}{k < s.split('\n').length - 1 && <br/>}</span>)
            )}
          </span>
        );
      })}
    </>
  );
}

// ── Nudge Card ────────────────────────────────────────────────────────────────
function NudgeCard({ nudge, onAck, onSuppress }) {
  const icons = { time: '🕰', worry: '💛', progress: '📈', context: '📅' };
  const icon = icons[nudge.nudge_type] || '✦';
  return (
    <motion.div
      className="nudge-card"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <span style={{ fontSize: 16, lineHeight: 1, marginTop: 2 }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div className="nudge-type-label">{nudge.nudge_type} nudge · {nudge.topic}</div>
          <p className="nudge-text">{nudge.message}</p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10, justifyContent: 'flex-end' }}>
        <button className="nudge-btn-dismiss" onClick={() => onSuppress(nudge.topic)} title="Never remind me about this">
          <BellOff size={11}/> Suppress
        </button>
        <button className="nudge-btn-ack" onClick={() => onAck(nudge.id)} title="Got it">
          <Check size={11}/> Got it
        </button>
      </div>
    </motion.div>
  );
}

// ── Memory Entry ──────────────────────────────────────────────────────────────
function MemoryEntry({ entry }) {
  const topicColors = {
    research: 'var(--accent)',
    personal: 'var(--gold)',
    academic: '#7B9FC4',
    social: '#B47EC0',
    general: 'var(--mist)',
  };
  return (
    <div className="mem-entry">
      <span className="mem-topic-dot" style={{ background: topicColors[entry.topic] || 'var(--mist)' }}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p className="mem-text">{entry.content.slice(0, 110)}{entry.content.length > 110 ? '…' : ''}</p>
        <span className="mem-meta">{entry.topic} · {entry.timestamp?.slice(0, 10)}</span>
      </div>
    </div>
  );
}

// ── Fact Entry ───────────────────────────────────────────────────────────────
function FactEntry({ fact }) {
  return (
    <div className="mem-entry fact-entry">
      <span style={{ fontSize: 13 }}>✦</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p className="mem-text">{fact.content}</p>
        <span className="mem-meta">{fact.topic} · remembered</span>
      </div>
    </div>
  );
}

// ── Right Panel Section ───────────────────────────────────────────────────────
function RPSection({ title, open, onToggle, children }) {
  return (
    <div className="rp-section">
      <div className="rp-section-hd">
        {title}
        <button onClick={onToggle}>
          <ChevronUp size={13} style={{ transform: open ? 'rotate(0)' : 'rotate(180deg)', transition: 'transform .2s' }}/>
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
export default function Dashboard() {
  // ── Chat state ──────────────────────────────────────────────────────────────
  const [query, setQuery]         = useState('');
  const [mode, setMode]           = useState('chat');
  const [view, setView]           = useState('home');
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
  const [isDark, setIsDark]       = useState(false);

  // ── Right panel toggles ─────────────────────────────────────────────────────
  const [ffOpen, setFfOpen]   = useState(true);
  const [ifOpen, setIfOpen]   = useState(true);
  const [memOpen, setMemOpen] = useState(true);
  const [nudgeOpen, setNudgeOpen] = useState(true);

  // ── Memory & Nudge state ────────────────────────────────────────────────────
  const [episodes, setEpisodes]   = useState([]);
  const [facts, setFacts]         = useState([]);
  const [nudges, setNudges]       = useState([]);
  const [memSearch, setMemSearch] = useState('');
  const [memSearchResults, setMemSearchResults] = useState(null);

  // ── LLM provider status ─────────────────────────────────────────────────
  const [llmStatus, setLlmStatus] = useState(null);

  // ── Mobile sync / QR state ────────────────────────────────────────────
  const [showSync, setShowSync]     = useState(false);
  const [syncData, setSyncData]     = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);

  // ── Settings ────────────────────────────────────────────────────────────────
  const [showSettings, setShowSettings] = useState(false);
  const [userSettings, setUserSettings] = useState({
    name: 'Guest', interests: 'machine learning', language: 'English',
    theme: 'light', nudge_sensitivity: 'balanced'
  });

  // ── Voice state ───────────────────────────────────────────────────
  const [showVoice, setShowVoice]       = useState(false);
  const [voiceMode, setVoiceMode]       = useState('off');
  const [voiceStatus, setVoiceStatus]   = useState(null);
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [dictationText, setDictationText]     = useState('');
  const [isVoiceRec, setIsVoiceRec]           = useState(false);
  const [isSpeaking, setIsSpeaking]           = useState(false);
  const [ttsText, setTtsText]                 = useState('');
  const voiceWsRef = useRef(null);

  const endRef = useRef(null);

  // ── Dark mode ───────────────────────────────────────────────────────────────
  const applyDark = (d) => { document.documentElement.classList.toggle('dark', d); setIsDark(d); };

  // ── Data fetchers ────────────────────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try { const r = await fetch(`${API}/api/sessions`); const d = await r.json(); setSessions(d.sessions || []); } catch {}
  }, []);

  const fetchMemory = useCallback(async () => {
    try {
      const [epR, factsR, nudgesR] = await Promise.all([
        fetch(`${API}/api/memory/episodes?days=14`),
        fetch(`${API}/api/memory/facts`),
        fetch(`${API}/api/nudges`),
      ]);
      const epD = await epR.json();
      const factsD = await factsR.json();
      const nudgesD = await nudgesR.json();
      setEpisodes(epD.episodes || []);
      setFacts(factsD.facts || []);
      setNudges(nudgesD.nudges || []);
    } catch {}
  }, []);

  const searchMemory = useCallback(async (q) => {
    if (!q.trim()) { setMemSearchResults(null); return; }
    try {
      const r = await fetch(`${API}/api/memory/search?q=${encodeURIComponent(q)}`);
      const d = await r.json();
      setMemSearchResults(d);
    } catch {}
  }, []);

  const loadSession = async (id) => {
    setSessionId(id); setView('home');
    try {
      const r = await fetch(`${API}/api/sessions/${id}`);
      const d = await r.json();
      setChat(d.messages?.length ? d.messages : [{ role: 'ai', text: 'What shall we explore?' }]);
    } catch {}
  };

  const newChat = async () => {
    setView('home');
    try {
      const r = await fetch(`${API}/api/sessions`, { method: 'POST' });
      const d = await r.json();
      setSessionId(d.session_id);
      setChat([{ role: 'ai', text: 'New session. What shall we explore?' }]);
      fetchSessions();
    } catch {}
  };

  const boot = () => {
    fetch(`${API}/api/settings`).then(r => r.json()).then(d => {
      setUserSettings({ name: 'Guest', interests: 'machine learning', language: 'English', theme: 'light', nudge_sensitivity: 'balanced', ...d });
      applyDark(d.theme === 'dark');
    }).catch(() => {});
    fetch(`${API}/api/calendar`).then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {});
    fetch(`${API}/api/research`).then(r => r.json()).then(d => setResearch(d.papers || [])).catch(() => {});
    fetch(`${API}/api/llm-status`).then(r => r.json()).then(d => setLlmStatus(d)).catch(() => {});
    fetch(`${API}/api/voice/status`).then(r => r.json()).then(d => setVoiceStatus(d)).catch(() => {});
    fetch(`${API}/api/sync/status`).then(r => r.json()).then(d => {
      if (d.tunnel_active) setSyncData(s => ({ ...s, ...d }));
    }).catch(() => {});
    fetchSessions();
    fetchMemory();
  };

  useEffect(() => { boot(); }, []);

  // Poll nudges every 2 minutes
  useEffect(() => {
    const iv = setInterval(() => fetchMemory(), 120_000);
    return () => clearInterval(iv);
  }, [fetchMemory]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chat, isTyping]);

  // ── Voice WebSocket ───────────────────────────────────────────────────
  const connectVoiceWs = useCallback(() => {
    if (voiceWsRef.current?.readyState === WebSocket.OPEN) return;
    try {
      const ws = new WebSocket(`${WS_API}/ws/voice`);
      voiceWsRef.current = ws;

      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
          case 'hello':
            setVoiceStatus(s => ({ ...s, ...msg }));
            setVoiceMode(msg.mode || 'off');
            break;
          case 'mode':
            setVoiceMode(msg.mode);
            break;
          case 'wake':
            setIsVoiceRec(true);
            break;
          case 'recording_start':
            setIsVoiceRec(true);
            break;
          case 'transcript':
            setIsVoiceRec(false);
            setVoiceTranscript(msg.text);
            if (msg.final) setChat(h => [...h, { role: 'user', text: '\uD83C\uDF99 ' + msg.text }]);
            break;
          case 'tts':
            setIsSpeaking(true); setTtsText(msg.text);
            setTimeout(() => setIsSpeaking(false), 4000);
            break;
          case 'tts_urgent':
            setIsSpeaking(true); setTtsText(msg.text);
            setTimeout(() => setIsSpeaking(false), 4000);
            break;
          case 'dictation_chunk':
            setDictationText(t => t + ' ' + msg.text);
            break;
          case 'dictation_done':
            setDictationText('');
            if (msg.text) setQuery(msg.text);
            break;
          default: break;
        }
      };

      ws.onclose = () => {
        setIsVoiceRec(false);
        setIsSpeaking(false);
      };
    } catch (e) {
      console.warn('Voice WS failed:', e);
    }
  }, []);

  const changeVoiceMode = useCallback((newMode) => {
    setVoiceMode(newMode);
    if (voiceWsRef.current?.readyState === WebSocket.OPEN) {
      voiceWsRef.current.send(JSON.stringify({ type: 'set_mode', mode: newMode }));
    } else {
      // fallback: REST
      fetch(`${API}/api/voice/mode`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      }).catch(() => {});
    }
  }, []);

  const handleDictationStop = useCallback(() => {
    if (voiceWsRef.current?.readyState === WebSocket.OPEN) {
      voiceWsRef.current.send(JSON.stringify({ type: 'dictation_stop' }));
    }
    changeVoiceMode('off');
  }, [changeVoiceMode]);

  const openVoice = useCallback(() => {
    setShowVoice(true);
    connectVoiceWs();
    fetch(`${API}/api/voice/status`).then(r => r.json()).then(d => setVoiceStatus(d)).catch(() => {});
  }, [connectVoiceWs]);

  // ── Settings save ────────────────────────────────────────────────────────────
  const saveSettings = async (e) => {
    e.preventDefault(); setShowSettings(false);
    try {
      await fetch(`${API}/api/settings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
      });
      boot();
    } catch {}
  };

  // ── Voice ────────────────────────────────────────────────────────────────────
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

  // ── Send message ─────────────────────────────────────────────────────────────
  const sendMsg = async (override) => {
    const text = override || query;
    if (!text.trim()) return;
    setChat(h => [...h, { role: 'user', text }]);
    setQuery(''); setIsTyping(true);
    try {
      const r = await fetch(`${API}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, mode, session_id: sessionId })
      });
      const d = await r.json();
      if (d.session_id && d.session_id !== sessionId) setSessionId(d.session_id);
      setChat(h => [...h, { role: 'ai', text: d.reply }]);
      speak(d.reply);
      fetchSessions();
      // Refresh memory & nudges after every message
      setTimeout(fetchMemory, 800);
    } catch {
      setChat(h => [...h, { role: 'ai', text: 'Connection lost. Check backend.' }]);
    }
    setIsTyping(false);
  };

  // ── Nudge handlers ───────────────────────────────────────────────────────────
  const ackNudge = async (id) => {
    try { await fetch(`${API}/api/nudges/acknowledge`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nudge_id: id }) }); }
    catch {}
    setNudges(ns => ns.filter(n => n.id !== id));
  };

  const suppressNudge = async (topic) => {
    try { await fetch(`${API}/api/nudges/suppress`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic }) }); }
    catch {}
    setNudges(ns => ns.filter(n => n.topic !== topic));
  };

  // ── Memory search debounce ───────────────────────────────────────────────────
  const memSearchTimer = useRef(null);
  const handleMemSearch = (v) => {
    setMemSearch(v);
    clearTimeout(memSearchTimer.current);
    memSearchTimer.current = setTimeout(() => searchMemory(v), 500);
  };

  // ── Displayed episodes/facts ─────────────────────────────────────────────────
  const displayEpisodes = memSearchResults ? memSearchResults.episodes : episodes.slice(0, 6);
  const displayFacts    = memSearchResults ? memSearchResults.facts    : facts.slice(0, 5);

  // ── Active nudges (unacknowledged) ───────────────────────────────────────────
  const activeNudges = nudges.filter(n => !n.acknowledged);

  // ── Sync / QR panel ──────────────────────────────────────────────────────────
  const openSyncPanel = useCallback(async () => {
    setShowSync(true);
    setSyncLoading(true);
    try {
      const r = await fetch(`${API}/api/sync/session`);
      const d = await r.json();
      setSyncData(d);
    } catch {
      setSyncData({ error: 'Backend not reachable. Is the API running?' });
    }
    setSyncLoading(false);
  }, []);

  return (
    <div className="app">

      {/* ── NUDGE TOAST OVERLAY (top-center soft cards) ──────────── */}
      <div className="nudge-toast-area">
        <AnimatePresence>
          {activeNudges.slice(0, 2).map(n => (
            <NudgeCard key={n.id} nudge={n} onAck={ackNudge} onSuppress={suppressNudge}/>
          ))}
        </AnimatePresence>
      </div>

      {/* ────────── LEFT SIDEBAR ────────── */}
      <aside className="sb-left">
        <div className="sb-logo-area">
          <div className="sb-logo-main">
            साथी <span className="sb-logo-sub">(saathi)</span>
          </div>
          {activeNudges.length > 0 && (
            <div className="nudge-badge">{activeNudges.length} nudge{activeNudges.length > 1 ? 's' : ''}</div>
          )}
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
          <button className={`nav-item ${view === 'memory' ? 'active' : ''}`} onClick={() => setView('memory')}>
            <Brain size={15}/> Memory
          </button>
          <button className={`nav-item ${view === 'nudges' ? 'active' : ''}`} onClick={() => setView('nudges')}>
            <Bell size={15}/> Nudges
            {activeNudges.length > 0 && <span className="nav-badge">{activeNudges.length}</span>}
          </button>
          <button className="nav-item" onClick={openSyncPanel} style={{ color: syncData?.tunnel_active ? 'var(--accent)' : undefined }}>
            <Radio size={15}/> Sync Mobile
            {syncData?.tunnel_active && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', marginLeft: 4 }}/>}
          </button>

          <AnimatePresence>
            {view === 'history' && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
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
          {/* Voice Interface button */}
          <button
            className="theme-btn"
            onClick={openVoice}
            style={{
              color: voiceMode !== 'off' ? (isVoiceRec ? '#e74c3c' : 'var(--accent)') : undefined,
              position: 'relative'
            }}
            title="Voice Interface"
          >
            {voiceMode === 'off' ? <MicOff size={16}/> : <Mic size={16}/>}
            {voiceMode !== 'off' && (
              <span style={{
                position: 'absolute', top: 2, right: 2,
                width: 6, height: 6, borderRadius: '50%',
                background: isVoiceRec ? '#e74c3c' : 'var(--accent)',
                animation: 'tb 1.2s infinite'
              }}/>
            )}
          </button>
          <div className="mode-pills">
            {['chat','agent','search'].map(m => (
              <button key={m} className={`mode-pill ${mode === m ? 'mp-on' : ''}`} onClick={() => setMode(m)}>
                {m === 'chat' ? 'Chat' : m === 'agent' ? 'Agent' : 'Search'}
              </button>
            ))}
          </div>
        </div>
        {/* ── Voice Overlay ── */}
        <AnimatePresence>
          {showVoice && (
            <VoiceOverlay
              status={voiceStatus}
              mode={voiceMode}
              onModeChange={changeVoiceMode}
              transcript={voiceTranscript}
              dictationText={dictationText}
              isRecording={isVoiceRec}
              isSpeaking={isSpeaking}
              ttsText={ttsText}
              onClose={() => setShowVoice(false)}
              onDictationStop={handleDictationStop}
            />
          )}
        </AnimatePresence>

        {/* Memory view overlay */}
        <AnimatePresence>
          {view === 'memory' && (
            <motion.div className="memory-view" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} transition={{ duration: 0.2 }}>
              <div className="mv-header">
                <Brain size={16} style={{ color: 'var(--accent)' }}/>
                <h3>Conversational Memory</h3>
                <button className="mv-close" onClick={() => setView('home')}><X size={14}/></button>
              </div>
              <div className="mv-search">
                <Search size={13} style={{ color: 'var(--mist)' }}/>
                <input
                  className="mv-search-input"
                  placeholder="Search my memories…"
                  value={memSearch}
                  onChange={e => handleMemSearch(e.target.value)}
                />
              </div>

              <div className="mv-commands">
                <span className="mv-hint">Try:</span>
                {['Remember that…', 'Forget what I said about…', 'What do you remember about…', 'What did we talk about last week?'].map(cmd => (
                  <button key={cmd} className="mv-cmd-chip" onClick={() => { setView('home'); setQuery(cmd); }}>
                    {cmd}
                  </button>
                ))}
              </div>

              <div className="mv-scroll">
                {displayFacts.length > 0 && (
                  <div className="mv-section">
                    <div className="mv-section-label">Named Facts</div>
                    {displayFacts.map((f, i) => <FactEntry key={i} fact={f}/>)}
                  </div>
                )}
                <div className="mv-section">
                  <div className="mv-section-label">
                    {memSearchResults ? `Search results` : 'Recent Episodes'}
                  </div>
                  {displayEpisodes.length === 0
                    ? <p style={{ color: 'var(--mist)', fontSize: 12, padding: '8px 4px' }}>No memories yet. Start chatting and I'll remember.</p>
                    : displayEpisodes.map((e, i) => <MemoryEntry key={i} entry={e}/>)
                  }
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Nudge history view overlay */}
        <AnimatePresence>
          {view === 'nudges' && (
            <motion.div className="memory-view" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} transition={{ duration: 0.2 }}>
              <div className="mv-header">
                <Bell size={16} style={{ color: 'var(--gold)' }}/>
                <h3>Gentle Nudges</h3>
                <button className="mv-close" onClick={() => setView('home')}><X size={14}/></button>
              </div>
              <div className="mv-scroll">
                {activeNudges.length === 0
                  ? <p style={{ color: 'var(--mist)', fontSize: 12, padding: '12px 4px' }}>No pending nudges. Saathi is watching quietly.</p>
                  : activeNudges.map(n => <NudgeCard key={n.id} nudge={n} onAck={ackNudge} onSuppress={suppressNudge}/>)
                }
              </div>
              <div style={{ padding: '8px 16px', borderTop: '1px solid var(--rule)', color: 'var(--mist)', fontSize: 10, letterSpacing: '.06em' }}>
                Nudge sensitivity: <strong style={{ color: 'var(--stone)' }}>{userSettings.nudge_sensitivity || 'balanced'}</strong> · change in Settings
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div className="messages-area">
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
              placeholder={
                mode === 'agent'  ? 'Automate something…'      :
                mode === 'search' ? 'Search the live web…'      :
                'Message Saathi… or "Remember that…" / "Forget…"'
              }
            />
            <button className={`voice-btn ${isListening ? 'on' : ''}`} onClick={toggleListen}>
              <Mic size={16} style={{ opacity: isListening ? 1 : 0.5 }}/>
            </button>
            <button className="send-btn-circle" onClick={() => sendMsg()} disabled={!query.trim()}>
              <Send size={14}/>
            </button>
          </div>
          <p className="dock-meta">
            mode: {mode} | {userSettings.name} | memory on
            {llmStatus && (
              <span style={{
                marginLeft: 8,
                color: llmStatus.ready ? 'var(--accent)' : 'var(--gold)',
                fontWeight: 500
              }}>
                · {llmStatus.provider} ({llmStatus.model})
              </span>
            )}
          </p>
        </div>
      </main>

      {/* ────────── RIGHT PANEL ────────── */}
      <aside className="sb-right">
        <div className="rp-header">
          <h2>Context &amp; Insights</h2>
        </div>

        <div className="rp-scroll">

          {/* Active Nudges (soft cards) */}
          {activeNudges.length > 0 && (
            <RPSection title="Gentle Nudges" open={nudgeOpen} onToggle={() => setNudgeOpen(v => !v)}>
              {activeNudges.slice(0, 3).map(n => (
                <NudgeCard key={n.id} nudge={n} onAck={ackNudge} onSuppress={suppressNudge}/>
              ))}
            </RPSection>
          )}

          {/* Memory Snapshot */}
          <RPSection title="Memory Snapshot" open={memOpen} onToggle={() => setMemOpen(v => !v)}>
            {facts.length === 0 && episodes.length === 0 ? (
              <div className="ff-tag" style={{ opacity: 0.5 }}>
                <Sparkles size={12} style={{ color: 'var(--accent)' }}/>
                <span>Tell me things to remember…</span>
              </div>
            ) : (
              <>
                {facts.slice(0, 2).map((f, i) => <FactEntry key={i} fact={f}/>)}
                {episodes.slice(0, 3).map((e, i) => <MemoryEntry key={i} entry={e}/>)}
                <button className="mem-see-all" onClick={() => setView('memory')}>
                  <Brain size={11}/> View all memory
                </button>
              </>
            )}
          </RPSection>

          {/* Focus Flow */}
          <RPSection title="Focus Flow" open={ffOpen} onToggle={() => setFfOpen(v => !v)}>
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
          </RPSection>

          {/* Insight Feed */}
          <RPSection title="Insight Feed" open={ifOpen} onToggle={() => setIfOpen(v => !v)}>
            {research.length === 0
              ? <div className="if-card" style={{ opacity: 0.5 }}><div className="if-card-body"><h4>Scanning arXiv…</h4></div></div>
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
          </RPSection>

        </div>
      </aside>

      {/* ────────── SYNC / QR MODAL ────────── */}
      <AnimatePresence>
        {showSync && (
          <motion.div className="modal-ov"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setShowSync(false); }}
          >
            <motion.div className="modal-box"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.22 }}
              style={{ maxWidth: 360 }}
            >
              <div className="modal-row" style={{ marginBottom: 20 }}>
                <div>
                  <h2 style={{ fontFamily: 'Cormorant Garamond', fontWeight: 300, fontSize: 28 }}>📱 Mobile Sync</h2>
                  <span style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--stone)' }}>scan to connect • anywhere</span>
                </div>
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--stone)', padding: 6 }} onClick={() => setShowSync(false)}><X size={16}/></button>
              </div>

              {syncLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
                  <div style={{ width: 28, height: 28, border: '2px solid var(--rule)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin .7s linear infinite' }}/>
                </div>
              ) : syncData?.error ? (
                <div style={{ textAlign: 'center', color: 'var(--stone)', fontSize: 13, padding: '20px 0' }}>{syncData.error}</div>
              ) : syncData ? (
                <>
                  {/* Tunnel status */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, background: syncData.tunnel_active || syncData.qr_image ? 'rgba(122,158,120,.1)' : 'rgba(200,165,112,.1)', border: `1px solid ${syncData.tunnel_active || syncData.qr_image ? 'rgba(122,158,120,.3)' : 'rgba(200,165,112,.3)'}`, borderRadius: 10, padding: '8px 12px' }}>
                    <span style={{ fontSize: 14 }}>{syncData.tunnel_type === 'cloudflare' ? '☁' : syncData.tunnel_type === 'ngrok' ? '🔗' : syncData.tunnel_type === 'lan' ? '📡' : '⚠'}</span>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', color: syncData.tunnel_active || syncData.qr_image ? 'var(--accent)' : 'var(--gold)' }}>
                        {syncData.tunnel_type || 'No tunnel'}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--stone)' }}>{syncData.public_url || syncData.mobile_url || 'Tunnel initialising…'}</div>
                    </div>
                  </div>

                  {/* QR Code */}
                  {syncData.qr_image ? (
                    <div style={{ textAlign: 'center', marginBottom: 16 }}>
                      <div style={{ background: '#fff', borderRadius: 12, padding: 10, display: 'inline-block' }}>
                        <img src={syncData.qr_image} alt="QR code" style={{ width: 200, height: 200, display: 'block' }}/>
                      </div>
                      <p style={{ fontSize: 11, color: 'var(--stone)', marginTop: 8 }}>Scan with your phone camera to connect</p>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', marginBottom: 16, padding: '30px 0', color: 'var(--stone)', fontSize: 12 }}>
                      ⏳ Tunnel starting up… Click Refresh in 10s.
                    </div>
                  )}

                  {/* PIN row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--cream)', borderRadius: 10, padding: '10px 14px', marginBottom: 12 }}>
                    <div>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--stone)', marginBottom: 3 }}>PIN</div>
                      <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '.25em', color: 'var(--ink)', fontFamily: 'DM Sans' }}>{syncData.pin || '—'}</div>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--stone)', textAlign: 'right', maxWidth: 130, lineHeight: 1.5 }}>Enter this PIN when connecting manually</div>
                  </div>

                  {/* Mobile URL link */}
                  {syncData.mobile_url && (
                    <div style={{ background: 'var(--cream)', borderRadius: 10, padding: '8px 12px', marginBottom: 14, wordBreak: 'break-all' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--stone)', marginBottom: 3 }}>Mobile URL</div>
                      <a href={syncData.mobile_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none' }}>{syncData.mobile_url}</a>
                    </div>
                  )}

                  {/* Refresh */}
                  <button onClick={() => { setSyncData(null); setSyncLoading(false); openSyncPanel(); }} style={{ width: '100%', padding: '11px', background: 'var(--cream)', border: '1px solid var(--rule)', borderRadius: 10, cursor: 'pointer', fontSize: 12, color: 'var(--stone)', fontFamily: 'inherit' }}>↻ Refresh QR</button>
                </>
              ) : null}

              {/* CloudFlare install hint */}
              {!syncData?.tunnel_active && !syncData?.qr_image && !syncLoading && (
                <div style={{ background: 'rgba(184,147,90,.08)', border: '1px solid rgba(184,147,90,.2)', borderRadius: 10, padding: '12px 14px', marginTop: 14 }}>
                  <div style={{ fontSize: 12, color: 'var(--gold)', fontWeight: 600, marginBottom: 6 }}>⚡ Enable internet access</div>
                  <div style={{ fontSize: 11, color: 'var(--stone)', lineHeight: 1.7 }}>
                    Install <code style={{ color: 'var(--accent)', background: 'var(--cream)', padding: '1px 5px', borderRadius: 3 }}>cloudflared</code> for free internet tunnel:<br/>
                    <code style={{ color: 'var(--accent)', background: 'var(--cream)', padding: '1px 5px', borderRadius: 3, fontSize: 10 }}>winget install Cloudflare.cloudflared</code>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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

                {/* ── LLM STATUS BANNER ───── */}
                {llmStatus && (
                  <div style={{
                    background: llmStatus.ready ? 'rgba(122,158,120,.12)' : 'rgba(200,165,112,.12)',
                    border: `1px solid ${llmStatus.ready ? 'rgba(122,158,120,.3)' : 'rgba(200,165,112,.35)'}`,
                    borderRadius: 10, padding: '10px 14px', marginBottom: 22
                  }}>
                    <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: llmStatus.ready ? 'var(--accent)' : 'var(--gold)', marginBottom: 4 }}>
                      {llmStatus.ready ? '✦ AI Engine Active' : '⚠ Offline Mode'}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--stone)' }}>
                      {llmStatus.provider} &mdash; {llmStatus.model}
                    </div>
                    {!llmStatus.ready && (
                      <div style={{ fontSize: 11, color: 'var(--mist)', marginTop: 6, lineHeight: 1.6 }}>
                        Add a <code style={{ color: 'var(--accent)', background: 'var(--cream)', padding: '1px 5px', borderRadius: 3 }}>GEMINI_API_KEY</code> to <code style={{ color: 'var(--accent)', background: 'var(--cream)', padding: '1px 5px', borderRadius: 3 }}>saathi-api/.env</code> for free AI.
                      </div>
                    )}
                  </div>
                )}
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

                {/* ── Nudge Sensitivity ────────────────────────────────── */}
                <div className="form-grp">
                  <label className="form-lbl">Nudge sensitivity</label>
                  <div className="nudge-sensitivity-row">
                    {['light', 'balanced', 'proactive'].map(lvl => (
                      <button
                        key={lvl} type="button"
                        className={`nudge-sens-btn ${userSettings.nudge_sensitivity === lvl ? 'active' : ''}`}
                        onClick={() => setUserSettings(s => ({ ...s, nudge_sensitivity: lvl }))}
                      >
                        {lvl === 'light' ? '🕊 Light' : lvl === 'balanced' ? '⚖️ Balanced' : '🔔 Proactive'}
                      </button>
                    ))}
                  </div>
                  <p className="nudge-sens-desc">
                    {userSettings.nudge_sensitivity === 'light'     ? 'Only time-based reminders, max 1 at a time.' :
                     userSettings.nudge_sensitivity === 'proactive' ? 'All nudge types — worry, progress, and time.' :
                     'Time & worry nudges, up to 3 at once.'}
                  </p>
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
