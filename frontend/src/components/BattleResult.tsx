import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { BattleResponse } from "../types";

// 5행 사이클: 금 → 바람 → 흙 → 물 → 불 → 금 (각 원소가 다음을 억제)
const CYCLE_NEXT: Record<string, string> = {
  "금": "바람", "바람": "흙", "흙": "물", "물": "불", "불": "금",
};

function matchup(weaponAttr: string | null | undefined, demonAttr: string | null | undefined):
  { label: string; color: string } | null {
  if (!weaponAttr || !demonAttr) return null;
  if (CYCLE_NEXT[weaponAttr] === demonAttr) return { label: "상성 우위 +30%", color: "#080" };
  if (CYCLE_NEXT[demonAttr] === weaponAttr) return { label: "상성 열세 −30%", color: "#a30" };
  return null;
}

export function BattleResult({ onDone }: { onDone: () => void }) {
  const [result, setResult] = useState<BattleResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;  // StrictMode dev double-invoke 방지
    ranRef.current = true;
    api.battle().then(setResult).catch((e) => setErr(e.message));
  }, []);

  if (err) return <p style={{ color: "red" }}>전투 실패: {err}</p>;
  if (!result) return <p>전투 중...</p>;

  const w = result.weapon;
  const d = result.demon;
  const m = matchup(w?.attribute, d?.attribute);

  return (
    <div>
      <h2>전투 결과</h2>
      {d && (
        <p style={d.is_boss ? { color: "#c00", fontWeight: "bold" } : undefined}>
          {d.is_boss ? "⚜ " : ""}
          상대: {d.type}
          {d.sin && <small> ({d.sin})</small>}
          <small> · {d.attribute ?? "무"}</small>
          <small> · 난이도 {d.difficulty}</small>
        </p>
      )}
      {w ? (
        <p>
          무기: <strong>{w.name}</strong> ({w.type}
 · {w.attribute ?? "무"}, 예리도 {w.sharpness}, 희귀도 {w.rarity})
          {m && <small style={{ color: m.color, marginLeft: 8 }}>{m.label}</small>}
        </p>
      ) : (
        <p><small>맨손 전투 (−30% 페널티)</small></p>
      )}
      <p style={{ whiteSpace: "pre-wrap" }}>{result.script}</p>
      <ul>
        <li>용사: <strong>{result.outcomes.hero}</strong></li>
        <li>무기: <strong>{result.outcomes.weapon}</strong></li>
        <li>마왕군: <strong>{result.outcomes.demon}</strong></li>
      </ul>
      <button className="btn" onClick={onDone}>다음으로</button>
    </div>
  );
}
