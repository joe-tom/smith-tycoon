-- 012_missions.sql
CREATE TABLE IF NOT EXISTS missions (
  id         BIGSERIAL PRIMARY KEY,
  player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  phase      TEXT NOT NULL,
  due_day    INT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending',
  payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  done_at    TIMESTAMPTZ,
  UNIQUE (player_id, kind, due_day, phase)
);
CREATE INDEX IF NOT EXISTS idx_missions_player_status
  ON missions(player_id, status, due_day);
