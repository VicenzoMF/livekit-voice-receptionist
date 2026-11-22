import { useEffect, useState } from "react";
import { type AgentConfig, getConfig, getTools, getVoices, saveConfig, type ToolInfo, type Voice } from "./api";

type Status = { kind: "idle" } | { kind: "saving" } | { kind: "saved" } | { kind: "error"; message: string };

const field = { display: "block", marginBottom: "1rem" } as const;

export default function App() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  useEffect(() => {
    Promise.all([getConfig(), getTools(), getVoices()])
      .then(([c, t, v]) => {
        setConfig(c);
        setTools(t);
        setVoices(v);
      })
      .catch((e: Error) => setStatus({ kind: "error", message: e.message }));
  }, []);

  if (!config) {
    return <p>{status.kind === "error" ? `Could not load config: ${status.message}` : "Loading…"}</p>;
  }

  const update = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
    setConfig({ ...config, [key]: value });
    setStatus({ kind: "idle" });
  };

  const toggleTool = (name: string, enabled: boolean) =>
    update("enabled_tools", enabled ? [...config.enabled_tools, name] : config.enabled_tools.filter((t) => t !== name));

  const handleSave = async () => {
    setStatus({ kind: "saving" });
    try {
      setConfig(await saveConfig(config));
      setStatus({ kind: "saved" });
    } catch (e) {
      setStatus({ kind: "error", message: (e as Error).message });
    }
  };

  return (
    <main style={{ maxWidth: 760, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>Receptionist Admin</h1>
      <p>
        Changes apply to the <b>next call</b>. Calls already in progress keep their config.
      </p>

      <fieldset>
        <legend>Persona</legend>
        <label style={field}>
          Name
          <br />
          <input value={config.agent_name} onChange={(e) => update("agent_name", e.target.value)} />
        </label>
        <label style={field}>
          Greeting (spoken word for word when the call starts)
          <br />
          <textarea
            rows={2}
            style={{ width: "100%" }}
            value={config.greeting}
            onChange={(e) => update("greeting", e.target.value)}
          />
        </label>
        <label style={field}>
          Voice
          <br />
          <select value={config.voice} onChange={(e) => update("voice", e.target.value)}>
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Instructions (system prompt)</legend>
        <textarea
          rows={16}
          style={{ width: "100%", fontFamily: "monospace" }}
          value={config.instructions}
          onChange={(e) => update("instructions", e.target.value)}
        />
        <small>Safety rules are added automatically by the platform and can't be removed here.</small>
      </fieldset>

      <fieldset>
        <legend>Tools</legend>
        {tools.map((t) => (
          <label key={t.name} style={field}>
            <input
              type="checkbox"
              checked={config.enabled_tools.includes(t.name)}
              onChange={(e) => toggleTool(t.name, e.target.checked)}
            />{" "}
            <b>{t.name}</b>: {t.description}
          </label>
        ))}
        <small>Transferring to a human and ending the call are always available.</small>
      </fieldset>

      <p>
        <button onClick={handleSave} disabled={status.kind === "saving"}>
          {status.kind === "saving" ? "Saving…" : "Save"}
        </button>{" "}
        {status.kind === "saved" && <span>✅ Saved. The next call will use this config.</span>}
        {status.kind === "error" && <span style={{ color: "crimson" }}>{status.message}</span>}
      </p>
    </main>
  );
}
