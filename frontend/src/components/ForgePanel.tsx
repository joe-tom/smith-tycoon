import { useState } from "react";
import { api } from "../api";
import type { Material, Weapon } from "../types";

const WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"];

export function ForgePanel({ inventory, onDone }: { inventory: Material[]; onDone: () => void }) {
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [type, setType] = useState(WEAPON_TYPES[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [crafted, setCrafted] = useState<Weapon[]>([]);

  const change = (mid: number, delta: number) => {
    setPicks((p) => {
      const cur = (p[mid] ?? 0) + delta;
      const max = inventory.find((m) => m.material_id === mid)?.qty ?? 0;
      const next = Math.max(0, Math.min(max, cur));
      const out = { ...p };
      if (next === 0) delete out[mid]; else out[mid] = next;
      return out;
    });
  };

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const materials = Object.entries(picks).map(([k, v]) => ({ material_id: Number(k), qty: v }));
      if (!materials.length) throw new Error("재료를 1개 이상 선택하세요");
      const w = await api.forge(type, materials);
      setCrafted((c) => [...c, w]);
      setPicks({});
      onDone();   // 부모 state 새로고침 (인벤토리 차감 반영, 진열장 추가)
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const finish = async () => {
    setBusy(true); setErr(null);
    try { await api.forgeSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>제작 (이번 phase에서 무기를 여러 개 만들 수 있습니다)</h2>

      {crafted.length > 0 && (
        <div style={{ marginBottom: 12, padding: 8, background: "#e8f5e9", borderRadius: 6 }}>
          <strong>이번 phase에서 만든 무기 ({crafted.length}개):</strong>
          <ul>
            {crafted.map((w) => (
              <li key={w.id}>{w.name} ({w.type}, 희귀도 {w.rarity}, 예리도 {w.sharpness})</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        무기 종류:
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {WEAPON_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <h4>재료 선택</h4>
      {inventory.map((m) => (
        <div key={m.material_id} className="material-row">
          <span style={{ flex: 1 }}>{m.name} <small>({m.category}, 보유 {m.qty})</small></span>
          <button className="btn" onClick={() => change(m.material_id, -1)}>−</button>
          <span style={{ width: 24, textAlign: "center" }}>{picks[m.material_id] ?? 0}</span>
          <button className="btn" onClick={() => change(m.material_id, +1)}>+</button>
        </div>
      ))}

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button className="btn" onClick={submit} disabled={busy}>{busy ? "제작 중..." : "제작하기"}</button>
        <button className="btn" onClick={finish} disabled={busy}>완료 (다음 단계로)</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
