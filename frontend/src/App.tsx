import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());

  useEffect(() => { refresh().catch(() => setState(null)); }, []);

  if (!state) {
    return (
      <div style={{ padding: 24 }}>
        <button className="btn" onClick={async () => { await api.resetGame(); await refresh(); }}>
          새 게임 시작
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="side">
        <h3>플레이어</h3>
        <p>금화: {state.player.gold}</p>
        <p>평판: {state.player.reputation}</p>
        <p>Phase: {state.player.current_phase}</p>
        <button className="btn" onClick={async () => { await api.resetGame(); await refresh(); }}>
          새 게임
        </button>
      </div>
      <div className="main">
        <pre>{JSON.stringify(state, null, 2)}</pre>
      </div>
    </div>
  );
}
