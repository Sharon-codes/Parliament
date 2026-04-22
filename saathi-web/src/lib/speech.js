import { useEffect, useMemo, useRef, useState } from "react";

import { LANGUAGE_LOCALES, WAKE_PHRASES } from "./config";

const FEMALE_HINTS = ["female", "woman", "natural", "neural", "ria", "aria", "samantha", "siri", "heera", "kalpana", "priya"];
const MALE_HINTS = ["male", "man", "natural", "neural", "guy", "david", "ravi", "aditya", "alex"];

function getRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function pickVoice(voices, language, gender) {
  if (!voices.length) return null;
  const locale = LANGUAGE_LOCALES[language] || "en-IN";
  const baseLang = locale.split("-")[0];
  const matchingLang = voices.filter(v => v.lang?.toLowerCase().startsWith(baseLang.toLowerCase()));
  const pool = matchingLang.length ? matchingLang : voices;
  const hints = gender === "male" ? MALE_HINTS : FEMALE_HINTS;
  
  // Rank voices by both gender hint AND "Natural/Neural" quality
  const scored = pool.map(v => {
    let score = 0;
    const name = v.name?.toLowerCase() || "";
    if (hints.some(h => name.includes(h))) score += 2;
    if (name.includes("natural") || name.includes("neural") || name.includes("premium")) score += 10;
    if (name.includes("google") || name.includes("microsoft")) score += 5;
    if (v.localService) score += 3;
    return { voice: v, score };
  }).sort((a,b) => b.score - a.score);

  return scored[0]?.voice || pool[0];
}

export function useSaathiVoice({ language, gender, enabled, onWakeCommand }) {
  const [voices, setVoices] = useState([]);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [wakeMode, setWakeMode] = useState(false);
  const [status, setStatus] = useState("Voice ready");

  const recognitionRef = useRef(null);
  const wakeArmedRef = useRef(false);
  const wakeModeRef = useRef(false);

  const selectedVoice = useMemo(
    () => pickVoice(voices, language, gender),
    [voices, language, gender]
  );
  const supported = useMemo(
    () => Boolean(getRecognition() && window.speechSynthesis),
    []
  );

  useEffect(() => {
    const syncVoices = () => {
      const availableVoices = window.speechSynthesis?.getVoices?.() || [];
      setVoices(availableVoices);
    };

    syncVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", syncVoices);
    return () => {
      window.speechSynthesis?.removeEventListener?.("voiceschanged", syncVoices);
    };
  }, []);

  useEffect(() => {
    wakeModeRef.current = wakeMode;
  }, [wakeMode]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop?.();
    };
  }, []);

  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
  };

  const speak = (text) => {
    if (!enabled || !supported || !text?.trim()) {
      return;
    }
    if (speaking) {
       stopSpeaking();
       return;
    }

    const utterance = new SpeechSynthesisUtterance(text.replace(/```[\s\S]*?```/g, " (code omitted) "));
    utterance.lang = LANGUAGE_LOCALES[language] || "en-IN";
    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }
    utterance.rate = 1.0; 
    utterance.pitch = gender === "male" ? 0.95 : 1.05;
    utterance.volume = 1;
    
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };

  const stopRecognition = () => {
    recognitionRef.current?.stop?.();
    recognitionRef.current = null;
    setListening(false);
  };

  const startRecognition = ({ continuous = false, expectWake = false } = {}) => {
    const Recognition = getRecognition();
    if (!Recognition) {
      setStatus("This browser does not support voice input.");
      return;
    }

    const recognition = new Recognition();
    recognition.lang = LANGUAGE_LOCALES[language] || "en-IN";
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognitionRef.current = recognition;
    setListening(true);
    setStatus(expectWake ? "Listening for 'Hey Saathi' or 'Oh Saathi'" : "Listening...");

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .slice(event.resultIndex)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();

      if (!transcript) {
        return;
      }

      const normalised = transcript.toLowerCase();

      if (expectWake) {
        const wakePhrase = WAKE_PHRASES.find((phrase) => normalised.includes(phrase));
        if (wakePhrase) {
          const leftover = transcript
            .replace(new RegExp(wakePhrase, "ig"), "")
            .trim();
          wakeArmedRef.current = !leftover;
          setStatus(leftover ? "Wake heard. Sending your request..." : "Wake heard. Tell me what you need.");
          if (leftover) {
            onWakeCommand(leftover);
          }
        } else if (wakeArmedRef.current && event.results[event.results.length - 1]?.isFinal) {
          wakeArmedRef.current = false;
          setStatus("Sending your request...");
          onWakeCommand(transcript);
        }
        return;
      }

      if (event.results[event.results.length - 1]?.isFinal) {
        setStatus("Voice captured");
        onWakeCommand(transcript);
        stopRecognition();
      }
    };

    recognition.onerror = () => {
      setStatus("Voice input ran into a browser error.");
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
      if (expectWake && wakeModeRef.current) {
        window.setTimeout(() => startRecognition({ continuous: true, expectWake: true }), 350);
      }
    };

    recognition.start();
  };

  const toggleWakeMode = () => {
    if (!supported) {
      setStatus("Voice is not available in this browser.");
      return;
    }
    if (wakeModeRef.current) {
      wakeModeRef.current = false;
      setWakeMode(false);
      setStatus("Wake mode off");
      stopRecognition();
      return;
    }
    wakeModeRef.current = true;
    setWakeMode(true);
    startRecognition({ continuous: true, expectWake: true });
  };

  const captureOnce = () => {
    if (!supported) {
      setStatus("Voice is not available in this browser.");
      return;
    }
    wakeArmedRef.current = false;
    startRecognition({ continuous: false, expectWake: false });
  };

  return {
    supported,
    listening,
    speaking,
    wakeMode,
    status,
    speak,
    stopSpeaking,
    captureOnce,
    toggleWakeMode,
    selectedVoiceName: selectedVoice?.name || "",
  };
}
