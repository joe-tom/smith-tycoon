import { useState } from "react";
import { api } from "../api";
import type { MerchantToday } from "../types";
import { MerchantNegotiation } from "./MerchantNegotiation";

export function MerchantPanel({ merchant, onDone }: { merchant: MerchantToday; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.merchantSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (entering) {
    return <MerchantNegotiation merchant={merchant} onDone={onDone} />;
  }

  const total = merchant.materials.reduce((s, m) => s + m.asking_price, 0)
              + (merchant.weapon?.asking_price ?? 0);

  return (
    <div>
      <h2>상인 방문</h2>
      <p>오늘의 묶음 (총 시세 {total} 골드):</p>
      <ul>
        {merchant.materials.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} — {m.asking_price} 골드 <small>({m.category})</small></li>
        ))}
        {merchant.weapon && (
          <li><strong>{merchant.weapon.name}</strong> ({merchant.weapon.type}, 예리도 {merchant.weapon.sharpness}, 희귀도 {merchant.weapon.rarity}) — {merchant.weapon.asking_price} 골드</li>
        )}
      </ul>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={() => setEntering(true)} disabled={busy}>협상하기</button>
        <button className="btn" onClick={skip} disabled={busy}>건너뛰기</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
