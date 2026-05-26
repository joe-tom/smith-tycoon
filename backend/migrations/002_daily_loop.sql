-- 002_daily_loop.sql — Plan 2: 다일 루프·상인·일일 요약·RLS

create table if not exists merchants_today (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  materials jsonb not null,
  weapon jsonb,
  outcome text not null default 'pending' check (outcome in ('pending','done')),
  unique (player_id, day)
);

create table if not exists day_events (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  phase text not null,
  kind text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

alter table heroes add column if not exists held_weapon_id bigint references weapons(id);
alter table heroes add column if not exists visit_count int not null default 0;

-- 기존 hero에 visit_count backfill: hero_roster day_event에 등장한 일자 수
with counts as (
  select (jsonb_array_elements_text(payload->'hero_ids'))::bigint as hero_id,
         count(distinct day) as visits
  from day_events
  where kind = 'hero_roster'
  group by hero_id
)
update heroes h set visit_count = c.visits
from counts c where h.id = c.hero_id and h.visit_count = 0;

-- RLS
alter table players          enable row level security;
alter table inventory        enable row level security;
alter table weapons          enable row level security;
alter table heroes           enable row level security;
alter table negotiations     enable row level security;
alter table battles          enable row level security;
alter table merchants_today  enable row level security;
alter table day_events       enable row level security;
alter table materials        enable row level security;

drop policy if exists "materials_anon_read" on materials;
create policy "materials_anon_read"
  on materials for select to anon using (true);
