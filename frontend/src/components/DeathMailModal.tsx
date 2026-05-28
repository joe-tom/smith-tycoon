import { useState } from "react";
import type { DeathMail } from "../types";
import { api } from "../api";

export function DeathMailModal({
  mails, onAllAcked,
}: { mails: DeathMail[]; onAllAcked: () => void }) {
  const [i, setI] = useState(0);
  if (mails.length === 0 || i >= mails.length) return null;
  const m = mails[i];
  const ack = async () => {
    await api.mailAck(m.id);
    if (i + 1 >= mails.length) onAllAcked();
    else setI(i + 1);
  };
  return (
    <div className="modal-backdrop" style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div className="modal death-mail" style={{
        background: "white", padding: 24, borderRadius: 8, maxWidth: 480,
      }}>
        <h3>비보(悲報)</h3>
        <p>{m.weapon_snapshot.name ?? "맨손으로"} 떠난 용사가 돌아오지 못했습니다.</p>
        <p>잡은 몹: {m.outcome.monsters_killed ?? 0}</p>
        <button className="btn" onClick={ack}>알겠다</button>
      </div>
    </div>
  );
}
