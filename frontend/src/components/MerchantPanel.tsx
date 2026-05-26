import { useState } from "react";
import { api } from "../api";
import type { MerchantToday } from "../types";
import { MerchantNegotiation } from "./MerchantNegotiation";

export function MerchantPanel({ merchant, onDone }: { merchant: MerchantToday; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);

  const [qtyByMid, setQtyByMid] = useState<Record<number, number>>({});
  const [pickWeapon, setPickWeapon] = useState(false);

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.merchantSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const change = (mid: number, available: number, delta: number) => {
    setQtyByMid((p) => {
      const cur = (p[mid] ?? 0) + delta;
      const next = Math.max(0, Math.min(available, cur));
      const out = { ...p };
      if (next === 0) delete out[mid]; else out[mid] = next;
      return out;
    });
  };

  const selectedRows = merchant.materials
    .map((m) => {
      const picked_qty = qtyByMid[m.material_id] ?? 0;
      const price = picked_qty > 0 ? Math.floor(m.asking_price * picked_qty / m.qty) : 0;
      return { ...m, picked_qty, price };
    })
    .filter((m) => m.picked_qty > 0);
  const matsTotal = selectedRows.reduce((s, m) => s + m.price, 0);
  const weaponTotal = pickWeapon && merchant.weapon ? merchant.weapon.asking_price : 0;
  const selectedTotal = matsTotal + weaponTotal;
  const hasSelection = selectedRows.length > 0 || pickWeapon;

  if (entering) {
    return (
      <MerchantNegotiation
        merchant={merchant}
        selectedMaterials={selectedRows.map((m) => ({
          material_id: m.material_id, qty: m.picked_qty, name: m.name, asking_price: m.price,
        }))}
        selectWeapon={pickWeapon}
        selectedTotal={selectedTotal}
        onDone={onDone}
      />
    );
  }

  return (
    <div>
      <h2>상인 방문</h2>
      <p>오늘의 매물 (원하는 항목과 수량만 선택해서 협상하세요):</p>

      <h4>재료</h4>
      {merchant.materials.map((m) => {
        const picked = qtyByMid[m.material_id] ?? 0;
        const unit = Math.floor(m.asking_price / m.qty);
        return (
          <div key={m.material_id} className="material-row">
            <span style={{ flex: 1 }}>
              {m.name} <small>({m.category}, 단가 ~{unit}골드, 재고 {m.qty})</small>
            </span>
            <button className="btn" onClick={() => change(m.material_id, m.qty, -1)}>−</button>
            <span style={{ width: 24, textAlign: "center" }}>{picked}</span>
            <button className="btn" onClick={() => change(m.material_id, m.qty, +1)}>+</button>
          </div>
        );
      })}

      {merchant.weapon && (
        <div style={{ marginTop: 12 }}>
          <h4>무기</h4>
          <label>
            <input type="checkbox" checked={pickWeapon} onChange={(e) => setPickWeapon(e.target.checked)} />
            &nbsp;{merchant.weapon.name} ({merchant.weapon.type}, 예리도 {merchant.weapon.sharpness}, 희귀도 {merchant.weapon.rarity}) — {merchant.weapon.asking_price} 골드
          </label>
        </div>
      )}

      <p style={{ marginTop: 16 }}>
        <strong>선택 합계: {selectedTotal} 골드</strong>
        {selectedRows.length > 0 && (
          <small style={{ marginLeft: 8 }}>
            ({selectedRows.map((m) => `${m.name}×${m.picked_qty}`).join(", ")}
            {pickWeapon && merchant.weapon ? `, ${merchant.weapon.name}` : ""})
          </small>
        )}
      </p>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={() => setEntering(true)} disabled={busy || !hasSelection}>
          협상하기
        </button>
        <button className="btn" onClick={skip} disabled={busy}>건너뛰기</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
