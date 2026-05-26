export const ENDINGS: Record<string, { title: string; won: boolean; flavor: string }> = {
  surt_killed: {
    title: "🏆 마왕 토벌", won: true,
    flavor: "수르트의 화염이 사그라들었다. 7대 죄악도 함께 무너졌고, 인간 세계는 다시 빛을 찾았다. 당신의 망치는 전설이 되었다.",
  },
  lonely_demon: {
    title: "🌒 외로운 마왕", won: true,
    flavor: "7대 죄악은 모두 무너졌지만 수르트는 끝내 모습을 드러내지 않았다. 100일의 항전은 끝나고, 세상은 마왕 하나만 남긴 채 평온해졌다.",
  },
  forge_burns: {
    title: "🔥 다 쓰러져가는 대장간은 불타야 해", won: false,
    flavor: "100일이 지났지만 수르트는 건재하다. 절반의 죄악을 베어낸 당신의 무기들은 영광스럽지만, 정작 마왕은 닿지 못한 곳에 있다. 대장간 문을 닫을 시간이다.",
  },
  retirement: {
    title: "💤 정년 퇴직", won: false,
    flavor: "100일 동안 망치질만 했다. 단 한 명의 죄악도 무너뜨리지 못했고 수르트는 더더욱. 당신은 평범한 대장장이로 늙어간다.",
  },
  youth_blood: {
    title: "💀 이기지도 못할 거면서 왜 싸웠어?", won: false,
    flavor: "200명의 용사가 당신 손에서 무기를 받았고, 200명이 돌아오지 못했다. 마을 입구마다 곡소리가 그치지 않는다.",
  },
  weapons_broken: {
    title: "⚔️ 우리나라 청년들은 너 때문에 죽은 거야", won: false,
    flavor: "당신이 만든 무기 200개가 마왕군 앞에서 부러졌다. 살아 돌아온 용사들의 손에는 부러진 자루만 남았고, 그들의 분노는 당신을 향한다.",
  },
};
