const KEY = "smith-tycoon:nickname";

export function getNickname(): string | null {
  return localStorage.getItem(KEY);
}

export function setNickname(name: string): void {
  localStorage.setItem(KEY, name);
}

export function clearNickname(): void {
  localStorage.removeItem(KEY);
}
