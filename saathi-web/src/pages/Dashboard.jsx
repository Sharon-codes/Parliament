import React, { useState, useEffect, useRef } from 'react';
import { Send, Clock, Calendar, Settings, Sparkles, BookOpen, Mic, MicOff, Volume2, VolumeX, Search, Code, MessageCircle, X, Loader2, Moon, Sun, Plus, AlignLeft } from 'lucide-react';
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
    { role: 'ai', text: "Peace and welcome. How may I be of service today?" }
  ]);
  const [sessions, setSessions] = useState([]);
  
  const [events, setEvents] = useState([]);
  const [research, setResearch] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  
  const [isListening, setIsListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const chatEndRef = useRef(null);
  
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
        setChatHistory([{ role: 'ai', text: "Peace and welcome. How may I be of service today?" }]);
      }
    } catch(e) { console.error(e); }
  };

  const createNewChat = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/sessions', { method: 'POST' });
      const data = await res.json();
      setSessionId(data.session_id);
      setChatHistory([{ role: 'ai', text: "A fresh perspective. What shall we explore?" }]);
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isTyping]);

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
    const utterance = new SpeechSynthesisUtterance(text.replace(/```.*?```/gs, 'code block'));
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
      setChatHistory(prev => [...prev, { role: 'ai', text: "Connection to core disrupted." }]);
    }
    setIsTyping(false);
  };

  return (
    <div className="flex h-screen w-full font-sans transition-colors duration-500 bg-[var(--bg-chat)] text-[#2D2D2D] dark:text-[#E5E5E5]">
      
      {/* LEFT SIDEBAR: MEMORY */}
      <div className="w-[280px] h-full border-r border-[var(--border)] flex flex-col bg-[var(--bg-sidebar)] z-10 shrink-0">
        <div className="p-6 flex items-center justify-between">
          <h1 className="text-xl font-medium tracking-wide">Saathi</h1>
          <button onClick={() => setShowSettings(true)} className="text-[var(--text-muted)] hover:text-[#2D2D2D] dark:hover:text-[#E5E5E5] transition-colors"><Settings size={18} /></button>
        </div>
        
        <div className="px-6 mb-4">
          <button onClick={createNewChat} className="w-full flex items-center justify-start gap-3 py-2.5 px-4 bg-[var(--bg-chat)] border border-[var(--border)] hover:bg-[#EBEBE9] dark:hover:bg-[#222222] rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} /> New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 space-y-1 pb-4">
          <p className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">History</p>
          {sessions.length === 0 ? (
             <p className="px-3 text-xs text-[var(--text-muted)]">No memory recorded.</p>
          ) : (
            sessions.map(s => (
              <button 
                key={s.session_id} 
                onClick={() => loadSessionChat(s.session_id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors flex items-center gap-3 text-sm truncate ${sessionId === s.session_id ? 'bg-[var(--bg-chat)] border border-[var(--border)] font-medium shadow-sm' : 'hover:bg-[#EAEAE8] dark:hover:bg-[#1A1A1A] font-normal text-[var(--text-muted)] hover:text-inherit'}`}
              >
                <AlignLeft size={14} className="shrink-0 opacity-50" />
                <span className="truncate">{s.title || "New Chat"}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* CENTER: CHAT */}
      <div className="flex-1 flex flex-col h-full relative z-0">
        
        <div className="absolute top-4 right-6 z-20 flex gap-2">
           <button onClick={() => setVoiceEnabled(!voiceEnabled)} className="p-2.5 rounded-full text-[var(--text-muted)] hover:bg-[var(--border)] transition-colors">
             {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
           </button>
           <button onClick={() => {setUserSettings({...userSettings, theme: userSettings.theme === 'dark' ? 'light' : 'dark'}); document.body.classList.toggle('dark')}} className="p-2.5 rounded-full text-[var(--text-muted)] hover:bg-[var(--border)] transition-colors">
             {userSettings.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
           </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 sm:px-12 md:px-[15%] pt-16 pb-36 scroll-smooth">
          <AnimatePresence>
            {chatHistory.map((msg, idx) => (
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} key={idx} className={`w-full flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-8`}>
                  <div className={`max-w-[85%] text-[15px] leading-relaxed ${msg.role === 'user' ? 'chat-bubble-user px-5 py-3 rounded-2xl rounded-tr-sm' : 'chat-bubble-ai markdown-body'}`}>
                    {msg.role === 'ai' ? (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({node, inline, className, children, ...props}) {
                            const match = /language-(\w+)/.exec(className || '')
                            return !inline && match ? (
                              <div className="rounded-lg overflow-hidden my-4 border border-[#333]">
                                <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" customStyle={{margin: 0, padding: "16px", background: "#1E1E1E", fontSize: "14px"}}>
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              </div>
                            ) : (
                              <code className={`${className}`} {...props}>{children}</code>
                            )
                          }
                        }}
                      >
                        {msg.text}
                      </ReactMarkdown>
                    ) : (
                      <p>{msg.text}</p>
                    )}
                  </div>
               </motion.div>
            ))}
          </AnimatePresence>
          
          {isTyping && (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start mb-8 ml-2">
               <div className="h-6 flex items-center">
                 <div className="dot-flashing"></div>
               </div>
             </motion.div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Minimalist Input Bar */}
        <div className="absolute bottom-0 w-full p-6 bg-gradient-to-t from-[var(--bg-chat)] via-[var(--bg-chat)] to-transparent pt-12">
          <div className="max-w-3xl mx-auto">
             <div className="flex items-center bg-[var(--bg-input)] border border-[var(--border)] rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] focus-within:border-[var(--accent)] transition-all overflow-hidden p-1.5 h-14">
                
                <div className="relative flex items-center h-full px-2">
                  <select value={mode} onChange={e => setMode(e.target.value)} className="appearance-none font-medium text-xs tracking-wider uppercase text-[var(--text-muted)] bg-transparent hover:bg-[var(--bg-sidebar)] pl-8 pr-4 py-2 rounded-lg cursor-pointer transition-colors outline-none">
                    <option value="chat">Chat</option>
                    <option value="agent">Agent</option>
                    <option value="search">Search</option>
                  </select>
                  <div className="absolute left-4 pointer-events-none text-[var(--text-muted)]">
                     {mode === 'chat' && <Sparkles size={14} />}
                     {mode === 'agent' && <Code size={14} />}
                     {mode === 'search' && <Search size={14} />}
                  </div>
                </div>

               <input 
                 autoFocus
                 type="text" 
                 value={query}
                 onChange={e => setQuery(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && handleSend()}
                 placeholder={mode === 'agent' ? "Instruct agent..." : mode === 'search' ? "Search..." : "Message Saathi..."}
                 className="flex-1 h-full bg-transparent border-none outline-none px-4 text-[15px]"
               />

               <button onClick={toggleListening} className={`p-2 shrink-0 transition-colors ${isListening ? 'text-red-500 animate-pulse' : 'text-[var(--text-muted)] hover:text-inherit'}`}>
                 {isListening ? <Mic size={18} /> : <MicOff size={18} />}
               </button>
               
               <button onClick={() => handleSend()} disabled={!query.trim()} className="ml-1 shrink-0 p-2 text-[#2D2D2D] dark:text-[#E5E5E5] disabled:opacity-30 disabled:cursor-not-allowed">
                  <Send size={18} />
               </button>
               
             </div>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR: INTELLIGENCE */}
      <div className="w-[320px] h-full border-l border-[var(--border)] flex flex-col bg-[var(--bg-sidebar)] z-10 shrink-0 overflow-y-auto p-6 hidden md:flex">
        <h2 className="text-[10px] font-bold tracking-[0.2em] text-[var(--text-muted)] uppercase mb-6 flex items-center">
             Radar & Sync
        </h2>

        <div className="space-y-8">
          <section>
             <h3 className="text-[11px] font-medium text-[var(--text-muted)] mb-3 flex items-center"><Calendar size={13} className="mr-2" /> Schedule</h3>
             <div className="space-y-3">
               {events.length === 0 ? <p className="text-xs text-[var(--text-muted)] italic">No events</p> : events.map(ev => (
                 <div key={ev.id} className="card-minimal p-4 rounded-xl">
                   <div className="flex gap-3">
                      <div className="mt-0.5 text-[var(--text-muted)]">{ev.type === 'meeting' ? <Clock size={14} /> : <AlertCircle size={14} />}</div>
                      <div>
                        <h4 className="font-medium text-sm leading-tight">{ev.title}</h4>
                        <p className="text-[11px] text-[var(--text-muted)] mt-1.5">{ev.time}</p>
                      </div>
                   </div>
                 </div>
               ))}
             </div>
          </section>

          <section>
             <h3 className="text-[11px] font-medium text-[var(--text-muted)] mb-3 flex items-center"><BookOpen size={13} className="mr-2" /> Focus: {userSettings.interests.split(" ")[0]}</h3>
             <div className="space-y-3">
               {research.length === 0 ? <Loader2 size={14} className="animate-spin text-[var(--text-muted)] ml-2" /> : research.map((r, i) => (
                 <a href={r.link} target="_blank" rel="noreferrer" key={i} className="block card-minimal p-4 rounded-xl group hover:-translate-y-0.5">
                   <h4 className="text-[13px] font-medium leading-relaxed group-hover:underline decoration-[var(--border)] underline-offset-4">{r.title}</h4>
                   <p className="text-[10px] text-[var(--text-muted)] mt-2 uppercase tracking-wide">ArXiv Open</p>
                 </a>
               ))}
             </div>
          </section>
        </div>
      </div>

      {/* Settings Modal overlay */}
      <AnimatePresence>
        {showSettings && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.98, opacity: 0, y: 10 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.98, opacity: 0, y: 10 }} className="bg-[var(--bg-input)] p-8 rounded-2xl w-full max-w-md border border-[var(--border)] shadow-2xl">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-medium">Settings</h2>
                <button onClick={() => setShowSettings(false)} className="text-[var(--text-muted)] hover:text-inherit transition-colors"><X size={18}/></button>
              </div>
              <form onSubmit={saveSettings} className="space-y-5">
                <div>
                  <label className="text-[11px] font-medium text-[var(--text-muted)] block mb-1">Name</label>
                  <input type="text" value={userSettings.name} onChange={e => setUserSettings({...userSettings, name: e.target.value})} className="w-full bg-[var(--bg-sidebar)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[var(--accent)] transition-colors" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-[var(--text-muted)] block mb-1">Research Field</label>
                  <input type="text" value={userSettings.interests} onChange={e => setUserSettings({...userSettings, interests: e.target.value})} className="w-full bg-[var(--bg-sidebar)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[var(--accent)] transition-colors" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-[var(--text-muted)] block mb-1">Language</label>
                  <select value={userSettings.language} onChange={e => setUserSettings({...userSettings, language: e.target.value})} className="w-full bg-[var(--bg-sidebar)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[var(--accent)] transition-colors appearance-none">
                    <option>English</option><option>Hindi</option><option>Japanese</option><option>French</option>
                  </select>
                </div>
                <button type="submit" className="w-full bg-[#2D2D2D] dark:bg-[#E5E5E5] text-[#E5E5E5] dark:text-[#2D2D2D] mt-6 py-3 rounded-lg font-medium text-sm hover:opacity-90 transition-opacity">
                   Save Changes
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
