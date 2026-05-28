import type { StateResponse } from "../types";
import { api } from "../api";
import { NegotiationChat } from "./NegotiationChat";
import { EnhanceNegotiation } from "./EnhanceNegotiation";
import { MerchantPanel } from "./MerchantPanel";
import { ReturningHeroPanel } from "./ReturningHeroPanel";

export function VisitorRouter({ state, refresh }: { state: StateResponse; refresh: () => void }) {
  const v = state.current_visitor;
  if (!v) return <p>방문자 정보를 불러오는 중...</p>;
  // 슬롯이 바뀌면 내부 state(협상 라운드 등)를 강제로 리셋
  const slotKey = `${state.current_visitor_index}-${v.kind}-${v.hero_id ?? v.outcome_id ?? "m"}`;

  if (v.kind === "returning_hero") {
    return <ReturningHeroPanel key={slotKey} visitor={v} refresh={refresh} />;
  }
  if (v.kind === "merchant") {
    if (!v.merchant) return <p>상인 정보를 불러오는 중...</p>;
    return <MerchantPanel key={slotKey} merchant={v.merchant} onDone={refresh} />;
  }
  const hero = v.hero;
  if (!hero) return <p>용사 정보를 불러오는 중...</p>;
  if (hero.mode === "enhance" && hero.held_weapon) {
    return (
      <EnhanceNegotiation
        key={slotKey}
        hero={hero}
        weapon={hero.held_weapon}
        inventory={state.inventory}
        onDone={refresh}
      />
    );
  }
  if (state.weapons.length === 0) {
    const skip = async () => { await api.visitorSkip(); refresh(); };
    return (
      <div>
        <p>판매할 무기가 없습니다. 다음 방문자로 건너뜁니다. (평판 -1)</p>
        <button className="btn" onClick={skip}>건너뛰기 (평판 -1)</button>
      </div>
    );
  }
  return <NegotiationChat key={slotKey} hero={hero} weapons={state.weapons} onDone={refresh} />;
}
