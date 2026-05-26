import { useState } from "react";
import { api } from "../api";
import type { Material } from "../types";

const WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"];

export function ForgePanel({ inventory, onDone }: { inventory: Material[]; onDone: () => void }) {
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [type, setType] = useState(WEAPON_TYPES[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
      await api.forge(type, materials);
      onDone();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.forgeSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>제작</h2>
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
        <button className="btn" onClick={skip} disabled={busy}>건너뛰기</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
