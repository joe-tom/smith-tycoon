-- 003_meta.sql — Plan 3 (단골 메타)
-- 기존 컬럼 재활용:
--   heroes.affinity, heroes.history, heroes.nickname, heroes.held_weapon_id, heroes.visit_count
--   weapons.enhancement_level, weapons.materials_used (jsonb)
--   negotiations.kind='enhance' (check constraint에 이미 포함)

-- finalize 멱등성을 위한 플래그
alter table negotiations add column if not exists finalized boolean not null default false;
