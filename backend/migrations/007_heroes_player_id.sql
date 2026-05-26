-- 007_heroes_player_id.sql — heroes 테이블에 누락된 player_id 스코프 컬럼
-- multi-player (005) 도입 시 코드는 heroes에 player_id를 기록·필터하도록 바꿨지만
-- 실제 컬럼은 추가되지 않아 /game/reset 등 player_id 필터 쿼리에서 42703 오류.
-- 005에서 heroes 행은 전부 wipe되었으므로 NOT NULL 안전.
alter table heroes add column player_id bigint not null references players(id) on delete cascade;
create index if not exists heroes_player_id_idx on heroes(player_id);
