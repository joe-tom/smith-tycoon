-- 013_negotiations_kind_buy_loot.sql
-- buy_loot 협상 종류 허용 (전리품 매수)

ALTER TABLE negotiations DROP CONSTRAINT negotiations_kind_check;
ALTER TABLE negotiations ADD CONSTRAINT negotiations_kind_check
  CHECK (kind IN ('sell','buy','enhance','buy_loot'));
