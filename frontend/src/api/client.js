/** Calls to the document-check API. The token is kept in local storage. */

const TOKEN_KEY = "formulary_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { json, body, method, auth = true } = {}) {
  const headers = new Headers();
  if (auth && getToken()) headers.set("Authorization", `Bearer ${getToken()}`);
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const response = await fetch(`/api${path}`, { method, headers, body });
  if (response.status === 401 && auth) {
    clearToken();
    window.location.assign("/login");
    throw new Error("Sign in again");
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json();
  return response;
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg).join(" ");
  } catch {
    /* response had no JSON body */
  }
  return "The request failed";
}

export function signIn(email, password) {
  return request("/auth/login", { method: "POST", json: { email, password }, auth: false });
}

export function signUp(email, password) {
  return request("/auth/signup", { method: "POST", json: { email, password }, auth: false });
}

export function currentUser() {
  return request("/auth/me");
}

export function listReferences() {
  return request("/references");
}

export function createReference(name, file) {
  const body = new FormData();
  body.append("name", name);
  body.append("file", file);
  return request("/references", { method: "POST", body });
}

export function listJobs() {
  return request("/jobs");
}

export function getJob(jobId) {
  return request(`/jobs/${jobId}`);
}

export function getResult(jobId) {
  return request(`/jobs/${jobId}/result`);
}

export function createJob(file, referenceId) {
  const body = new FormData();
  body.append("file", file);
  body.append("reference_id", referenceId);
  return request("/jobs", { method: "POST", body });
}

export async function fetchFile(jobId) {
  const response = await request(`/jobs/${jobId}/file`);
  const blob = await response.blob();
  return { blob, type: response.headers.get("content-type") || "" };
}

export async function streamJob(jobId, onEvent, signal) {
  const response = await fetch(`/api/jobs/${jobId}/events`, {
    headers: { Authorization: `Bearer ${getToken()}` },
    signal,
  });
  if (response.status === 401) {
    clearToken();
    window.location.assign("/login");
    return;
  }
  if (!response.ok || !response.body) throw new Error("Live updates are unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      if (!part.trim() || part.startsWith(":")) continue;
      let event = "message";
      const data = [];
      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) onEvent(event, JSON.parse(data.join("\n")));
    }
  }
}
