import { useState } from "react";
import { api } from "../api";
import type { Hero, Weapon, Material, NegotiateResponse, EnhanceResult } from "../types";
import { PatienceGauge } from "./PatienceGauge";

interface ChatMsg { role: "player" | "hero"; message: string; price?: number | null }

interface Props {
  hero: Hero;
  weapon: Weapon;
  inventory: Material[];
  onDone: () => void;
}

export function EnhanceNegotiation({ hero, weapon, inventory, onDone }: Props) {
  const [stage, setStage] = useState<"pick_materials" | "negotiate">("pick_materials");
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [price, setPrice] = useState<number>(500);
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [enhanceResult, setEnhanceResult] = useState<EnhanceResult | null>(null);

  const matSum = Object.entries(picks).reduce((s, [k, v]) => {
    const mat = inventory.find((m) => m.material_id === Number(k));
    return s + (mat?.base_price ?? 0) * v;
  }, 0);
  const marketEst = Math.max(1, Math.floor(matSum * 1.5));
  const askCap = Math.min(hero.gold, marketEst * 3);

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

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.enhanceSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const enterNegotiate = () => {
    if (Object.keys(picks).length === 0) { setErr("재료를 1개 이상 선택하세요"); return; }
    setErr(null);
    setPrice(marketEst);  // 추천 시세를 초기 제시가로
    setStage("negotiate");
  };

  const negotiationStarted = msgs.length > 0;

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const selected = Object.entries(picks).map(([k, v]) => ({ material_id: Number(k), qty: v }));
      const isFirst = last === null;
      const res = await api.enhanceNegotiate(
        price, text, last?.negotiation_id ?? null,
        isFirst ? selected : null,
      );
      setMsgs((m) => [...m,
        { role: "player", message: text, price },
        { role: "hero", message: res.message, price: res.counter_price }]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const finalize = async () => {
    if (!last) return;
    setBusy(true);
    try {
      const res = await api.enhanceFinalize(last.negotiation_id);
      setEnhanceResult(res.result);
    }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try {
      const res = await api.enhancePlayerAccept(last.negotiation_id);
      setEnhanceResult(res.result);
    }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const reject = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.enhancePlayerReject(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (stage === "pick_materials") {
    return (
      <div>
        <h2>강화 의뢰 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})</h2>
        <p>용사의 무기: <strong>{weapon.name}</strong> <small>· {weapon.attribute ?? "무"}</small> (예리도 {weapon.sharpness}, 희귀도 {weapon.rarity}, 강화 {weapon.enhancement_level ?? 0}회)</p>
        <p>호감도 <strong>{hero.affinity >= 0 ? "+" : ""}{hero.affinity}</strong> · 보유 금화 {hero.gold}</p>

        <h4>강화에 투입할 재료 선택</h4>
        {inventory.filter((m) => m.qty > 0).map((m) => (
          <div key={m.material_id} className="material-row">
            <span style={{ flex: 1 }}>{m.name} <small>({m.category} · {m.attribute ?? "무"}, 시세 {m.base_price}골드, 보유 {m.qty})</small></span>
            <button className="btn" onClick={() => change(m.material_id, -1)}>−</button>
            <span style={{ width: 24, textAlign: "center" }}>{picks[m.material_id] ?? 0}</span>
            <button className="btn" onClick={() => change(m.material_id, +1)}>+</button>
          </div>
        ))}

        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="btn" onClick={enterNegotiate} disabled={busy}>가격 협상 시작</button>
          <button className="btn" onClick={skip} disabled={busy}>강화 안 함 (다음 단계로)</button>
        </div>
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    );
  }

  if (enhanceResult) {
    const r = enhanceResult;
    const arrow = (b: number, a: number) => {
      const d = a - b;
      const sign = d > 0 ? "+" : "";
      const color = d > 0 ? "#1a7f37" : d < 0 ? "#cf222e" : "#666";
      return <span style={{ color }}>{b} → <strong>{a}</strong> ({sign}{d})</span>;
    };
    return (
      <div>
        <h2>✨ 강화 완료 — {r.weapon_name}</h2>
        <div style={{ background: "#f8f4ee", padding: 16, borderRadius: 8, margin: "12px 0", maxWidth: 360 }}>
          <p style={{ margin: "4px 0" }}>예리도: {arrow(r.before.sharpness, r.after.sharpness)}</p>
          <p style={{ margin: "4px 0" }}>희귀도: {arrow(r.before.rarity, r.after.rarity)}</p>
          <p style={{ margin: "4px 0" }}>강화 횟수: {r.before.enhancement_level}회 → <strong>{r.after.enhancement_level}회</strong></p>
        </div>
        <button className="btn" onClick={onDone}>다음으로</button>
      </div>
    );
  }

  return (
    <div>
      <h2>강화 비용 협상 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""}</h2>
      <PatienceGauge current={last?.patience_current} start={last?.patience_start} label={`${hero.name}의 인내심`} />
      <p>강화 대상: <strong>{weapon.name}</strong> <small>· {weapon.attribute ?? "무"}</small> (예리도 {weapon.sharpness}, 희귀도 {weapon.rarity})</p>
      <p>투입 재료: {Object.entries(picks).map(([k, v]) => {
        const mat = inventory.find((m) => m.material_id === Number(k));
        return `${mat?.name ?? "?"}×${v}`;
      }).join(", ")} <small>(재료 시세 합 {matSum} 골드)</small></p>
      <p><strong>추천 강화비: ~{marketEst} 골드</strong> <small>(재료 시세 × 1.5 — 대장장이 수공비 포함)</small></p>
      <p><small>용사 보유 금화: {hero.gold} / 호감도 {hero.affinity} · 최대 제시가 {askCap} 골드</small></p>

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "player" ? "player" : "hero"}`}>
            <strong>{m.role === "player" ? "나" : hero.name}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>용사가 수락했습니다. 강화를 진행하시겠습니까?</p>
          <button className="btn" onClick={finalize} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>강화 의뢰가 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          {last?.decision === "counter" && last.counter_price != null && (
            <div style={{ marginBottom: 12, padding: 8, background: "#fff4d6", borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px" }}>용사가 <strong>{last.counter_price} 골드</strong>를 역제안했습니다.</p>
              <button className="btn" onClick={acceptCounter} disabled={busy} style={{ marginRight: 8 }}>
                {last.counter_price} 골드에 수락
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <label>강화 비용:&nbsp;
              <input type="number" value={price} max={askCap}
                     onChange={(e) => setPrice(Math.min(askCap, Math.max(0, Number(e.target.value))))} />
            </label>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 500))} disabled={busy}>−500</button>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 100))} disabled={busy}>−100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(askCap, p + 100))} disabled={busy}>+100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(askCap, p + 500))} disabled={busy}>+500</button>
            <small>최대 {askCap} 골드 (시세 ×3 / 용사 보유 중 낮은 값)</small>
          </div>
          {negotiationStarted && (
            <textarea rows={2} style={{ width: "100%", marginTop: 8 }} value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="용사에게 한마디 (선택사항)" />
          )}
          <button className="btn" onClick={send} disabled={busy} style={{ marginTop: 8 }}>
            {busy ? "..." : negotiationStarted ? "재제안" : "제안하기"}
          </button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
