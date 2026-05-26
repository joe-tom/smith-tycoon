import type { StateResponse } from "../types";
import { ForgePanel } from "./ForgePanel";
import { NegotiationChat } from "./NegotiationChat";
import { BattleResult } from "./BattleResult";
import { MerchantPanel } from "./MerchantPanel";
import { DaySummary } from "./DaySummary";
import { GameOver } from "./GameOver";

const NEGOTIATE_PHASES = new Set(["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]);
const BATTLE_PHASES = new Set(["hero1_battle", "hero2_battle", "hero3_battle"]);
const FORGE_PHASES = new Set(["forge_open", "forge_open_2"]);

export function DayRouter({ state, refresh, onReset }: { state: StateResponse; refresh: () => void; onReset: () => void }) {
  if (!state.player) return null;
  const phase = state.player.current_phase;

  if (FORGE_PHASES.has(phase)) {
    return <ForgePanel inventory={state.inventory} onDone={refresh} />;
  }
  if (NEGOTIATE_PHASES.has(phase)) {
    if (!state.hero || state.weapons.length === 0) {
      return <p>판매할 무기가 없습니다. (제작을 건너뛰셨다면 이번 협상은 무기 없이 진행됩니다.)</p>;
    }
    return <NegotiationChat hero={state.hero} weapon={state.weapons[0]} onDone={refresh} />;
  }
  if (BATTLE_PHASES.has(phase)) {
    return <BattleResult onDone={refresh} />;
  }
  if (phase === "merchant_negotiate") {
    if (!state.merchant) return <p>상인 정보를 불러오는 중...</p>;
    return <MerchantPanel merchant={state.merchant} onDone={refresh} />;
  }
  if (phase === "day_summary") {
    return <DaySummary onDone={refresh} />;
  }
  if (phase === "game_over") {
    return <GameOver onReset={onReset} />;
  }
  return <p>알 수 없는 phase: {phase}</p>;
}
