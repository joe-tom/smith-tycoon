import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { DaySummaryResponse } from "../types";

export function DaySummary({ onDone }: { onDone: () => void }) {
  const [data, setData] = useState<DaySummaryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    api.daySummary().then(setData).catch((e) => setErr(e.message));
  }, []);

  const next = async () => {
    setBusy(true);
    try { await api.nextDay(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (err) return <p style={{ color: "red" }}>요약 로드 실패: {err}</p>;
  if (!data) return <p>요약 준비 중...</p>;

  const s = data.summary;
  return (
    <div>
      <h2>Day {data.day} 요약</h2>
      <ul>
        <li>제작: {s.forges}건</li>
        <li>판매: {s.sales}건, 골드 변화 {s.gold_delta >= 0 ? "+" : ""}{s.gold_delta}</li>
        <li>구매: {s.buys}건</li>
        <li>전투: {s.battles}건 (생존 {s.heroes_survived} / 부상 {s.heroes_injured} / 사망 {s.heroes_died})</li>
        <li>평판 변화: {s.rep_delta >= 0 ? "+" : ""}{s.rep_delta}</li>
      </ul>

      <h4>이벤트 로그</h4>
      <ul style={{ maxHeight: 240, overflowY: "auto", border: "1px solid #ccc", padding: 8 }}>
        {data.events.map((e) => (
          <li key={e.id}><code>{e.kind}</code>: {JSON.stringify(e.payload)}</li>
        ))}
      </ul>

      <button className="btn" onClick={next} disabled={busy} style={{ marginTop: 16 }}>
        {busy ? "..." : "다음 날"}
      </button>
    </div>
  );
}
