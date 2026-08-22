-- Cesta Solidária - schema Supabase
-- Executar no SQL editor do Supabase (idempotente, pode reexecutar)

-- ============ profiles ============
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null default '',
  is_admin boolean not null default false,
  criado_em timestamptz not null default now()
);

-- Migração: coluna email usada pelo código (src/db.py)
alter table public.profiles add column if not exists email text;

-- Migração: coluna termo_busca em produtos (marca mais barata automática)
alter table public.produtos add column if not exists termo_busca text;

-- Backfill idempotente: usuarios criados antes da migracao nao passam pelo
-- trigger handle_new_user, entao o email precisa vir de auth.users.
update public.profiles p
set email = (select u.email from auth.users u where u.id = p.id)
where p.email is null;

alter table public.profiles enable row level security;

drop policy if exists "profiles leitura autenticado" on public.profiles;
create policy "profiles leitura autenticado"
  on public.profiles for select to authenticated using (true);
drop policy if exists "profiles update proprio" on public.profiles;
create policy "profiles update proprio"
  on public.profiles for update to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

-- Bloqueia qualquer usuário autenticado de alterar is_admin via REST/SQL.
-- Somente service_role (criar_usuario/excluir_usuario) pode mudar o papel,
-- pois conexões service_role não têm auth.uid().
create or replace function public.block_admin_change()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  if auth.uid() is not null and new.is_admin is distinct from old.is_admin then
    raise exception 'is_admin so pode ser alterado via operacao administrativa';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_block_admin_change on public.profiles;
create trigger trg_block_admin_change
  before update on public.profiles
  for each row execute procedure public.block_admin_change();

create or replace function public.handle_new_user()
returns trigger
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, nome, email, is_admin)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'nome', ''),
    new.email,
    false
  )
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ============ produtos ============
create table if not exists public.produtos (
  id bigserial primary key,
  nome text not null,
  marca text,
  unidade text,
  qtd_por_cesta numeric not null default 1,
  estoque_atual numeric not null default 0,
  preco_atual numeric,
  token_tenda text,
  -- termo generico de busca: quando preenchido, o workflow diario busca o
  -- termo e grava sempre a marca mais barata do mesmo peso/volume.
  termo_busca text,
  url_tenda text,
  ativo boolean not null default true,
  ultima_atualizacao_preco timestamptz,
  criado_em timestamptz not null default now()
);

alter table public.produtos enable row level security;

drop policy if exists "produtos leitura autenticado" on public.produtos;
create policy "produtos leitura autenticado"
  on public.produtos for select to authenticated using (true);
drop policy if exists "produtos insert admin" on public.produtos;
create policy "produtos insert admin"
  on public.produtos for insert to authenticated
  with check ((select is_admin from public.profiles where id = auth.uid()));
drop policy if exists "produtos update admin" on public.produtos;
create policy "produtos update admin"
  on public.produtos for update to authenticated
  using ((select is_admin from public.profiles where id = auth.uid()));
drop policy if exists "produtos delete admin" on public.produtos;
create policy "produtos delete admin"
  on public.produtos for delete to authenticated
  using ((select is_admin from public.profiles where id = auth.uid()));

-- ============ precos_historico ============
create table if not exists public.precos_historico (
  id bigserial primary key,
  produto_id bigint not null references public.produtos(id) on delete cascade,
  preco numeric not null,
  dia date not null default current_date,
  data_consulta timestamptz not null default now(),
  region_id text,
  fonte text not null default 'tenda',
  unique (produto_id, dia)
);

alter table public.precos_historico enable row level security;

drop policy if exists "precos leitura autenticado" on public.precos_historico;
create policy "precos leitura autenticado"
  on public.precos_historico for select to authenticated using (true);
drop policy if exists "precos insert admin" on public.precos_historico;
create policy "precos insert admin"
  on public.precos_historico for insert to authenticated
  with check ((select is_admin from public.profiles where id = auth.uid()));
-- inserir_precos_historico usa on_conflict=produto_id,dia com
-- resolution=merge-duplicates -> vira INSERT .. ON CONFLICT DO UPDATE,
-- que exige privilegio e policy de UPDATE no Postgres/PostgREST.
drop policy if exists "precos update admin" on public.precos_historico;
create policy "precos update admin"
  on public.precos_historico for update to authenticated
  using ((select is_admin from public.profiles where id = auth.uid()));

-- ============ regions ============
create table if not exists public.regions (
  region_id text primary key,
  nome text not null,
  cep_referencia text,
  ativo boolean not null default true
);

alter table public.regions enable row level security;

drop policy if exists "regions leitura autenticado" on public.regions;
create policy "regions leitura autenticado"
  on public.regions for select to authenticated using (true);
drop policy if exists "regions write admin" on public.regions;
create policy "regions write admin"
  on public.regions for all to authenticated
  using ((select is_admin from public.profiles where id = auth.uid()))
  with check ((select is_admin from public.profiles where id = auth.uid()));

-- ============ config ============
create table if not exists public.config (
  chave text primary key,
  valor text not null
);

alter table public.config enable row level security;

drop policy if exists "config leitura autenticado" on public.config;
create policy "config leitura autenticado"
  on public.config for select to authenticated using (true);
drop policy if exists "config write admin" on public.config;
create policy "config write admin"
  on public.config for all to authenticated
  using ((select is_admin from public.profiles where id = auth.uid()))
  with check ((select is_admin from public.profiles where id = auth.uid()));

-- ============ compras ============
create table if not exists public.compras (
  id bigserial primary key,
  data timestamptz not null default now(),
  orcamento numeric,
  num_cestas int,
  itens jsonb not null default '[]'::jsonb,
  total numeric,
  criado_por uuid references auth.users(id)
);

alter table public.compras enable row level security;

create index if not exists idx_compras_criado_por on public.compras(criado_por);

-- Migração: exclusão de usuário não deve perder o histórico de compras.
do $$
begin
  if exists (
    select 1 from pg_constraint
    where conname = 'compras_criado_por_fkey'
      and confdeltype <> 'n'
  ) then
    alter table public.compras drop constraint compras_criado_por_fkey;
    alter table public.compras
      add constraint compras_criado_por_fkey
      foreign key (criado_por) references auth.users(id) on delete set null;
  elsif not exists (
    select 1 from pg_constraint where conname = 'compras_criado_por_fkey'
  ) then
    alter table public.compras
      add constraint compras_criado_por_fkey
      foreign key (criado_por) references auth.users(id) on delete set null;
  end if;
end $$;

drop policy if exists "compras leitura autenticado" on public.compras;
create policy "compras leitura autenticado"
  on public.compras for select to authenticated using (true);
drop policy if exists "compras insert proprio" on public.compras;
create policy "compras insert proprio"
  on public.compras for insert to authenticated
  with check (criado_por = (select auth.uid()));

-- ============ GRANTS ============
-- Privilégio mínimo: políticas RLS continuam como segunda camada.
-- Revoke primeiro: GRANT é aditivo e não remove concessões amplas de
-- execuções anteriores do schema.
grant usage on schema public to authenticated, service_role;

revoke all privileges on all tables in schema public from authenticated;
revoke all privileges on all tables in schema public from anon;
revoke all privileges (nome, email) on public.profiles from authenticated;

-- Tabelas futuras criadas pelo postgres ja nascem fechadas para anon.
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    alter default privileges for role postgres in schema public revoke all on tables from anon;
    alter default privileges for role postgres in schema public revoke all on sequences from anon;
  end if;
end $$;

-- Leitura geral para autenticados (todas as tabelas têm policy de leitura).
grant select on all tables in schema public to authenticated;
-- Escrita: apenas onde existe política correspondente.
grant insert, update, delete on public.produtos to authenticated;
grant insert, update on public.precos_historico to authenticated;
grant insert on public.compras to authenticated;
grant update (nome, email) on public.profiles to authenticated;
grant insert, update on public.regions to authenticated;
grant insert, update on public.config to authenticated;

grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to authenticated, service_role;

-- ============ LIMPEZA DE POLITICAS LEGADAS ============
-- Versoes antigas do schema criavam politicas permissivas "* autenticado"
-- (with check true) para escrita. Os drops nomeados das secoes acima nao
-- as removem, entao sao eliminadas aqui para convergir ao modelo admin-only.
drop policy if exists "produtos insert autenticado" on public.produtos;
drop policy if exists "produtos update autenticado" on public.produtos;
drop policy if exists "produtos delete autenticado" on public.produtos;
drop policy if exists "precos_historico insert autenticado" on public.precos_historico;
drop policy if exists "regions insert autenticado" on public.regions;
drop policy if exists "regions update autenticado" on public.regions;
drop policy if exists "config insert autenticado" on public.config;
drop policy if exists "config update autenticado" on public.config;
drop policy if exists "compras insert autenticado" on public.compras;

-- ============ OPERACOES ADMIN DE USUARIOS VIA RPC ============
-- O frontend chama estas funcoes com o JWT do admin logado; nenhuma
-- SERVICE_ROLE_KEY fica no app. Security definer permite escrever em
-- auth.users (criar/excluir conta GoTrue) com porteira de is_admin aqui.

create extension if not exists pgcrypto with schema extensions;

create or replace function public.admin_criar_usuario(
  p_email text,
  p_senha text,
  p_nome text,
  p_is_admin boolean default false
) returns uuid
language plpgsql
security definer set search_path = public, extensions
as $$
declare
  novo_id uuid;
begin
  if coalesce((select is_admin from public.profiles where id = auth.uid()), false) is not true then
    raise exception 'apenas administradores podem criar usuarios';
  end if;

  insert into auth.users (id, aud, role, email, encrypted_password,
      email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
      created_at, updated_at)
  values (gen_random_uuid(), 'authenticated', 'authenticated',
      lower(p_email), extensions.crypt(p_senha, extensions.gen_salt('bf')),
      now(), '{"provider":"email","providers":["email"]}'::jsonb,
      jsonb_build_object('nome', p_nome),
      now(), now());

  -- o trigger handle_new_user criou o profile; aplica o papel pedido
  select id into novo_id from auth.users where email = lower(p_email);
  update public.profiles set is_admin = p_is_admin where id = novo_id;
  return novo_id;
end $$;

create or replace function public.admin_excluir_usuario(p_id uuid) returns void
language plpgsql
security definer set search_path = public
as $$
begin
  if coalesce((select is_admin from public.profiles where id = auth.uid()), false) is not true then
    raise exception 'apenas administradores podem excluir usuarios';
  end if;
  if p_id = auth.uid() then
    raise exception 'nao e possivel excluir a propria conta';
  end if;
  delete from auth.users where id = p_id;
end $$;

revoke execute on function public.admin_criar_usuario(text, text, text, boolean) from public, anon;
revoke execute on function public.admin_excluir_usuario(uuid) from public, anon;
grant execute on function public.admin_criar_usuario(text, text, text, boolean) to authenticated;
grant execute on function public.admin_excluir_usuario(uuid) to authenticated;

-- ============ seed ============

-- ============ seed ============
insert into public.regions (region_id, nome, cep_referencia)
values
  ('000010', 'Indaiatuba', null),
  ('000020', 'Salto', null),
  ('000030', 'Itu', null),
  ('000040', 'Campinas', null)
on conflict (region_id) do nothing;

insert into public.config (chave, valor) values
  ('tenda_region_id', '000010'),
  ('preco_stale_dias', '2')
on conflict (chave) do nothing;
