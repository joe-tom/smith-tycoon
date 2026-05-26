import { useState } from "react";
import { api } from "../api";

export function GameOver({ onReset }: { onReset: () => void }) {
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try { await api.resetGame(); onReset(); }
    finally { setBusy(false); }
  };
  return (
    <div>
      <h2>5일 운영 종료</h2>
      <p>대장간 5일 운영이 마무리되었습니다. 새 게임을 시작하시겠어요?</p>
      <button className="btn" onClick={reset} disabled={busy}>새 게임</button>
    </div>
  );
}
