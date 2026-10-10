const LABELS = {
  parsed: "Parsed",
  chunked: "Chunked",
  embedded: "Embedded",
  summarized: "Summarized",
  key_points: "Key points",
  entities: "Entities",
  verified: "Verified",
  done: "Done",
};

export const OPTIMISTIC_STAGES = Object.keys(LABELS).map((name) => ({
  name,
  status: "pending",
  started_at: null,
  finished_at: null,
  error: null,
}));

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

export function completedStages(stages, status, finishedAt) {
  if (status !== "succeeded") return stages || [];
  return (stages || []).map((stage) =>
    stage.name === "done" && stage.status !== "failed"
      ? { ...stage, status: "succeeded", finished_at: stage.finished_at || finishedAt || null }
      : stage,
  );
}

export function Pipeline({ stages }) {
  return (
    <ol className="pipeline">
      {stages.map((stage) => (
        <li key={stage.name} className={`stage ${stage.status}`}>
          <span className="stage-name">{LABELS[stage.name] || stage.name}</span>
          <span className="stage-time">{when(stage)}</span>
        </li>
      ))}
    </ol>
  );
}

function when(stage) {
  if (stage.error) return stage.error;
  if (stage.finished_at) return formatTime(stage.finished_at);
  if (stage.started_at) return `Started ${formatTime(stage.started_at)}`;
  if (stage.status === "pending") return "Waiting";
  return stage.status;
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
