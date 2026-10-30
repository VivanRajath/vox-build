import { useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "./Modal.jsx";
import { CloseIcon } from "./icons.jsx";

const PROVIDERS = [
  { id: "groq", label: "Groq", keyHint: "gsk_...", url: "https://console.groq.com/keys" },
  { id: "anthropic", label: "Anthropic (Claude)", keyHint: "sk-ant-...", url: "https://console.anthropic.com/settings/keys" },
  { id: "openai", label: "OpenAI", keyHint: "sk-...", url: "https://platform.openai.com/api-keys" },
  { id: "gemini", label: "Google Gemini", keyHint: "AIza...", url: "https://aistudio.google.com/apikey" },
  { id: "custom", label: "Other (OpenAI-compatible)", keyHint: "API key" },
];
const PROVIDER_LABEL = Object.fromEntries(PROVIDERS.map((p) => [p.id, p.label]));

const TIERS = [
  { id: "jnr", label: "Small edits", sub: "Colours, text, one element. Pick something fast." },
  { id: "snr", label: "Bigger edits", sub: "New sections, moving things around." },
  { id: "architect", label: "Full builds", sub: "First build and redesigns. Your best model." },
];

const TABS = [
  ["keys", "API keys"],
  ["models", "Models"],
  ["photos", "Photos"],
];

export default function SettingsModal({ onClose, onChanged }) {
  const [view, setView] = useState(null);
  const [tab, setTab] = useState("keys");
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.settings().then(setView).catch((e) => setStatus({ error: true, text: e.message }));
  }, []);

  // Every settings call returns the fresh view; keep the app's "AI ready" state in sync too.
  const run = async (fn, okText) => {
    setBusy(true);
    setStatus(null);
    try {
      const next = await fn();
      if (next?.keys) {
        setView(next);
        onChanged(next);
      }
      if (okText) setStatus({ text: typeof okText === "function" ? okText(next) : okText });
      return next;
    } catch (e) {
      setStatus({ error: true, text: e.message });
      return null;
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Settings" onClose={onClose}>
      {!view ? (
        status ? <div className="notice is-error">{status.text}</div> : <span className="progress" />
      ) : (
        <>
          {view.user?.guest && (
            <p className="modal-sub">
              You're not signed in, so these settings are saved for this browser. Sign in later and they move to your account.
            </p>
          )}

          <div className="tabs settings-tabs" role="tablist" aria-label="Settings">
            {TABS.map(([id, label]) => (
              <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "is-on" : ""} onClick={() => { setTab(id); setStatus(null); }}>
                {label}
                {id === "keys" && view.keys.length > 0 && <span className="count">{view.keys.length}</span>}
              </button>
            ))}
          </div>

          <div className="settings-panel" role="tabpanel">
            {tab === "keys" && <KeysTab view={view} busy={busy} run={run} />}
            {tab === "models" && <ModelsTab view={view} busy={busy} run={run} />}
            {tab === "photos" && <PhotosTab view={view} busy={busy} run={run} />}
          </div>

          {status && <div className={status.error ? "notice is-error" : "notice is-ok"} role="status">{status.text}</div>}

          <div className="modal-actions">
            <span className="spacer" />
            <button className="btn primary" onClick={onClose}>Done</button>
          </div>
        </>
      )}
    </Modal>
  );
}

function KeysTab({ view, busy, run }) {
  const [provider, setProvider] = useState("groq");
  const [apiKey, setApiKey] = useState("");
  const [label, setLabel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const info = PROVIDERS.find((p) => p.id === provider);
  const serverProviders = Object.entries(view.server.providers);

  const add = async (e) => {
    e.preventDefault();
    const next = await run(
      () => api.addKey({ provider, api_key: apiKey, label, base_url: baseUrl }),
      (r) => `Key works and is saved. ${r.models.length} models available.`
    );
    if (next) {
      setApiKey("");
      setLabel("");
    }
  };

  return (
    <>
      <p className="modal-sub">
        Add as many keys as you like, from any provider. When a key hits its rate limit, the next key for that provider takes over. Keys are stored encrypted on the server and never shown again.
      </p>

      {view.keys.length > 0 ? (
        <ul className="key-list">
          {view.keys.map((k) => (
            <li key={k.id}>
              <span className="key-provider">{PROVIDER_LABEL[k.provider] || k.provider}</span>
              <span className="key-name">{k.label || "Unnamed key"}</span>
              <span className="key-hint">{k.hint}</span>
              <button className="icon-btn small" onClick={() => run(() => api.removeKey(k.id), "Key removed.")} disabled={busy} aria-label={`Remove ${k.label || "key"}`}>
                <CloseIcon />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-keys">No keys of your own yet.</p>
      )}

      {serverProviders.length > 0 && (
        <p className="server-keys">
          The server also has {serverProviders.map(([p, n]) => `${n} ${PROVIDER_LABEL[p] || p} key${n > 1 ? "s" : ""}`).join(", ")}, used after yours.
        </p>
      )}

      <form className="add-key" onSubmit={add}>
        <h4>Add a key</h4>
        <div className="field-grid">
          <label className="field">
            <span>Provider</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Name <em>optional</em></span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Personal, Team" maxLength={40} />
          </label>
        </div>
        {provider === "custom" && (
          <label className="field">
            <span>Base URL</span>
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://openrouter.ai/api/v1" />
          </label>
        )}
        <label className="field">
          <span>
            API key{" "}
            {info.url && <em><a href={info.url} target="_blank" rel="noreferrer">Get a {info.label.split(" ")[0]} key</a></em>}
          </span>
          <div className="field-row">
            <input type="password" autoComplete="new-password" data-1p-ignore data-lpignore="true" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={info.keyHint} />
            <button className="btn primary" type="submit" disabled={busy || !apiKey.trim()}>
              {busy ? "Checking..." : "Test and add"}
            </button>
          </div>
        </label>
      </form>
    </>
  );
}

function ModelsTab({ view, busy, run }) {
  // Providers you can pick: your keys plus the server's.
  const usable = [...new Set([...view.keys.map((k) => k.provider), ...Object.keys(view.server.providers)])];
  const fallbackProvider = usable[0] || view.server.default_provider;
  const [picks, setPicks] = useState(() =>
    Object.fromEntries(TIERS.map((t) => [t.id, view.models[t.id] || { provider: fallbackProvider, model: "" }]))
  );
  const [available, setAvailable] = useState({});

  const loadModels = async (provider) => {
    if (!provider || available[provider]) return;
    try {
      const { models } = await api.listModels(provider);
      setAvailable((a) => ({ ...a, [provider]: models }));
    } catch {
      /* the field still accepts any model id */
    }
  };

  useEffect(() => {
    Object.values(picks).forEach((p) => loadModels(p.provider));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setPick = (tier, change) => {
    setPicks((all) => ({ ...all, [tier]: { ...all[tier], ...change } }));
    if (change.provider) loadModels(change.provider);
  };

  if (usable.length === 0) {
    return <p className="modal-sub">Add an API key first, then choose which model handles each kind of change.</p>;
  }

  return (
    <>
      <p className="modal-sub">Choose who handles each kind of change. Leave the model empty to use the recommended one.</p>
      {TIERS.map((t) => {
        const pick = picks[t.id];
        const recommended = view.default_models[pick.provider]?.[t.id];
        return (
          <fieldset className="tier-row" key={t.id}>
            <legend>
              {t.label} <em>{t.sub}</em>
            </legend>
            <div className="field-grid">
              <label className="field">
                <span>Provider</span>
                <select value={pick.provider} onChange={(e) => setPick(t.id, { provider: e.target.value, model: "" })}>
                  {usable.map((p) => <option key={p} value={p}>{PROVIDER_LABEL[p] || p}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Model</span>
                <input
                  list={`models-${pick.provider}`}
                  value={pick.model}
                  onChange={(e) => setPick(t.id, { model: e.target.value })}
                  placeholder={recommended ? `Recommended: ${recommended}` : "model id"}
                />
              </label>
            </div>
          </fieldset>
        );
      })}
      {usable.map((p) => (
        <datalist id={`models-${p}`} key={p}>
          {(available[p] || []).map((id) => <option key={id} value={id} />)}
        </datalist>
      ))}
      <div className="modal-actions">
        <button className="btn primary" onClick={() => run(() => api.saveModels(picks), "Models saved.")} disabled={busy}>
          Save models
        </button>
      </div>
    </>
  );
}

function PhotosTab({ view, busy, run }) {
  const [apiKey, setApiKey] = useState("");
  return (
    <>
      <p className="modal-sub">
        The researcher finds photos for your sites. Without a key it uses Wikimedia Commons. A free{" "}
        <a href="https://www.pexels.com/api/" target="_blank" rel="noreferrer">Pexels key</a> gives polished stock photos instead.
      </p>
      {view.pexels ? (
        <div className="key-list single">
          <span className="key-provider">Pexels</span>
          <span className="key-name">Your key</span>
          <span className="key-hint">{view.pexels.hint}</span>
          <button className="icon-btn small" onClick={() => run(() => api.savePexels(""), "Pexels key removed.")} disabled={busy} aria-label="Remove Pexels key">
            <CloseIcon />
          </button>
        </div>
      ) : view.server.pexels ? (
        <p className="server-keys">The server has a Pexels key, so photos already come from Pexels. You can add your own to use instead.</p>
      ) : null}
      <label className="field">
        <span>Pexels API key</span>
        <div className="field-row">
          <input type="password" autoComplete="new-password" data-1p-ignore data-lpignore="true" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Paste your Pexels key" />
          <button
            className="btn primary"
            onClick={async () => (await run(() => api.savePexels(apiKey), "Pexels key saved.")) && setApiKey("")}
            disabled={busy || !apiKey.trim()}
          >
            {busy ? "Checking..." : "Test and save"}
          </button>
        </div>
      </label>
    </>
  );
}
