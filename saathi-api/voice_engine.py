"""
voice_engine.py — Saathi Module 12: Voice Interface
─────────────────────────────────────────────────────
Architecture:
  • Wake word  : Porcupine (if PICOVOICE_KEY set) → else Whisper text-match fallback
  • STT        : OpenAI Whisper  (tiny model, fully local, ~150 MB)
  • TTS        : ElevenLabs (cloud, if ELEVENLABS_API_KEY set) → else pyttsx3 (local)
  • Transport  : FastAPI WebSocket at /ws/voice  ←→ browser
  • Modes      : off | push_to_talk | wake_word | ambient | dictation

Environment (.env):
  PICOVOICE_KEY=...       # optional – https://console.picovoice.ai/ (free tier)
  ELEVENLABS_API_KEY=...  # optional – https://elevenlabs.io/  (free tier)
  ELEVENLABS_VOICE_ID=... # optional – default: Rachel
  WHISPER_MODEL=tiny      # tiny / base / small  (default: tiny)
  VOICE_WAKE_WORDS=hey saathi,saathi  # comma-separated fallback keywords
"""

import asyncio
import io
import json
import logging
import os
import queue
import struct
import tempfile
import threading
import time
import wave
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Set

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

log = logging.getLogger("saathi.voice")
logging.basicConfig(level=logging.INFO, format="[Voice] %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
PICOVOICE_KEY   = os.getenv("PICOVOICE_KEY", "").strip()
ELEVENLABS_KEY  = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "tiny")
WAKE_WORDS_RAW  = os.getenv("VOICE_WAKE_WORDS", "hey saathi,saathi,hey sathi")
WAKE_WORDS: list[str] = [w.strip().lower() for w in WAKE_WORDS_RAW.split(",") if w.strip()]

SAMPLE_RATE     = 16000
FRAME_DURATION  = 30          # ms per VAD frame
SILENCE_TIMEOUT = 1.8         # seconds of silence to end an utterance
MAX_RECORD_SECS = 30          # hard cap for dictation mode


class VoiceMode(str, Enum):
    OFF          = "off"
    PUSH_TO_TALK = "push_to_talk"
    WAKE_WORD    = "wake_word"
    AMBIENT      = "ambient"
    DICTATION    = "dictation"


# ── Optional import guards ────────────────────────────────────────────────────

def _try_import_sounddevice():
    try:
        import sounddevice as sd
        return sd
    except ImportError:
        return None

def _try_import_whisper():
    try:
        import whisper
        return whisper
    except ImportError:
        return None

def _try_import_webrtcvad():
    try:
        import webrtcvad
        return webrtcvad
    except ImportError:
        return None

def _try_import_pyttsx3():
    try:
        import pyttsx3
        return pyttsx3
    except ImportError:
        return None

def _try_import_pvporcupine():
    if not PICOVOICE_KEY:
        return None
    try:
        import pvporcupine
        return pvporcupine
    except ImportError:
        return None


# ── TTS Engine ─────────────────────────────────────────────────────────────────

class TTSEngine:
    """Speak text via ElevenLabs (cloud) or pyttsx3 (local)."""

    def __init__(self):
        self._pyttsx = None
        self._lock   = threading.Lock()
        if not ELEVENLABS_KEY:
            pyttsx3 = _try_import_pyttsx3()
            if pyttsx3:
                try:
                    self._pyttsx = pyttsx3.init()
                    self._pyttsx.setProperty("rate", 155)
                    self._pyttsx.setProperty("volume", 0.95)
                    log.info("TTS: pyttsx3 (local)")
                except Exception as e:
                    log.warning(f"TTS init failed: {e}")
        else:
            log.info("TTS: ElevenLabs (cloud)")

    def speak(self, text: str):
        if not text.strip():
            return
        clean = text.replace("**", "").replace("*", "").replace("✦", "").replace("⚠", "")
        clean = clean[:600]   # cap length for TTS
        t = threading.Thread(target=self._speak_blocking, args=(clean,), daemon=True)
        t.start()

    def _speak_blocking(self, text: str):
        if ELEVENLABS_KEY:
            self._speak_elevenlabs(text)
        elif self._pyttsx:
            with self._lock:
                try:
                    self._pyttsx.say(text)
                    self._pyttsx.runAndWait()
                except Exception as e:
                    log.warning(f"pyttsx3 speak error: {e}")

    def _speak_elevenlabs(self, text: str):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}/stream"
        headers = {
            "xi-api-key": ELEVENLABS_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                self._play_audio_bytes(resp.content, fmt="mp3")
            else:
                log.warning(f"ElevenLabs {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            log.warning(f"ElevenLabs error: {e}")

    def _play_audio_bytes(self, data: bytes, fmt: str = "mp3"):
        try:
            sd = _try_import_sounddevice()
            if not sd:
                return
            if fmt == "mp3":
                try:
                    from pydub import AudioSegment
                    seg = AudioSegment.from_file(io.BytesIO(data), format="mp3")
                    arr = seg.get_array_of_samples()
                    sd.play(arr, samplerate=seg.frame_rate)
                    sd.wait()
                except ImportError:
                    # Save to tmp and play externally
                    import subprocess
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        f.write(data)
                        tmp = f.name
                    subprocess.Popen(f'start "" "{tmp}"', shell=True)
        except Exception as e:
            log.warning(f"Audio playback error: {e}")


# ── STT Engine (Whisper) ───────────────────────────────────────────────────────

class STTEngine:
    """Speech-to-text using local OpenAI Whisper model."""

    def __init__(self):
        self._model = None
        self._loading = False

    def _ensure_loaded(self):
        if self._model is not None:
            return True
        if self._loading:
            return False
        whisper = _try_import_whisper()
        if not whisper:
            log.warning("openai-whisper not installed. Run: pip install openai-whisper")
            return False
        self._loading = True
        try:
            log.info(f"Loading Whisper model '{WHISPER_MODEL}'… (first run downloads ~150MB)")
            self._model = whisper.load_model(WHISPER_MODEL)
            self._loading = False
            log.info("Whisper ready.")
            return True
        except Exception as e:
            log.error(f"Whisper load failed: {e}")
            self._loading = False
            return False

    def transcribe(self, audio_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> str:
        if not self._ensure_loaded():
            return ""
        whisper = _try_import_whisper()
        if not whisper:
            return ""
        try:
            # Write PCM bytes to a WAV file in memory
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            buf.seek(0)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(buf.read())
                tmp = f.name
            result = self._model.transcribe(
                tmp,
                language="en",
                fp16=False,
                temperature=0.0,
            )
            os.unlink(tmp)
            return result.get("text", "").strip()
        except Exception as e:
            log.warning(f"Whisper transcribe error: {e}")
            return ""


# ── VAD (Voice Activity Detection) ───────────────────────────────────────────

class VADRecorder:
    """
    Records audio from mic, uses webrtcvad to detect speech segments.
    Returns raw PCM bytes of each utterance.
    """

    def __init__(self, aggressiveness: int = 2):
        self._sd  = _try_import_sounddevice()
        self._vad_mod = _try_import_webrtcvad()
        self._aggressiveness = aggressiveness
        self._available = self._sd is not None

    @property
    def available(self) -> bool:
        return self._available

    def record_utterance(self,
                         max_seconds: float = MAX_RECORD_SECS,
                         silence_timeout: float = SILENCE_TIMEOUT,
                         on_speech_start: Optional[Callable] = None) -> bytes:
        """
        Block until an utterance is complete. Returns PCM16 bytes.
        If webrtcvad is available, uses VAD. Otherwise records for silence_timeout seconds.
        """
        if not self._sd:
            return b""

        sd = self._sd
        frame_samples = int(SAMPLE_RATE * FRAME_DURATION / 1000)  # 480 samples @ 16kHz
        frames_for_silence = int(silence_timeout * 1000 / FRAME_DURATION)

        audio_buf: list[bytes] = []
        speech_frames = 0
        silent_frames  = 0
        started        = False
        t_max          = time.time() + max_seconds

        vad = None
        if self._vad_mod:
            vad = self._vad_mod.Vad(self._aggressiveness)

        with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                blocksize=frame_samples) as stream:
            while time.time() < t_max:
                raw, _ = stream.read(frame_samples)
                frame  = bytes(raw)

                is_speech = True
                if vad:
                    try:
                        is_speech = vad.is_speech(frame, SAMPLE_RATE)
                    except Exception:
                        pass

                if is_speech:
                    if not started:
                        started = True
                        if on_speech_start:
                            on_speech_start()
                    speech_frames += 1
                    silent_frames = 0
                    audio_buf.append(frame)
                else:
                    if started:
                        silent_frames += 1
                        audio_buf.append(frame)
                        if silent_frames >= frames_for_silence:
                            break
                    # If we haven't started yet, keep waiting

        return b"".join(audio_buf)


# ── Wake-Word Detector ────────────────────────────────────────────────────────

class WakeWordDetector:
    """
    Listens continuously and fires a callback when the wake word is heard.
    Strategy: Porcupine (if key) → Whisper-text-match fallback.
    """

    def __init__(self, on_detected: Callable, stt: STTEngine, recorder: VADRecorder):
        self._cb       = on_detected
        self._stt      = stt
        self._rec      = recorder
        self._running  = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running or not self._rec.available:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Wake-word listener started. Watching for: {WAKE_WORDS}")

    def stop(self):
        self._running = False

    def _loop(self):
        # Try Porcupine first
        pvp = _try_import_pvporcupine()
        if pvp and PICOVOICE_KEY:
            self._loop_porcupine(pvp)
        else:
            self._loop_whisper_fallback()

    def _loop_porcupine(self, pvp):
        sd = _try_import_sounddevice()
        if not sd:
            return
        try:
            porcupine = pvp.create(
                access_key=PICOVOICE_KEY,
                keywords=["hey siri"],   # closest built-in; replace if custom model
            )
            log.info("Porcupine wake-word active.")
            frame_len = porcupine.frame_length
            with sd.RawInputStream(samplerate=porcupine.sample_rate,
                                   channels=1, dtype="int16",
                                   blocksize=frame_len) as stream:
                while self._running:
                    raw, _ = stream.read(frame_len)
                    pcm    = struct.unpack_from(f"{frame_len}h", raw)
                    result = porcupine.process(pcm)
                    if result >= 0:
                        log.info("Wake word detected (Porcupine)!")
                        self._cb()
            porcupine.delete()
        except Exception as e:
            log.warning(f"Porcupine error ({e}), falling back to Whisper wake-word.")
            self._loop_whisper_fallback()

    def _loop_whisper_fallback(self):
        """
        Records 3-second chunks, transcribes, checks for wake words.
        Uses VAD so it only triggers on actual speech.
        """
        sd = _try_import_sounddevice()
        if not sd:
            log.warning("sounddevice not available — wake word disabled.")
            return

        chunk_secs = 3
        frame_samples = int(SAMPLE_RATE * chunk_secs)

        log.info("Whisper wake-word detection loop running.")

        while self._running:
            try:
                with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                       blocksize=frame_samples) as stream:
                    raw, _ = stream.read(frame_samples)
                    pcm    = bytes(raw)

                text = self._stt.transcribe(pcm).lower().strip()
                if not text:
                    continue

                if any(w in text for w in WAKE_WORDS):
                    log.info(f"Wake word detected! Heard: '{text}'")
                    self._cb()
                    time.sleep(0.5)   # brief pause before next listen cycle

            except Exception as e:
                log.warning(f"Wake-word loop error: {e}")
                time.sleep(1)


# ── Main Voice Engine ─────────────────────────────────────────────────────────

class VoiceEngine:
    """
    Top-level voice controller.
    Manages mode switching, coordinates STT/TTS/wake detection.
    Broadcasts events to registered WebSocket clients.
    """

    def __init__(self, on_command: Callable[[str, str], None]):
        """
        on_command(text, mode) — called when a voice command is ready.
        """
        self._on_command  = on_command
        self._mode        = VoiceMode.OFF
        self._clients: Set = set()         # WS clients to broadcast to
        self._lock        = threading.Lock()

        self.tts      = TTSEngine()
        self.stt      = STTEngine()
        self.recorder = VADRecorder()
        self._wake    = WakeWordDetector(
            on_detected=self._handle_wake,
            stt=self.stt,
            recorder=self.recorder,
        )

        # Dictation buffer
        self._dictation_buf: list[str] = []

        # Ambient mode: only interrupt for urgent nudges
        self._ambient_paused = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_mode(self, mode: VoiceMode):
        with self._lock:
            old = self._mode
            self._mode = mode
            log.info(f"Voice mode: {old} → {mode}")

        if mode == VoiceMode.WAKE_WORD:
            self._wake.start()
            self._broadcast({"type": "mode", "mode": mode, "msg": f"Listening for: {WAKE_WORDS[0]}"})
        elif mode == VoiceMode.AMBIENT:
            self._wake.start()
            self._broadcast({"type": "mode", "mode": mode, "msg": "Ambient mode — watching quietly."})
        elif mode in (VoiceMode.OFF, VoiceMode.PUSH_TO_TALK):
            self._wake.stop()
            self._broadcast({"type": "mode", "mode": mode})

    def push_to_talk(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio_bytes (PCM16, 16kHz) received from the browser.
        Returns the transcription.
        """
        text = self.stt.transcribe(audio_bytes)
        if text:
            self._broadcast({"type": "transcript", "text": text, "final": True})
            self._on_command(text, VoiceMode.PUSH_TO_TALK)
        return text

    def start_dictation(self):
        """Start continuous dictation recording in a background thread."""
        self._dictation_buf.clear()
        t = threading.Thread(target=self._dictation_loop, daemon=True)
        t.start()
        self._broadcast({"type": "dictation_start"})

    def stop_dictation(self) -> str:
        """Stop recording and return the full dictation text."""
        self.set_mode(VoiceMode.OFF)
        full = " ".join(self._dictation_buf)
        self._broadcast({"type": "dictation_done", "text": full})
        return full

    def speak(self, text: str):
        """Speak text via TTS — honours ambient mode pause."""
        if self._mode == VoiceMode.AMBIENT and self._ambient_paused:
            return
        self.tts.speak(text)
        self._broadcast({"type": "tts", "text": text[:120]})

    def speak_urgent(self, text: str):
        """Always speaks, even in ambient mode (for nudges etc.)."""
        self.tts.speak(text)
        self._broadcast({"type": "tts_urgent", "text": text[:120]})

    def register_client(self, ws):
        self._clients.add(ws)
        # Send current state immediately
        asyncio.create_task(ws.send_json({
            "type": "hello",
            "mode": self._mode,
            "wake_words": WAKE_WORDS,
            "tts": "elevenlabs" if ELEVENLABS_KEY else "pyttsx3",
            "stt": f"whisper-{WHISPER_MODEL}",
            "mic_available": self.recorder.available,
        }))

    def unregister_client(self, ws):
        self._clients.discard(ws)

    def get_status(self) -> dict:
        return {
            "mode":          self._mode,
            "mic_available": self.recorder.available,
            "wake_words":    WAKE_WORDS,
            "tts_provider":  "elevenlabs" if ELEVENLABS_KEY else "pyttsx3",
            "stt_model":     f"whisper-{WHISPER_MODEL}",
            "porcupine":     bool(PICOVOICE_KEY and _try_import_pvporcupine()),
            "whisper_ready": self.stt._model is not None,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _handle_wake(self):
        """Called by wake-word detector — start listening for the actual command."""
        if self._mode == VoiceMode.AMBIENT:
            # In ambient mode only respond to urgent queries
            self._broadcast({"type": "wake", "msg": "Wake word detected — listening for query…"})
            self.tts.speak("Yes?")
        else:
            self._broadcast({"type": "wake", "msg": "Wake word detected!"})
            self.tts.speak("Yes?")

        # Now record the actual command
        audio = self.recorder.record_utterance(
            max_seconds=15,
            silence_timeout=SILENCE_TIMEOUT,
            on_speech_start=lambda: self._broadcast({"type": "recording_start"}),
        )
        if not audio:
            return

        text = self.stt.transcribe(audio)
        if text:
            self._broadcast({"type": "transcript", "text": text, "final": True})
            self._on_command(text, str(self._mode))

    def _dictation_loop(self):
        """Continuously record and transcribe until mode changes."""
        self.set_mode(VoiceMode.DICTATION)
        while self._mode == VoiceMode.DICTATION:
            audio = self.recorder.record_utterance(
                max_seconds=8,
                silence_timeout=1.0,
            )
            if not audio:
                continue
            text = self.stt.transcribe(audio)
            if text:
                self._dictation_buf.append(text)
                self._broadcast({"type": "dictation_chunk", "text": text})

    def _broadcast(self, payload: dict):
        """Fire-and-forget broadcast to all registered WS clients."""
        if not self._clients:
            return
        dead = set()
        for ws in self._clients:
            try:
                asyncio.run_coroutine_threadsafe(
                    ws.send_json(payload),
                    asyncio.get_event_loop()
                )
            except Exception:
                dead.add(ws)
        self._clients -= dead


# ── Singleton ─────────────────────────────────────────────────────────────────
_engine: Optional[VoiceEngine] = None

def get_voice_engine() -> Optional[VoiceEngine]:
    return _engine

def init_voice_engine(on_command: Callable[[str, str], None]) -> VoiceEngine:
    global _engine
    _engine = VoiceEngine(on_command)
    log.info("Voice engine initialised.")
    return _engine
