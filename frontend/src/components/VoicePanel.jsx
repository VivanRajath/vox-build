import { useState } from "react";

const STATUS = {
  idle: "Tap to talk",
  connecting: "Connecting…",
  ringing: "Connecting…",
  active: "Listening. Just talk.",
  ended: "Tap to talk again",
};

const BLANK_IDEAS = [
  "Build a landing page for a South Indian café called Filter Kaapi",
  "Make a portfolio for a wedding photographer in Jaipur",
  "Create a site for a yoga studio with class timings and pricing",
];
const EDIT_IDEAS = ["Make the header dark green", "Add a testimonials section", "Make this bigger", "Undo that"];

export default function VoicePanel({
  voice, config, userHasKey, onOpenSettings, busy, picking, onTogglePick, selection, onClearSelection, onCommand, isBlank,
}) {
  const [text, setText] = useState("");
  const live = voice.state === "active";
  const connecting = voice.state === "connecting" || voice.state === "ringing";
  const voiceReady = config?.voice_enabled;
  const scale = 1 + Math.min(voice.volume, 1) * 0.6;

  const submit = (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    onCommand(value);
    setText("");
  };

  return (
    <div className="panel voice-panel">
      <div className="mic-row">
        <button
          className={`mic ${live ? "live" : ""} ${connecting ? "connecting" : ""}`}
          onClick={live || connecting ? voice.stop : voice.start}
          disabled={!voiceReady}
          aria-label={live ? "End voice session" : "Start voice session"}
        >
          <span className="mic-glow" style={{ transform: `scale(${live ? scale : 1})` }} />
          <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
            {live ? (
              <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
            ) : (
              <path
                fill="currentColor"
                d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z"
              />
            )}
          </svg>
        </button>
        <div className="mic-text">
          <div className="mic-status">{voiceReady ? STATUS[voice.state] || voice.state : "Voice not configured"}</div>
          <div className="mic-sub">
            {voiceReady
              ? live
                ? "Vox can hear you. Say what to build or change."
                : "Talk to Vox, your voice web designer"
              : "Set BOLNA_API_KEY and BOLNA_AGENT_ID. You can still type below."}
          </div>
          {live && (
            <button className="link" onClick={voice.toggleMute}>
              {voice.muted ? "Unmute mic" : "Mute mic"}
            </button>
          )}
        </div>
      </div>

      {voice.error && <div className="alert">{voice.error}</div>}
      {config?.llm_provider === "none" && !userHasKey && (
        <div className="alert">
          No AI model set up yet.{" "}
          {onOpenSettings ? (
            <button className="link" onClick={onOpenSettings}>Add your API key</button>
          ) : (
            "Sign in (top right) to add your own API key"
          )}
          , or set one in the server's .env.
        </div>
      )}

      <div className="select-row">
        <button className={`chip ${picking ? "active" : ""}`} onClick={onTogglePick} disabled={isBlank}>
          {picking ? "Cancel picking" : "Point at an element"}
        </button>
        {selection && (
          <span className="chip selected" title={selection.path}>
            {selection.label}
            <button className="chip-x" onClick={onClearSelection} aria-label="Clear selection">×</button>
          </span>
        )}
      </div>

      <form className="command" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={isBlank ? "Or type: describe your website…" : "Or type a change…"}
          disabled={!!busy}
        />
        <button type="submit" disabled={!text.trim() || !!busy}>Send</button>
      </form>

      <div className="ideas">
        <span>Try saying</span>
        {(isBlank ? BLANK_IDEAS : EDIT_IDEAS).map((idea) => (
          <button key={idea} className="idea" onClick={() => setText(idea)}>“{idea}”</button>
        ))}
      </div>
    </div>
  );
}
