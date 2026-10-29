import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { useVoiceCall } from "./useVoiceCall.js";
import Preview from "./components/Preview.jsx";
import VoicePanel from "./components/VoicePanel.jsx";
import ActivityLog from "./components/ActivityLog.jsx";
import History from "./components/History.jsx";
import AccountMenu from "./components/AccountMenu.jsx";
import SettingsModal from "./components/SettingsModal.jsx";
import GitHubModal from "./components/GitHubModal.jsx";

const TIER_LABEL = { research: "Researcher", jnr: "Junior dev", snr: "Senior dev", architect: "Architect" };

function useProjectId() {
  const [projectId, setProjectId] = useState(() => new URLSearchParams(location.search).get("p"));
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const ensure = async () => {
      if (projectId) {
        try {
          await api.getProject(projectId);
          return;
        } catch {
          /* stale link: fall through and start a fresh project */
        }
      }
      try {
        const meta = await api.createProject();
        if (cancelled) return;
        history.replaceState(null, "", `?p=${meta.id}`);
        setProjectId(meta.id);
      } catch (e) {
        setError(e.message);
      }
    };
    ensure();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { projectId, error };
}

export default function App() {
  const { projectId, error: projectError } = useProjectId();
  const voice = useVoiceCall(projectId);
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState(null);
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(null);
  const [selection, setSelection] = useState(null);
  const [picking, setPicking] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [user, setUser] = useState(null);
  const [dialog, setDialog] = useState(null); // "settings" | "github"
  const nextId = useRef(1);

  const addLog = useCallback((entry) => {
    setLog((prev) => [...prev.slice(-80), { id: nextId.current++, ts: Date.now(), ...entry }]);
  }, []);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig({ voice_enabled: false, llm_provider: "none" }));
    api.me().then((r) => setUser(r.user)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!projectId) return;
    api.getProject(projectId).then((m) => {
      setMeta(m);
      setSelection(m.selection);
    });

    const source = new EventSource(`/api/projects/${projectId}/events`);
    source.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      switch (ev.type) {
        case "job_started":
          setBusy({ instruction: ev.instruction, tier: ev.tier });
          addLog({ kind: "user", text: ev.instruction, tier: ev.tier });
          break;
        case "job_stage":
          setBusy((b) => (b ? { ...b, tier: ev.tier } : b));
          break;
        case "research_done":
          addLog({
            kind: "research",
            text: ev.summary,
            palette: ev.palette,
            images: (ev.images || []).map((img) => ({ ...img, src: `/preview/${projectId}/${img.path}` })),
          });
          break;
        case "job_escalated":
          setBusy((b) => (b ? { ...b, tier: ev.tier } : b));
          addLog({ kind: "info", text: `Handing over to the ${TIER_LABEL[ev.tier] || ev.tier}` });
          break;
        case "job_done":
          setBusy(null);
          setMeta((m) => ({ ...m, current: ev.current, versions: ev.versions }));
          setReloadKey((k) => k + 1);
          addLog({ kind: "done", text: ev.version.summary, tier: ev.version.tier });
          break;
        case "job_failed":
          setBusy(null);
          addLog({ kind: "error", text: ev.reason });
          break;
        case "version":
          setMeta((m) => ({ ...m, current: ev.current, versions: ev.versions }));
          setReloadKey((k) => k + 1);
          if (ev.undo) addLog({ kind: "info", text: "Undid the last change" });
          break;
        case "selection":
          setSelection(ev.selection);
          break;
      }
    };
    return () => source.close();
  }, [projectId, addLog]);

  const handleSelect = useCallback(
    (sel) => {
      setSelection(sel);
      setPicking(false);
      api.select(projectId, sel).catch(() => {});
    },
    [projectId]
  );

  const clearSelection = () => {
    setSelection(null);
    api.select(projectId, null).catch(() => {});
  };

  const sendCommand = async (text) => {
    try {
      await api.command(projectId, text);
    } catch (e) {
      addLog({ kind: "error", text: e.message });
    }
  };

  if (projectError) return <div className="fatal">Couldn't reach the backend: {projectError}</div>;
  if (!projectId || !meta) return <div className="fatal">Loading…</div>;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" />
          VoiceSite
          <span className="brand-sub">talk to your website</span>
        </div>
        <div className="topbar-actions">
          <button className="ghost hide-sm" onClick={() => navigator.clipboard?.writeText(location.href)}>Copy link</button>
          <a className="ghost hide-sm" href={`/preview/${projectId}/`} target="_blank" rel="noreferrer">Open site ↗</a>
          <a className="ghost" href={api.downloadUrl(projectId)} download>Download ZIP</a>
          <button className="ghost" onClick={() => setDialog("github")}>Push to GitHub</button>
          <AccountMenu
            user={user}
            auth={config?.auth}
            onOpenSettings={() => setDialog("settings")}
            onSignedOut={() => setUser(null)}
          />
        </div>
      </header>

      {dialog === "settings" && user && (
        <SettingsModal user={user} defaults={config?.default_models} onClose={() => setDialog(null)} onSaved={setUser} />
      )}
      {dialog === "github" && (
        <GitHubModal
          projectId={projectId}
          meta={meta}
          user={user}
          auth={config?.auth}
          onClose={() => setDialog(null)}
          onPushed={(res) => {
            setMeta((m) => ({ ...m, github: { repo: res.repo, url: res.url } }));
            addLog({ kind: "done", text: `Pushed v${meta.current} to GitHub: ${res.repo}` });
          }}
        />
      )}

      <main className="workspace">
        <Preview
          projectId={projectId}
          version={meta.current}
          reloadKey={reloadKey}
          busy={busy}
          tierLabel={TIER_LABEL}
          picking={picking}
          selection={selection}
          onSelect={handleSelect}
        />

        <aside className="sidebar">
          <VoicePanel
            voice={voice}
            config={config}
            userHasKey={!!user?.llm?.has_key}
            onOpenSettings={user ? () => setDialog("settings") : null}
            busy={busy}
            picking={picking}
            onTogglePick={() => setPicking((p) => !p)}
            selection={selection}
            onClearSelection={clearSelection}
            onCommand={sendCommand}
            isBlank={meta.current === 0 && meta.versions.length === 1}
          />
          <ActivityLog entries={log} tierLabel={TIER_LABEL} />
          <History
            versions={meta.versions}
            current={meta.current}
            tierLabel={TIER_LABEL}
            onUndo={() => api.undo(projectId)}
            onRestore={(n) => api.restore(projectId, n)}
          />
        </aside>
      </main>
    </div>
  );
}
