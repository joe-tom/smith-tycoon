-- 010_weapons_owner_dispatched.sql
-- 009 비동기 전투의 weapon 소프트삭제(owner='dispatched')를 위한 CHECK 확장.

ALTER TABLE weapons DROP CONSTRAINT IF EXISTS weapons_owner_check;
ALTER TABLE weapons ADD CONSTRAINT weapons_owner_check
  CHECK (owner = ANY (ARRAY['player'::text, 'hero'::text, 'sold'::text, 'dispatched'::text]));
