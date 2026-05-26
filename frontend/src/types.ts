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
}

export interface Player {
  id: number;
  gold: number;
  reputation: number;
  current_day: number;
  current_phase: string;
}

export interface StateResponse {
  player: Player;
  inventory: Material[];
  weapons: Weapon[];
  hero: Hero | null;
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
