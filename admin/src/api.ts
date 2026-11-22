export type AgentConfig = {
  agent_name: string;
  greeting: string;
  voice: string;
  instructions: string;
  enabled_tools: string[];
};

export type ToolInfo = { name: string; description: string };
export type Voice = { id: string; name: string };

type ErrorBody = { detail?: string | { loc: (string | number)[]; msg: string }[] };

function formatError(body: ErrorBody | null): string | null {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ");
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ErrorBody | null;
    throw new Error(formatError(body) ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const getConfig = () => request<AgentConfig>("/config");
export const getTools = () => request<ToolInfo[]>("/tools");
export const getVoices = () => request<Voice[]>("/voices");
export const saveConfig = (config: AgentConfig) =>
  request<AgentConfig>("/config", { method: "PUT", body: JSON.stringify(config) });
