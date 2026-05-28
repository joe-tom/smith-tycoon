export function PatienceGauge({
  current, start, label = "인내심",
}: { current?: number | null; start?: number | null; label?: string }) {
  if (current == null || start == null) return null;
  const max = Math.max(start, 1);
  const pct = Math.max(0, Math.min(100, (current / max) * 100));
  const color = current <= 0 ? "#888" : current <= 30 ? "#d33" : pct >= 60 ? "#3a3" : "#da3";
  return (
    <div style={{ margin: "4px 0", fontSize: 13 }}>
      <span>{label}: {current}/{start}</span>
      <div style={{ background: "#eee", height: 6, borderRadius: 3, overflow: "hidden", marginTop: 2 }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%" }} />
      </div>
    </div>
  );
}
