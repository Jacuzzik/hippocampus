-- Teams (D.07): people who share the same agents, tasks and notes, each with their own sign-in.
-- Paste into Supabase > SQL Editor once, after 20261118_account_features.sql. Nothing is shared by itself:
-- a person presses Save to team, and a teammate presses Get from team. Notes up to 200 KB, items up to 256 KB.
-- Every table is locked by row level security: only a team's members can read or write its rows.

create table if not exists public.teams (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 80),
  join_code text not null unique default encode(extensions.gen_random_bytes(6), 'hex'),
  owner uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);

create table if not exists public.team_members (
  team_id uuid not null references public.teams (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  email text not null default '',
  role text not null default 'member' check (role in ('owner', 'member')),
  joined_at timestamptz not null default now(),
  primary key (team_id, user_id)
);

create table if not exists public.team_items (
  team_id uuid not null references public.teams (id) on delete cascade,
  kind text not null check (kind in ('agents', 'tasks', 'note')),
  name text not null default '' check (char_length(name) <= 200),
  body text not null check (octet_length(body) <= 262144),
  updated_by uuid not null default auth.uid() references auth.users (id) on delete cascade,
  updated_at timestamptz not null default now(),
  primary key (team_id, kind, name)
);

create or replace function public.is_team_member(p_team uuid)
returns boolean language sql security definer stable set search_path = public as $$
  select exists (select 1 from public.team_members where team_id = p_team and user_id = auth.uid());
$$;

alter table public.teams enable row level security;
alter table public.team_members enable row level security;
alter table public.team_items enable row level security;

drop policy if exists "members read team" on public.teams;
create policy "members read team" on public.teams for select to authenticated using (public.is_team_member(id));
drop policy if exists "members read members" on public.team_members;
create policy "members read members" on public.team_members for select to authenticated using (public.is_team_member(team_id));
drop policy if exists "members use items" on public.team_items;
create policy "members use items" on public.team_items for all to authenticated
  using (public.is_team_member(team_id)) with check (public.is_team_member(team_id) and updated_by = auth.uid());

-- A team is made, joined and left only through these functions, so limits live here, not in the app.
create or replace function public.create_team(p_name text)
returns table (id uuid, name text, join_code text)
language plpgsql security definer set search_path = public, extensions as $$
declare
  me uuid := auth.uid();
  made public.teams;
begin
  if me is null then raise exception 'sign in first'; end if;
  if (select count(*) from public.teams where owner = me) >= 5 then raise exception 'you can own up to 5 teams'; end if;
  insert into public.teams (name, owner) values (trim(p_name), me) returning * into made;
  insert into public.team_members (team_id, user_id, email, role)
    values (made.id, me, coalesce((select email from auth.users where auth.users.id = me), ''), 'owner');
  return query select made.id, made.name, made.join_code;
end $$;

create or replace function public.join_team(p_code text)
returns table (id uuid, name text)
language plpgsql security definer set search_path = public as $$
declare
  me uuid := auth.uid();
  found public.teams;
begin
  if me is null then raise exception 'sign in first'; end if;
  select * into found from public.teams where join_code = lower(trim(p_code));
  if found.id is null then raise exception 'no team has that code'; end if;
  if (select count(*) from public.team_members where team_id = found.id) >= 50 then raise exception 'the team is full (50 people)'; end if;
  insert into public.team_members (team_id, user_id, email)
    values (found.id, me, coalesce((select email from auth.users where auth.users.id = me), ''))
    on conflict do nothing;
  return query select found.id, found.name;
end $$;

create or replace function public.leave_team(p_team uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  delete from public.team_members where team_id = p_team and user_id = auth.uid() and role <> 'owner';
  if not found then raise exception 'an owner cannot leave; delete the team instead'; end if;
end $$;

create or replace function public.delete_team(p_team uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  delete from public.teams where id = p_team and owner = auth.uid();
end $$;

revoke all on function public.create_team(text), public.join_team(text), public.leave_team(uuid), public.delete_team(uuid) from public, anon;
grant execute on function public.create_team(text), public.join_team(text), public.leave_team(uuid), public.delete_team(uuid) to authenticated;
