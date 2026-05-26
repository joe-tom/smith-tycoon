import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { DaySummaryResponse, DayEvent } from "../types";

const HERO_RESULT_KR: Record<string, string> = { survived: "생존", injured: "부상", died: "사망" };
const WEAPON_RESULT_KR: Record<string, string> = { preserved: "보존", destroyed: "파괴", none: "맨손" };
const DEMON_RESULT_KR: Record<string, string> = { killed: "처치", fled: "도망", survived: "생존" };

function repTag(d: number): string {
  if (d > 0) return ` (평판 +${d})`;
  if (d < 0) return ` (평판 ${d})`;
  return "";
}

function formatEvent(e: DayEvent): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.kind) {
    case "hero_roster": {
      const ids = (p.hero_ids as number[]) ?? [];
      return `오늘의 용사 명단 (#${ids.join(", #")})`;
    }
    case "forge":
      return `제작: ${p.name} (${p.type}, 희귀도 ${p.rarity}, 예리도 ${p.sharpness})`;
    case "sale":
      return `판매: 무기 #${p.weapon_id}를 용사 #${p.hero_id}에게 ${p.price}골드에 판매 (평판 +1)`;
    case "buy": {
      const mats = (p.materials as Array<{ name: string; qty: number }>) ?? [];
      const items = mats.map((m) => `${m.name}×${m.qty}`).join(", ");
      const w = p.weapon as { name?: string } | null | undefined;
      const tail = w?.name ? `${items ? ", " : ""}${w.name}` : "";
      return `구매: ${items}${tail} → ${p.price}골드 지불 (평판 +1)`;
    }
    case "battle": {
      const o = (p.outcomes as Record<string, string>) ?? {};
      const d = (p.demon as { type?: string; difficulty?: number }) ?? {};
      const heroR = HERO_RESULT_KR[o.hero] ?? o.hero;
      const wR = WEAPON_RESULT_KR[o.weapon] ?? o.weapon;
      const dR = DEMON_RESULT_KR[o.demon] ?? o.demon;
      const rep = Number(p.rep_delta ?? 0);
      return `전투: 용사 #${p.hero_id} vs ${d.type} (난이도 ${d.difficulty}) — 용사 ${heroR}, 무기 ${wR}, 마왕군 ${dR}${repTag(rep)}`;
    }
    case "skip": {
      const rep = Number(p.rep_delta ?? -1);
      return `협상 건너뜀 (팔지 않음)${repTag(rep)}`;
    }
    case "reject": {
      const by = String(p.by ?? "");
      const rep = Number(p.rep_delta ?? -1);
      if (by === "hero") return `용사가 협상 거절${repTag(rep)}`;
      if (by === "player") return `플레이어가 협상 결렬${repTag(rep)}`;
      if (by === "player_buy") return `상인 협상 결렬${repTag(rep)}`;
      return `협상 거절${repTag(rep)}`;
    }
    default:
      return `${e.kind}: ${JSON.stringify(p)}`;
  }
}

function repBreakdownText(bd: { battle: number; sale: number; buy: number; skip: number; reject: number }): string {
  const parts: string[] = [];
  if (bd.battle !== 0) parts.push(`전투 ${bd.battle >= 0 ? "+" : ""}${bd.battle}`);
  if (bd.sale > 0) parts.push(`판매 +${bd.sale}`);
  if (bd.buy > 0) parts.push(`구매 +${bd.buy}`);
  if (bd.skip !== 0) parts.push(`협상 건너뜀 ${bd.skip >= 0 ? "+" : ""}${bd.skip}`);
  if (bd.reject !== 0) parts.push(`결렬 ${bd.reject >= 0 ? "+" : ""}${bd.reject}`);
  return parts.length ? parts.join(", ") : "변화 없음";
}

export function DaySummary({ onDone }: { onDone: () => void }) {
  const [data, setData] = useState<DaySummaryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    api.daySummary().then(setData).catch((e) => setErr(e.message));
  }, []);

  const next = async () => {
    setBusy(true);
    try { await api.nextDay(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (err) return <p style={{ color: "red" }}>요약 로드 실패: {err}</p>;
  if (!data) return <p>요약 준비 중...</p>;

  const s = data.summary;
  const bd = (s as unknown as { rep_breakdown: { battle: number; sale: number; buy: number; skip: number; reject: number } }).rep_breakdown
    ?? { battle: 0, sale: 0, buy: 0, skip: 0, reject: 0 };

  return (
    <div>
      <h2>Day {data.day} 요약</h2>
      <ul>
        <li>제작: {s.forges}건</li>
        <li>판매: {s.sales}건</li>
        <li>구매: {s.buys}건</li>
        <li>전투: {s.battles}건 (생존 {s.heroes_survived} / 부상 {s.heroes_injured} / 사망 {s.heroes_died})</li>
        <li>골드 변화: {s.gold_delta >= 0 ? "+" : ""}{s.gold_delta}</li>
        <li>
          평판 변화: <strong>{s.rep_delta >= 0 ? "+" : ""}{s.rep_delta}</strong>
          {" "}<small>({repBreakdownText(bd)})</small>
        </li>
      </ul>

      <h4>이벤트 로그</h4>
      <ul style={{ maxHeight: 240, overflowY: "auto", border: "1px solid #ccc", padding: 8 }}>
        {data.events.map((e) => (
          <li key={e.id}>{formatEvent(e)}</li>
        ))}
      </ul>

      <button className="btn" onClick={next} disabled={busy} style={{ marginTop: 16 }}>
        {busy ? "..." : "다음 날"}
      </button>
    </div>
  );
}
