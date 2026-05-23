const activityForm = document.querySelector("#activityForm");
const activityName = document.querySelector("#activityName");
const activityList = document.querySelector("#activityList");
const summaryText = document.querySelector("#summaryText");
const template = document.querySelector("#activityTemplate");
const today = new Date().toISOString().slice(0, 10);
const mockAssignmentStorageKey = `ttk:mock-assignments:${today}`;
const mockInitializedStorageKey = `ttk:mock-initialized:${today}`;

let activities = [];
let mockAssignments = loadMockAssignments();
let mockInitializedActivities = loadMockInitializedActivities();

activityForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = activityName.value.trim();

  if (!name) return;

  await apiRequest("/api/activities", {
    method: "POST",
    body: { name },
  });

  activityName.value = "";
  await loadAndRender();
});

async function loadAndRender() {
  try {
    const data = await apiRequest("/api/activities");
    activities = data.activities;
    render();
  } catch (error) {
    renderError("データを読み込めませんでした。サーバーが起動しているか確認してください。");
  }
}

async function apiRequest(path, options = {}) {
  const fetchOptions = {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
  };

  if (options.body) {
    fetchOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, fetchOptions);
  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

async function readErrorMessage(response) {
  try {
    const data = await response.json();
    return data.error || "request failed";
  } catch {
    return "request failed";
  }
}

function render() {
  activityList.replaceChildren();
  summaryText.textContent = `アクティビティ ${activities.length}件`;

  if (activities.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "まだアクティビティがありません。最初の活動を追加してください。";
    activityList.append(empty);
    return;
  }

  activities.forEach((activity) => {
    const node = template.content.firstElementChild.cloneNode(true);
    const title = node.querySelector(".activity-title");
    const meta = node.querySelector(".activity-meta");
    const deleteButton = node.querySelector(".activity-delete");
    const roleForm = node.querySelector(".role-form");
    const memberForm = node.querySelector(".member-form");

    title.textContent = activity.name;
    meta.textContent = `役割 ${activity.roles.length}件 / メンバー ${activity.members.length}人 / ${today}`;
    node.querySelector(".assignment-date").textContent = today;

    deleteButton.addEventListener("click", async () => {
      await apiRequest(`/api/activities/${activity.id}`, { method: "DELETE" });
      await loadAndRender();
    });

    roleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = roleForm.elements.roleName;
      await addItem(activity.id, "roles", input.value);
      input.value = "";
    });

    memberForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = memberForm.elements.memberName;
      await addItem(activity.id, "members", input.value);
      input.value = "";
    });

    renderItems(node.querySelector(".role-list"), activity, "roles");
    renderItems(node.querySelector(".member-list"), activity, "members");
    renderAssignmentTable(node, activity);
    node.querySelector(".role-count").textContent = activity.roles.length;
    node.querySelector(".member-count").textContent = activity.members.length;

    activityList.append(node);
  });
}

async function addItem(activityId, key, rawValue) {
  const value = rawValue.trim();
  if (!value) return;

  await apiRequest(`/api/activities/${activityId}/${key}`, {
    method: "POST",
    body: { name: value },
  });
  await loadAndRender();
}

async function removeItem(activityId, key, itemId) {
  await apiRequest(`/api/activities/${activityId}/${key}/${itemId}`, { method: "DELETE" });
  await loadAndRender();
}

function renderItems(list, activity, key) {
  list.replaceChildren();

  activity[key].forEach((item) => {
    const chip = document.createElement("li");
    chip.className = "chip";

    const label = document.createElement("span");
    label.textContent = item.name;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "x";
    removeButton.setAttribute("aria-label", `${item.name}を削除`);
    removeButton.addEventListener("click", () => removeItem(activity.id, key, item.id));

    chip.append(label, removeButton);
    list.append(chip);
  });
}

function renderAssignmentTable(node, activity) {
  const tableWrap = node.querySelector(".assignment-table-wrap");
  const empty = node.querySelector(".assignment-empty");
  tableWrap.replaceChildren();

  if (activity.roles.length === 0 || activity.members.length === 0) {
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  ensureMockAssignment(activity);

  const table = document.createElement("table");
  table.className = "assignment-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  headerRow.append(document.createElement("th"));

  activity.roles.forEach((role) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = role.name;
    headerRow.append(th);
  });

  thead.append(headerRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  activity.members.forEach((member) => {
    const row = document.createElement("tr");
    const memberHeader = document.createElement("th");
    memberHeader.scope = "row";
    memberHeader.textContent = member.name;
    row.append(memberHeader);

    activity.roles.forEach((role) => {
      const td = document.createElement("td");
      const button = document.createElement("button");
      const checked = isMockAssigned(activity.id, role.id, member.id);

      button.type = "button";
      button.className = "assignment-cell";
      button.textContent = checked ? "✓" : "";
      button.setAttribute("aria-pressed", String(checked));
      button.setAttribute(
        "aria-label",
        `${today}: ${member.name}が${role.name}を担当`
      );
      button.addEventListener("click", () => {
        toggleMockAssignment(activity.id, role.id, member.id);
        renderAssignmentTable(node, activity);
      });

      td.append(button);
      row.append(td);
    });

    tbody.append(row);
  });

  table.append(tbody);
  tableWrap.append(table);
}

function assignmentKey(activityId, roleId, memberId) {
  return `${activityId}:${roleId}:${memberId}`;
}

function isMockAssigned(activityId, roleId, memberId) {
  return mockAssignments.includes(assignmentKey(activityId, roleId, memberId));
}

function toggleMockAssignment(activityId, roleId, memberId) {
  const key = assignmentKey(activityId, roleId, memberId);
  if (mockAssignments.includes(key)) {
    mockAssignments = mockAssignments.filter((item) => item !== key);
  } else {
    mockAssignments = [...mockAssignments, key];
  }
  saveMockAssignments();
}

function ensureMockAssignment(activity) {
  if (mockInitializedActivities.includes(activity.id)) return;

  mockAssignments = [
    ...mockAssignments,
    assignmentKey(activity.id, activity.roles[0].id, activity.members[0].id),
  ];
  mockInitializedActivities = [...mockInitializedActivities, activity.id];
  saveMockAssignments();
  saveMockInitializedActivities();
}

function loadMockAssignments() {
  try {
    const parsed = JSON.parse(localStorage.getItem(mockAssignmentStorageKey) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveMockAssignments() {
  localStorage.setItem(mockAssignmentStorageKey, JSON.stringify(mockAssignments));
}

function loadMockInitializedActivities() {
  try {
    const parsed = JSON.parse(localStorage.getItem(mockInitializedStorageKey) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveMockInitializedActivities() {
  localStorage.setItem(
    mockInitializedStorageKey,
    JSON.stringify(mockInitializedActivities)
  );
}

function renderError(message) {
  activityList.replaceChildren();
  summaryText.textContent = "接続エラー";

  const error = document.createElement("p");
  error.className = "empty";
  error.textContent = message;
  activityList.append(error);
}

loadAndRender();
