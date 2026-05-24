export const today = formatDate(new Date());

let activities = [];
const selectedDates = new Map();
const assignmentViews = new Map();

export function getActivities() {
  return activities;
}

export function setActivities(nextActivities) {
  activities = nextActivities;
}

export function getSelectedDate(activityId) {
  if (!selectedDates.has(activityId)) {
    selectedDates.set(activityId, today);
  }
  return selectedDates.get(activityId);
}

export function setSelectedDate(activityId, assignedOn) {
  selectedDates.set(activityId, assignedOn);
}

export function hasAssignmentView(activityId, assignedOn) {
  return assignmentViews.has(viewKey(activityId, assignedOn));
}

export function setAssignmentView(activityId, assignedOn, view) {
  assignmentViews.set(viewKey(activityId, assignedOn), view);
}

export function getAssignmentView(activityId, assignedOn) {
  return assignmentViews.get(viewKey(activityId, assignedOn)) || {
    status: "loading",
    assignments: [],
  };
}

export function deleteAssignmentView(activityId, assignedOn) {
  assignmentViews.delete(viewKey(activityId, assignedOn));
}

export function clearAssignmentViews() {
  assignmentViews.clear();
}

export function shiftDate(value, days) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return formatDate(date);
}

function viewKey(activityId, assignedOn) {
  return `${activityId}:${assignedOn}`;
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
