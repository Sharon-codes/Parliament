import React, { useState, useEffect } from 'react';
import { Send, Clock, Calendar, Settings, Sparkles, AlertCircle, BookOpen, Mic, MicOff, Volume2, VolumeX, Search, Code, MessageCircle, X, Loader2, Moon, Sun, PlusCircle, MessageSquare } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const Dashboard = () => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('chat');
  const [sessionId, setSessionId] = useState(null);
  
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', text: "Namaste! My serene memory matrix is online. How can I assist you today?" }
  ]);
  const [sessions, setSessions] = useState([]);
  
  const [events, setEvents] = useState([]);
  const [research, setResearch] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  
  // App States
  const [isListening, setIsListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  
  // User Settings
  const [userSettings, setUserSettings] = useState({
    name: 'Guest', interests: 'machine learning', language: 'English', theme: 'light'
  });

  const fetchSessions = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch(e) { console.error("Error fetching sessions", e); }
  };

  const loadSessionChat = async (id) => {
    setSessionId(id);
    setChatHistory([]);
    try {
      const res = await fetch(`http://localhost:8000/api/sessions/${id}`);
      const data = await res.json();
      if(data.messages && data.messages.length > 0) {
        setChatHistory(data.messages);
      } else {
        setChatHistory([{ role: 'ai', text: "Namaste! My serene memory matrix is online. How can I assist you today?" }]);
      }
    } catch(e) { console.error(e); }
  };

  const createNewChat = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/sessions', { method: 'POST' });
      const data = await res.json();
      setSessionId(data.session_id);
      setChatHistory([{ role: 'ai', text: "Namaste! Initializing new encrypted thought channel. What shall we explore?" }]);
      fetchSessions();
    } catch(e) { console.error(e); }
  };

  const loadSettingsAndData = () => {
    fetch('http://localhost:8000/api/settings')
      .then(res => res.json())
      .then(data => {
        setUserSettings(data);
        if(data.theme === 'dark') document.body.classList.add('dark');
        else document.body.classList.remove('dark');
      }).catch(e => console.error(e));

    fetch('http://localhost:8000/api/calendar')
      .then(res => res.json()).then(data => setEvents(data.events || []));

    fetch('http://localhost:8000/api/research')
      .then(res => res.json()).then(data => setResearch(data.papers || []));
      
    fetchSessions();
  };

  useEffect(() => { loadSettingsAndData(); }, []);

  const saveSettings = async (e) => {
    e.preventDefault();
    setShowSettings(false);
    if(userSettings.theme === 'dark') document.body.classList.add('dark');
    else document.body.classList.remove('dark');
    await fetch('http://localhost:8000/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(userSettings)
    });
    loadSettingsAndData();
  };

  const toggleListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Browser voice unsupported.");
    const recognition = new SpeechRecognition();
    recognition.lang = userSettings.language === 'Hindi' ? 'hi-IN' : 'en-US';
    
    if (isListening) { setIsListening(false); return recognition.stop(); }
    setIsListening(true);
    recognition.start();

    recognition.onresult = (e) => { setQuery(e.results[0][0].transcript); setIsListening(false); };
    recognition.onerror = () => setIsListening(false);
  };

  const speak = (text) => {
    if (!voiceEnabled || !('speechSynthesis' in window)) return;
    const utterance = new SpeechSynthesisUtterance(text.replace(/```.*?```/gs, 'code omitted'));
    if(userSettings.language === 'Hindi') utterance.lang = 'hi-IN';
    window.speechSynthesis.speak(utterance);
  };

  const handleSend = async (overrideText = null) => {
    const text = overrideText || query;
    if (!text.trim()) return;
    
    setChatHistory([...chatHistory, { role: 'user', text }]);
    setQuery('');
    setIsTyping(true);
    
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, mode, session_id: sessionId })
      });
      const data = await response.json();
      
      if(data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
      }
      
      setChatHistory(prev => [...prev, { role: 'ai', text: data.reply }]);
      speak(data.reply);
      fetchSessions();
    } catch(e) {
      setChatHistory(prev => [...prev, { role: 'ai', text: "Ollama is disconnected or processing timed out." }]);
    }
    setIsTyping(false);
  };

  return (
    <div className="min-h-screen flex h-screen overflow-hidden text-primary relative">
      {/* Background ambient ocean blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] bg-[var(--blob-1)] rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob z-0 pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[35vw] h-[35vw] bg-[var(--blob-2)] rounded-full mix-blend-multiply filter blur-[80px] opacity-40 animate-blob animation-delay-2000 z-0 pointer-events-none"></div>

      {/* LEFT SIDEBAR: MEMORY MANAGER */}
      <motion.div initial={{ x: -100, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="w-[300px] glass-panel flex flex-col h-full z-10 border-r border-[#0ea5e9]/10">
        <div className="p-6 pb-2">
          <h1 className="text-3xl font-serif tracking-wide flex items-center gap-2">
             <span className="text-[var(--accent)] drop-shadow-[0_0_10px_var(--accent-glow)]">साथी</span>
          </h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-secondary mt-1 opacity-70">Cognitive Registry</p>
        </div>
        
        <div className="p-4">
          <button onClick={createNewChat} className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-[var(--accent)] text-white hover:brightness-110 rounded-2xl shadow-[0_4px_15px_var(--accent-glow)] font-semibold transition-all">
            <PlusCircle size={18} /> New Channel
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-10 space-y-2 mt-4 custom-scrollbar">
          {sessions.length === 0 ? (
            <p className="text-xs text-secondary text-center mt-6 italic">No memory found.</p>
          ) : (
            sessions.map(s => (
              <button 
                key={s.session_id} 
                onClick={() => loadSessionChat(s.session_id)}
                className={`w-full text-left p-3 rounded-2xl transition-all flex items-center gap-3 text-sm font-medium ${sessionId === s.session_id ? 'bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20 shadow-sm' : 'hover:bg-black/5 dark:hover:bg-white/5 text-primary'}`}
              >
                <MessageSquare size={16} className={sessionId === s.session_id ? "opacity-100" : "opacity-40"} />
                <span className="truncate flex-1">{s.title || "New Chat"}</span>
              </button>
            ))
          )}
        </div>
        
        <div className="p-4 pt-2 border-t border-[var(--border)]">
           <button onClick={() => setShowSettings(true)} className="w-full p-3 hover:bg-black/5 dark:hover:bg-white/10 rounded-2xl transition-colors flex items-center gap-3 text-sm font-medium text-secondary hover:text-primary">
             <Settings size={18} /> Deep Settings
           </button>
        </div>
      </motion.div>

      {/* CENTER: THE BRAIN TERMINAL (CHAT) */}
      <div className="flex-1 flex flex-col relative z-10 bg-black/5 dark:bg-black/20">
        <div className="absolute top-6 right-6 z-20 flex gap-3">
           <button onClick={() => setVoiceEnabled(!voiceEnabled)} className={`p-2.5 rounded-full backdrop-blur-md transition-all ${voiceEnabled ? 'bg-[var(--accent)] text-white shadow-[0_0_15px_var(--accent-glow)]' : 'bg-primary border border-theme text-secondary hover:text-primary'}`}>
             {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
           </button>
           <button onClick={() => {setUserSettings({...userSettings, theme: userSettings.theme === 'dark' ? 'light' : 'dark'}); document.body.classList.toggle('dark')}} className="p-2.5 rounded-full border border-theme backdrop-blur-md text-secondary hover:text-primary bg-primary transition-all">
             {userSettings.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
           </button>
        </div>

        <div className="flex-1 overflow-y-auto px-[10%] pt-16 pb-[140px] space-y-8 scroll-smooth">
          <AnimatePresence>
            {chatHistory.map((msg, idx) => (
               <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} key={idx} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] p-6 text-[15px] leading-relaxed shadow-lg ${msg.role === 'user' ? 'bg-[var(--accent)] text-white rounded-3xl rounded-br-[4px] font-medium' : 'ocean-card text-primary rounded-3xl rounded-bl-[4px] markdown-body'}`}>
                    {msg.role === 'ai' && <div className="text-[10px] font-bold mb-3 uppercase tracking-widest flex items-center text-[var(--accent)]"><Sparkles size={12} className="mr-1"/> Saathi Matrix</div>}
                    
                    {msg.role === 'ai' ? (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({node, inline, className, children, ...props}) {
                            const match = /language-(\w+)/.exec(className || '')
                            return !inline && match ? (
                              <div className="rounded-xl overflow-hidden my-4 shadow-xl border border-white/10">
                                <div className="bg-[#1a1b26] px-4 py-2 text-xs text-blue-300 font-mono flex items-center">
                                  <Code size={12} className="mr-2" /> {match[1]}
                                </div>
                                <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" customStyle={{margin: 0, padding: "16px", background: "#1a1b26"}}>
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              </div>
                            ) : (
                              <code className={`${className} bg-blue-500/10 text-[var(--accent)] px-1.5 py-0.5 rounded-md mx-0.5 font-mono text-[13px]`} {...props}>
                                {children}
                              </code>
                            )
                          }
                        }}
                      >
                        {msg.text}
                      </ReactMarkdown>
                    ) : (
                      msg.text
                    )}
                  </div>
               </motion.div>
            ))}
          </AnimatePresence>
          
          {isTyping && (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
               <div className="ocean-card p-5 rounded-3xl rounded-bl-sm shadow-sm flex items-center gap-2">
                 <div className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce"></div>
                 <div className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></div>
                 <div className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></div>
               </div>
             </motion.div>
          )}
        </div>

        {/* Dynamic Ocean Dock */}
        <div className="absolute bottom-0 w-full p-8 pt-10 bg-gradient-to-t from-[var(--bg-primary)] to-transparent via-[var(--bg-primary)] z-20">
          <div className="max-w-4xl mx-auto flex gap-3 h-[60px]">
             
             {/* Dropped Selector */}
             <div className="h-full flex items-center bg-white/40 dark:bg-black/40 backdrop-blur-xl border border-white/20 dark:border-white/10 rounded-[20px] shadow-[0_8px_30px_var(--accent-glow)] focus-within:ring-2 ring-[var(--accent)] transition-all flex-1 px-4">
                <div className="relative flex items-center h-full pr-4 border-r border-[#0ea5e9]/20 group">
                  {mode === 'chat' && <MessageCircle size={18} className="text-[var(--accent)] absolute left-0 pointer-events-none" />}
                  {mode === 'agent' && <Code size={18} className="text-blue-500 absolute left-0 pointer-events-none" />}
                  {mode === 'search' && <Search size={18} className="text-teal-500 absolute left-0 pointer-events-none" />}
                  
                  <select value={mode} onChange={e => setMode(e.target.value)} className="pl-6 h-full bg-transparent border-none outline-none text-sm font-bold text-primary appearance-none cursor-pointer tracking-wide w-[90px]">
                    <option value="chat">TALK</option>
                    <option value="agent">AGENT</option>
                    <option value="search">RADAR</option>
                  </select>
                </div>

               <button onClick={toggleListening} className={`p-3 shrink-0 transition-all ${isListening ? 'text-rose-500 animate-pulse' : 'text-secondary hover:text-[var(--accent)]'}`}>
                 {isListening ? <Mic size={20} /> : <MicOff size={20} />}
               </button>

               <input 
                 autoFocus
                 type="text" 
                 value={query}
                 onChange={e => setQuery(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && handleSend()}
                 placeholder={mode === 'agent' ? "Write and physically run a script..." : mode === 'search' ? "Search global indexes..." : "Whisper to Saathi..."}
                 className="flex-1 h-full bg-transparent border-none outline-none py-2 px-3 text-primary placeholder:text-secondary/60 font-medium text-[15px]"
               />
             </div>

             <button 
               onClick={() => handleSend()}
               disabled={!query.trim()}
               className="h-full px-6 flex items-center justify-center bg-[var(--accent)] text-white rounded-[20px] hover:brightness-110 active:scale-95 transition-all shadow-[0_8px_25px_var(--accent-glow)] disabled:opacity-50 disabled:cursor-not-allowed"
             >
                <Send size={20} />
             </button>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR: INTELLIGENCE WIDGETS */}
      <motion.div initial={{ x: 100, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="w-[350px] glass-panel h-full z-10 flex flex-col overflow-y-auto px-6 py-8 border-l border-[#0ea5e9]/10">
        <h2 className="text-xs font-bold tracking-[0.25em] text-secondary uppercase mb-6 drop-shadow-sm flex items-center">
            <Sparkles size={14} className="mr-2 text-[var(--accent)]" /> Active Sync
        </h2>

        <div className="space-y-6">
          <section>
            <h3 className="text-[11px] font-bold tracking-[0.2em] text-[var(--accent)] mb-3 uppercase flex items-center opacity-80"><Calendar size={13} className="mr-2" /> Live Timeline</h3>
            <div className="grid gap-3">
              {events.length === 0 ? <p className="text-xs text-secondary opacity-50">Calibrating timeline...</p> : events.map(ev => (
                <div key={ev.id} className="ocean-card p-4 rounded-2xl flex items-start gap-4 transition-transform hover:scale-[1.02]">
                  <div className={`mt-0.5 p-2 rounded-xl backdrop-blur-md ${ev.type === 'meeting' ? 'bg-blue-500/10 text-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.3)]' : 'bg-rose-500/10 text-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.3)]'}`}>
                    {ev.type === 'meeting' ? <Clock size={16} /> : <AlertCircle size={16} />}
                  </div>
                  <div>
                    <h4 className="font-bold text-[13px] leading-tight text-primary/90">{ev.title}</h4>
                    <span className="inline-block mt-2 text-[10px] uppercase tracking-wider font-bold bg-white/40 dark:bg-black/40 px-2 py-0.5 rounded-md text-secondary">{ev.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-[11px] font-bold tracking-[0.2em] mb-4 uppercase flex items-center text-[var(--accent)] opacity-80 mt-6"><BookOpen size={13} className="mr-2" /> {userSettings.interests} Radar</h3>
            <div className="space-y-4">
              {research.length === 0 ? <Loader2 size={16} className="animate-spin text-[var(--accent)] ml-2" /> : research.map((r, i) => (
                <a href={r.link} target="_blank" rel="noreferrer" key={i} className="block ocean-card p-5 rounded-2xl group transition-all hover:-translate-y-1 hover:shadow-[0_12px_30px_var(--accent-glow)]">
                  <div className="flex items-center gap-2 mb-2">
                     <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-pulse shadow-[0_0_5px_#2dd4bf]"></span>
                     <span className="text-[9px] uppercase font-bold text-teal-500 tracking-widest">Live Paper</span>
                  </div>
                  <h4 className="text-[13px] font-semibold leading-relaxed text-primary/90 group-hover:text-[var(--accent)]">{r.title}</h4>
                </a>
              ))}
            </div>
          </section>
        </div>
      </motion.div>

      {/* Settings Modal overlay */}
      <AnimatePresence>
        {showSettings && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-[#020617]/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.95, opacity: 0, y: -20 }} className="ocean-card p-8 rounded-[30px] w-full max-w-md border border-[var(--border)] overflow-hidden relative">
              <div className="flex justify-between items-center mb-8 relative z-10">
                <h2 className="text-xl font-bold text-primary flex items-center gap-2"><Sparkles size={20} className="text-[var(--accent)]"/> Matrix Settings</h2>
                <button onClick={() => setShowSettings(false)} className="bg-black/5 dark:bg-white/5 p-2 rounded-full hover:bg-[var(--accent)] hover:text-white transition-colors text-secondary"><X size={16}/></button>
              </div>
              <form onSubmit={saveSettings} className="space-y-6 relative z-10 w-full">
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-secondary block mb-2 px-1">Display Name</label>
                  <input type="text" value={userSettings.name} onChange={e => setUserSettings({...userSettings, name: e.target.value})} className="w-full bg-white/50 dark:bg-black/50 border border-[var(--border)] rounded-2xl px-5 py-3.5 text-sm font-semibold outline-none focus:ring-2 ring-[var(--accent)]/50 transition-all shadow-inner" />
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-secondary block mb-2 px-1">Focus Target</label>
                  <input type="text" value={userSettings.interests} onChange={e => setUserSettings({...userSettings, interests: e.target.value})} className="w-full bg-white/50 dark:bg-black/50 border border-[var(--border)] rounded-2xl px-5 py-3.5 text-sm font-semibold outline-none focus:ring-2 ring-[var(--accent)]/50 transition-all shadow-inner" />
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-secondary block mb-2 px-1">Voice Protocol</label>
                  <select value={userSettings.language} onChange={e => setUserSettings({...userSettings, language: e.target.value})} className="w-full bg-white/50 dark:bg-black/50 border border-[var(--border)] rounded-2xl px-5 py-3.5 text-sm font-semibold outline-none focus:ring-2 ring-[var(--accent)]/50 transition-all shadow-inner appearance-none cursor-pointer">
                    <option>English</option><option>Hindi</option><option>Japanese</option><option>French</option>
                  </select>
                </div>
                <button type="submit" className="w-full bg-gradient-to-r from-[var(--accent)] to-blue-500 text-white mt-8 py-4 rounded-2xl font-bold tracking-widest text-[11px] uppercase shadow-[0_8px_25px_var(--accent-glow)] hover:opacity-90 active:scale-[0.98] transition-all relative overflow-hidden">
                   Re-sync Memory
                </button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default Dashboard;
