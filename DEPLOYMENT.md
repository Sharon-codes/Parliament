# Saathi Deployment Notes

## What changed

- Google sign-in and sign-up are now the primary auth flow.
- Supabase is the main storage layer for profiles, chat sessions, and Google Workspace connections.
- Gmail, Calendar, Docs, and Drive support are wired through a dedicated Google Workspace OAuth flow.
- The dashboard and mobile handoff now share one responsive light UI instead of separate, mismatched experiences.

## Services you need

### 1. Supabase

This is the free-first database + auth layer.

- Create a new project in Supabase.
- In the SQL editor, run [supabase/schema.sql](./supabase/schema.sql).
- Enable Google as an auth provider in Supabase Authentication.
- Copy:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`

### 2. Google Cloud

This is required for Gmail, Calendar, Docs, and Drive access.

- Create a project in Google Cloud Console.
- Enable these APIs:
  - Gmail API
  - Google Calendar API
  - Google Docs API
  - Google Drive API
- Configure the OAuth consent screen.
- Create **OAuth 2.0 Client ID -> Web application**.
- Download the OAuth client JSON.

This downloaded JSON file is the file you need to provide for mail/calendar/docs integration.

From that file, copy:

- `client_id` -> `GOOGLE_OAUTH_CLIENT_ID`
- `client_secret` -> `GOOGLE_OAUTH_CLIENT_SECRET`

### 3. AI provider

Free-first recommendation:

- Google Gemini API key -> `GEMINI_API_KEY`

Optional paid backup keys:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

## Redirect URLs to configure

### Supabase Google auth

Use your frontend app URL:

- Local: `http://localhost:5173/auth/callback`
- Production example: `https://your-saathi-web.vercel.app/auth/callback`

### Google Workspace OAuth

Use your backend callback URL:

- Local: `http://localhost:8000/api/workspace/callback`
- Production example: `https://your-saathi-api.onrender.com/api/workspace/callback`

## Frontend environment

Create `saathi-web/.env` from [saathi-web/.env.example](./saathi-web/.env.example):

```env
VITE_API_URL=http://localhost:8000
VITE_WEB_URL=http://localhost:5173
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Backend environment

Create `saathi-api/.env` from [saathi-api/.env.example](./saathi-api/.env.example):

```env
PUBLIC_API_URL=http://localhost:8000
PUBLIC_WEB_URL=http://localhost:5173
APP_TIMEZONE=Asia/Kolkata
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_STATE_SECRET=replace-this-with-a-long-random-secret
GEMINI_API_KEY=...
```

## Local run

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

## Suggested hosting

- Frontend: Vercel or Netlify
- Backend: Render, Railway, or Fly.io
- Database/Auth: Supabase

## Important production note

Gmail read scopes are sensitive/restricted. For broad public production use, Google may require app verification before unrestricted external use. The code is wired for it, but verification is a Google-side process, not a code-side one.
