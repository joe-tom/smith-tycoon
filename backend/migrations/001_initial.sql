-- 단일 플레이어 MVP. player_id = 1 고정
create table if not exists players (
  id bigint primary key,
  gold int not null default 5000,
  reputation int not null default 0,
  craft_power int not null default 0,
  current_day int not null default 1,
  current_phase text not null default 'forge_open'
);

create table if not exists materials (
  id bigint primary key,
  name text not null,
  category text not null,
  attribute text,
  base_price int not null
);

create table if not exists inventory (
  player_id bigint references players(id) on delete cascade,
  material_id bigint references materials(id),
  qty int not null default 0,
  primary key (player_id, material_id)
);

create table if not exists weapons (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  owner text not null check (owner in ('player','hero','sold')),
  name text not null,
  type text not null,
  rarity int not null,
  sharpness int not null,
  attribute text,
  skill text not null,
  str_req int not null,
  mag_req int not null,
  enhancement_level int not null default 0,
  materials_used jsonb not null,
  created_day int not null
);

create table if not exists heroes (
  id bigserial primary key,
  name text not null,
  job text not null,
  str int not null,
  mag int not null,
  gold int not null,
  mood text not null,
  personality_tags text[] not null default '{}',
  affinity int not null default 0,
  nickname text,
  return_day int,
  status text not null default 'alive' check (status in ('alive','fled','dead')),
  history jsonb not null default '[]'::jsonb
);

create table if not exists negotiations (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  phase text not null,
  kind text not null check (kind in ('sell','buy','enhance')),
  counterparty_id bigint not null,
  weapon_id bigint references weapons(id),
  materials jsonb,
  rounds jsonb not null default '[]'::jsonb,
  outcome text not null default 'open' check (outcome in ('accepted','rejected','open')),
  agreed_price int
);

create table if not exists battles (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  hero_id bigint references heroes(id),
  weapon_id bigint references weapons(id),
  demon jsonb not null,
  script_text text not null,
  outcomes jsonb not null
);
