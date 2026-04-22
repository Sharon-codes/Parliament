# Saathi

Saathi is a personal AI companion with:

- Google sign-in and sign-up
- a light, mobile-friendly dashboard
- Supabase-backed profiles and chat history
- Gmail, Calendar, Google Docs, and Drive connection scaffolding
- browser-based voice input, wake-word support, and language-aware speech output

## Apps

- `saathi-web` — React + Vite frontend
- `saathi-api` — FastAPI backend
- `saathi-remote` — legacy static mobile page, now reduced to a branded bridge page

## Local development

### Backend

```powershell
cd saathi-api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```powershell
cd saathi-web
npm install
npm run dev
```

## Environment files

- [saathi-web/.env.example](./saathi-web/.env.example)
- [saathi-api/.env.example](./saathi-api/.env.example)

## Supabase schema

- [supabase/schema.sql](./supabase/schema.sql)

## Deployment and Google setup

Full deployment, Supabase, and Google Cloud instructions are in [DEPLOYMENT.md](./DEPLOYMENT.md).
