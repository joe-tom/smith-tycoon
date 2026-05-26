-- 008_endgame.sql — 엔딩 시스템: 누적 카운터 + ending_kind
alter table players
  add column heroes_died_total       int  not null default 0,
  add column weapons_destroyed_total int  not null default 0,
  add column ending_kind             text;
