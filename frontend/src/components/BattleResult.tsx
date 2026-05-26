import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { BattleResponse } from "../types";

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

  return (
    <div>
      <h2>전투 결과</h2>
      {result.demon && (
        <p style={result.demon.is_boss ? { color: "#c00", fontWeight: "bold" } : undefined}>
          {result.demon.is_boss ? "⚜ " : ""}
          상대: {result.demon.type}
          {result.demon.sin && <small> ({result.demon.sin})</small>}
          {result.demon.attribute && <small> · {result.demon.attribute}</small>}
          <small> · 난이도 {result.demon.difficulty}</small>
        </p>
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
