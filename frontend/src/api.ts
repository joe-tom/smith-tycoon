import type { StateResponse, Weapon, NegotiateResponse, BattleResponse } from "./types";

const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw Object.assign(new Error("api_error"), { detail, status: r.status });
  }
  return r.json();
}

export const api = {
  getState: () => request<StateResponse>("GET", "/state"),
  resetGame: () => request<{ ok: true }>("POST", "/game/reset"),
  forge: (weapon_type: string, materials: { material_id: number; qty: number }[]) =>
    request<Weapon>("POST", "/forge", { weapon_type, materials }),
  negotiate: (weapon_id: number, price_offered: number, player_message: string, negotiation_id: number | null = null) =>
    request<NegotiateResponse>("POST", "/negotiate", { weapon_id, price_offered, player_message, negotiation_id }),
  finalize: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/negotiate/finalize", { negotiation_id }),
  battle: () => request<BattleResponse>("POST", "/battle"),
};
