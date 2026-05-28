export type MissionKind = "tax" | "league_chief";
export type MissionPhase = "warning" | "collect" | "challenge" | "praise";

export const MISSION_TITLE: Record<MissionKind, string> = {
  tax: "세금 징수관",
  league_chief: "한자 상인조합장",
};

export const MISSION_MESSAGE: Record<MissionKind, Partial<Record<MissionPhase, string>>> = {
  tax: {
    warning: "이 마을은 세금을 매기지! 열흘 뒤 다시 와서 1000골드 받아간다. 그때 안 내면 알지?",
    collect: "오늘이 그날이다. 1000골드 내놔라. 못 내면 끝장이다.",
  },
  league_chief: {
    challenge: "한자 상인조합장이다. 너 같은 무명 대장장이가 우리 도시에서 장사하려면 평판 50은 찍어야지. 3일 안에 못 보이면 가게 닫게 만들 거다.",
    praise: "고생했다, 대장장이. 인정해주마. 잘 해 봐라.",
  },
};

export interface MissionAction {
  label: string;
  action: "pay" | "ack" | "skip";
  variantDanger?: boolean;
}

export function actionsFor(
  kind: MissionKind, phase: MissionPhase, amount: number,
): MissionAction[] {
  if (kind === "tax" && phase === "warning") {
    return [{ label: "알겠다", action: "ack" }];
  }
  if (kind === "tax" && phase === "collect") {
    return [
      { label: `${amount}골드 상납하기`, action: "pay" },
      { label: "도망간다 (게임오버)", action: "skip", variantDanger: true },
    ];
  }
  return [{ label: "알겠다", action: "ack" }];
}
