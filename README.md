# साथी · Saathi
**Your Personal AI Companion built for Project Parliament**

Saathi is a personalized, locally-powered ambient intelligence agent. It is not just a chatbot; it is a unified cognitive layer that integrates natively with your workflow. Driven entirely by open-source local AI (Llama 3), Saathi gives you privacy-first superpowers without cloud subscription fees.

---

## ✨ Live Modules Currently Active

This build implements several critical modules derived from the official *Saathi Blueprint v2.0*:

*   **🧠 Local Intelligence (Core Engine):** Chat responses are processed natively on your machine by hooking into a running **Ollama (`llama3:latest`)** instance. Your data never leaves your laptop.
*   **🌐 Module 9 - Web Intelligence & Radar:** Saathi features an integrated DuckDuckGo scraper and ArXiv paper feed. Saathi actively pulls published works based heavily on your configured "Research Background" in settings. 
*   **🔍 Module 9 - Deep Web Scraping Tool:** Toggle the `+` button in the chat input. Once active, Saathi will search the internet in real-time, fetching live content to feed the brain before answering you.
*   **🎙️ Module 12 - Voice Interface:** Native Web Speech API integration. 
    *   *Dictation:* Click the microphone to narrate your prompt directly text-free. 
    *   *TTS (Text-to-Speech):* Enable the audio button on the top right, and Saathi will physically speak her responses aloud.
*   **👤 Module 6 - Settings Memory (SQLite):** User preferences are dynamically bound to a SQLite database. Changing your primary Language or Theme in the Settings instantly recalibrates the Dashboard interface and prompts Llama-3 to switch to that language natively.
*   **🎨 Dynamic "Thine.ai" Interface:** An aesthetically serene, custom-tailored frontend using Glassmorphism, Framer Motion, and soft ambient Japanese minimalist styles, complete with a fluent Light and Dark mode.

---

## 🚀 How to Run Saathi Locally

Since Saathi avoids cloud infrastructure securely, you need two parallel terminals to run the ecosystem:

### 1. Start the Backend API (Python)
The backend acts as the Orchestrator, running the scrapers and bridging communication to Ollama.
```bash
# Navigate to the API folder
cd saathi-api

# Create a virtual environment and activate it
python -m venv venv
venv\Scripts\activate   # For Windows

# Install Dependencies
pip install fastapi uvicorn httpx pydantic google-auth-oauthlib google-api-python-client duckduckgo-search feedparser bs4

# Start the Server (Listens on port 8000)
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
> *Ensure your local Ollama instance is turned on before running the API!*

### 2. Start the Frontend Dashboard (React + Vite)
The front-facing UI where you interact with Saathi.
```bash
# Open a new terminal and navigate to the Web folder
cd saathi-web

# Install all Node Dependencies
npm install

# Start the amazing Dashboard! (Listens on port 5173 or 5174)
npm run dev
```

### 3. Experience Saathi 
Open `http://localhost:5174` (or whatever port Vite provides) in your browser. Click the **Settings (Gear Icon)** in the top left to setup your name and active research field to initialize Saathi's radar!
