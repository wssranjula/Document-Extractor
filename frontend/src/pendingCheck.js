/** Remembers an upload that has not received a job id yet.

The upload page navigates to the job page immediately. This record lets that
page show the first stage while the file is still being accepted.
*/

import { OPTIMISTIC_STAGES } from "./components/Pipeline";

const PENDING_KEY = "pending-check";

export function acceptingStages() {
  const started = new Date().toISOString();
  return OPTIMISTIC_STAGES.map((stage, index) =>
    index === 0 ? { ...stage, status: "running", started_at: started } : { ...stage },
  );
}

export function rememberPendingCheck(check) {
  sessionStorage.setItem(PENDING_KEY, JSON.stringify(check));
}

export function forgetPendingCheck() {
  sessionStorage.removeItem(PENDING_KEY);
}

export function loadPendingCheck() {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
