-- 006_players_id_identity.sql — players.id를 identity 컬럼으로 (자동 증가)
-- 기존 001은 id를 bigint PK로만 선언했고, single-player라 id=1 하드코딩으로 충분했음.
-- 멀티 플레이어 도입으로 닉네임마다 새 row를 insert해야 해서 자동 증가가 필요.
alter table players alter column id add generated always as identity;
