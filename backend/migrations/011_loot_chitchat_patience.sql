-- 011_loot_chitchat_patience.sql
-- 2차 배치: 전리품 + chitchat + 인내심

ALTER TABLE heroes
  ADD COLUMN IF NOT EXISTS lore JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS loot_pending JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE negotiations
  ADD COLUMN IF NOT EXISTS patience_start INT,
  ADD COLUMN IF NOT EXISTS patience_current INT;
