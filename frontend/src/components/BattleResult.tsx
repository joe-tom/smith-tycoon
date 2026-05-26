import { useEffect, useState } from "react";
import { api } from "../api";
import type { BattleResponse } from "../types";

export function BattleResult({ onDone }: { onDone: () => void }) {
  const [result, setResult] = useState<BattleResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.battle().then(setResult).catch((e) => setErr(e.message));
  }, []);

  if (err) return <p style={{ color: "red" }}>전투 실패: {err}</p>;
  if (!result) return <p>전투 중...</p>;

  return (
    <div>
      <h2>전투 결과</h2>
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
