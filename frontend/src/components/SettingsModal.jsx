import { useState } from "react";
import { api } from "../api.js";
import Modal from "./Modal.jsx";

const PROVIDERS = [
  { id: "anthropic", label: "Anthropic (Claude)", keyHint: "sk-ant-…" },
  { id: "openai", label: "OpenAI", keyHint: "sk-…" },
  { id: "gemini", label: "Google Gemini", keyHint: "AIza…" },
  { id: "groq", label: "Groq", keyHint: "gsk_…" },
  { id: "custom", label: "Other (OpenAI-compatible)", keyHint: "API key" },
];

const TIERS = [
  { id: "jnr", label: "Small edits", sub: "colours, text, one element. Fast and cheap." },
  { id: "snr", label: "Bigger edits", sub: "new sections, moving things around" },
  { id: "architect", label: "Full builds", sub: "first build and redesigns. Your best model." },
];

export default function SettingsModal({ user, defaults, onClose, onSaved }) {
  const saved = user.llm;
  const [provider, setProvider] = useState(saved?.provider || "anthropic");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(saved?.base_url || "");
  const [models, setModels] = useState(saved?.models || {});
  const [available, setAvailable] = useState([]);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  // A stored key is reused (never shown again) as long as the provider is unchanged.
  const hasStoredKey = saved?.has_key && saved.provider === provider;
  const tierDefaults = defaults?.[provider] || {};
  const form = () => ({ provider, api_key: apiKey.trim() || undefined, base_url: baseUrl, models });

  const changeProvider = (id) => {
    setProvider(id);
    setModels(id === saved?.provider ? saved.models : {});
    setAvailable([]);
    setStatus(null);
  };

  const run = async (fn) => {
    setBusy(true);
    setStatus(null);
    try {
      await fn();
    } catch (e) {
      setStatus({ error: true, text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const loadModels = () =>
    run(async () => {
      const { models: ids } = await api.listModels(form());
      setAvailable(ids);
      setStatus({ text: `Key works. ${ids.length} models available.` });
    });

  const save = () =>
    run(async () => {
      const { user: updated } = await api.saveLlm(form());
      onSaved(updated);
      onClose();
    });

  const reset = () =>
    run(async () => {
      const { user: updated } = await api.clearLlm();
      onSaved(updated);
      onClose();
    });

  return (
    <Modal title="AI model & API key" onClose={onClose}>
      <p className="modal-sub">
        Your sites are written with your own key. It's stored encrypted on the server and never sent back to the browser.
      </p>

      <label className="field">
        <span>Provider</span>
        <select value={provider} onChange={(e) => changeProvider(e.target.value)}>
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </label>

      {provider === "custom" && (
        <label className="field">
          <span>Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://openrouter.ai/api/v1" />
        </label>
      )}

      <label className="field">
        <span>API key</span>
        <div className="field-row">
          <input
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={hasStoredKey ? `Saved key ${saved.key_hint || ""} (leave blank to keep)` : PROVIDERS.find((p) => p.id === provider).keyHint}
          />
          <button className="ghost" onClick={loadModels} disabled={busy || (!apiKey.trim() && !hasStoredKey)}>
            Test & load models
          </button>
        </div>
      </label>

      <div className="tiers">
        {TIERS.map((t) => (
          <label className="field" key={t.id}>
            <span>
              {t.label} <em>{t.sub}</em>
            </span>
            <input
              list="model-options"
              value={models[t.id] || ""}
              onChange={(e) => setModels((m) => ({ ...m, [t.id]: e.target.value }))}
              placeholder={tierDefaults[t.id] ? `Default: ${tierDefaults[t.id]}` : "model id"}
            />
          </label>
        ))}
        <datalist id="model-options">
          {available.map((id) => (
            <option key={id} value={id} />
          ))}
        </datalist>
      </div>

      {status && <div className={status.error ? "alert" : "note"}>{status.text}</div>}

      <div className="modal-actions">
        {saved && (
          <button className="ghost" onClick={reset} disabled={busy}>Use server default</button>
        )}
        <span className="spacer" />
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || (!apiKey.trim() && !hasStoredKey)}>Save</button>
      </div>
    </Modal>
  );
}
