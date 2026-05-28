import type {
  StateResponse, Weapon, NegotiateResponse, DaySummaryResponse, EnhanceResult,
} from "./types";
import { getNickname } from "./auth";

const BASE = "/api";

function buildHeaders(): HeadersInit {
  const nickname = getNickname();
  if (!nickname) throw new Error("no_nickname");
  return { "Content-Type": "application/json", "X-Player-Nickname": nickname };
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: buildHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({} as Record<string, unknown>));
    const detail = (body as Record<string, unknown>).detail as Record<string, unknown> | undefined;
    const message = (detail?.message as string) || (detail?.error as string) || `api_error (${r.status})`;
    throw Object.assign(new Error(message), { detail, status: r.status });
  }
  return r.json();
}

export const api = {
  getState: () => request<StateResponse>("GET", "/state"),
  resetGame: () => request<{ ok: true }>("POST", "/game/reset"),

  forge: (weapon_type: string, materials: { material_id: number; qty: number }[]) =>
    request<Weapon>("POST", "/forge", { weapon_type, materials }),
  forgeSkip: () =>
    request<{ ok: true; current_phase: string }>("POST", "/forge/skip"),

  negotiate: (weapon_id: number, price_offered: number, player_message: string, negotiation_id: number | null = null) =>
    request<NegotiateResponse>("POST", "/negotiate", { weapon_id, price_offered, player_message, negotiation_id }),
  finalize: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string }>("POST", "/negotiate/finalize", { negotiation_id }),
  playerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; current_phase: string }>("POST", "/negotiate/player_accept", { negotiation_id }),
  playerReject: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string }>("POST", "/negotiate/player_reject", { negotiation_id }),
  negotiateSkip: () =>
    request<{ ok: true; current_phase: string }>("POST", "/negotiate/skip"),

  visitorReturn: () => request<{ ok: true; current_phase: string }>("POST", "/visitor/current/return"),
  visitorSkip: () => request<{ ok: true; current_phase: string }>("POST", "/visitor/current/skip"),
  mailAck: (id: number) => request<{ ok: true }>("POST", `/mail/${id}/ack`),

  visitorMissionAction: (action: "pay" | "ack" | "skip") =>
    request<{ ok: true; current_phase?: string; ending?: string }>(
      "POST", "/visitor/current/mission_action", { action }),

  chitchat: (player_message: string = "") =>
    request<{ lore_text: string; entry: { day: number; text: string } }>(
      "POST", "/visitor/current/chitchat", { player_message }),

  lootNegotiate: (price_offered: number, player_message: string, negotiation_id: number | null = null) =>
    request<NegotiateResponse & { patience_current?: number; patience_start?: number }>(
      "POST", "/loot/negotiate", { price_offered, player_message, negotiation_id }),
  lootPlayerAccept: (negotiation_id: number) =>
    request<{ ok: true }>("POST", "/loot/player_accept", { negotiation_id }),
  lootPlayerReject: (negotiation_id: number) =>
    request<{ ok: true }>("POST", "/loot/player_reject", { negotiation_id }),
  lootFinalize: (negotiation_id: number) =>
    request<{ ok: true }>("POST", "/loot/finalize", { negotiation_id }),

  merchantNegotiate: (
    merchant_id: number,
    price_offered: number,
    player_message: string,
    negotiation_id: number | null = null,
    selected_materials: { material_id: number; qty: number }[] | null = null,
    select_weapon: boolean = false,
  ) =>
    request<NegotiateResponse>("POST", "/merchant/negotiate", {
      merchant_id, price_offered, player_message, negotiation_id,
      selected_materials, select_weapon,
    }),
  merchantFinalize: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string }>("POST", "/merchant/negotiate/finalize", { negotiation_id }),
  merchantPlayerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; current_phase: string }>("POST", "/merchant/player_accept", { negotiation_id }),
  merchantPlayerReject: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string }>("POST", "/merchant/player_reject", { negotiation_id }),
  merchantSkip: () =>
    request<{ ok: true; current_phase: string }>("POST", "/merchant/skip"),

  daySummary: () => request<DaySummaryResponse>("GET", "/day/summary"),
  nextDay: () => request<{ ok: true; current_day: number; current_phase: string }>("POST", "/day/next"),

  enhanceNegotiate: (
    price_offered: number,
    player_message: string,
    negotiation_id: number | null = null,
    selected_materials: { material_id: number; qty: number }[] | null = null,
  ) =>
    request<NegotiateResponse>("POST", "/enhance/negotiate", {
      price_offered, player_message, negotiation_id, selected_materials,
    }),
  enhanceFinalize: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string; result: EnhanceResult }>(
      "POST", "/enhance/finalize", { negotiation_id }),
  enhancePlayerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; current_phase: string; result: EnhanceResult }>(
      "POST", "/enhance/player_accept", { negotiation_id }),
  enhancePlayerReject: (negotiation_id: number) =>
    request<{ ok: true; current_phase: string }>("POST", "/enhance/player_reject", { negotiation_id }),
  enhanceSkip: () =>
    request<{ ok: true; current_phase: string }>("POST", "/enhance/skip"),
};
