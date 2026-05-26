import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";
import { SidePanel } from "./components/SidePanel";
import { DayRouter } from "./components/DayRouter";
import { Login } from "./components/Login";
import { getNickname } from "./auth";

export default function App() {
  const [nick, setNick] = useState<string | null>(getNickname());
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());
  const reset = async () => { await api.resetGame(); await refresh(); };

  useEffect(() => {
    if (nick) refresh().catch(() => setState(null));
  }, [nick]);

  if (!nick) {
    return <Login onDone={() => setNick(getNickname())} />;
  }

  if (!state || !state.player) {
    return (
      <div style={{ padding: 24 }}>
        <p>로딩 중…</p>
      </div>
    );
  }

  return (
    <div className="app">
      <SidePanel state={state} onReset={reset} />
      <div className="main">
        <DayRouter state={state} refresh={refresh} onReset={reset} />
      </div>
    </div>
  );
}
