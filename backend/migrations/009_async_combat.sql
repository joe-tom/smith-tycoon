-- 009_async_combat.sql
-- 비동기 전투 + 가변 하루 길이 지원

-- 1) players 컬럼 추가
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS day_schedule JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS current_visitor_index INT NOT NULL DEFAULT 0;

-- 2) pending_outcomes 테이블
CREATE TABLE IF NOT EXISTS pending_outcomes (
  id              BIGSERIAL PRIMARY KEY,
  player_id       BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  hero_id         BIGINT NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
  depart_day      INT NOT NULL,
  resolve_day     INT NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('revisit_survive','revisit_injure','death_mail')),
  outcome_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
  weapon_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  consumed        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_outcomes_player_resolve
  ON pending_outcomes(player_id, resolve_day, consumed);

-- 3) 기존 진행 중 게임의 phase 정규화
UPDATE players
  SET current_phase = 'forge_open',
      current_visitor_index = 0,
      day_schedule = '[]'::jsonb
  WHERE current_phase NOT IN ('forge_open', 'visitor', 'day_summary', 'game_over');
