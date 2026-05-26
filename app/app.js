import { apiRequest } from "./api.js";
import {
  clearAssignmentViews,
  deleteAssignmentView,
  getActivities,
  getSelectedDate,
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
  onToggleDayOff: toggleDayOff,
  onToggleSkip: toggleSkip,
};

let hasPendingRemoteAssignmentUpdate = false;
const realtimeUpdateTypes = new Set([
  "activities_changed",
  "assignments_changed",
  "availability_changed",
]);

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
    if (!realtimeUpdateTypes.has(payload.type)) return;

    await handleRemoteAssignmentUpdate(payload);
  });
}

async function handleRemoteAssignmentUpdate(payload) {
  if (!isDisplayedUpdate(payload)) {
    await applySilentRemoteUpdate();
    return;
  }

  hasPendingRemoteAssignmentUpdate = true;
  showUpdateNotice(hasPendingUserInput());
}

function isDisplayedUpdate(payload) {
  if (payload.type === "activities_changed") {
    if (payload.action === "created") return false;
    return hasDisplayedActivity(payload.activity_id);
  }

  if (payload.type === "assignments_changed") {
    return assignmentUpdateIsDisplayed(payload);
  }

  if (payload.type === "availability_changed") {
    if (payload.off_on) {
      return (
        hasDisplayedActivity(payload.activity_id) &&
        getSelectedDate(payload.activity_id) === payload.off_on
      );
    }
    return hasDisplayedActivity(payload.activity_id);
  }

  return true;
}

function assignmentUpdateIsDisplayed(payload) {
  if (payload.activity_id) {
    return (
      hasDisplayedActivity(payload.activity_id) &&
      getSelectedDate(payload.activity_id) === payload.assigned_on
    );
  }

  if (Array.isArray(payload.activity_ids)) {
    return payload.activity_ids.some(
      (activityId) =>
        hasDisplayedActivity(activityId) &&
        getSelectedDate(activityId) === payload.assigned_on
    );
  }

  return true;
}

function hasDisplayedActivity(activityId) {
  return getActivities().some((activity) => activity.id === Number(activityId));
}

async function applyRemoteAssignmentUpdate() {
  if (!hasPendingRemoteAssignmentUpdate) return;

  hasPendingRemoteAssignmentUpdate = false;
  hideUpdateNotice();
  clearAssignmentViews();
  await loadAndRender();
}

async function applySilentRemoteUpdate() {
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
  deleteAssignmentView(activityId, assignedOn);
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

async function toggleDayOff(activityId, assignedOn, memberId, dayOff, dayOffType) {
  const path = `/api/activities/${activityId}/members/${memberId}/days-off`;
  try {
    if (dayOff?.day_off_type === dayOffType) {
      await apiRequest(`${path}/${dayOff.off_on}`, { method: "DELETE" });
    } else {
      await apiRequest(path, {
        method: "POST",
        body: { off_on: assignedOn, day_off_type: dayOffType },
      });
    }
  } finally {
    deleteAssignmentView(activityId, assignedOn);
    await loadAndRender();
  }
}

async function toggleSkip(activityId, roleId, memberId, skip, skipType) {
  const path = `/api/activities/${activityId}/roles/${roleId}/skips`;
  try {
    if (skip?.skip_type === skipType) {
      await apiRequest(`${path}/${memberId}`, { method: "DELETE" });
    } else {
      await apiRequest(path, {
        method: "POST",
        body: { member_id: memberId, skip_type: skipType },
      });
    }
  } finally {
    await loadAndRender();
  }
}
