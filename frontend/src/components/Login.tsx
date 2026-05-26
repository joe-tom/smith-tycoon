import { useState } from "react";
import { setNickname } from "../auth";

export function Login({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setErr("닉네임을 입력하세요");
      return;
    }
    if (trimmed.length > 20) {
      setErr("닉네임은 20자 이내");
      return;
    }
    setNickname(trimmed);
    onDone();
  };

  return (
    <div style={{ padding: 24, maxWidth: 360 }}>
      <h2>대장간 입장</h2>
      <p><small>닉네임으로 세이브가 구분됩니다 (대소문자 구분).</small></p>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        placeholder="닉네임"
        maxLength={20}
        style={{ width: "100%", padding: 8, marginBottom: 8 }}
      />
      <button className="btn" onClick={submit}>입장</button>
      {err && <p style={{ color: "red", marginTop: 8 }}>{err}</p>}
    </div>
  );
}
