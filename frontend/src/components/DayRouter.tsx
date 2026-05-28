import type { StateResponse } from "../types";
import { ForgePanel } from "./ForgePanel";
import { VisitorRouter } from "./VisitorRouter";
import { DaySummary } from "./DaySummary";
import { GameOver } from "./GameOver";

export function DayRouter({ state, refresh, onReset }: { state: StateResponse; refresh: () => void; onReset: () => void }) {
  if (!state.player) return null;
  const phase = state.player.current_phase;

  if (phase === "forge_open") {
    return <ForgePanel inventory={state.inventory} onDone={refresh} />;
  }
  if (phase === "visitor") {
    return <VisitorRouter state={state} refresh={refresh} />;
  }
  if (phase === "day_summary") {
    return <DaySummary onDone={refresh} />;
  }
  if (phase === "game_over") {
    return <GameOver state={state} onReset={onReset} />;
  }
  return <p>알 수 없는 phase: {phase}</p>;
}
