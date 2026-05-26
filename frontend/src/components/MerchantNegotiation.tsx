import { useState } from "react";
import { api } from "../api";
import type { MerchantToday, NegotiateResponse } from "../types";

interface ChatMsg { role: "player" | "merchant"; message: string; price?: number | null }

export function MerchantNegotiation({ merchant, onDone }: { merchant: MerchantToday; onDone: () => void }) {
  const baseTotal = merchant.materials.reduce((s, m) => s + m.asking_price, 0)
                  + (merchant.weapon?.asking_price ?? 0);

  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "merchant", message: `이 묶음 ${baseTotal} 골드는 어떻소?`, price: baseTotal },
  ]);
  const [price, setPrice] = useState<number>(Math.floor(baseTotal * 0.7));
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.merchantNegotiate(merchant.id, price, text, last?.negotiation_id ?? null);
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
      <p>묶음 시세: {baseTotal} 골드</p>

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
              <button className="btn" onClick={acceptCounter} disabled={busy} style={{ marginRight: 8 }}>
                {last.counter_price} 골드에 수락
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div>
            <label>제시 가격:
              <input type="number" value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            </label>
          </div>
          <textarea rows={3} style={{ width: "100%" }} value={text} onChange={(e) => setText(e.target.value)} placeholder="상인에게 한마디" />
          <button className="btn" onClick={send} disabled={busy || !text.trim()}>{busy ? "..." : "제안하기"}</button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
