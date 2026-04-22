import React, { useState, useRef } from "react";
import { ArrowLeft, Languages, Upload, FileText, Send, LoaderCircle, CheckCircle2, FileUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { apiFetch } from "../lib/api";

const PolyglotPortal = ({ session, onBack }) => {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [targetLang, setTargetLang] = useState("hi");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleTranslate = async () => {
    if (!text.trim() && !file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let data;
      if (file) {
        // Binary Translation Pipeline
        const formData = new FormData();
        formData.append("file", file);
        formData.append("target_lang", targetLang);
        
        const response = await fetch(`${import.meta.env.VITE_API_BASE || ""}/api/workspace/translate-file`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${session.access_token}` },
          body: formData
        });
        if (!response.ok) throw new Error("Binary extraction failed.");
        data = await response.json();
      } else {
        // Text Translation Pipeline
        data = await apiFetch("/api/workspace/translate", {
          session,
          method: "POST",
          body: { text, target_lang: targetLang, title: "Polyglot Session" }
        });
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Neural translation failed. Check connectivity.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;
    setFile(selectedFile);
    setText(`[Targeting Binary File: ${selectedFile.name}]`);
  };

  return (
    <div className="polyglot-portal" style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto', minHeight: '100vh', background: 'white' }}>
      <button className="pill-btn secondary" onClick={onBack} style={{ marginBottom: '40px' }}>
        <ArrowLeft size={18} />
        <span>Return to Hub</span>
      </button>

      <div className="hero-section" style={{ marginBottom: '60px' }}>
        <h1 className="serif" style={{ fontSize: '3.5rem', marginBottom: '16px', letterSpacing: '-0.02em' }}>Intelligence Suite</h1>
        <p className="hero-tag" style={{ fontSize: '1.2rem', maxWidth: '600px' }}>The Polyglot Engine parses, distills, and mirrors your documents directly into Google Workspace.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '40px' }}>
        <div className="input-zone">
          <div className="wabi-card" style={{ padding: '8px', borderRadius: '32px', background: '#f5f5f4' }}>
            <textarea 
              className="wabi-input" 
              style={{ width: '100%', height: '450px', borderRadius: '24px', resize: 'none', border: 'none', background: 'transparent', padding: '30px', fontSize: '1.1rem' }}
              placeholder="Paste document corridor or upload binary below..."
              value={text}
              onChange={(e) => { setText(e.target.value); setFile(null); }}
              disabled={loading}
            />
          </div>
          
          <div style={{ display: 'flex', gap: '20px', marginTop: '24px' }}>
            <button 
              className={`pill-btn ${file ? "active" : "secondary"}`} 
              onClick={() => fileInputRef.current.click()}
              style={{ height: '60px', padding: '0 30px' }}
            >
              <FileUp size={20} />
              <span>{file ? file.name : "Target File (PDF/DOCX)"}</span>
              <input type="file" ref={fileInputRef} style={{ display: 'none' }} onChange={handleFileUpload} accept=".txt,.pdf,.docx" />
            </button>
            
            <button 
              className="pill-btn" 
              onClick={handleTranslate} 
              disabled={loading || (!text.trim() && !file)} 
              style={{ flex: 1, height: '60px', fontSize: '1.1rem', background: 'var(--ink)', color: 'white' }}
            >
              {loading ? <LoaderCircle className="animate-spin" /> : <Languages size={20} />}
              <span>{loading ? "Parsing Neural Buffers..." : "Initiate Translation"}</span>
            </button>
          </div>
        </div>

        <div className="control-zone">
          <div className="wabi-card" style={{ padding: '32px', position: 'sticky', top: '40px' }}>
            <h4 className="serif" style={{ fontSize: '1.4rem', marginBottom: '24px' }}>Configuration</h4>
            
            <div style={{ marginBottom: '30px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, opacity: 0.5, textTransform: 'uppercase', display: 'block', marginBottom: '12px' }}>Mirror Language</label>
              <select 
                className="wabi-input" 
                style={{ width: '100%', padding: '16px', background: '#f5f5f4', border: 'none' }}
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
              >
                <option value="hi">Hindi (हिन्दी)</option>
                <option value="te">Telugu (తెలుగు)</option>
                <option value="ta">Tamil (தமிழ்)</option>
                <option value="ka">Kannada (ಕನ್ನಡ)</option>
                <option value="fr">French (Français)</option>
                <option value="es">Spanish (Español)</option>
                <option value="ja">Japanese (日本語)</option>
              </select>
            </div>

            <AnimatePresence>
              {result && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="wabi-card"
                  style={{ background: '#ecfdf5', border: '1px solid #10b981', padding: '24px', color: '#065f46' }}
                >
                  <CheckCircle2 size={32} style={{ marginBottom: '16px', color: '#10b981' }} />
                  <p style={{ fontWeight: 700, fontSize: '1.1rem', marginBottom: '8px' }}>Asset Synchronized</p>
                  <p style={{ fontSize: '0.85rem', opacity: 0.8, marginBottom: '20px' }}>Your document has been translated and mirrored to Google Docs.</p>
                  <a 
                    href={result.document.url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="pill-btn"
                    style={{ background: '#10b981', color: 'white', border: 'none', justifyContent: 'center' }}
                  >
                    Open Google Doc
                  </a>
                </motion.div>
              )}

              {error && (
                <motion.div 
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  style={{ background: '#fef2f2', border: '1px solid #f87171', borderRadius: '16px', padding: '20px', color: '#991b1b', fontSize: '0.9rem' }}
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PolyglotPortal;
