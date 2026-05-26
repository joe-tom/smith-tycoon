import { useState } from "react";
import { api } from "../api";
import type { StateResponse } from "../types";
import { ENDINGS } from "../endings";

export function GameOver({ state, onReset }: { state: StateResponse; onReset: () => void }) {
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try { await api.resetGame(); onReset(); }
    finally { setBusy(false); }
  };
  if (!state.player) return null;
  const kind = state.player.ending_kind;
  const meta = kind ? ENDINGS[kind] : null;
  return (
    <div style={{ padding: 24 }}>
      <h2>{meta?.title ?? "게임 종료"}</h2>
      <p style={{ whiteSpace: "pre-wrap", color: meta?.won ? "#080" : "#a30" }}>
        {meta?.flavor ?? "100일 운영이 종료되었습니다."}
      </p>
      <div style={{ marginTop: 16, padding: 12, background: "#f5f5f5" }}>
        <p>Day {state.player.current_day} / 100</p>
        <p>골드 {state.player.gold.toLocaleString()} · 평판 {state.player.reputation}</p>
        <p>처치한 보스: {state.boss_kill_count}명</p>
        <p>사망한 용사: {state.player.heroes_died_total}명</p>
        <p>파괴된 무기: {state.player.weapons_destroyed_total}개</p>
      </div>
      <button className="btn" onClick={reset} disabled={busy} style={{ marginTop: 16 }}>
        새 게임
      </button>
    </div>
  );
}
