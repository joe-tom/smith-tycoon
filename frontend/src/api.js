const BASE = "/api";
async function request(method, path, body) {
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
    getState: () => request("GET", "/state"),
    resetGame: () => request("POST", "/game/reset"),
    forge: (weapon_type, materials) => request("POST", "/forge", { weapon_type, materials }),
    negotiate: (weapon_id, price_offered, player_message) => request("POST", "/negotiate", { weapon_id, price_offered, player_message }),
    finalize: (negotiation_id) => request("POST", "/negotiate/finalize", { negotiation_id }),
    battle: () => request("POST", "/battle"),
};
