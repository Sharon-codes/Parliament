# 🚀 Saathi Deployment Guide (Hugging Face Only)

This guide helps you deploy both the Backend and Frontend to **Hugging Face Spaces**.

## 1. Backend (saathi-api)
1. Go to [Hugging Face Spaces](https://huggingface.co/new-space).
2. Name: `saathi-api`
3. SDK: **Docker** (Blank template).
4. Upload all files from the `saathi-api` folder.
5. In the Space **Settings**, add these **Variables** (Secrets):
   - `GEMINI_API_KEY`: (Your key)
   - `GROQ_API_KEY`: (Your key)
   - `HF_API_KEY`: (Your key)
   - `SUPABASE_URL`: (From .env)
   - `SUPABASE_SERVICE_ROLE_KEY`: (From .env)
   - `GOOGLE_OAUTH_CLIENT_ID`: (From .env)
   - `GOOGLE_OAUTH_CLIENT_SECRET`: (From .env)

## 2. Frontend (saathi-web)
1. Create another Space called `saathi-web`.
2. SDK: **Docker** (Blank template).
3. Upload all files from the `saathi-web` folder.
4. **IMPORTANT**: The `Dockerfile` already points to `https://sharon-codes-saathi-api.hf.space`. 

---

### ⚠️ Note on Desktop Control
When Saathi is deployed to Hugging Face, it runs in the cloud. This means:
- ✅ Gmail, Docs, Calendar, and AI Chat will work **anywhere**.
- ❌ **VS Code and Local Python** will **NOT** work (because the cloud cannot reach your physical computer).

**To keep desktop control**: Keep the backend running on your PC and use the tunnel URL we set up (`tasty-stars-love.loca.lt`).
