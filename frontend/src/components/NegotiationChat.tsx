import { useState } from "react";
import { api } from "../api";
import type { Hero, Weapon, NegotiateResponse } from "../types";

interface ChatMsg { role: "player" | "hero"; message: string; price?: number | null }

export function NegotiationChat({ hero, weapons, onDone }: { hero: Hero; weapons: Weapon[]; onDone: () => void }) {
  const [selectedId, setSelectedId] = useState<number>(weapons[0].id);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [price, setPrice] = useState<number>(500);
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const weapon = weapons.find((w) => w.id === selectedId) ?? weapons[0];
  const negotiationStarted = msgs.length > 0;
  const [showFormula, setShowFormula] = useState(false);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.negotiate(weapon.id, price, text, last?.negotiation_id ?? null);
      setMsgs((m) => [
        ...m,
        { role: "player", message: text, price },
        { role: "hero", message: res.message, price: res.counter_price },
      ]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const accept = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.finalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.playerAccept(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const reject = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.playerReject(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const skipWithoutSelling = async () => {
    setBusy(true); setErr(null);
    try { await api.negotiateSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>
        협상 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})
        {hero.visit_count != null && hero.visit_count > 1 && (
          <small style={{ marginLeft: 8, color: "#a06" }}>
            · {hero.visit_count}번째 방문 🔁
          </small>
        )}
        {hero.visit_count === 1 && (
          <small style={{ marginLeft: 8, color: "#888" }}>· 첫 방문</small>
        )}
      </h2>

      <div style={{ marginBottom: 8 }}>
        <label>판매할 무기:&nbsp;
          <select value={selectedId} onChange={(e) => setSelectedId(Number(e.target.value))} disabled={negotiationStarted}>
            {weapons.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.type}, 희귀도 {w.rarity}, 예리도 {w.sharpness}{w.market_price != null ? `, 시세 ${w.market_price}` : ""})
              </option>
            ))}
          </select>
        </label>
        {negotiationStarted && <small style={{ marginLeft: 8 }}>(협상 시작 후엔 변경 불가)</small>}
      </div>

      {weapon.market_price != null && (
        <div style={{ margin: "4px 0" }}>
          <p style={{ margin: 0 }}>
            현재 무기 시세: <strong>{weapon.market_price} 골드</strong>
            <button
              type="button"
              className="btn"
              style={{ marginLeft: 8, padding: "2px 8px", fontSize: "0.85em" }}
              onClick={() => setShowFormula((v) => !v)}
            >
              {showFormula ? "공식 숨기기" : "ⓘ 공식 보기"}
            </button>
          </p>
          {showFormula && (
            <pre style={{
              margin: "6px 0", padding: 8, background: "#f3f3f3",
              borderRadius: 6, fontSize: "0.85em", whiteSpace: "pre-wrap",
            }}>
{`시세 = 재료값 × (1 + 희귀도/100) × (1 + 예리도/200)
재료값 = Σ (카테고리 단가 × 수량)
  카테고리 단가: 일반 50, 이상한 5, 특수 250, 전설 1500

이 무기: 희귀도 ${weapon.rarity}, 예리도 ${weapon.sharpness}
계산 결과: ${weapon.market_price} 골드 (정수 내림)
* LLM이 협상 응답할 때 이 숫자를 시세로 인용합니다.`}
            </pre>
          )}
        </div>
      )}

      <p><small>
        용사 기분: {hero.mood} / 성격: {hero.personality_tags.join(", ")} / 보유 금화: {hero.gold} / 근력 {hero.str}·마력 {hero.mag}
        {" / "}호감도 <strong style={{
          color: hero.affinity >= 20 ? "#0a6" : hero.affinity <= -20 ? "#a30" : "#666"
        }}>{hero.affinity >= 0 ? "+" : ""}{hero.affinity}</strong>
      </small></p>

      {hero.preferences && (
        <div style={{
          marginBottom: 8, padding: 8, background: "#eef6ff",
          borderRadius: 6, fontSize: "0.9em",
        }}>
          <div>
            <strong>선호 무기:</strong>{" "}
            {hero.preferences.types.length > 0
              ? hero.preferences.types.map((t) => (
                  <span key={t} style={{
                    display: "inline-block", marginRight: 6, padding: "2px 8px",
                    background: weapons.find((w) => w.id === selectedId)?.type === t ? "#a5e0a5" : "#fff",
                    border: "1px solid #99c", borderRadius: 4,
                  }}>{t}</span>
                ))
              : <em>특별한 선호 없음</em>}
          </div>
          <div style={{ marginTop: 4 }}><small>{hero.preferences.hint} · {hero.preferences.stat_hint}</small></div>
        </div>
      )}

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <strong>{m.role === "player" ? "나" : hero.name}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>용사가 수락했습니다. 거래를 확정하시겠습니까?</p>
          <button className="btn" onClick={accept} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>거래가 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          {last?.decision === "counter" && last.counter_price != null && (
            <div style={{ marginBottom: 12, padding: 8, background: "#fff4d6", borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px" }}>
                용사가 <strong>{last.counter_price} 골드</strong>를 역제안했습니다.
              </p>
              <button className="btn" onClick={acceptCounter} disabled={busy} style={{ marginRight: 8 }}>
                {last.counter_price} 골드에 수락
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <label>제시 가격:&nbsp;
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
            <textarea rows={2} style={{ width: "100%", marginTop: 8 }} value={text} onChange={(e) => setText(e.target.value)}
                      placeholder="용사에게 한마디 (선택사항)" />
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn" onClick={send} disabled={busy}>
              {busy ? "..." : negotiationStarted ? "재제안" : "제안하기"}
            </button>
            {!negotiationStarted && (
              <button className="btn" onClick={skipWithoutSelling} disabled={busy}
                      title="용사 무시·다음 단계로. 평판 -1">
                팔지 않고 건너뛰기 (평판 -1)
              </button>
            )}
          </div>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
