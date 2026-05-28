import { useState } from "react";
import type { CurrentVisitor, StateResponse } from "../types";
import { api } from "../api";
import { NegotiationChat } from "./NegotiationChat";
import { EnhanceNegotiation } from "./EnhanceNegotiation";
import { LootNegotiation } from "./LootNegotiation";
import { ChitchatPanel } from "./ChitchatPanel";

type Mode = "menu" | "sell" | "enhance" | "loot" | "chitchat";

export function HeroVisitorPanel({
  state, visitor, refresh,
}: { state: StateResponse; visitor: CurrentVisitor; refresh: () => void }) {
  const [mode, setMode] = useState<Mode>("menu");
  const hero = visitor.hero;
  if (!hero) return <p>용사 정보를 불러오는 중...</p>;

  const isReturning = visitor.kind === "returning_hero";
  const hasWeapons = state.weapons.length > 0;
  const hasHeld = hero.mode === "enhance" && !!hero.held_weapon;
  const hasLoot = (hero.loot_pending?.length ?? 0) > 0;
  const canChitchat = (hero.affinity ?? 0) >= 0;

  const back = async () => { await refresh(); setMode("menu"); };
  const sendAway = async () => {
    if (isReturning) await api.visitorReturn();
    else await api.visitorSkip();
    refresh();
  };

  if (mode === "sell" && hasWeapons) {
    return <NegotiationChat hero={hero} weapons={state.weapons} onDone={back} />;
  }
  if (mode === "enhance" && hasHeld) {
    return <EnhanceNegotiation hero={hero} weapon={hero.held_weapon!} inventory={state.inventory} onDone={back} />;
  }
  if (mode === "loot" && hasLoot) {
    return <LootNegotiation hero={hero} onDone={back} />;
  }
  if (mode === "chitchat") {
    return <ChitchatPanel hero={hero} onDone={back} />;
  }

  return (
    <div>
      <h2>
        {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})
        {isReturning && <small style={{ marginLeft: 8, color: "#a06" }}>· 재방문 🔁</small>}
      </h2>
      {isReturning && visitor.recap && (
        <div style={{ background: "#f8f4ee", padding: 12, borderRadius: 6, margin: "8px 0" }}>
          <strong>지난 출정 회고</strong>
          <p style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{visitor.recap}</p>
        </div>
      )}
      <p>호감도 {hero.affinity ?? 0} · 보유 금화 {hero.gold ?? 0}</p>
      <div style={{ display: "grid", gap: 8, marginTop: 12, maxWidth: 320 }}>
        <button className="btn" disabled={!hasWeapons} onClick={() => setMode("sell")}>
          무기 판매{!hasWeapons && " (인벤토리 비어있음)"}
        </button>
        <button className="btn" disabled={!hasHeld} onClick={() => setMode("enhance")}>
          무기 강화{!hasHeld && " (들고 있는 무기 없음)"}
        </button>
        <button className="btn" disabled={!hasLoot} onClick={() => setMode("loot")}>
          전리품 매수{!hasLoot && " (전리품 없음)"}
        </button>
        <button className="btn" disabled={!canChitchat} onClick={() => setMode("chitchat")}>
          잡담{!canChitchat && " (호감도 부족)"}
        </button>
        <button className="btn" onClick={sendAway}>보내기</button>
      </div>
    </div>
  );
}
