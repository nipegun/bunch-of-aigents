/* The board page. */

const lBoardStates = ["todo", "doing", "done"];

/* Two tabs, and which one is open travels in the URL - the same as Settings,
 * so a reload, a bookmark and the back button all land where the user was. */
const lKanbanTabs = ["board", "new"];
const cDefaultKanbanTab = "board";

function fGetCurrentTab() {
  const vTab = new URLSearchParams(window.location.search).get("tab");
  return lKanbanTabs.indexOf(vTab) !== -1 ? vTab : cDefaultKanbanTab;
}

function fSelectTab(pTab, pUpdateHistory) {
  const vTab = lKanbanTabs.indexOf(pTab) !== -1 ? pTab : cDefaultKanbanTab;

  document.querySelectorAll(".tab").forEach(function (vButton) {
    vButton.setAttribute("aria-selected",
      vButton.getAttribute("data-tab") === vTab ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach(function (vPanel) {
    vPanel.hidden = vPanel.getAttribute("data-panel") !== vTab;
  });

  /* Refreshing is about the board, so the button goes away with it rather than
   * sitting above a form it does nothing to. */
  document.getElementById("vRefreshBoardButton").hidden = vTab !== "board";

  if (pUpdateHistory) {
    const vQuery = new URLSearchParams(window.location.search);
    vQuery.set("tab", vTab);
    window.history.replaceState({}, "", "?" + vQuery.toString());
  }
}

/* One card on the board is a summary, not the card.
 *
 * It used to print the whole body, and an agent writing up what it found
 * produces a body that is twenty lines of shell output: one card filled the
 * column and the two below it were off screen. What a board is for is seeing
 * at a glance what there is, so the title gets two lines, the body three, and
 * the full text of both is in the tooltip - the same bargain the sidebar
 * makes with an agent's name.
 *
 * The line that says WHEN is the one that was missing. A card with no time on
 * it is not broken and is not late: nobody is woken for it and its agent will
 * find it on its next scheduled run. With nothing on the card saying so, a
 * card sitting in "to do" for three days looks like a failure.
 */
function fBuildCard(dCard) {
  const vCard = fCreateElement("div", "card");

  /* Who it came from and who has it, on one line with the id. */
  const vHeader = fCreateElement("div", "card-header");
  vHeader.appendChild(fCreateElement("span", "card-id", "#" + dCard.id));
  vHeader.appendChild(fCreateElement(
    "span", "",
    fTranslate("kanban.by", "by {creator}")
      .replace("{creator}", dCard.created_by || "—")));
  vHeader.appendChild(fCreateElement(
    "span", "",
    fTranslate("kanban.owner", "owner: {owner}")
      .replace("{owner}", dCard.owner_agent
                          || fTranslate("kanban.nobody", "nobody"))));
  if (dCard.created_at) {
    const vCreated = fCreateElement(
      "span", "",
      fTranslate("kanban.created", "created {time}")
        .replace("{time}", fShortenTime(dCard.created_at)));
    vCreated.title = dCard.created_at;
    vHeader.appendChild(vCreated);
  }
  vCard.appendChild(vHeader);

  /* Clamped to two lines by the stylesheet; the whole thing is in the
   * tooltip, because cutting text is only fair if the rest is a mouse away. */
  const vTitle = fCreateElement("div", "card-title", dCard.title);
  vTitle.title = dCard.title;
  vCard.appendChild(vTitle);

  if (dCard.body) {
    /* Collapsed to one flowing paragraph for the card: an agent's write-up is
     * full of blank lines, and with the line breaks kept, two of the three
     * lines a card shows go to whitespace. The original is in the tooltip. */
    const vBody = fCreateElement(
      "div", "card-body", dCard.body.replace(/\s+/g, " ").trim());
    vBody.title = dCard.body;
    vCard.appendChild(vBody);
  }

  vCard.appendChild(fBuildCardSchedule(dCard));

  const vActions = fCreateElement("div", "card-actions");
  /* "Doing" and "Done" on their own read as labels rather than as buttons
   * that move the card, which is all they do: this board has no dragging, so
   * these are how a person moves one by hand. */
  vActions.appendChild(fCreateElement(
    "span", "card-actions-label", fTranslate("kanban.moveTo", "Move to")));
  lBoardStates.forEach(function (vState) {
    if (vState === dCard.state) { return; }
    const vButton = fCreateElement("button", "button", fTranslate("kanban.state." + vState, vState));
    vButton.type = "button";
    vButton.addEventListener("click", function () { fMoveCard(dCard.id, vState); });
    vActions.appendChild(vButton);
  });

  const vDeleteButton = fCreateElement(
    "button", "button button-danger", fTranslate("common.delete", "Delete")
  );
  vDeleteButton.type = "button";
  vDeleteButton.addEventListener("click", function () { fDeleteCard(dCard.id, dCard.title); });
  vActions.appendChild(vDeleteButton);

  vCard.appendChild(vActions);
  return vCard;
}

/* "2026-09-12 07:54:56" -> "2026-09-12 07:54". The seconds are noise on a
 * board, and the whole value goes in the tooltip. */
function fShortenTime(pTime) {
  return String(pTime || "").slice(0, 16);
}

/* When this card runs, said in the card rather than left to be worked out.
 *
 * Three states, and the third is the one people ask about: no time at all
 * means nobody is woken and the agent picks it up on its next run of its own.
 */
function fBuildCardSchedule(dCard) {
  const vLine = fCreateElement("div", "card-schedule");

  if (dCard.buzzed_at) {
    vLine.appendChild(fCreateElement(
      "span", "",
      fTranslate("kanban.ranAt", "ran {time}")
        .replace("{time}", fShortenTime(dCard.buzzed_at))));
    vLine.title = dCard.buzzed_at;
    return vLine;
  }

  if (dCard.run_at) {
    vLine.appendChild(fCreateElement(
      "span", "card-due",
      fTranslate("kanban.dueAt", "due {time}")
        .replace("{time}", fShortenTime(dCard.run_at))));
    vLine.title = dCard.run_at;
    return vLine;
  }

  vLine.appendChild(fCreateElement(
    "span", "card-waiting",
    fTranslate("kanban.whenAgentWakes",
               "waits for the agent's next scheduled run")));
  return vLine;
}

async function fRenderBoard() {
  const vBoard = document.getElementById("vBoard");
  let dResult;
  try {
    const vLimit = fReadInterfacePreference("boa.kanbanLimit", "50");
    dResult = await fCallApi("/kanban?limit=" + encodeURIComponent(vLimit));
  } catch (vError) {
    fShowError(vError);
    return;
  }

  fClear(vBoard);
  lBoardStates.forEach(function (vState) {
    const lCards = (dResult.board && dResult.board[vState]) || [];
    const vColumn = fCreateElement("section", "column");
    vColumn.setAttribute("data-state", vState);

    const vHeader = fCreateElement("div", "column-header");
    vHeader.appendChild(fCreateElement(
      "span", "column-name", fTranslate("kanban.state." + vState, vState)
    ));
    vHeader.appendChild(fCreateElement("span", "column-count", String(lCards.length)));
    vColumn.appendChild(vHeader);

    if (lCards.length === 0) {
      vColumn.appendChild(fCreateElement("p", "empty", fTranslate("kanban.empty", "Empty")));
    }
    lCards.forEach(function (dCard) { vColumn.appendChild(fBuildCard(dCard)); });
    vBoard.appendChild(vColumn);
  });
}

async function fMoveCard(pCardId, pState) {
  try {
    await fCallApi("/kanban/cards/" + pCardId, "PUT", { state: pState });
    await fRenderBoard();
  } catch (vError) {
    fShowError(vError);
  }
}

async function fDeleteCard(pCardId, pTitle) {
  const vConfirmed = await fConfirm({
    title: fTranslate("kanban.deleteTitle", "Delete card"),
    message: fTranslate("kanban.deleteConfirm", "Delete card \"{title}\"?")
      .replace("{title}", pTitle),
    confirmLabel: fTranslate("common.delete", "Delete"),
    danger: true,
  });
  if (!vConfirmed) { return; }
  try {
    await fCallApi("/kanban/cards/" + pCardId, "DELETE");
    await fRenderBoard();
  } catch (vError) {
    fShowError(vError);
  }
}

async function fPopulateOwnerSelect() {
  const vSelect = document.getElementById("vCardOwnerInput");
  fClear(vSelect);
  const vNobody = document.createElement("option");
  vNobody.value = "";
  vNobody.textContent = fTranslate("kanban.nobody", "nobody");
  vSelect.appendChild(vNobody);

  try {
    const dResult = await fCallApi("/agents?kanban=1");
    const lAgents = dResult.agents || [];
    lAgents.forEach(function (dAgent) {
      const vOption = document.createElement("option");
      vOption.value = dAgent.id;
      vOption.textContent = dAgent.id + " · " + dAgent.name;
      vSelect.appendChild(vOption);
    });

    /* Assigning a card to an agent that cannot read the board is writing to
     * somebody who never opens their post: the card sits there, the agent
     * wakes on its schedule and never learns it exists. The board is not put
     * into the prompt - an agent reads it by calling kanban.list_cards or not
     * at all - so this is worth saying at the moment of assigning, not after
     * a week of nothing happening. It is a warning and not a block: granting
     * the tool afterwards is a tick box away. */
    const vWarning = document.getElementById("vOwnerWarning");
    function fShowOwnerWarning() {
      const dChosen = lAgents.find(function (dAgent) {
        return dAgent.id === vSelect.value;
      });
      const vBlind = dChosen && dChosen.reads_kanban === false;
      vWarning.hidden = !vBlind;
      if (vBlind) {
        vWarning.textContent = fTranslate(
          "kanban.ownerCannotRead",
          "{agent} cannot read the board: it has no kanban.list_cards tool, so "
          + "it will never see this card. Grant it under the agent's Tools tab."
        ).replace("{agent}", dChosen.id + " · " + dChosen.name);
      }
    }
    vSelect.addEventListener("change", fShowOwnerWarning);
    fShowOwnerWarning();
  } catch (vError) {
    /* The form still works with no owner. */
  }
}

function fReadRequestedTime() {
  /* "now" is a word and not a timestamp on purpose: the browser's clock and
   * the server's do not have to agree, and the only one that decides when a
   * card is due is the server's. */
  const vWhen = document.getElementById("vCardWhenInput").value;
  /* No time at all: the card waits on the board and the agent finds it the
   * next time it wakes for its own reasons. Nobody is woken for it. */
  if (vWhen === "wake") { return ""; }
  if (vWhen === "now") { return "now"; }
  return document.getElementById("vCardAtInput").value || "now";
}

function fBindScheduleFields() {
  const vWhenSelect = document.getElementById("vCardWhenInput");
  const vAtField = document.getElementById("vCardAtField");
  function fShowTimeField() {
    vAtField.hidden = vWhenSelect.value !== "at";
  }
  vWhenSelect.addEventListener("change", fShowTimeField);
  fShowTimeField();
}

async function fAddCard(pEvent) {
  pEvent.preventDefault();
  const vTitleInput = document.getElementById("vCardTitleInput");
  const vBodyInput = document.getElementById("vCardBodyInput");
  try {
    await fCallApi("/kanban/cards", "POST", {
      title: vTitleInput.value,
      body: vBodyInput.value,
      owner_agent: document.getElementById("vCardOwnerInput").value,
      run_at: fReadRequestedTime(),
    });
    vTitleInput.value = "";
    vBodyInput.value = "";
    await fRenderBoard();
    /* Straight to the board: the card was just made and the point of making it
     * is seeing it land, not looking at an empty form again. */
    fSelectTab("board", true);
  } catch (vError) {
    fShowError(vError);
  }
}

document.addEventListener("DOMContentLoaded", async function () {
  await fWaitForTranslations();
  document.getElementById("vAddCardForm").addEventListener("submit", fAddCard);
  fBindScheduleFields();
  document.querySelectorAll(".tab").forEach(function (vButton) {
    vButton.addEventListener("click", function () {
      fSelectTab(vButton.getAttribute("data-tab"), true);
    });
  });
  fSelectTab(fGetCurrentTab(), false);
  document.getElementById("vRefreshBoardButton").addEventListener("click", fRenderBoard);
  await fRenderSidebar();
  await fPopulateOwnerSelect();
  await fRenderBoard();
});
