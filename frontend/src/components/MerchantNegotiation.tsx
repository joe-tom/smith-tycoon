import { useState, useEffect } from "react";
import { api } from "../api";
import type { MerchantToday, NegotiateResponse } from "../types";
import { PatienceGauge } from "./PatienceGauge";

interface ChatMsg { role: "player" | "merchant"; message: string; price?: number | null }

interface SelectedMaterial {
  material_id: number;
  qty: number;
  name: string;
  asking_price: number;
}

export function MerchantNegotiation({
  merchant, selectedMaterials, selectWeapon, selectedTotal, onDone,
}: {
  merchant: MerchantToday;
  selectedMaterials: SelectedMaterial[];
  selectWeapon: boolean;
  selectedTotal: number;
  onDone: () => void;
}) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "merchant", message: `이 묶음 ${selectedTotal} 골드는 어떻소?`, price: selectedTotal },
  ]);
  const [price, setPrice] = useState<number>(Math.max(1, Math.floor(selectedTotal * 0.7)));
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [playerGold, setPlayerGold] = useState<number>(0);

  useEffect(() => {
    api.getState().then((s) => setPlayerGold(s.player?.gold ?? 0)).catch(() => {});
  }, []);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const isFirst = last === null;
      const res = await api.merchantNegotiate(
        merchant.id, price, text, last?.negotiation_id ?? null,
        isFirst ? selectedMaterials.map((m) => ({ material_id: m.material_id, qty: m.qty })) : null,
        isFirst ? selectWeapon : false,
      );
      setMsgs((m) => [...m,
        { role: "player", message: text, price },
        { role: "merchant", message: res.message, price: res.counter_price }]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const finalize = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantFinalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantPlayerAccept(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const reject = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantPlayerReject(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>상인 협상</h2>
      <PatienceGauge current={last?.patience_current} start={last?.patience_start} label="상인의 인내심" />
      <p>협상 묶음 (선택 합계 시세: <strong>{selectedTotal} 골드</strong>):</p>
      <ul>
        {selectedMaterials.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} — {m.asking_price} 골드</li>
        ))}
        {selectWeapon && merchant.weapon && (
          <li>{merchant.weapon.name} ({merchant.weapon.type}) — {merchant.weapon.asking_price} 골드</li>
        )}
      </ul>

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "player" ? "player" : "hero"}`}>
            <strong>{m.role === "player" ? "나" : "상인"}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>상인이 수락했습니다.</p>
          <button className="btn" onClick={finalize} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>협상이 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          {last?.decision === "counter" && last.counter_price != null && (
            <div style={{ marginBottom: 12, padding: 8, background: "#fff4d6", borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px" }}>상인이 <strong>{last.counter_price} 골드</strong>를 역제안했습니다.</p>
              <button className="btn" onClick={acceptCounter}
                      disabled={busy || last.counter_price > playerGold} style={{ marginRight: 8 }}
                      title={last.counter_price > playerGold ? "보유 금화 부족" : ""}>
                {last.counter_price} 골드에 수락
                {last.counter_price > playerGold && " (금화 부족)"}
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <label>제시 가격:&nbsp;
              <input
                type="number"
                value={price}
                max={playerGold}
                onChange={(e) => setPrice(Math.min(Math.max(0, Number(e.target.value)), playerGold))}
              />
            </label>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 500))} disabled={busy}>−500</button>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 100))} disabled={busy}>−100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(playerGold, p + 100))} disabled={busy}>+100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(playerGold, p + 500))} disabled={busy}>+500</button>
            <small>최대 {playerGold} 골드</small>
          </div>
          <textarea rows={2} style={{ width: "100%", marginTop: 8 }} value={text} onChange={(e) => setText(e.target.value)}
                    placeholder="상인에게 한마디 (선택사항)" />
          <button className="btn" onClick={send} disabled={busy || price > playerGold}>
            {busy ? "..." : "제안하기"}
          </button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
