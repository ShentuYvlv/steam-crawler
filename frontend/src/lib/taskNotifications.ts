import type { SyncJob } from "@/lib/api";

const storageKey = "steam_admin_seen_task_states";
const attentionStatuses = new Set(["pending", "running", "failed", "partial_success"]);

function taskStateKey(task: SyncJob) {
  return `${task.id}:${task.status}`;
}

function readSeenStates() {
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : []);
  } catch {
    return new Set<string>();
  }
}

function writeSeenStates(states: Set<string>) {
  window.localStorage.setItem(storageKey, JSON.stringify([...states]));
  window.dispatchEvent(new Event("task-notification-sync"));
}

export function getUnreadTaskCount(tasks: SyncJob[]) {
  const seenStates = readSeenStates();
  return tasks.filter(
    (task) => attentionStatuses.has(task.status) && !seenStates.has(taskStateKey(task))
  ).length;
}

export function markTasksSeen(tasks: SyncJob[]) {
  const seenStates = readSeenStates();
  tasks.forEach((task) => {
    if (attentionStatuses.has(task.status)) {
      seenStates.add(taskStateKey(task));
    }
  });
  writeSeenStates(seenStates);
}
