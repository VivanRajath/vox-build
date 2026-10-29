import { useCallback, useEffect, useRef, useState } from "react";
import { BolnaWebCall } from "@bolna/web-call";

const ERROR_MESSAGES = {
  mint_failed: "Couldn't start a voice session. Check BOLNA_API_KEY and BOLNA_AGENT_ID on the server.",
  at_capacity: "Voice is busy right now. Try again in a moment.",
  microphone_denied: "Microphone access is blocked. Allow it in your browser and try again.",
  connect_failed: "Couldn't connect to the voice agent. Check your network.",
  call_rejected: "The voice agent declined the call.",
  autoplay_blocked: "Your browser blocked audio. Click the mic again.",
  already_active: "A call is already running.",
};

// The SDK's own messages use em dashes; keep the UI free of them.
const plain = (message) => (message || "").replace(/\s*[—–]\s*/g, ". ");

export function useVoiceCall(projectId) {
  const callRef = useRef(null);
  const [state, setState] = useState("idle");
  const [volume, setVolume] = useState(0);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    const call = new BolnaWebCall({
      sessionUrl: "/api/bolna-session",
      userData: { project_id: projectId },
    });
    call.on("state-change", (s) => setState(s));
    call.on("volume-level", (v) => setVolume(v));
    call.on("call-end", () => {
      setVolume(0);
      setMuted(false);
    });
    call.on("error", (e) => {
      if (e.code === "at_capacity" && e.scope === "not_enabled") {
        setError("Web calls aren't enabled on this Bolna account yet.");
      } else {
        setError(ERROR_MESSAGES[e.code] || plain(e.message) || "Voice call error");
      }
    });
    callRef.current = call;
    return () => {
      call.stop();
      callRef.current = null;
    };
  }, [projectId]);

  // Must be called straight from a click handler, or browsers block audio.
  const start = useCallback(async () => {
    setError(null);
    try {
      await callRef.current?.start();
    } catch (e) {
      setError(ERROR_MESSAGES[e?.code] || plain(e?.message) || "Couldn't start the call");
    }
  }, []);

  const stop = useCallback(() => callRef.current?.stop(), []);

  const toggleMute = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    call.setMuted(!call.isMuted());
    setMuted(call.isMuted());
  }, []);

  return { state, volume, muted, error, start, stop, toggleMute };
}
