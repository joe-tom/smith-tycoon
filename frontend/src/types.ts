export interface Material {
  material_id: number;
  qty: number;
  name: string;
  category: string;
  attribute: string | null;
  base_price: number;
}

export interface Weapon {
  id: number;
  name: string;
  type: string;
  rarity: number;
  sharpness: number;
  attribute: string | null;
  skill: string;
  str_req: number;
  mag_req: number;
  market_price?: number;   // 서버 자동 계산 — /state 응답에서 채움
  enhancement_level?: number | null;
}

export interface HeroPreferences {
  types: string[];
  hint: string;
  stat_hint: string;
}

export interface LoreEntry {
  day: number;
  text: string;
}

export interface LootItem {
  material_id: number;
  qty: number;
  asking_price?: number;
  name?: string;
}

export interface Hero {
  id: number;
  name: string;
  job: string;
  str: number;
  mag: number;
  gold: number;
  mood: string;
  personality_tags: string[];
  affinity: number;
  visit_count?: number;
  preferences?: HeroPreferences;
  nickname?: string | null;
  mode?: "sell" | "enhance";
  held_weapon?: Weapon | null;
  // 011 (2차 배치)
  lore?: LoreEntry[];
  loot_pending?: LootItem[];
}

export interface Player {
  id: number;
  gold: number;
  reputation: number;
  effort: number;
  current_day: number;
  current_phase: string;
  heroes_died_total: number;
  weapons_destroyed_total: number;
  ending_kind: string | null;
}

export interface MerchantInventoryMaterial {
  material_id: number;
  name: string;
  category: string;
  attribute: string | null;
  base_price: number;
  qty: number;
  asking_price: number;
}

export interface MerchantInventoryWeapon {
  name: string;
  type: string;
  rarity: number;
  sharpness: number;
  attribute: string | null;
  skill: string;
  str_req: number;
  mag_req: number;
  asking_price: number;
}

export interface MerchantToday {
  id: number;
  day: number;
  materials: MerchantInventoryMaterial[];
  weapon: MerchantInventoryWeapon | null;
  outcome: "pending" | "done";
}

export type VisitorKind = "new_hero" | "returning_hero" | "merchant";

export interface WeaponSnapshot {
  id?: number;
  name?: string;
  type?: string;
  attack?: number;
  attribute?: string | null;
  weapon_type?: string;
  rarity?: number;
  sharpness?: number;
}

export interface BattleOutcome {
  hero: "survived" | "injured" | "died" | string;
  weapon?: "preserved" | "destroyed" | "none" | string;
  demon?: string;
  monsters_killed?: number;
  hero_opinion?: "want_better_weapon" | "weapon_broke" | "none";
  recap?: string;
}

export interface CurrentVisitor {
  kind: VisitorKind;
  hero_id?: number;
  outcome_id?: number;
  hero?: Hero;
  outcome?: BattleOutcome;
  weapon_snapshot?: WeaponSnapshot;
  depart_day?: number;
  recap?: string;
  merchant?: MerchantToday;
}

export interface DeathMail {
  id: number;
  hero_id: number;
  weapon_snapshot: WeaponSnapshot;
  outcome: BattleOutcome;
}

export interface StateResponse {
  player: Player | null;
  inventory: Material[];
  weapons: Weapon[];
  current_visitor: CurrentVisitor | null;
  day_schedule: CurrentVisitor[];
  current_visitor_index: number;
  death_mails: DeathMail[];
  boss_kill_count: number;
}

export interface NegotiateResponse {
  negotiation_id: number;
  decision: "accept" | "reject" | "counter";
  counter_price: number | null;
  message: string;
}

export interface Demon {
  type: string;
  attribute: string | null;
  difficulty: number;
  is_boss?: boolean;
  boss_id?: string;
  sin?: string | null;
}

export interface BattleResponse {
  script: string;
  outcomes: { hero: string; weapon: string; demon: string };
  demon: Demon;
  weapon: Weapon | null;
  next_phase: string;
}

export interface DayEvent {
  id: number;
  day: number;
  phase: string;
  kind: string;
  payload: Record<string, unknown>;
}

export interface DaySummaryResponse {
  day: number;
  events: DayEvent[];
  summary: {
    forges: number; sales: number; buys: number; battles: number;
    heroes_survived: number; heroes_injured: number; heroes_died: number;
    rep_delta: number; gold_delta: number;
  };
}
