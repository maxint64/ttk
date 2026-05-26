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
const updateNotice = document.querySelector("#updateNotice");
const updateNoticeButton = document.querySelector("#updateNoticeButton");
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

export function setupUpdateNotice(onConfirmUpdate) {
  updateNoticeButton.addEventListener("click", async () => {
    clearErrorMessage();
    updateNoticeButton.disabled = true;
    updateNoticeButton.textContent = "更新中";
    try {
      await onConfirmUpdate();
    } catch (error) {
      showErrorMessage(error.message);
    } finally {
      updateNoticeButton.disabled = false;
      updateNoticeButton.textContent = "最新情報を表示";
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

export function showUpdateNotice(hasPendingInput = false) {
  updateNotice.querySelector("span").textContent = hasPendingInput
    ? "担当情報が更新されています。入力中の内容を確認してから最新情報を表示してください。"
    : "担当情報が更新されています。最新情報を表示できます。";
  updateNotice.hidden = false;
}

export function hideUpdateNotice() {
  updateNotice.hidden = true;
}

export function hasPendingUserInput() {
  const active = document.activeElement;
  if (isEditableInput(active)) return true;
  return Array.from(document.querySelectorAll(".create-form input, .mini-form input"))
    .some((input) => input.value.trim() !== "");
}

function setupDateControls(node, activity, selectedDate, handlers) {
  const todayButton = node.querySelector(".date-today");
  const previousButton = node.querySelector(".date-previous");
  const nextButton = node.querySelector(".date-next");
  const dateInput = node.querySelector(".assignment-date-input");

  dateInput.value = selectedDate;
  todayButton.addEventListener("click", () => {
    handlers.onSelectAssignmentDate(activity.id, today);
  });
  previousButton.addEventListener("click", () => {
    handlers.onSelectAssignmentDate(activity.id, shiftDate(selectedDate, -1));
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

function isEditableInput(element) {
  return (
    element instanceof HTMLInputElement &&
    (
      element.closest(".create-form") ||
      element.closest(".mini-form") ||
      element.classList.contains("assignment-date-input")
    )
  );
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
    const dayOff = findDayOff(activity.member_days_off, member.id, selectedDate);
    const row = document.createElement("tr");
    const memberHeader = document.createElement("th");
    memberHeader.scope = "row";

    const memberHeaderInner = document.createElement("div");
    memberHeaderInner.className = "member-row-header";

    const memberName = document.createElement("span");
    memberName.textContent = member.name;

    const dayOffButton = document.createElement("button");
    dayOffButton.type = "button";
    dayOffButton.className = "day-off-toggle";
    dayOffButton.setAttribute("aria-pressed", String(Boolean(dayOff)));
    dayOffButton.textContent = dayOff ? "休み中" : "休み";
    dayOffButton.addEventListener("click", async () => {
      try {
        clearErrorMessage();
        await handlers.onToggleDayOff(activity.id, selectedDate, member.id, dayOff);
      } catch (error) {
        showErrorMessage(error.message);
      }
    });

    memberHeaderInner.append(memberName, dayOffButton);
    memberHeader.append(memberHeaderInner);
    row.append(memberHeader);

    activity.roles.forEach((role) => {
      const td = document.createElement("td");
      const cell = document.createElement("div");
      cell.className = "assignment-cell-stack";
      const button = document.createElement("button");
      const assignment = findAssignment(view.assignments, role.id, member.id);
      const skip = findSkip(activity.role_member_skips, role.id, member.id);
      const checked = Boolean(assignment);
      const unavailable = Boolean(dayOff || skip);

      button.type = "button";
      button.className = "assignment-cell";
      button.setAttribute("aria-pressed", String(checked));
      button.disabled = unavailable && !checked;
      button.setAttribute(
        "aria-label",
        `${selectedDate}: ${member.name}が${role.name}を担当`
      );
      if (checked) {
        const mark = document.createElement("span");
        mark.className = "assignment-mark";
        mark.textContent = "✓";

        const createdAt = document.createElement("span");
        createdAt.className = "assignment-created-at";
        createdAt.textContent = `最終更新時間 ${formatAssignmentMinute(assignment.created_at)}`;

        button.append(mark, createdAt);
      } else if (dayOff) {
        button.textContent = "休み";
      } else if (skip) {
        button.textContent = "スキップ";
      }
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

      const skipButton = document.createElement("button");
      skipButton.type = "button";
      skipButton.className = "skip-toggle";
      skipButton.setAttribute("aria-pressed", String(Boolean(skip)));
      skipButton.textContent = skip ? "スキップ中" : "スキップ";
      skipButton.addEventListener("click", async () => {
        try {
          clearErrorMessage();
          await handlers.onToggleSkip(activity.id, role.id, member.id, skip);
        } catch (error) {
          showErrorMessage(error.message);
        }
      });

      cell.append(button, skipButton);
      td.append(cell);
      row.append(td);
    });

    tbody.append(row);
  });

  table.append(tbody);
  tableWrap.append(table);
}

function formatAssignmentMinute(value) {
  if (!value) return "";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const date = new Date(normalized.endsWith("Z") ? normalized : `${normalized}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ja-JP", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

function findAssignment(assignments, roleId, memberId) {
  return assignments.find(
    (assignment) =>
      assignment.role_id === roleId &&
      assignment.member_id === memberId
  );
}

function findDayOff(daysOff = [], memberId, offOn) {
  return daysOff.find(
    (dayOff) =>
      dayOff.member_id === memberId &&
      dayOff.off_on === offOn
  );
}

function findSkip(skips = [], roleId, memberId) {
  return skips.find(
    (skip) =>
      skip.role_id === roleId &&
      skip.member_id === memberId
  );
}
