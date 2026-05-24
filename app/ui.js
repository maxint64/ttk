import {
  getAssignmentView,
  getSelectedDate,
  shiftDate,
  today,
} from "./state.js";

const activityForm = document.querySelector("#activityForm");
const activityName = document.querySelector("#activityName");
const activityList = document.querySelector("#activityList");
const summaryText = document.querySelector("#summaryText");
const errorMessage = document.querySelector("#errorMessage");
const template = document.querySelector("#activityTemplate");

export function setupCreateForm(onCreateActivity) {
  activityForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = activityName.value.trim();

    if (!name) return;

    clearErrorMessage();
    try {
      await onCreateActivity(name);
      activityName.value = "";
    } catch (error) {
      showErrorMessage(error.message);
    }
  });
}

export function render(activities, handlers) {
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
    setupDateControls(node, activity, selectedDate, handlers);

    deleteButton.addEventListener("click", async () => {
      try {
        clearErrorMessage();
        await handlers.onDeleteActivity(activity.id);
      } catch (error) {
        showErrorMessage(error.message);
      }
    });

    roleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = roleForm.elements.roleName;
      try {
        clearErrorMessage();
        await handlers.onAddItem(activity.id, "roles", { name: input.value });
        input.value = "";
      } catch (error) {
        showErrorMessage(error.message);
      }
    });

    memberForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const nameInput = memberForm.elements.memberName;
      const emailInput = memberForm.elements.memberEmail;
      try {
        clearErrorMessage();
        await handlers.onAddItem(activity.id, "members", {
          name: nameInput.value,
          email: emailInput.value,
        });
        nameInput.value = "";
        emailInput.value = "";
      } catch (error) {
        showErrorMessage(error.message);
      }
    });

    renderItems(node.querySelector(".role-list"), activity, "roles", handlers);
    renderItems(node.querySelector(".member-list"), activity, "members", handlers);
    renderAssignmentTable(node, activity, selectedDate, handlers);
    node.querySelector(".role-count").textContent = activity.roles.length;
    node.querySelector(".member-count").textContent = activity.members.length;

    activityList.append(node);
    handlers.onEnsureAssignmentView(activity.id, selectedDate);
  });
}

export function renderError(message) {
  activityList.replaceChildren();
  summaryText.textContent = "接続エラー";

  const error = document.createElement("p");
  error.className = "empty";
  error.textContent = message;
  activityList.append(error);
}

export function showErrorMessage(message) {
  errorMessage.textContent = message || "エラーが発生しました。";
  errorMessage.hidden = false;
}

export function clearErrorMessage() {
  errorMessage.textContent = "";
  errorMessage.hidden = true;
}

function setupDateControls(node, activity, selectedDate, handlers) {
  const previousButton = node.querySelector(".date-previous");
  const todayButton = node.querySelector(".date-today");
  const nextButton = node.querySelector(".date-next");
  const dateInput = node.querySelector(".assignment-date-input");

  dateInput.value = selectedDate;
  previousButton.addEventListener("click", () => {
    handlers.onSelectAssignmentDate(activity.id, shiftDate(selectedDate, -1));
  });
  todayButton.addEventListener("click", () => {
    handlers.onSelectAssignmentDate(activity.id, today);
  });
  nextButton.addEventListener("click", () => {
    handlers.onSelectAssignmentDate(activity.id, shiftDate(selectedDate, 1));
  });
  dateInput.addEventListener("change", () => {
    if (dateInput.value) {
      handlers.onSelectAssignmentDate(activity.id, dateInput.value);
    }
  });
}

function renderItems(list, activity, key, handlers) {
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
    removeButton.addEventListener("click", async () => {
      try {
        clearErrorMessage();
        await handlers.onRemoveItem(activity.id, key, item.id);
      } catch (error) {
        showErrorMessage(error.message);
      }
    });

    chip.append(label, removeButton);
    list.append(chip);
  });
}

function renderAssignmentTable(node, activity, selectedDate, handlers) {
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
    empty.textContent = view.message || "担当データを読み込めませんでした。";
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
        try {
          clearErrorMessage();
          await handlers.onToggleAssignment(
            activity.id,
            selectedDate,
            role.id,
            member.id,
            assignment
          );
        } catch (error) {
          showErrorMessage(error.message);
        }
      });

      td.append(button);
      row.append(td);
    });

    tbody.append(row);
  });

  table.append(tbody);
  tableWrap.append(table);
}

function findAssignment(assignments, roleId, memberId) {
  return assignments.find(
    (assignment) =>
      assignment.role_id === roleId &&
      assignment.member_id === memberId
  );
}
