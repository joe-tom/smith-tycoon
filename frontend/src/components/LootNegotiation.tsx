import { useState } from "react";
import type { Hero, NegotiateResponse } from "../types";
import { api } from "../api";
import { PatienceGauge } from "./PatienceGauge";

type LootResp = NegotiateResponse;

export function LootNegotiation({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  const loot = hero.loot_pending ?? [];
  const [price, setPrice] = useState(0);
  const [text, setText] = useState("");
  const [last, setLast] = useState<LootResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.lootNegotiate(price, text, last?.negotiation_id ?? null);
      setLast(res);
      if (res.counter_price) setPrice(res.counter_price);
      if (res.decision === "accept") {
        await api.lootFinalize(res.negotiation_id);
        setDone(true);
      } else if (res.decision === "reject") {
        setDone(true);
      }
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const accept = async () => {
    if (!last) return;
    setBusy(true);
    try {
      await api.lootPlayerAccept(last.negotiation_id);
      setDone(true);
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const reject = async () => {
    if (last) await api.lootPlayerReject(last.negotiation_id);
    onDone();
  };

  if (done) {
    return (
      <div>
        <p>{last?.decision === "accept" ? "거래 성사!" : "거래 결렬."}</p>
        <button className="btn" onClick={onDone}>돌아가기</button>
      </div>
    );
  }

  return (
    <div>
      <h2>전리품 매수 — {hero.name}</h2>
      <PatienceGauge current={last?.patience_current} start={last?.patience_start} label={`${hero.name}의 인내심`} />
      <p>호감도 {hero.affinity ?? 0}</p>
      <ul>
        {loot.map((it, i) => (
          <li key={i}>{it.name ?? `재료 #${it.material_id}`} × {it.qty}</li>
        ))}
      </ul>
      {last && (
        <div style={{ margin: "8px 0", padding: 8, background: "#f5f5f5" }}>
          <strong>{hero.name}:</strong> {last.message}
          {last.counter_price != null && <em> ({last.counter_price} 골드)</em>}
        </div>
      )}
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <label>제시 가격:&nbsp;
          <input type="number" value={price} onChange={(e) => setPrice(Math.max(0, Number(e.target.value)))} />
        </label>
        <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 100))} disabled={busy}>−100</button>
        <button className="btn" onClick={() => setPrice((p) => p + 100)} disabled={busy}>+100</button>
      </div>
      <textarea rows={2} style={{ width: "100%", marginTop: 8 }} value={text}
                onChange={(e) => setText(e.target.value)} placeholder="용사에게 한마디 (선택)" />
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="btn" disabled={busy} onClick={send}>{last ? "재제안" : "제안"}</button>
        {last?.counter_price != null && (
          <button className="btn" disabled={busy} onClick={accept}>{last.counter_price} 골드에 수락</button>
        )}
        <button className="btn" disabled={busy} onClick={reject}>거절하고 돌아가기</button>
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
