import { useState } from "react";
import type { Hero } from "../types";
import { api } from "../api";

export function ChitchatPanel({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  const [resp, setResp] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const talk = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.chitchat(msg);
      setResp(r.lore_text);
      setMsg("");
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const lore = hero.lore ?? [];

  return (
    <div>
      <h2>잡담 — {hero.name}</h2>
      <p>호감도 {hero.affinity ?? 0}</p>
      <textarea rows={2} style={{ width: "100%" }} value={msg}
                onChange={(e) => setMsg(e.target.value)}
                placeholder="할 말 (비워두면 그냥 듣기)" />
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button className="btn" disabled={busy} onClick={talk}>이야기 듣기</button>
        <button className="btn" onClick={onDone}>돌아가기</button>
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {resp && (
        <div style={{ marginTop: 12, padding: 12, background: "#f0f4f8", borderRadius: 6 }}>
          <p style={{ whiteSpace: "pre-wrap" }}>{resp}</p>
        </div>
      )}
      {lore.length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary>지난 잡담 기록 ({lore.length})</summary>
          <ul style={{ marginTop: 4 }}>
            {lore.slice().reverse().map((l, i) => (
              <li key={i}>[Day {l.day}] {l.text}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
