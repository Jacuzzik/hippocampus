-- What a Hippocampus account unlocks (plan 14.02, 14.04, 14.06, 14.07). Paste into Supabase > SQL Editor once.
-- Every table is locked to its owner by row level security; the share functions are the only way in for others.

create extension if not exists pgcrypto with schema extensions;

-- 14.02 Sync: one row per user and kind, saved and fetched only when the user presses a button.
create table if not exists public.sync_items (
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('agents', 'settings')),
  body text not null check (octet_length(body) <= 262144),
  updated_at timestamptz not null default now(),
  primary key (user_id, kind)
);
alter table public.sync_items enable row level security;
drop policy if exists "own sync items" on public.sync_items;
create policy "own sync items" on public.sync_items
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 14.07 Usage history: one number per day, only if the user turned it on.
create table if not exists public.usage_days (
  user_id uuid not null references auth.users (id) on delete cascade,
  day date not null,
  tokens bigint not null check (tokens >= 0),
  primary key (user_id, day)
);
alter table public.usage_days enable row level security;
drop policy if exists "own usage" on public.usage_days;
create policy "own usage" on public.usage_days
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 14.04 Share links: one note behind a password, until it expires.
create table if not exists public.shares (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null check (char_length(title) <= 200),
  body text not null check (octet_length(body) <= 204800),
  password_hash text not null,
  expires_at timestamptz not null,
  failed int not null default 0,
  created_at timestamptz not null default now()
);
alter table public.shares enable row level security;
-- Owners may list and delete their links; nobody reads them directly (open_share checks the password).
drop policy if exists "own shares read" on public.shares;
create policy "own shares read" on public.shares for select to authenticated using (user_id = auth.uid());
drop policy if exists "own shares delete" on public.shares;
create policy "own shares delete" on public.shares for delete to authenticated using (user_id = auth.uid());
revoke all on public.shares from anon, authenticated;
grant select (id, title, expires_at, failed, created_at), delete on public.shares to authenticated;

-- 14.06 Limits live here, so a changed app cannot skip them.
create or replace function public.create_share(p_title text, p_body text, p_password text, p_minutes int)
returns table (id uuid, expires_at timestamptz)
language plpgsql security definer set search_path = public, extensions as $$
declare
  me uuid := auth.uid();
begin
  if me is null then raise exception 'sign in first'; end if;
  if char_length(coalesce(p_password, '')) < 8 then raise exception 'the password must be at least 8 characters'; end if;
  if p_minutes is null or p_minutes < 1 or p_minutes > 1440 then raise exception 'a link lasts from 1 minute to 24 hours'; end if;
  if (select count(*) from shares s where s.user_id = me and s.expires_at > now()) >= 20 then
    raise exception 'you have 20 live links; delete one first';
  end if;
  if (select count(*) from shares s where s.user_id = me and s.created_at > now() - interval '1 day') >= 50 then
    raise exception 'that is 50 links today; try again tomorrow';
  end if;
  delete from shares s where s.user_id = me and s.expires_at < now() - interval '7 days';
  return query
    insert into shares (user_id, title, body, password_hash, expires_at)
    values (me, left(coalesce(p_title, 'Note'), 200), p_body, crypt(p_password, gen_salt('bf')),
            now() + make_interval(mins => p_minutes))
    returning shares.id, shares.expires_at;
end $$;

create or replace function public.open_share(p_id uuid, p_password text)
returns table (title text, body text, expires_at timestamptz)
language plpgsql security definer set search_path = public, extensions as $$
declare
  hit shares%rowtype;
begin
  select * into hit from shares s where s.id = p_id;
  if not found or hit.expires_at < now() then raise exception 'this link does not exist or has expired'; end if;
  if hit.failed >= 10 then raise exception 'this link is locked after too many wrong passwords'; end if;
  if hit.password_hash <> crypt(coalesce(p_password, ''), hit.password_hash) then
    update shares set failed = failed + 1 where shares.id = p_id;
    return;  -- no rows: wrong password
  end if;
  return query select hit.title, hit.body, hit.expires_at;
end $$;

revoke all on function public.create_share(text, text, text, int) from public, anon;
grant execute on function public.create_share(text, text, text, int) to authenticated;
grant execute on function public.open_share(uuid, text) to anon, authenticated;

revoke all on public.sync_items, public.usage_days from anon;
grant select, insert, update, delete on public.sync_items, public.usage_days to authenticated;
