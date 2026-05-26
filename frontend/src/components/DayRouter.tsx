import type { StateResponse } from "../types";
import { ForgePanel } from "./ForgePanel";
import { NegotiationChat } from "./NegotiationChat";
import { BattleResult } from "./BattleResult";

export function DayRouter({ state, refresh }: { state: StateResponse; refresh: () => void }) {
  const phase = state.player.current_phase;
  if (phase === "forge_open") {
    return <ForgePanel inventory={state.inventory} onDone={refresh} />;
  }
  if (phase === "hero_negotiate") {
    if (!state.hero || state.weapons.length === 0) {
      return <p>준비 안 됨 (용사 또는 무기 없음).</p>;
    }
    return <NegotiationChat hero={state.hero} weapon={state.weapons[0]} onDone={refresh} />;
  }
  if (phase === "hero_battle") {
    return <BattleResult onDone={refresh} />;
  }
  return (
    <div>
      <h2>슬라이스 종료</h2>
      <p>한 번의 vertical slice가 끝났습니다. 새 게임으로 다시 시작할 수 있습니다.</p>
    </div>
  );
}
