import React, { useState, useEffect } from 'react';
import { Send, Clock, Calendar, Settings, Sparkles, AlertCircle, BookOpen, Mic, MicOff, Volume2, VolumeX, Search, Code, MessageCircle, X, Loader2, Moon, Sun } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const Dashboard = () => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('chat'); // chat, agent, search
  
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', text: "Namaste! My memory is active. Select your Interaction Mode below, and tell me how I can help." }
  ]);
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
    const utterance = new SpeechSynthesisUtterance(text.replace(/```.*?```/gs, 'code block omitted'));
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
        body: JSON.stringify({ message: text, mode })
      });
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: 'ai', text: data.reply }]);
      speak(data.reply);
    } catch(e) {
      setChatHistory(prev => [...prev, { role: 'ai', text: "Ollama is disconnected or processing timed out." }]);
    }
    setIsTyping(false);
  };

  return (
    <div className="min-h-screen relative flex h-screen overflow-hidden text-primary">
      {/* Background ambient blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-[var(--blob-1)] rounded-full mix-blend-multiply filter blur-3xl opacity-60 animate-blob z-0 pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[30rem] h-[30rem] bg-[var(--blob-2)] rounded-full mix-blend-multiply filter blur-3xl opacity-70 animate-blob animation-delay-2000 z-0 pointer-events-none"></div>

      {/* Sidebar / Nudges */}
      <motion.div initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="w-[450px] border-r border-theme glass-panel flex flex-col h-full z-10">
        <div className="p-6 border-b border-theme flex justify-between items-center">
          <h1 className="text-2xl font-serif text-[var(--accent)] tracking-wide">साथी <span className="font-sans text-sm ml-2 font-medium opacity-50 text-primary">Dashboard</span></h1>
          <button onClick={() => setShowSettings(true)} className="p-2 hover:bg-black/5 dark:hover:bg-white/10 rounded-full transition-colors"><Settings size={20} className="text-secondary" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8 pb-10">
          <section>
            <h3 className="text-xs font-bold tracking-[0.2em] text-secondary mb-4 uppercase flex items-center"><Calendar size={13} className="mr-2" /> Live Timeline</h3>
            <div className="space-y-3">
              {events.length === 0 ? <Loader2 size={16} className="animate-spin text-secondary" /> : events.map(ev => (
                <motion.div whileHover={{ scale: 1.02 }} key={ev.id} className="p-4 bg-secondary border border-theme rounded-2xl flex flex-col gap-2 shadow-[0_4px_20px_var(--accent-glow)] transition-all cursor-default">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl ${ev.type === 'meeting' ? 'bg-blue-500/10 text-blue-500' : 'bg-rose-500/10 text-rose-500'}`}>
                      {ev.type === 'meeting' ? <Clock size={16} /> : <AlertCircle size={16} />}
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-sm leading-tight text-primary">{ev.title}</h4>
                      <p className="text-xs text-secondary mt-1 tracking-wide">{ev.time}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-xs font-bold tracking-[0.2em] mb-4 uppercase flex items-center text-[var(--accent)]"><BookOpen size={13} className="mr-2" /> Radar: {userSettings.interests}</h3>
            <div className="space-y-3">
              {research.length === 0 ? <Loader2 size={16} className="animate-spin text-secondary" /> : research.map((r, i) => (
                <motion.a whileHover={{ y: -2 }} href={r.link} target="_blank" rel="noreferrer" key={i} className="block p-5 bg-secondary border border-theme rounded-2xl shadow-[0_4px_20px_var(--accent-glow)] transition-all group">
                  <div className="text-[9px] uppercase font-bold text-[var(--accent)] mb-2 tracking-widest flex items-center"><Sparkles size={10} className="mr-1" /> New Scrape</div>
                  <h4 className="text-[13px] font-semibold leading-relaxed group-hover:text-[var(--accent)] transition-colors text-primary">{r.title}</h4>
                </motion.a>
              ))}
            </div>
          </section>
        </div>
      </motion.div>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col relative z-10 bg-black/5 dark:bg-black/20">
        <div className="absolute top-6 right-6 z-20 flex gap-2">
           <button onClick={() => setVoiceEnabled(!voiceEnabled)} className={`p-2.5 rounded-full border transition-all backdrop-blur-md ${voiceEnabled ? 'bg-[var(--accent)] text-white border-transparent shadow-[0_0_15px_var(--accent-glow)]' : 'glass-panel text-secondary hover:text-primary'}`}>
             {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
           </button>
           <button onClick={() => {setUserSettings({...userSettings, theme: userSettings.theme === 'dark' ? 'light' : 'dark'}); document.body.classList.toggle('dark')}} className="p-2.5 rounded-full border transition-all backdrop-blur-md glass-panel text-secondary hover:text-primary">
             {userSettings.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
           </button>
        </div>

        <div className="flex-1 overflow-y-auto p-12 space-y-8 scroll-smooth pb-[120px]">
          <AnimatePresence>
            {chatHistory.map((msg, idx) => (
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] p-6 text-[15px] leading-relaxed shadow-lg ${msg.role === 'user' ? 'bg-[var(--accent)] text-white rounded-3xl rounded-br-sm font-medium' : 'bg-secondary border border-theme text-primary rounded-3xl rounded-bl-sm markdown-body'}`}>
                    {msg.role === 'ai' && <div className="text-[11px] font-sans font-bold mb-3 uppercase tracking-widest flex items-center opacity-70"><Sparkles size={12} className="mr-1 text-[var(--accent)]"/> Saathi Assistant</div>}
                    
                    {msg.role === 'ai' ? (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({node, inline, className, children, ...props}) {
                            const match = /language-(\w+)/.exec(className || '')
                            return !inline && match ? (
                              <div className="rounded-xl overflow-hidden my-4 shadow-md bg-[#1e1e1e]">
                                <div className="bg-[#2d2d2d] px-4 py-1.5 text-xs text-gray-400 flex justify-between items-center font-mono">
                                  {match[1]}
                                </div>
                                <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" customStyle={{margin: 0, border: 'none'}}>
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              </div>
                            ) : (
                              <code className={`${className} bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded-md mx-0.5`} {...props}>
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
               <div className="bg-secondary border border-theme p-5 rounded-3xl rounded-bl-sm shadow-sm flex items-center gap-1.5">
                 <div className="w-2 h-2 bg-[var(--accent)] rounded-full animate-pulse opacity-60"></div>
                 <div className="w-2 h-2 bg-[var(--accent)] rounded-full animate-pulse opacity-60" style={{ animationDelay: '0.2s' }}></div>
                 <div className="w-2 h-2 bg-[var(--accent)] rounded-full animate-pulse opacity-60" style={{ animationDelay: '0.4s' }}></div>
               </div>
             </motion.div>
          )}
        </div>

        {/* Input Dock */}
        <div className="absolute bottom-0 w-full p-8 pt-0 bg-gradient-to-t from-[var(--bg-primary)] to-transparent via-[var(--bg-primary)] z-20">
          <div className="max-w-4xl mx-auto flex gap-3 items-end">
             
             {/* Dynamic Mode Switcher Dropdown */}
             <div className="flex bg-secondary border border-theme rounded-3xl shadow-lg focus-within:ring-2 ring-[var(--accent)] transition-all overflow-hidden items-center group relative p-1.5">
                <div className="relative flex items-center pl-2 pr-1 border-r border-theme">
                  {mode === 'chat' && <MessageCircle size={16} className="text-[var(--accent)] absolute left-3 pointer-events-none" />}
                  {mode === 'agent' && <Code size={16} className="text-blue-500 absolute left-3 pointer-events-none" />}
                  {mode === 'search' && <Search size={16} className="text-indigo-500 absolute left-3 pointer-events-none" />}
                  
                  <select 
                    value={mode} 
                    onChange={e => setMode(e.target.value)}
                    className="pl-8 pr-4 py-3 bg-transparent border-none outline-none text-sm font-semibold text-primary appearance-none cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 rounded-2xl transition hover:opacity-80"
                  >
                    <option value="chat">Talk</option>
                    <option value="agent">Agent OS</option>
                    <option value="search">Search</option>
                  </select>
                </div>

               <button onClick={toggleListening} className={`p-4 shrink-0 transition-all ${isListening ? 'text-rose-500 animate-pulse' : 'text-secondary hover:text-primary'}`}>
                 {isListening ? <Mic size={20} /> : <MicOff size={20} />}
               </button>

               <input 
                 autoFocus
                 type="text" 
                 value={query}
                 onChange={e => setQuery(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && handleSend()}
                 placeholder={mode === 'agent' ? "e.g., 'Write and run a matrix sum program in python'" : mode === 'search' ? "Search the live entire web for..." : "Ask Saathi anything..."}
                 className="flex-1 bg-transparent border-none outline-none py-4 px-2 text-primary placeholder:text-secondary/70 font-medium w-[400px]"
               />
               
             </div>

             <button 
               onClick={() => handleSend()}
               disabled={!query.trim()}
               className="h-[66px] w-[66px] shrink-0 bg-[var(--accent)] text-white rounded-[24px] hover:brightness-110 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center shadow-[0_8px_20px_var(--accent-glow)]"
             >
                <Send size={22} className="ml-1" />
             </button>
          </div>
        </div>
      </div>

      {/* Settings Modal overlay */}
      <AnimatePresence>
        {showSettings && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} className="bg-secondary p-8 rounded-3xl w-full max-w-md shadow-2xl border border-theme">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-primary">Preferences</h2>
                <button onClick={() => setShowSettings(false)} className="text-secondary hover:text-primary"><X size={20}/></button>
              </div>
              <form onSubmit={saveSettings} className="space-y-5">
                <div>
                  <label className="text-xs font-bold uppercase tracking-widest text-secondary block mb-2">Display Name</label>
                  <input type="text" value={userSettings.name} onChange={e => setUserSettings({...userSettings, name: e.target.value})} className="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-primary outline-none focus:ring-2 ring-[var(--accent)]" />
                </div>
                <div>
                  <label className="text-xs font-bold uppercase tracking-widest text-secondary block mb-2">Research Field for Radar</label>
                  <input type="text" value={userSettings.interests} onChange={e => setUserSettings({...userSettings, interests: e.target.value})} className="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-primary outline-none focus:ring-2 ring-[var(--accent)]" />
                </div>
                <div>
                  <label className="text-xs font-bold uppercase tracking-widest text-secondary block mb-2">Language</label>
                  <select value={userSettings.language} onChange={e => setUserSettings({...userSettings, language: e.target.value})} className="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-primary outline-none focus:ring-2 ring-[var(--accent)]">
                    <option>English</option><option>Hindi</option><option>Japanese</option><option>French</option>
                  </select>
                </div>
                <button type="submit" className="w-full bg-[var(--accent)] text-white py-3.5 rounded-xl font-bold tracking-wide hover:brightness-110 transition-all shadow-[0_8px_20px_var(--accent-glow)] mt-4">Save & Reboot Context</button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default Dashboard;
