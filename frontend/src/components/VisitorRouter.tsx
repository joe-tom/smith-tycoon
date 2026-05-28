import type { StateResponse } from "../types";
import { MerchantPanel } from "./MerchantPanel";
import { HeroVisitorPanel } from "./HeroVisitorPanel";

export function VisitorRouter({ state, refresh }: { state: StateResponse; refresh: () => void }) {
  const v = state.current_visitor;
  if (!v) return <p>방문자 정보를 불러오는 중...</p>;
  const slotKey = `${state.current_visitor_index}-${v.kind}-${v.hero_id ?? v.outcome_id ?? "m"}`;

  if (v.kind === "merchant") {
    if (!v.merchant) return <p>상인 정보를 불러오는 중...</p>;
    return <MerchantPanel key={slotKey} merchant={v.merchant} onDone={refresh} />;
  }
  return <HeroVisitorPanel key={slotKey} state={state} visitor={v} refresh={refresh} />;
}
