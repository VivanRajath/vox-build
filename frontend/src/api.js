async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  config: () => request("/api/config"),
  createProject: () => request("/api/projects", { method: "POST" }),
  getProject: (id) => request(`/api/projects/${id}`),
  command: (id, text) => request(`/api/projects/${id}/command`, { method: "POST", body: JSON.stringify({ text }) }),
  undo: (id) => request(`/api/projects/${id}/undo`, { method: "POST" }),
  restore: (id, n) => request(`/api/projects/${id}/restore/${n}`, { method: "POST" }),
  select: (id, selection) => request(`/api/projects/${id}/select`, { method: "POST", body: JSON.stringify({ selection }) }),
  downloadUrl: (id) => `/api/projects/${id}/download`,
  pushGithub: (id, repo, isPrivate) =>
    request(`/api/projects/${id}/github`, { method: "POST", body: JSON.stringify({ repo, private: isPrivate }) }),

  me: () => request("/api/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  loginUrl: (provider) => `/auth/${provider}/login?next=${encodeURIComponent(location.pathname + location.search)}`,
  settings: () => request("/api/settings"),
  addKey: (key) => request("/api/settings/keys", { method: "POST", body: JSON.stringify(key) }),
  removeKey: (id) => request(`/api/settings/keys/${id}`, { method: "DELETE" }),
  listModels: (provider) => request("/api/settings/models/list", { method: "POST", body: JSON.stringify({ provider }) }),
  saveModels: (models) => request("/api/settings/models", { method: "PUT", body: JSON.stringify({ models }) }),
  savePexels: (apiKey) => request("/api/settings/pexels", { method: "PUT", body: JSON.stringify({ api_key: apiKey }) }),
};
