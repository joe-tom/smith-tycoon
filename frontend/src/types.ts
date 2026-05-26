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
}

export interface HeroPreferences {
  types: string[];
  hint: string;
  stat_hint: string;
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
  // Plan 3 신규
  nickname?: string | null;
  mode?: "sell" | "enhance";
  held_weapon?: Weapon | null;
}

export interface Player {
  id: number;
  gold: number;
  reputation: number;
  current_day: number;
  current_phase: string;
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

export interface StateResponse {
  player: Player | null;
  inventory: Material[];
  weapons: Weapon[];
  hero: Hero | null;
  merchant: MerchantToday | null;
}

export interface NegotiateResponse {
  negotiation_id: number;
  decision: "accept" | "reject" | "counter";
  counter_price: number | null;
  message: string;
}

export interface BattleResponse {
  script: string;
  outcomes: { hero: string; weapon: string; demon: string };
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
