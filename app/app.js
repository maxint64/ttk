import { apiRequest } from "./api.js";
import {
  clearAssignmentViews,
  deleteAssignmentView,
  getActivities,
  hasAssignmentView,
  setActivities,
  setAssignmentView,
  setSelectedDate,
} from "./state.js";
import {
  hasPendingUserInput,
  hideUpdateNotice,
  render,
  renderError,
  setupCreateForm,
  setupUpdateNotice,
  showUpdateNotice,
} from "./ui.js";

const handlers = {
  onAddItem: addItem,
  onDeleteActivity: deleteActivity,
  onEnsureAssignmentView: ensureAssignmentView,
  onRemoveItem: removeItem,
  onSelectAssignmentDate: selectAssignmentDate,
  onToggleAssignment: toggleAssignment,
};

let hasPendingRemoteAssignmentUpdate = false;

setupCreateForm(createActivity);
setupUpdateNotice(applyRemoteAssignmentUpdate);
loadAndRender();
setupRealtimeUpdates();

async function createActivity(name) {
  await apiRequest("/api/activities", {
    method: "POST",
    body: { name },
  });
  await loadAndRender();
}

async function loadAndRender() {
  try {
    const data = await apiRequest("/api/activities");
    setActivities(data.activities);
    render(getActivities(), handlers);
  } catch (error) {
    renderError(error.message || "データを読み込めませんでした。サーバーが起動しているか確認してください。");
  }
}

function setupRealtimeUpdates() {
  const source = new EventSource("/api/events");
  source.addEventListener("message", async (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload.type !== "assignments_changed") return;

    await handleRemoteAssignmentUpdate();
  });
}

async function handleRemoteAssignmentUpdate() {
  hasPendingRemoteAssignmentUpdate = true;
  if (hasPendingUserInput()) {
    showUpdateNotice();
    return;
  }

  await applyRemoteAssignmentUpdate();
}

async function applyRemoteAssignmentUpdate() {
  if (!hasPendingRemoteAssignmentUpdate) return;

  hasPendingRemoteAssignmentUpdate = false;
  hideUpdateNotice();
  clearAssignmentViews();
  await loadAndRender();
}

async function deleteActivity(activityId) {
  await apiRequest(`/api/activities/${activityId}`, { method: "DELETE" });
  await loadAndRender();
}

async function addItem(activityId, key, values) {
  const body = Object.fromEntries(
    Object.entries(values).map(([field, value]) => [field, value.trim()])
  );
  if (!body.name) return;

  await apiRequest(`/api/activities/${activityId}/${key}`, {
    method: "POST",
    body,
  });
  await loadAndRender();
}

async function removeItem(activityId, key, itemId) {
  await apiRequest(`/api/activities/${activityId}/${key}/${itemId}`, { method: "DELETE" });
  await loadAndRender();
}

function selectAssignmentDate(activityId, assignedOn) {
  setSelectedDate(activityId, assignedOn);
  render(getActivities(), handlers);
}

function ensureAssignmentView(activityId, assignedOn) {
  if (hasAssignmentView(activityId, assignedOn)) return;
  loadAssignmentsForDate(activityId, assignedOn);
}

async function loadAssignmentsForDate(activityId, assignedOn) {
  setAssignmentView(activityId, assignedOn, { status: "loading", assignments: [] });

  try {
    const data = await apiRequest(
      `/api/activities/${activityId}/assignments/dates/${assignedOn}`
    );
    setAssignmentView(activityId, assignedOn, {
      status: "ready",
      assignments: data.assignments,
    });
  } catch (error) {
    if (error.status === 404) {
      setAssignmentView(activityId, assignedOn, { status: "missing", assignments: [] });
    } else {
      setAssignmentView(activityId, assignedOn, {
        status: "error",
        assignments: [],
        message: error.message,
      });
    }
  }
  render(getActivities(), handlers);
}

async function toggleAssignment(activityId, assignedOn, roleId, memberId, assignment) {
  if (assignment) {
    await apiRequest(`/api/activities/${activityId}/assignments/${assignment.id}`, {
      method: "DELETE",
    });
  } else {
    await apiRequest(`/api/activities/${activityId}/assignments`, {
      method: "POST",
      body: {
        role_id: roleId,
        member_id: memberId,
        assigned_on: assignedOn,
      },
    });
  }
  deleteAssignmentView(activityId, assignedOn);
  await loadAndRender();
}
