import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { GitHubIcon, GoogleIcon } from "./icons.jsx";

function SignInButtons({ auth }) {
  if (!auth?.google && !auth?.github) {
    return <p className="muted-text">Sign-in isn't configured. Set GOOGLE_CLIENT_ID/SECRET or GITHUB_CLIENT_ID/SECRET on the server.</p>;
  }
  return (
    <div className="signin-buttons">
      {auth.google && <a className="btn signin" href={api.loginUrl("google")}><GoogleIcon /> Continue with Google</a>}
      {auth.github && <a className="btn signin" href={api.loginUrl("github")}><GitHubIcon /> Continue with GitHub</a>}
    </div>
  );
}

export { SignInButtons };

export default function AccountMenu({ user, auth, onOpenSettings, onSignedOut }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const signOut = async () => {
    await api.logout().catch(() => {});
    setOpen(false);
    onSignedOut();
  };

  return (
    <div className="account" ref={ref}>
      <button className="account-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {user ? (
          <>
            {user.avatar ? <img className="avatar" src={user.avatar} alt="" referrerPolicy="no-referrer" /> : <span className="avatar" />}
            <span className="account-name">{user.name || user.email}</span>
          </>
        ) : (
          "Sign in"
        )}
      </button>
      {open && (
        <div className="menu">
          {user ? (
            <>
              <div className="menu-who">
                <strong>{user.name}</strong>
                {user.email && <span>{user.email}</span>}
              </div>
              <div className="menu-row">
                <span>GitHub</span>
                {user.github ? (
                  <span className="muted">@{user.github.login}</span>
                ) : auth?.github ? (
                  <a className="text-btn" href={api.loginUrl("github")}>Connect</a>
                ) : (
                  <span className="muted">not configured</span>
                )}
              </div>
              <button className="menu-item" onClick={() => { setOpen(false); onOpenSettings(); }}>
                AI model & API key
                <span className="muted">{user.llm?.has_key ? user.llm.provider : "Server key"}</span>
              </button>
              <button className="menu-item" onClick={signOut}>Sign out</button>
            </>
          ) : (
            <SignInButtons auth={auth} />
          )}
        </div>
      )}
    </div>
  );
}
