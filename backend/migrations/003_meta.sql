-- 003_meta.sql — Plan 3 (단골 메타) 기록용
-- 신규 컬럼/테이블 없음. 기존 컬럼 재활용:
--   heroes.affinity, heroes.history, heroes.nickname, heroes.held_weapon_id, heroes.visit_count
--   weapons.enhancement_level, weapons.materials_used (jsonb)
--   negotiations.kind='enhance' (check constraint에 이미 포함)
-- 이 파일은 향후 Plan 3 관련 인덱스 등 필요 시 추가될 수 있음.
select 1;   -- 빈 마이그레이션 회피용 no-op
