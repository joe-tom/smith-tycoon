import type { Hero } from "../types";
export function LootNegotiation({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  return <div><p>전리품 협상 (구현 중) — {hero.name}</p><button className="btn" onClick={onDone}>돌아가기</button></div>;
}
