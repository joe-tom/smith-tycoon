import type { StateResponse } from "../types";

export function SidePanel({ state, onReset }: { state: StateResponse; onReset: () => void }) {
  if (!state.player) return null;
  return (
    <div className="side">
      <h3>플레이어</h3>
      <p>일차: <strong>Day {state.player.current_day} / 5</strong></p>
      <p>금화: {state.player.gold}</p>
      <p>평판: {state.player.reputation}</p>
      <p>Phase: <code>{state.player.current_phase}</code></p>

      <h4>인벤토리</h4>
      <ul>
        {state.inventory.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} <small>({m.category})</small></li>
        ))}
      </ul>

      <h4>진열장</h4>
      {state.weapons.length === 0 ? <p><em>(없음)</em></p> : (
        <ul>
          {state.weapons.map((w) => (
            <li key={w.id}>
              {w.name} ({w.type})
              {w.market_price != null && <small> — 시세 {w.market_price}골드</small>}
            </li>
          ))}
        </ul>
      )}

      <button className="btn" onClick={onReset} style={{ marginTop: 16 }}>새 게임</button>
    </div>
  );
}
