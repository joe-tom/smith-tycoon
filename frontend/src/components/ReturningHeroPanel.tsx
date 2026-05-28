import type { CurrentVisitor } from "../types";
import { api } from "../api";

export function ReturningHeroPanel({
  visitor, refresh,
}: { visitor: CurrentVisitor; refresh: () => void }) {
  const outcome = visitor.outcome;
  const weaponName = visitor.weapon_snapshot?.name ?? "맨손";
  return (
    <div className="returning-hero-panel">
      <h2>돌아온 용사 — {visitor.hero?.name ?? `#${visitor.hero_id}`}</h2>
      <p className="recap" style={{ whiteSpace: "pre-wrap" }}>{visitor.recap ?? "..."}</p>
      <ul>
        <li>맡긴 무기: {weaponName}</li>
        <li>상태: {outcome?.hero ?? "?"}</li>
        <li>잡은 몹: {outcome?.monsters_killed ?? 0}</li>
        <li>무기 상태: {outcome?.weapon ?? "?"}</li>
      </ul>
      <button className="btn" onClick={async () => { await api.visitorReturn(); refresh(); }}>
        보내기
      </button>
    </div>
  );
}
