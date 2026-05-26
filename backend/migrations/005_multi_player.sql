-- 005_multi_player.sql — 닉네임 기반 멀티 세이브
-- 기존 데이터 와이프 (FK 순서 준수)
delete from day_events;
delete from merchants_today;
delete from battles;
delete from negotiations;
delete from heroes;
delete from weapons;
delete from inventory;
delete from players;
-- 닉네임 컬럼
alter table players add column nickname text unique not null;
