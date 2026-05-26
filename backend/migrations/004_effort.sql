-- 004_effort.sql — 플레이어 노력(스태미나) 스탯
-- 제작 시 재료 카테고리 가중치만큼 소비, 시세 130%↑/200%↑ 매도 시 회복.
alter table players add column if not exists effort int not null default 50;
