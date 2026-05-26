import { useState } from "react";
import { api } from "../api";
import type { Hero, Weapon, Material, NegotiateResponse } from "../types";

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
    try { await api.enhanceFinalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.enhancePlayerAccept(last.negotiation_id); onDone(); }
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
        {inventory.map((m) => (
          <div key={m.material_id} className="material-row">
            <span style={{ flex: 1 }}>{m.name} <small>({m.category} · {m.attribute ?? "무"}, 보유 {m.qty})</small></span>
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

  return (
    <div>
      <h2>강화 비용 협상 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""}</h2>
      <p>강화 대상: <strong>{weapon.name}</strong> <small>· {weapon.attribute ?? "무"}</small> (예리도 {weapon.sharpness}, 희귀도 {weapon.rarity})</p>
      <p>투입 재료: {Object.entries(picks).map(([k, v]) => {
        const mat = inventory.find((m) => m.material_id === Number(k));
        return `${mat?.name ?? "?"}×${v}`;
      }).join(", ")}</p>
      <p><small>용사 보유 금화: {hero.gold} / 호감도 {hero.affinity}</small></p>

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
              <input type="number" value={price} max={hero.gold}
                     onChange={(e) => setPrice(Math.min(hero.gold, Math.max(0, Number(e.target.value))))} />
            </label>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 500))} disabled={busy}>−500</button>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 100))} disabled={busy}>−100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(hero.gold, p + 100))} disabled={busy}>+100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(hero.gold, p + 500))} disabled={busy}>+500</button>
            <small>최대 {hero.gold} 골드 (용사 보유)</small>
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
