import { useState } from "react";
import type { CurrentVisitor, Player } from "../types";
import { api } from "../api";
import {
  MISSION_TITLE, MISSION_MESSAGE, actionsFor,
  type MissionKind, type MissionPhase,
} from "../missions";

export function MissionPanel({
  visitor, player, refresh,
}: { visitor: CurrentVisitor; player: Player; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const kind = visitor.mission_kind as MissionKind;
  const phase = (visitor.phase ?? "") as MissionPhase;
  const amount = visitor.amount ?? 0;
  const title = MISSION_TITLE[kind] ?? "미션 NPC";
  const msg = MISSION_MESSAGE[kind]?.[phase] ?? "...";
  const actions = actionsFor(kind, phase, amount);

  const doAction = async (action: "pay" | "ack" | "skip") => {
    setBusy(true); setErr(null);
    try {
      await api.visitorMissionAction(action);
      refresh();
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>{title}</h2>
      <p style={{ whiteSpace: "pre-wrap" }}>{msg}</p>
      {visitor.deadline && visitor.threshold && (
        <p style={{ color: "#a06" }}>
          기한: day {visitor.deadline}까지 · 목표 평판 {visitor.threshold} · 현재 {player.reputation}
        </p>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        {actions.map((a, i) => {
          const disabled = busy || (a.action === "pay" && player.gold < amount);
          return (
            <button key={i} className="btn"
                    style={a.variantDanger ? { color: "crimson" } : undefined}
                    disabled={disabled}
                    onClick={() => doAction(a.action)}>
              {a.label}
            </button>
          );
        })}
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
