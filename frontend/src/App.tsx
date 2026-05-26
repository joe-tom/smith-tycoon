import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";
import { SidePanel } from "./components/SidePanel";
import { DayRouter } from "./components/DayRouter";

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());
  const reset = async () => { await api.resetGame(); await refresh(); };

  useEffect(() => { refresh().catch(() => setState(null)); }, []);

  if (!state || !state.player) {
    return (
      <div style={{ padding: 24 }}>
        <button className="btn" onClick={reset}>새 게임 시작</button>
      </div>
    );
  }

  return (
    <div className="app">
      <SidePanel state={state} onReset={reset} />
      <div className="main">
        <DayRouter state={state} refresh={refresh} />
      </div>
    </div>
  );
}
