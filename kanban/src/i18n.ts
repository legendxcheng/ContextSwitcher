import zh from "./locales/zh-CN.json";
import en from "./locales/en-US.json";

export function tr(key: string): string {
  const locale = document.documentElement.lang;
  const catalog: Record<string, string> = locale.startsWith("en") ? en : zh;
  return catalog[key] ?? (zh as Record<string, string>)[key] ?? key;
}

export function errorText(error: unknown): string {
  const message = String(error).replace(/^Error: /, "");
  const [key, ...details] = message.split(":");
  const translated = tr(key);
  return translated === key ? String(error) : `${translated}${details.length ? `: ${details.join(":")}` : ""}`;
}
