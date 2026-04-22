import React, { useState, useEffect, useRef } from "react";
import { 
  Plus, Settings, LogOut, Send, Mic, 
  LoaderCircle, Mail, Calendar, ExternalLink, Smartphone, 
  MessageSquare, Trash2, ArrowRight, Brain, Globe, Volume2, 
  ArrowLeft, Clock, CheckCircle2, AlertCircle, Trash, Menu, X, Monitor, FileText, PlusCircle, Languages, Paperclip
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { apiFetch, getAvatarUrl, formatSessionDate } from "../lib/api";
import { API_BASE } from "../lib/config";
import WorkspaceActionModal from "../components/WorkspaceActionModal";
import ConnectPage from "./ConnectPage";
import PolyglotPortal from "./PolyglotPortal";

function createLocalMessage(role, text) {
  return { id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`, role, text };
}

function detectQuickAction(message, activeProtocol) {
  const text = (message || "").trim();
  const lower = text.toLowerCase();
  const protocolName = activeProtocol?.name;

  if (protocolName === "Gmail") return "email";
  if (protocolName === "GMeet") return "meeting";
  if (protocolName === "Mirror") return "doc";
  if (protocolName === "YouTube") return "youtube";
  if (protocolName === "Computer") return "app";

  if (/^(mail|email|send email|compose email)\b/i.test(text)) return "email";
  if (/^(meeting|schedule meeting|book meeting|create meeting)\b/i.test(text)) return "meeting";
  if (/^(doc|document|create doc|create google doc|make google doc)\b/i.test(text)) return "doc";
  if (/\b(youtube|watch|play)\b/i.test(text)) return "youtube";
  if (/^(open|launch|start)\b/i.test(text) && !lower.includes("google doc")) return "app";
  return null;
}

function extractAppName(message, activeProtocol) {
  const text = (message || activeProtocol?.draft || "").trim();
  // ROBUST ROUTING (v122.0): Keep implementation intent (write/create/etc)
  let cleaned = text
    .replace(/^(saathi,\s*)?/i, "")
    .replace(/^(open|launch|start)\s+/i, "")
    .replace(/\s+(on my laptop|on my computer)\s*$/i, "")
    .trim();
  
  // If it starts with "my workstation:", keep the rest
  cleaned = cleaned.replace(/^(my\s+workstation\s*:?\s*)/i, "").trim();
  return cleaned;
}

function extractYouTubeQuery(message, activeProtocol) {
  const text = (message || activeProtocol?.draft || "").trim();
  return text
    .replace(/^(open youtube|youtube|play|watch)\s*/i, "")
    .replace(/\s+on youtube\s*$/i, "")
    .trim();
}

function shouldAttachDocumentContext(message, currentFile) {
  if (!currentFile?.content) return false;
  return /\b(doc|document|file|attached|attachment|this|summarize|summary|translate|analyze|review|read)\b/i.test(message || "");
}

const MessageBubble = ({ message, onSpeak, speakingId }) => {
  const isAssistant = message.role === "assistant";
  
  const linkify = (text) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    return parts.map((part, i) => {
      if (part.match(urlRegex)) {
        return (
          <a 
            key={i} 
            href={part} 
            target="_blank" 
            rel="noopener noreferrer" 
            style={{ 
              display: 'inline-flex', alignItems: 'center', gap: '8px',
              padding: '6px 12px', background: '#1c1917', color: 'white',
              borderRadius: '8px', textDecoration: 'none', fontSize: '0.8rem',
              margin: '4px 0', fontWeight: '500'
            }}
          >
            <ExternalLink size={14} />
            Open Resource
          </a>
        );
      }
      return part;
    });
  };

  return (
    <motion.div 
      className={`msg-row ${message.role}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ overflowWrap: 'anywhere', wordBreak: 'break-word', width: '100%' }}
    >
      <div className="msg-bubble" style={{ maxWidth: '85%', position: 'relative' }}>
        {linkify(message.text)}
        {isAssistant && (
          <button style={{ 
            marginTop: '10px', display: 'flex', alignItems: 'center', background: 'none', border: 'none', color: '#78716c', cursor: 'pointer' 
          }} onClick={() => onSpeak(message.id, message.text)}>
            <Volume2 size={14} />
          </button>
        )}
      </div>
    </motion.div>
  );
};

const Dashboard = ({ session, profile, setProfile, onSignOut }) => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [view, setView] = useState("DASHBOARD"); 
  const [chatMode, setChatMode] = useState("agentic"); 
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [speakingId, setSpeakingId] = useState(null);
  const [activeProtocol, setActiveProtocol] = useState(null); // {icon: any, name: string, draft: string}
  const [showFab, setShowFab] = useState(false);
  const [showLanguageSelector, setShowLanguageSelector] = useState(false);
  const [currentFile, setCurrentFile] = useState(null);
  const [workspaceModal, setWorkspaceModal] = useState(null);
  const [pendingQuickActionPrompt, setPendingQuickActionPrompt] = useState("");
  const fileInputRef = useRef(null);
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extracting, setExtracting] = useState(false);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 1024;

  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadSessions();
    // Proactive Workspace Sync
    apiFetch("/api/workspace/sync", { session, method: "POST" }).catch(err => console.error("Sync fail:", err));
  }, []);

  useEffect(() => {
    if (activeSession) loadMessages(activeSession.id);
  }, [activeSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const loadSessions = async () => {
    try {
      const data = await apiFetch("/api/sessions", { session });
      if (Array.isArray(data)) {
        setSessions(data);
        if (data.length > 0 && !activeSession) setActiveSession(data[0]);
      } else {
        console.error("Invalid sessions response:", data);
        setSessions([]);
      }
    } catch (err) {
      console.error("Load sessions crash:", err);
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadMessages = async (sid) => {
    if (!sid) return;
    setLoadingMessages(true);
    try {
      const data = await apiFetch(`/api/sessions/${sid}/messages`, { session });
      if (Array.isArray(data)) {
        setMessages(data);
      } else {
        console.error("Invalid messages response:", data);
        setMessages([]);
      }
    } catch (err) {
      console.error("Load messages crash:", err);
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  };

  const ensureSession = async (title = "Quick Action") => {
    if (activeSession?.id) return activeSession.id;
    const created = await apiFetch("/api/sessions", {
      session,
      method: "POST",
      body: { title },
    });
    setSessions((prev) => [created, ...prev]);
    setActiveSession(created);
    return created.id;
  };

  const appendQuickActionMessages = async (userText, assistantText) => {
    await ensureSession();
    setMessages((prev) => [
      ...prev,
      createLocalMessage("user", userText),
      createLocalMessage("assistant", assistantText),
    ]);
  };

  const openWorkspaceModal = (type, prompt = "") => {
    setPendingQuickActionPrompt(prompt || draft);
    setWorkspaceModal(type);
    setShowFab(false);
  };

  const handleCreateSession = async () => {
    const res = await apiFetch("/api/sessions", {
      session,
      method: "POST",
      body: { title: "New Thought" }
    });
    setSessions([res, ...sessions]);
    setActiveSession(res);
  };

  const handleDeleteSession = async (id, e) => {
    e.stopPropagation();
    await apiFetch(`/api/sessions/${id}`, { session, method: "DELETE" });
    setSessions(sessions.filter(s => s.id !== id));
    if (activeSession?.id === id) setActiveSession(null);
  };

  const handleProtocolSelect = (icon, name, draft) => {
    if (name === "Gmail") {
      openWorkspaceModal("email", currentFile ? `email ${currentFile.name}` : draft);
      return;
    }

    if (name === "GMeet") {
      openWorkspaceModal("meeting", draft);
      return;
    }

    if (name === "Mirror") {
      openWorkspaceModal("doc", currentFile?.content || draft);
      return;
    }

    if (name === "Translate" && currentFile) {
        setShowLanguageSelector(true);
        setShowFab(false);
        return;
    }

    setActiveProtocol({ icon, name, draft });
    setDraft(draft);
    setShowFab(false);
  };

  const resetProtocol = () => {
    setActiveProtocol(null);
    setDraft("");
    setShowFab(false);
    setWorkspaceModal(null);
    setPendingQuickActionPrompt("");
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (file) {
      setSending(true);
      setUploadProgress(10);
      const formData = new FormData();
      formData.append("file", file);
      
      const simulateProgress = setInterval(() => {
        setUploadProgress(prev => (prev < 90 ? prev + 15 : prev));
      }, 300);

      try {
        setExtracting(true);
        const res = await apiFetch(`/api/extract-doc`, {
          session,
          method: "POST",
          body: formData
        });
        setUploadProgress(100);
        setTimeout(() => setUploadProgress(0), 800);
        setCurrentFile({ name: file.name, content: res.content, file, size: (file.size / 1024).toFixed(1) + " KB" });
      } catch (err) {
        setUploadProgress(0);
        alert("Failed to read document: " + err.message);
      } finally {
        clearInterval(simulateProgress);
        setExtracting(false);
        setSending(false);
      }
    }
  };

  const handleTranslateDoc = async (targetLang) => {
    if (!currentFile) return;
    
    try {
      setSending(true);
      let res;
      if (currentFile.file) {
        const formData = new FormData();
        formData.append("file", currentFile.file);
        formData.append("target_lang", targetLang || "hi");
        res = await apiFetch(`/api/workspace/translate-file`, {
          session,
          method: "POST",
          body: formData,
        });
      } else {
        const sid = await ensureSession(currentFile.name);
        res = await apiFetch(`/api/sessions/${sid}/translate`, {
          session,
          method: "POST",
          body: {
            name: currentFile.name,
            content: currentFile.content,
            target_lang: targetLang || "hi"
          }
        });
      }
      setMessages(prev => [...prev, createLocalMessage("assistant", `Translation mirrored to Workspace.\nLink: ${res.document?.url || res.link}`)]);
    } catch (err) {
      alert("Translation failed: " + err.message);
    } finally {
      setSending(false);
    }
  };

  const handleDirectQuickAction = async (type, userMsg) => {
    if (type === "email" || type === "meeting" || type === "doc") {
      openWorkspaceModal(type, userMsg);
      setDraft("");
      setActiveProtocol(null);
      return;
    }

    try {
      setSending(true);
      if (type === "youtube") {
        const query = extractYouTubeQuery(userMsg, activeProtocol);
        const result = await apiFetch("/api/system/open-youtube", {
          session,
          method: "POST",
          body: { query },
        });
        await appendQuickActionMessages(userMsg, result.message);
      }

      if (type === "app") {
        const appName = extractAppName(userMsg, activeProtocol);
        const result = await apiFetch("/api/system/open-app", {
          session,
          method: "POST",
          body: { app_name: appName },
        });
        await appendQuickActionMessages(userMsg, result.message);
      }

      setDraft("");
      setActiveProtocol(null);
    } finally {
      setSending(false);
    }
  };

  const handleSend = async () => {
    const userMsg = draft.trim();
    if (!userMsg || sending) return;

    const quickAction = detectQuickAction(userMsg, activeProtocol);
    if (quickAction) {
      await handleDirectQuickAction(quickAction, userMsg);
      return;
    }

    setDraft(activeProtocol ? activeProtocol.draft : "");

    const sid = await ensureSession(userMsg.slice(0, 30));
    const activeFile = currentFile;
    setMessages(prev => [...prev, createLocalMessage("user", userMsg)]);
    setSending(true);

    try {
      const res = await apiFetch(`/api/sessions/${sid}/chat`, {
        session,
        method: "POST",
        body: { 
          text: userMsg, 
          mode: chatMode,
          doc_context: shouldAttachDocumentContext(userMsg, activeFile) ? { name: activeFile.name, content: activeFile.content } : null
        }
      });
      
      // 🧬 Smart Redirect Handler (v113.0)
      if (typeof res.text === "string" && res.text.includes("DEVICE_REDIRECT:")) {
        const parts = res.text.split("DEVICE_REDIRECT:");
        const urlPart = parts[1].split(/\s/)[0].trim();
        window.open(urlPart, "_blank");
        res.text = res.text.replace(/DEVICE_REDIRECT:[^\s]+/, "🚀 Signal intercepted. Command executed on this device.");
      }
      
      setMessages(prev => [...prev, res]);
    } finally {
      setSending(false);
    }
  };

  const speakMessage = (id, text) => {
    if (speakingId) {
      window.speechSynthesis.cancel();
      if (speakingId === id) { setSpeakingId(null); return; }
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setSpeakingId(null);
    setSpeakingId(id);
    window.speechSynthesis.speak(utterance);
  };


  if (view === "MOBILE_CONNECT") {
    return <ConnectPage onBack={() => setView("DASHBOARD")} session={session} />;
  }

  if (view === "POLYGLOT_PORTAL") {
    return <PolyglotPortal session={session} onBack={() => setView("DASHBOARD")} />;
  }

  const fabTargets = isMobile
    ? {
        conversation: { x: 0, y: -76 },
        gmail: { x: 76, y: -76 },
        meeting: { x: 152, y: -76 },
        translate: { x: 0, y: -152 },
        youtube: { x: 76, y: -152 },
        computer: { x: 152, y: -152 },
        doc: { x: 76, y: -228 },
      }
    : {
        conversation: { x: -140, y: 0 },
        gmail: { x: -121, y: -70 },
        meeting: { x: -70, y: -121 },
        translate: { x: 0, y: -140 },
        youtube: { x: 70, y: -121 },
        computer: { x: 121, y: -70 },
        doc: { x: 140, y: 0 },
      };

  return (
    <div className="wabi-shell">
      <WorkspaceActionModal
        open={Boolean(workspaceModal)}
        type={workspaceModal}
        session={session}
        initialPrompt={pendingQuickActionPrompt}
        currentFile={currentFile}
        onClose={() => {
          setWorkspaceModal(null);
          setPendingQuickActionPrompt("");
        }}
        onSuccess={async ({ assistantText }) => {
          await appendQuickActionMessages(pendingQuickActionPrompt || workspaceModal, assistantText);
          setWorkspaceModal(null);
          setPendingQuickActionPrompt("");
          setDraft("");
          setActiveProtocol(null);
        }}
      />

      {isMobile && (
        <button 
          onClick={() => setShowMobileSidebar(true)}
          style={{ position: 'fixed', top: '24px', left: '24px', zIndex: 1000, background: 'var(--ink)', color: 'white', borderRadius: '50%', width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
        >
          <Menu size={20} />
        </button>
      )}

      <div className={`dashboard-layout ${showMobileSidebar ? "mobile-sidebar-active" : ""}`}>
        <aside className={`side-panel ${showMobileSidebar ? "active" : ""}`}>
          {isMobile && (
            <button 
              onClick={() => setShowMobileSidebar(false)}
              style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'var(--ink)' }}
            >
              <X size={24} />
            </button>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginBottom: '10px' }}>
            <Brain size={28} />
            <h2 className="serif" style={{ fontSize: '1.8rem' }}>Saathi</h2>
          </div>
          <p className="hero-tag" style={{ textAlign: 'center', marginBottom: '20px' }}>Neural Intelligence</p>

          <button className="pill-btn" onClick={() => { handleCreateSession(); if(isMobile) setShowMobileSidebar(false); }} style={{ padding: '14px' }}>
            <Plus size={18} />
            <span>New Session</span>
          </button>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <p className="hero-tag" style={{ marginBottom: 0 }}>Memory Threads</p>
            {sessions.map(s => (
              <div 
                key={s.id} 
                className={`wabi-card ${activeSession?.id === s.id ? "active" : ""}`}
                style={{ 
                  padding: '16px 20px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between',
                  background: activeSession?.id === s.id ? '#1c1917' : 'white',
                  color: activeSession?.id === s.id ? 'white' : '#1c1917'
                }}
                onClick={() => { setActiveSession(s); if(isMobile) setShowMobileSidebar(false); }}
              >
                <div style={{ overflow: 'hidden' }}>
                  <h4 className="serif" style={{ fontSize: '1rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{s.title}</h4>
                  <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>{formatSessionDate(s.updated_at)}</span>
                </div>
                <button 
                  onClick={(e) => handleDeleteSession(s.id, e)} 
                  style={{ 
                    background: 'none', border: 'none', color: activeSession?.id === s.id ? '#78716c' : '#f87171',
                    cursor: 'pointer', padding: '4px' 
                  }}
                >
                  <Trash size={14} />
                </button>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            {!isMobile && (
              <button className="pill-btn secondary" onClick={() => setView("MOBILE_CONNECT")} style={{ flex: 1, padding: '12px', justifyContent: 'center' }} title="Mobile Link">
                <Smartphone size={18} />
              </button>
            )}
            <button className="pill-btn secondary" onClick={onSignOut} style={{ flex: 1, padding: '12px', justifyContent: 'center' }} title="Sign Out">
              <LogOut size={18} />
            </button>
          </div>

          <div style={{ marginTop: '20px', textAlign: 'center', opacity: 0.4, fontSize: '0.65rem' }}>
            <p className="serif">By Khushi & Sharon</p>
            <p>Warriors against Antigravity ⚔️</p>
          </div>
        </aside>

        <main className="main-panel">
          <div className="chat-scroll">
            {messages.length === 0 && !loadingMessages && (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', opacity: 0.5 }}>
                <MessageSquare size={48} style={{ marginBottom: '20px' }} />
                <h3 className="serif">Neural Canvas Empty</h3>
                <p>Begin a conversation to anchor your thoughts.</p>
              </div>
            )}
            {messages.map(m => (
              <MessageBubble 
                key={m.id} 
                message={m} 
                onSpeak={speakMessage} 
                speakingId={speakingId} 
              />
            ))}
            {sending && (
              <div className="msg-row assistant">
                <div className="msg-bubble" style={{ display: 'flex', gap: '8px', padding: '16px 24px' }}>
                  <LoaderCircle size={18} className="animate-spin" />
                  <span>Saathi is thinking...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Language Selector Overlay (v101.0) */}
          <AnimatePresence>
            {showLanguageSelector && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="language-selector-overlay"
              >
                <div className="selector-header">
                  <Languages size={20} />
                  <span>Select Target Language</span>
                  <button onClick={() => setShowLanguageSelector(false)}><X size={16} /></button>
                </div>
                <div className="selector-grid">
                   <button onClick={() => { handleTranslateDoc("hi"); setShowLanguageSelector(false); }}>Hindi</button>
                   <button onClick={() => { handleTranslateDoc("bn"); setShowLanguageSelector(false); }}>Bengali</button>
                   <button onClick={() => { handleTranslateDoc("te"); setShowLanguageSelector(false); }}>Telugu</button>
                   <button onClick={() => { handleTranslateDoc("mr"); setShowLanguageSelector(false); }}>Marathi</button>
                   <button onClick={() => { handleTranslateDoc("ta"); setShowLanguageSelector(false); }}>Tamil</button>
                   <button onClick={() => { handleTranslateDoc("kn"); setShowLanguageSelector(false); }}>Kannada</button>
                   <button onClick={() => { handleTranslateDoc("ml"); setShowLanguageSelector(false); }}>Malayalam</button>
                   <button onClick={() => { handleTranslateDoc("gu"); setShowLanguageSelector(false); }}>Gujarati</button>
                   <button onClick={() => { handleTranslateDoc("pa"); setShowLanguageSelector(false); }}>Punjabi</button>
                   <button onClick={() => { handleTranslateDoc("or"); setShowLanguageSelector(false); }}>Odia</button>
                   <button onClick={() => { handleTranslateDoc("as"); setShowLanguageSelector(false); }}>Assamese</button>
                   <button onClick={() => { handleTranslateDoc("sa"); setShowLanguageSelector(false); }}>Sanskrit</button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Premium Document Attachment Pill (v121.8) */}
          <AnimatePresence>
            {currentFile && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                className="premium-doc-pill"
              >
                <div className="doc-icon-box">
                  <FileText size={20} />
                </div>
                <div className="doc-info">
                  <span className="doc-name">{currentFile.name}</span>
                  <span className="doc-meta">Neural Sync Active • {currentFile.status || "Ready"}</span>
                </div>
                <button 
                  className="doc-purge-btn" 
                  onClick={() => { setCurrentFile(null); if(activeProtocol?.name === "Gmail") resetProtocol(); }}
                >
                  <X size={16} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Neural Analysis Progress Pill */}
          <AnimatePresence>
            {extracting && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="analysis-progress-pill"
              >
                <LoaderCircle size={18} className="animate-spin" />
                <span>Anchoring Semantic Context...</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Neural Analysis Progress */}
          <AnimatePresence>
            {uploadProgress > 0 && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="upload-progress-bar"
              >
                <div className="progress-label">Neural Analysis Underway... {uploadProgress}%</div>
                <div className="progress-track">
                  <motion.div 
                    className="progress-fill" 
                    initial={{ width: 0 }}
                    animate={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="chat-input-bar">
             <div className="fab-container">
                <motion.div className="fab-menu">
                   <AnimatePresence>
                   {showFab && (
                     <>
                       {/* Icon 1: Normal Chat (Left) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.conversation.x, y: fabTargets.conversation.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={resetProtocol}
                         title="Pure Conversation"
                       >
                         <MessageSquare size={20} />
                       </motion.button>

                       {/* Icon 2: Gmail (30 deg) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.gmail.x, y: fabTargets.gmail.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(Mail, "Gmail", "")}
                         title="Gmail Courier"
                       >
                         <Mail size={20} />
                       </motion.button>

                       {/* Icon 3: GMeet (60 deg) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.meeting.x, y: fabTargets.meeting.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(Calendar, "GMeet", "")}
                         title="GMeet Link"
                       >
                         <Calendar size={20} />
                       </motion.button>

                       {/* Icon 4: Translate (90 deg) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.translate.x, y: fabTargets.translate.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(Languages, "Translate", "Translate this doc: ")}
                         title="Polyglot Engine"
                       >
                         <Languages size={20} />
                       </motion.button>

                       {/* Icon 5: YouTube (120 deg) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.youtube.x, y: fabTargets.youtube.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(Globe, "YouTube", "Open YouTube: ")}
                         title="YouTube Search"
                       >
                         <Globe size={20} />
                       </motion.button>

                       {/* Icon 6: Computer (150 deg) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.computer.x, y: fabTargets.computer.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(Monitor, "Computer", "Saathi, open my workstation: ")}
                         title="Computer Control"
                       >
                         <Monitor size={20} />
                       </motion.button>

                       {/* Icon 7: Docs (Right) */}
                       <motion.button 
                         className="fab-sub-btn"
                         initial={{ scale: 0, x: 0, y: 0 }}
                         animate={{ scale: 1, x: fabTargets.doc.x, y: fabTargets.doc.y }}
                         exit={{ scale: 0, x: 0, y: 0 }}
                         onClick={() => handleProtocolSelect(FileText, "Mirror", "Create Google Doc: ")}
                         title="Mirror: Google Doc"
                       >
                         <FileText size={20} />
                       </motion.button>
                     </>
                   )}
                   </AnimatePresence>

                 <motion.button 
                   className={`main-fab ${showFab ? "active" : ""} ${activeProtocol ? "protocol-active" : ""}`}
                   onClick={() => setShowFab(!showFab)}
                   whileTap={{ scale: 0.9 }}
                   style={{ background: activeProtocol ? '#1c1917' : 'var(--ink)' }}
                 >
                   {activeProtocol ? (
                      <activeProtocol.icon size={24} />
                   ) : (
                      <Plus size={24} style={{ transform: showFab ? "rotate(45deg)" : "rotate(0deg)", transition: 'transform 0.3s ease' }} />
                   )}
                 </motion.button>
                </motion.div>
             </div>

             <input 
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                onChange={handleFileUpload}
             />

             <button className="bar-icon-btn" onClick={() => fileInputRef.current.click()} title="Attach Document" style={{ marginRight: '-8px' }}>
               <Paperclip size={22} />
             </button>

             <input 
               className="wabi-input"
               placeholder="Whisper your intent..."
               value={draft}
               onChange={(e) => setDraft(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && handleSend()}
             />

             <button className="pill-btn send-btn" onClick={handleSend}>
               <Send size={20} />
             </button>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Dashboard;

const fabStyles = `
.msg-bubble {
  padding: 16px 24px;
  border-radius: 20px;
  font-size: 1rem;
}

.assistant .msg-bubble {
  background: #f5f5f4;
  color: #1c1917;
}

.user .msg-bubble {
  background: #1c1917;
  color: white;
}

.side-panel {
  background: white;
  border-right: 1px solid #e7e5e4;
}

.wabi-card {
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
}

.wabi-card.active {
  background: #1c1917;
  color: white;
}


.purge-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #a8a29e;
  display: flex;
}
  position: absolute;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  padding: 24px;
  border-radius: 24px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.15);
  border: 1px solid #e7e5e4;
  z-index: 100000;
  width: 300px;
}

.selector-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-weight: 600;
}

.selector-header span { flex: 1; }
.selector-header button { background: none; border: none; cursor: pointer; color: #a8a29e; }

.selector-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.selector-grid button {
  padding: 12px;
  background: #f5f5f4;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s ease;
}

.selector-grid button:hover {
  background: var(--ink);
  color: white;
}

.chat-input-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  background: white;
  padding: 10px 0;
  width: 100%;
}

.fab-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000;
  margin-right: 20px;
}

.fab-menu {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.main-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--ink);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  z-index: 100001;
  pointer-events: auto;
}

.active-protocol-badge {
  position: absolute;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  background: #1c1917;
  color: white;
  padding: 8px 16px;
  border-radius: 100px;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
  z-index: 10000;
}

.badge-icon {
  width: 24px;
  height: 24px;
  background: white;
  color: #1c1917;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.main-fab.active {
  background: #78716c;
}

.fab-sub-btn {
  position: absolute;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: white;
  color: var(--ink);
  border: 1px solid #e7e5e4;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(0,0,0,0.2);
  z-index: 100002;
  pointer-events: auto;
  transition: all 0.2s ease;
}

.fab-sub-btn:hover {
  background: #f5f5f4;
  box-shadow: 0 8px 20px rgba(0,0,0,0.25);
}

.send-btn {
  border-radius: 100px !important;
  width: 60px !important;
  height: 60px !important;
  padding: 0 !important;
  justify-content: center !important;
}

.wabi-input {
  flex: 1;
  background: #f5f5f4;
  border: none;
  border-radius: 100px;
  padding: 18px 30px;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s ease;
}

.wabi-input:focus {
  background: white;
  box-shadow: inset 0 0 0 2px var(--ink);
}

.premium-doc-pill {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  border: 1px solid #e7e5e4;
  border-radius: 16px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.1);
  z-index: 1000;
  min-width: 280px;
}

.doc-icon-box {
  width: 40px;
  height: 40px;
  background: #f5f5f4;
  color: #1c1917;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.doc-info {
  display: flex;
  flex-direction: column;
}

.doc-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: #1c1917;
}

.doc-meta {
  font-size: 0.75rem;
  color: #78716c;
}

.doc-purge-btn {
  background: none;
  border: none;
  color: #d6d3d1;
  cursor: pointer;
  padding: 4px;
  margin-left: auto;
  transition: color 0.2s;
}

.doc-purge-btn:hover { color: #ef4444; }

.upload-progress-bar {
  position: absolute;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  width: 300px;
  text-align: center;
  z-index: 1001;
}

.progress-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #1c1917;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.progress-track {
  width: 100%;
  height: 6px;
  background: #f5f5f4;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #1c1917;
}
`;

if (typeof document !== 'undefined') {
  const styleSheet = document.createElement("style");
  styleSheet.innerText = fabStyles;
  document.head.appendChild(styleSheet);
}

