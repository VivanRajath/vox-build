import { useState } from "react";
import { api } from "../api.js";
import Modal from "./Modal.jsx";
import { SignInButtons } from "./AccountMenu.jsx";

function suggestName(meta) {
  if (meta.github?.repo) return meta.github.repo;
  const slug = (meta.brief?.business || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug ? `${slug}-website` : `vox-build-${meta.id}`;
}

export default function GitHubModal({ projectId, meta, user, auth, onClose, onPushed }) {
  const [repo, setRepo] = useState(() => suggestName(meta));
  const [isPrivate, setIsPrivate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const push = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.pushGithub(projectId, repo.trim(), isPrivate);
      setResult(res);
      onPushed(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  let body;
  if (!user) {
    body = (
      <>
        <p className="modal-sub">Sign in to push your site to GitHub.</p>
        <SignInButtons auth={auth} />
      </>
    );
  } else if (!user.github) {
    body = (
      <>
        <p className="modal-sub">Connect your GitHub account so Vox Build can create a repository and push your site to it.</p>
        {auth?.github ? (
          <a className="btn primary" href={api.loginUrl("github")}>Connect GitHub</a>
        ) : (
          <p className="muted-text">GitHub isn't configured on the server (GITHUB_CLIENT_ID/SECRET).</p>
        )}
      </>
    );
  } else if (result) {
    body = (
      <>
        <p className="modal-sub">
          Pushed version {meta.current} to <strong>{result.repo}</strong> on <code>{result.branch}</code>.
        </p>
        <div className="modal-actions">
          <span className="spacer" />
          <button className="btn" onClick={onClose}>Close</button>
          <a className="btn primary" href={result.url} target="_blank" rel="noreferrer">Open repository</a>
        </div>
      </>
    );
  } else {
    body = (
      <form onSubmit={push}>
        <p className="modal-sub">
          The current version (v{meta.current}) becomes one commit. A new repository is created if it doesn't exist yet.
        </p>
        <label className="field">
          <span>Repository</span>
          <div className="field-row">
            {!repo.includes("/") && <span className="prefix">{user.github.login} /</span>}
            <input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="my-website" required />
          </div>
          <em>Use owner/name to push to an organisation or an existing repo.</em>
        </label>
        <label className="check">
          <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} />
          Make it private (only applies when creating the repo)
        </label>
        {error && <div className="notice is-error">{error}</div>}
        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary" disabled={busy || !repo.trim()}>
            {busy ? "Pushing…" : "Push to GitHub"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <Modal title="Push to GitHub" onClose={onClose}>
      {body}
    </Modal>
  );
}
