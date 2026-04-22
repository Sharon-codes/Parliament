create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text default 'Friend',
  language text default 'English' check (language in ('English', 'Hindi', 'Tamil', 'Kannada', 'Telugu')),
  voice_gender text default 'female' check (voice_gender in ('female', 'male')),
  onboarding_completed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'New chat',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.chat_sessions (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  text text not null,
  created_at timestamptz default now()
);

create table if not exists public.google_integrations (
  user_id uuid primary key references auth.users (id) on delete cascade,
  google_email text,
  access_token text,
  refresh_token text,
  token_expiry timestamptz,
  scopes text[] default '{}'::text[],
  connected_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists chat_sessions_user_updated_idx on public.chat_sessions (user_id, updated_at desc);
create index if not exists chat_messages_session_created_idx on public.chat_messages (session_id, created_at asc);

alter table public.profiles enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.google_integrations enable row level security;

create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id);

create policy "chat_sessions_select_own"
  on public.chat_sessions for select
  using (auth.uid() = user_id);

create policy "chat_sessions_insert_own"
  on public.chat_sessions for insert
  with check (auth.uid() = user_id);

create policy "chat_sessions_update_own"
  on public.chat_sessions for update
  using (auth.uid() = user_id);

create policy "chat_sessions_delete_own"
  on public.chat_sessions for delete
  using (auth.uid() = user_id);

create policy "chat_messages_select_own"
  on public.chat_messages for select
  using (auth.uid() = user_id);

create policy "chat_messages_insert_own"
  on public.chat_messages for insert
  with check (auth.uid() = user_id);

create policy "google_integrations_select_own"
  on public.google_integrations for select
  using (auth.uid() = user_id);

-- Note:
-- access_token and refresh_token are stored so the backend can call Gmail,
-- Calendar, Drive, and Docs on behalf of each user. For a production launch,
-- pair this with a stronger secret-management approach or application-level
-- encryption before storing long-lived refresh tokens.
