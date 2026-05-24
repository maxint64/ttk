const activityForm = document.querySelector("#activityForm");
const activityName = document.querySelector("#activityName");
const activityList = document.querySelector("#activityList");
const summaryText = document.querySelector("#summaryText");
const template = document.querySelector("#activityTemplate");
const today = formatDate(new Date());

let activities = [];
const selectedDates = new Map();
const assignmentViews = new Map();

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
    const error = new Error(message);
    error.status = response.status;
    throw error;
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
    const selectedDate = getSelectedDate(activity.id);

    title.textContent = activity.name;
    meta.textContent = `役割 ${activity.roles.length}件 / メンバー ${activity.members.length}人 / ${selectedDate}`;
    node.querySelector(".assignment-date").textContent = selectedDate;
    setupDateControls(node, activity, selectedDate);

    deleteButton.addEventListener("click", async () => {
      await apiRequest(`/api/activities/${activity.id}`, { method: "DELETE" });
      await loadAndRender();
    });

    roleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = roleForm.elements.roleName;
      try {
        await addItem(activity.id, "roles", { name: input.value });
        input.value = "";
      } catch (error) {
        alert(error.message);
      }
    });

    memberForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const nameInput = memberForm.elements.memberName;
      const emailInput = memberForm.elements.memberEmail;
      try {
        await addItem(activity.id, "members", {
          name: nameInput.value,
          email: emailInput.value,
        });
        nameInput.value = "";
        emailInput.value = "";
      } catch (error) {
        alert(error.message);
      }
    });

    renderItems(node.querySelector(".role-list"), activity, "roles");
    renderItems(node.querySelector(".member-list"), activity, "members");
    renderAssignmentTable(node, activity, selectedDate);
    node.querySelector(".role-count").textContent = activity.roles.length;
    node.querySelector(".member-count").textContent = activity.members.length;

    activityList.append(node);
    ensureAssignmentView(activity.id, selectedDate);
  });
}

function setupDateControls(node, activity, selectedDate) {
  const previousButton = node.querySelector(".date-previous");
  const todayButton = node.querySelector(".date-today");
  const nextButton = node.querySelector(".date-next");
  const dateInput = node.querySelector(".assignment-date-input");

  dateInput.value = selectedDate;
  previousButton.addEventListener("click", () => selectAssignmentDate(activity.id, shiftDate(selectedDate, -1)));
  todayButton.addEventListener("click", () => selectAssignmentDate(activity.id, today));
  nextButton.addEventListener("click", () => selectAssignmentDate(activity.id, shiftDate(selectedDate, 1)));
  dateInput.addEventListener("change", () => {
    if (dateInput.value) {
      selectAssignmentDate(activity.id, dateInput.value);
    }
  });
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

function renderItems(list, activity, key) {
  list.replaceChildren();

  activity[key].forEach((item) => {
    const chip = document.createElement("li");
    chip.className = "chip";

    const label = document.createElement("span");
    label.className = "chip-label";
    label.textContent = item.name;
    if (key === "members" && item.email) {
      const email = document.createElement("small");
      email.textContent = item.email;
      label.append(email);
    }

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "x";
    removeButton.setAttribute("aria-label", `${item.name}を削除`);
    removeButton.addEventListener("click", () => removeItem(activity.id, key, item.id));

    chip.append(label, removeButton);
    list.append(chip);
  });
}

function renderAssignmentTable(node, activity, selectedDate) {
  const tableWrap = node.querySelector(".assignment-table-wrap");
  const empty = node.querySelector(".assignment-empty");
  const view = getAssignmentView(activity.id, selectedDate);
  tableWrap.replaceChildren();

  if (activity.roles.length === 0 || activity.members.length === 0) {
    empty.hidden = false;
    empty.textContent = "役割とメンバーを追加すると表が表示されます。";
    return;
  }

  empty.hidden = view.status === "ready";
  if (view.status === "loading") {
    empty.textContent = "担当データを読み込み中です。";
  } else if (view.status === "missing") {
    empty.textContent = "この日の担当データはありません。";
  } else if (view.status === "error") {
    empty.textContent = "担当データを読み込めませんでした。";
  }

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
      const assignment = findAssignment(view.assignments, role.id, member.id);
      const checked = Boolean(assignment);

      button.type = "button";
      button.className = "assignment-cell";
      button.textContent = checked ? "✓" : "";
      button.setAttribute("aria-pressed", String(checked));
      button.setAttribute(
        "aria-label",
        `${selectedDate}: ${member.name}が${role.name}を担当`
      );
      button.addEventListener("click", async () => {
        await toggleAssignment(activity.id, selectedDate, role.id, member.id, assignment);
      });

      td.append(button);
      row.append(td);
    });

    tbody.append(row);
  });

  table.append(tbody);
  tableWrap.append(table);
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
  assignmentViews.delete(viewKey(activityId, assignedOn));
  await loadAndRender();
}

function findAssignment(assignments, roleId, memberId) {
  return assignments.find(
    (assignment) =>
      assignment.role_id === roleId &&
      assignment.member_id === memberId
  );
}

function getSelectedDate(activityId) {
  if (!selectedDates.has(activityId)) {
    selectedDates.set(activityId, today);
  }
  return selectedDates.get(activityId);
}

function selectAssignmentDate(activityId, assignedOn) {
  selectedDates.set(activityId, assignedOn);
  render();
}

function ensureAssignmentView(activityId, assignedOn) {
  const key = viewKey(activityId, assignedOn);
  if (assignmentViews.has(key)) return;
  loadAssignmentsForDate(activityId, assignedOn);
}

async function loadAssignmentsForDate(activityId, assignedOn) {
  const key = viewKey(activityId, assignedOn);
  assignmentViews.set(key, { status: "loading", assignments: [] });

  try {
    const data = await apiRequest(
      `/api/activities/${activityId}/assignments/dates/${assignedOn}`
    );
    assignmentViews.set(key, { status: "ready", assignments: data.assignments });
  } catch (error) {
    if (error.status === 404) {
      assignmentViews.set(key, { status: "missing", assignments: [] });
    } else {
      assignmentViews.set(key, { status: "error", assignments: [] });
    }
  }
  render();
}

function getAssignmentView(activityId, assignedOn) {
  return assignmentViews.get(viewKey(activityId, assignedOn)) || {
    status: "loading",
    assignments: [],
  };
}

function viewKey(activityId, assignedOn) {
  return `${activityId}:${assignedOn}`;
}

function shiftDate(value, days) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return formatDate(date);
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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
