/* The agent page: read one agent, edit it, save it, run it. */

let dCurrentAgent = null;
let vChatPollTimer = null;
let vLastRenderedChatSignature = "";

/* How often the interface asks whether the answer has arrived. An agent run
 * takes seconds at best and minutes at worst, so polling faster would just
 * mean more requests for the same wait. */
const cChatPollMilliseconds = 2000;

const lAgentTabs = ["general", "model", "tools", "skills", "channels", "prompt",
                    "memory", "schedule", "history"];

/* The roles a chat line can have, as the backend writes them into chat.jsonl. */
const cRoleAgent = "agent";
const cRoleCard = "card";
/* A run the agent's own crontab started, which had something to report. It is
 * one message and not a turn: nobody asked it anything. */
const cRoleRun = "run";

/* Which settings tab is open travels in the URL alongside the agent, so a
 * reload lands on the same one. */
function fGetAgentSettingsTab() {
  const vTab = new URLSearchParams(window.location.search).get("section");
  return lAgentTabs.indexOf(vTab) !== -1 ? vTab : lAgentTabs[0];
}

function fSelectAgentTab(pTab) {
  const vTab = lAgentTabs.indexOf(pTab) !== -1 ? pTab : lAgentTabs[0];

  document.querySelectorAll("[data-agent-tab]").forEach(function (vButton) {
    vButton.setAttribute("aria-selected",
      vButton.getAttribute("data-agent-tab") === vTab ? "true" : "false");
  });
  document.querySelectorAll("[data-agent-panel]").forEach(function (vPanel) {
    vPanel.hidden = vPanel.getAttribute("data-agent-panel") !== vTab;
  });

  const vQuery = new URLSearchParams(window.location.search);
  vQuery.set("section", vTab);
  window.history.replaceState({}, "", "?" + vQuery.toString());
}
let lAvailableTools = [];
let lAvailableSkills = [];
let lAvailableChannels = [];
let lAvailableProviders = [];

function fBuildCheckbox(pId, pLabelText, pHintText, pChecked) {
  const vRow = fCreateElement("div", "checkbox-row");
  const vInput = document.createElement("input");
  vInput.type = "checkbox";
  vInput.id = pId;
  vInput.checked = !!pChecked;
  vRow.appendChild(vInput);

  const vLabel = document.createElement("label");
  vLabel.setAttribute("for", pId);
  vLabel.appendChild(fCreateElement("div", "", pLabelText));
  if (pHintText) {
    vLabel.appendChild(fCreateElement("div", "field-hint", pHintText));
  }
  vRow.appendChild(vLabel);
  return vRow;
}

async function fLoadReferenceData() {
  const [dTools, dSkills, dChannels, dProviders] = await Promise.all([
    fCallApi("/tools"), fCallApi("/skills"), fCallApi("/channels"),
    fCallApi("/providers"),
  ]);
  lAvailableTools = dTools.tools || [];
  lAvailableSkills = dSkills.skills || [];
  lAvailableChannels = dChannels.channels || [];
  lAvailableProviders = dProviders.providers || [];

  fRenderProviderOptions("");
  fRenderProviderOptions("", "vFallbackProviderInput", true);

  /* Both model boxes behave the same way: picking a provider replaces the
   * model with that provider's default, whatever was typed. A model name from
   * the previous provider is never valid for the new one, and leaving it there
   * only produces a 404 at the first run. Empty when the provider has no
   * sensible default, which is vLLM - it has to be the exact served name and
   * guessing would be worse than an empty field.
   *
   * `pAvoidModelId`, given only for the backup, names the field whose model it
   * must not end up equal to. See fPickDifferentModel. */
  function fBindProviderToModel(pSelectId, pModelId, pBaseUrlId, pFieldId,
                                pDataListId, pHintId, pAvoidModelId) {
    const vSelect = document.getElementById(pSelectId);
    vSelect.addEventListener("change", function () {
      const dProvider = lAvailableProviders.find(function (dCandidate) {
        return dCandidate.name === vSelect.value;
      });
      if (!dProvider) {
        /* "none" on the backup: clear the boxes rather than leave a model
         * sitting next to no provider. */
        document.getElementById(pModelId).value = "";
        document.getElementById(pBaseUrlId).value = "";
        fShowBaseUrlField(pFieldId, "");
        fRenderModelOptions({}, pDataListId, pHintId);
        fUpdateFallbackWarning();
        return;
      }
      const vAvoid = pAvoidModelId
        ? document.getElementById(pAvoidModelId).value.trim() : "";
      document.getElementById(pModelId).value = fPickDifferentModel(dProvider, vAvoid);
      document.getElementById(pBaseUrlId).value = dProvider.default_base_url || "";
      fShowBaseUrlField(pFieldId, dProvider.name);
      fRenderModelOptions(dProvider, pDataListId, pHintId);
      fUpdateFallbackWarning();
    });
  }

  fBindProviderToModel("vProviderInput", "vModelInput", "vBaseUrlInput",
                       "vBaseUrlField", "vModelOptions", "vModelHint");
  fBindProviderToModel("vFallbackProviderInput", "vFallbackModelInput",
                       "vFallbackBaseUrlInput", "vFallbackBaseUrlField",
                       "vFallbackModelOptions", "vFallbackModelHint",
                       "vModelInput");

  /* Both model boxes are free text, so the pair can be made identical again by
   * typing after the provider was picked. Watched rather than validated on
   * save: the warning belongs next to the field, while it is being edited. */
  ["vModelInput", "vFallbackModelInput", "vProviderInput",
   "vFallbackProviderInput"].forEach(function (vId) {
    const vField = document.getElementById(vId);
    if (!vField) { return; }
    vField.addEventListener("input", fUpdateFallbackWarning);
    vField.addEventListener("change", fUpdateFallbackWarning);
  });
}

/* The model to put in the box when a provider has just been picked.
 *
 * Normally the provider's default. The exception is the backup with the same
 * provider as the main one: the same provider AND the same model cannot answer
 * anything the main one could not - a backup that fails for exactly the same
 * reason, every time, is not a backup - so the next model in that provider's
 * catalogue is used instead.
 *
 * When the catalogue has nothing else to offer, the default goes in anyway and
 * the warning under the field says so. Inventing a model name would be worse:
 * it would be a 404 on the one call that only happens when something is
 * already going wrong.
 */
function fPickDifferentModel(dProvider, pAvoidModel) {
  const vDefault = dProvider.default_model || "";
  const vAvoid = String(pAvoidModel || "").trim();
  if (!vAvoid || vDefault !== vAvoid) { return vDefault; }

  const dOther = (dProvider.models || []).find(function (dModel) {
    return dModel.id && dModel.id !== vAvoid;
  });
  return dOther ? dOther.id : vDefault;
}

/* Says so when the backup would fail for exactly the same reason as the main
 * model. Not refused on save: it is the user's agent, and a provider that is
 * down for one model is not always down for the same model twice - but nobody
 * chooses this on purpose, so it is worth a line. */
function fUpdateFallbackWarning() {
  const vWarning = document.getElementById("vFallbackSameWarning");
  if (!vWarning) { return; }
  const vProvider = document.getElementById("vProviderInput").value;
  const vModel = document.getElementById("vModelInput").value.trim();
  const vFallbackProvider = document.getElementById("vFallbackProviderInput").value;
  const vFallbackModel = document.getElementById("vFallbackModelInput").value.trim();

  vWarning.hidden = !(vFallbackProvider
                      && vFallbackProvider === vProvider
                      && vFallbackModel === vModel);
}

function fRenderProviderOptions(pSelectedName, pSelectId, pAllowNone) {
  /* Only what this installation can actually run: the three self-hosted
   * providers, which need no key, and the cloud ones whose key is set in
   * Settings. A cloud provider with no key would take the agent to its first
   * run and fail there, which is a slow way to find out.
   *
   * The agent's current provider is listed even when it is not selectable, and
   * marked. Dropping it would leave the box showing a provider nobody chose
   * and save that one on the next click - and a key can also live in the
   * agent's own home, where the web application cannot see it, so "no shared
   * key" does not mean "cannot run". */
  const vSelect = document.getElementById(pSelectId || "vProviderInput");
  fClear(vSelect);

  /* The backup may be nothing at all, and that is the default: a backup the
   * user did not choose would bill an account they did not mean to use. */
  if (pAllowNone) {
    const vNone = document.createElement("option");
    vNone.value = "";
    vNone.textContent = fTranslate("agents.noFallback", "none");
    vSelect.appendChild(vNone);
  }

  lAvailableProviders.forEach(function (dProvider) {
    const vIsCurrent = dProvider.name === pSelectedName;
    if (dProvider.selectable === false && !vIsCurrent) { return; }

    const vOption = document.createElement("option");
    vOption.value = dProvider.name;
    let vSuffix = "";
    if (dProvider.self_hosted) {
      vSuffix = " " + fTranslate("agents.providerSelfHosted", "(self-hosted)");
    } else if (dProvider.selectable === false) {
      vSuffix = " " + fTranslate("agents.providerNoKey", "(no key configured)");
    }
    /* The name the provider spells itself by. The value stays the internal
     * one, which is what everything else keys off. */
    vOption.textContent = fDescribeProviderName(dProvider.name) + vSuffix;
    vOption.disabled = dProvider.available === false;
    vSelect.appendChild(vOption);
  });
}

/* The Base URL box, shown only for a provider that runs on a machine of the
 * user's: Ollama, llama.cpp and vLLM.
 *
 * A cloud provider is reached at its own address, which the adapter already
 * holds - `base.fInit` falls back to `cDefaultBaseUrl` - so the box asked a
 * question that was already answered and offered a way to break the agent by
 * answering it differently.
 *
 * Hidden rather than emptied: an installation that put a proxy in front of a
 * cloud provider has that address stored, and hiding the box is not a reason
 * to throw it away behind the user's back. What the provider picker writes
 * into it is unchanged - the new provider's own default.
 */
function fShowBaseUrlField(pFieldId, pProviderName) {
  const vField = document.getElementById(pFieldId);
  if (!vField) { return; }
  const dProvider = lAvailableProviders.find(function (dCandidate) {
    return dCandidate.name === pProviderName;
  });
  vField.hidden = !(dProvider && dProvider.self_hosted);
}

function fRenderModelOptions(dProvider, pDataListId, pHintId) {
  /* The model field is a free text box with a datalist attached: the browser
   * shows the list, and filters it down as the user types, natively. A model
   * released this morning is in no catalogue yet, so typing must always win
   * over the list. */
  const vDataList = document.getElementById(pDataListId || "vModelOptions");
  fClear(vDataList);

  (dProvider.models || []).forEach(function (dModel) {
    const vOption = document.createElement("option");
    vOption.value = dModel.id;
    const lLabelParts = [];
    if (dModel.label && dModel.label !== dModel.id) { lLabelParts.push(dModel.label); }
    if (dModel.context) { lLabelParts.push(dModel.context); }
    if (dModel.note) { lLabelParts.push(dModel.note); }
    if (lLabelParts.length > 0) { vOption.label = lLabelParts.join(" · "); }
    vDataList.appendChild(vOption);
  });

  const vHint = document.getElementById(pHintId || "vModelHint");
  const lHintParts = [];
  const vCount = (dProvider.models || []).length;
  if (vCount === 1) {
    lHintParts.push(fTranslate("agents.modelSuggestionOne",
      "One model suggested. You can type any other one."));
  } else if (vCount > 1) {
    lHintParts.push(
      fTranslate("agents.modelSuggestions",
        "{count} models suggested. You can type any other one.")
        .replace("{count}", vCount)
    );
  }
  if (dProvider.note) { lHintParts.push(dProvider.note); }
  vHint.textContent = lHintParts.join(" ");
}

/* A tool is named `family.action`, so the family is already there in the name
 * and nothing has to be tagged: `mail.read` belongs with `mail.forward`
 * because it says so. The headings live in api.js, which every page loads,
 * because the new-agent dialog names the same families.
 *
 * Groups a list of tools by family, ordered by the heading the user reads.
 * Ordered by that and not by the family name, for the same reason the theme
 * list is: the two orders do not agree once the headings are translated. */
/* The one family with a switch of its own beside it. */
const cKanbanFamily = "kanban";

function fGroupToolsByFamily(lTools) {
  const dGroups = {};
  lTools.forEach(function (dTool) {
    /* By section rather than by family: two families can share one, which is
     * how web.fetch and rss.fetch end up in the same box. */
    const vSection = fGetToolSection(String(dTool.name || "").split(".")[0]);
    if (!dGroups[vSection]) { dGroups[vSection] = []; }
    dGroups[vSection].push(dTool);
  });

  return Object.keys(dGroups).map(function (vSection) {
    return {
      family: vSection,
      title: fDescribeToolFamilyName(vSection),
      tools: dGroups[vSection].sort(function (dLeft, dRight) {
        return dLeft.name.localeCompare(dRight.name);
      }),
    };
  }).sort(function (dLeft, dRight) {
    return dLeft.title.localeCompare(dRight.title);
  });
}

/* One box per family, not one box with headings inside it.
 *
 * A family is a decision of its own - "may this agent read the mailbox?" -
 * and the rest of the application already draws a decision as a box. The
 * families are whatever is installed on the server, so the boxes are built
 * here rather than written into the template.
 */
function fRenderToolCheckboxes(lGrantedTools) {
  const vContainer = document.getElementById("vToolPanels");
  const vKanbanSwitch = document.getElementById("vKanbanSwitch");
  const vSection = vContainer.parentNode;

  /* Taken out before the container is emptied and put back afterwards. It is
   * markup from the page, with its own id and its translated label, so it is
   * moved rather than rebuilt: rebuilding it would lose whatever the user has
   * just ticked. */
  vKanbanSwitch.remove();

  fClear(vContainer);
  if (lAvailableTools.length === 0) {
    const vEmpty = fCreateElement("div", "panel");
    vEmpty.appendChild(fCreateElement(
      "p", "empty", fTranslate("tools.none", "No tools installed on the server.")
    ));
    vContainer.appendChild(vEmpty);
    vSection.appendChild(vKanbanSwitch);
    return;
  }

  let vKanbanPanel = null;
  fGroupToolsByFamily(lAvailableTools).forEach(function (dGroup) {
    const vPanel = fCreateElement("div", "panel tool-group");
    vPanel.setAttribute("data-family", dGroup.family);

    const vHeading = fCreateElement("h2", "panel-title tool-group-title",
                                    dGroup.title);
    /* The count is worth having: it is the difference between "I have not
     * given this agent any mail tools" and "there are no mail tools". */
    vHeading.appendChild(fCreateElement(
      "span", "tool-group-count",
      String(dGroup.tools.filter(function (dTool) {
        return lGrantedTools.indexOf(dTool.name) !== -1;
      }).length) + " / " + String(dGroup.tools.length)
    ));
    vPanel.appendChild(vHeading);

    dGroup.tools.forEach(function (dTool) {
      vPanel.appendChild(fBuildCheckbox(
        "vTool_" + dTool.name.replace(/\./g, "_"),
        dTool.name, fDescribeTool(dTool),
        lGrantedTools.indexOf(dTool.name) !== -1
      ));
    });
    vContainer.appendChild(vPanel);
    if (dGroup.family === cKanbanFamily) { vKanbanPanel = vPanel; }
  });

  /* The switch belongs with the tools it governs. With no kanban tools
   * installed there is no box to put it in, so it keeps one of its own at the
   * end rather than disappearing: it still decides whether the board is in
   * this agent's prompt. */
  if (vKanbanPanel) {
    vKanbanSwitch.classList.remove("panel");
    vKanbanPanel.appendChild(vKanbanSwitch);
  } else {
    vKanbanSwitch.classList.add("panel");
    vSection.appendChild(vKanbanSwitch);
  }
}

/* One checkbox per skill installed on the server.
 *
 * The description under each is the skill's own, straight out of its SKILL.md,
 * and is not translated: it was written on this server by whoever wrote the
 * procedure, in whatever language they wrote it in. Only the sentence about an
 * empty list belongs to the interface. */
function fRenderSkillCheckboxes(lGrantedSkills) {
  const vContainer = document.getElementById("vSkillCheckboxes");
  fClear(vContainer);

  if (!lAvailableSkills.length) {
    vContainer.appendChild(fCreateElement(
      "p", "field-hint",
      fTranslate("agents.skillsNone",
                 "No skills on this server yet. Write one in /opt/boa/skills/.")
    ));
    return;
  }

  lAvailableSkills.forEach(function (dSkill) {
    let vHint = dSkill.description || "";
    if (dSkill.files && dSkill.files.length) {
      vHint = vHint
        ? vHint + " (" + dSkill.files.join(", ") + ")"
        : dSkill.files.join(", ");
    }
    vContainer.appendChild(fBuildCheckbox(
      "vSkill_" + dSkill.id, dSkill.name, vHint,
      lGrantedSkills.indexOf(dSkill.id) !== -1
    ));
  });
}

function fRenderChannelCheckboxes(lGrantedChannels) {
  const vContainer = document.getElementById("vChannelCheckboxes");
  fClear(vContainer);
  lAvailableChannels.forEach(function (dChannel) {
    const vHint = dChannel.configured
      ? ""
      : fTranslate("agents.channelUnconfigured", "Not configured yet. Set it up in Settings.");
    /* Telegram, not telegram: it is the product's own name, and the lower
     * case one read as an internal identifier that had leaked out. */
    vContainer.appendChild(fBuildCheckbox(
      "vChannel_" + dChannel.name, fDescribeChannelName(dChannel.name), vHint,
      lGrantedChannels.indexOf(dChannel.name) !== -1
    ));
  });
}

/* The last runs, with what each one answered.
 *
 * A scheduled run used to leave `steps` and `tokens` and nothing else: the
 * report the agent wrote went to standard output and, under cron, nowhere at
 * all. The text is in the journal now, so this is where it is read. */
function fRenderRunHistory(lEntries) {
  const vList = document.getElementById("vRunHistory");
  if (!vList) { return; }
  fClear(vList);

  const lRuns = (lEntries || []).filter(function (dEntry) {
    return dEntry.kind === "run_finished";
  }).slice(0, cShownRuns);

  if (lRuns.length === 0) {
    vList.appendChild(fCreateElement(
      "p", "empty", fTranslate("agents.noRuns", "This agent has not run yet.")));
    return;
  }

  lRuns.forEach(function (dEntry) {
    const vRun = fCreateElement("div", "run-entry");
    const vHead = fCreateElement("div", "run-entry-head");
    vHead.appendChild(fCreateElement(
      "span", "run-status", fTranslate("agents.runStatus." + dEntry.status,
                                       dEntry.status)));
    vHead.appendChild(fCreateElement(
      "span", "", String(dEntry.at || "").replace("T", " ").replace("Z", "")));
    if (dEntry.steps) {
      vHead.appendChild(fCreateElement(
        "span", "", fTranslate("chat.steps", "{steps} steps")
          .replace("{steps}", dEntry.steps)));
    }
    if (dEntry.tokens) {
      vHead.appendChild(fCreateElement(
        "span", "", fTranslate("chat.tokens", "{tokens} tokens")
          .replace("{tokens}", dEntry.tokens)));
    }
    vRun.appendChild(vHead);

    if (dEntry.error) {
      vRun.appendChild(fCreateElement("div", "run-error", dEntry.error));
    }
    if (dEntry.answer) {
      const vBody = fCreateElement("div", "md run-answer");
      vBody.appendChild(fRenderMarkdown(dEntry.answer));
      vRun.appendChild(vBody);
    }
    vList.appendChild(vRun);
  });
}

/* Asked for separately: the journal of an agent that has been running for
 * months is the largest thing this interface can ask for, and nobody needs it
 * until they open History. A journal that cannot be read is not a reason to
 * fail the page. */
async function fLoadRunHistory(pAgentId) {
  try {
    const dResult = await fCallApi(
      "/agents/" + encodeURIComponent(pAgentId) + "/journal?limit=200");
    fRenderRunHistory(dResult.entries || []);
  } catch (vError) {
    fRenderRunHistory([]);
  }
}

/* Enough to see a pattern, few enough that the tab is not a wall of text. */
const cShownRuns = 10;

function fRenderUsage(dUsage) {
  const vTable = document.getElementById("vUsageTable");
  fClear(vTable);
  const lRows = [
    [fTranslate("agents.usageRuns", "Runs"), dUsage.runs || 0],
    [fTranslate("agents.usageFailed", "Failed runs"), dUsage.failed_runs || 0],
    [fTranslate("agents.usageTokens", "Tokens used"), dUsage.total_tokens || 0],
    [fTranslate("agents.usageLast", "Last run"), dUsage.last_run_at || "—"],
    [fTranslate("agents.usageStatus", "Last status"), dUsage.last_status || "—"],
  ];
  lRows.forEach(function (lRow) {
    const vTableRow = document.createElement("tr");
    vTableRow.appendChild(fCreateElement("th", "", lRow[0]));
    vTableRow.appendChild(fCreateElement("td", "", String(lRow[1])));
    vTable.appendChild(vTableRow);
  });
}

/* Chat ---------------------------------------------------------------------- */

function fBuildTypingIndicator() {
  const vTyping = fCreateElement("span", "chat-typing");
  for (let vIndex = 0; vIndex < 3; vIndex += 1) {
    vTyping.appendChild(fCreateElement("span"));
  }
  return vTyping;
}

/* The time a card was scheduled for, as the user writes one: year, month, day
 * and the time of day. Shown exactly as it is stored, in UTC, because that is
 * what the board shows next to the same card - converting here and not there
 * would give one card two different times. */
function fFormatCardTime(pTime) {
  const lMatch = String(pTime || "").match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!lMatch) { return String(pTime || ""); }
  return "a" + lMatch[1] + "m" + lMatch[2] + "d" + lMatch[3]
    + "@" + lMatch[4] + ":" + lMatch[5];
}

/* A card that came due and woke the agent.
 *
 * The backend stores the card's own fields and nothing else - who assigned it,
 * whether it was asked for now or for a time - so the sentences around them are
 * written here, in the language the user reads, the same way a ceiling is.
 *
 * Built as DOM nodes: a card title and body are written by whoever made the
 * card, which can be an agent that has been reading command output and web
 * pages. */
function fBuildCardAnnouncement(dMessage) {
  const vBlock = document.createDocumentFragment();

  const vAssignedByName = dMessage.card_assigned_by_name || "";
  vBlock.appendChild(fCreateElement(
    "div", "chat-card-heading",
    vAssignedByName
      ? fTranslate("chat.cardFromAgent", "{agent} has assigned you a new card:")
        .replace("{agent}", vAssignedByName)
      : fTranslate("chat.cardFromUser", "You have been assigned a task on a card:")
  ));

  const lLines = [
    fTranslate("chat.cardId", "Card id: {id}")
      .replace("{id}", dMessage.card_id),
    fTranslate("chat.cardTitle", "Title: {title}")
      .replace("{title}", dMessage.card_title || ""),
    fTranslate("chat.cardBody", "What to do: \u201c{body}\u201d")
      .replace("{body}", dMessage.text
        || fTranslate("chat.cardNoBody", "no instructions on the card")),
    fTranslate("chat.cardRunAt", "To run: {when}")
      .replace("{when}", dMessage.card_immediate
        ? fTranslate("chat.cardNow", "Immediately")
        : fFormatCardTime(dMessage.card_run_at)),
  ];
  lLines.forEach(function (vLine) {
    vBlock.appendChild(fCreateElement("div", "chat-card-field", vLine));
  });
  return vBlock;
}

/* Why a run ended before it asked the model anything. The file carries the
 * name, not the sentence, so that the sentence can be this one. */
const dChatErrorReasons = {
  disabled: ["chat.errorDisabled",
             "This agent is switched off, so it did not act on this card. "
             + "Switch it on under General."],
  daily_ceiling: ["chat.errorDailyCeiling",
                  "This agent has already used up its runs for today, so it did "
                  + "not act on this card. Raise the daily ceiling under Model."],
  cannot_start: ["chat.errorCannotStart",
                 "The run could not be started, so this card was not acted on. "
                 + "Check that the agent's Linux user still exists."],
};

/* Where a message came in through, when it was not this page. A closed list:
 * the value arrives from the server and is used to look up a label, never
 * shown as it comes. */
const dChatSources = {
  telegram: ["chat.sourceTelegram", "via Telegram"],
};

function fRenderChat(lMessages, pPending) {
  const vLog = document.getElementById("vChatLog");

  /* Re-rendering on every poll would fight the user's scrolling and kill any
   * text they were selecting, so the log is only rebuilt when it changed. */
  const vSignature = JSON.stringify(lMessages.map(function (dMessage) {
    return [dMessage.id, dMessage.pending];
  })) + String(pPending);
  if (vSignature === vLastRenderedChatSignature) { return; }
  vLastRenderedChatSignature = vSignature;

  const vWasAtBottom =
    vLog.scrollHeight - vLog.scrollTop - vLog.clientHeight < 60;

  fClear(vLog);

  if (lMessages.length === 0) {
    vLog.appendChild(fCreateElement(
      "p", "empty",
      fTranslate("chat.empty",
        "Nothing said yet. Ask this agent to do something and watch the board.")
    ));
  }

  lMessages.forEach(function (dMessage) {
    const vBubble = fCreateElement("div", "chat-message");
    vBubble.setAttribute("data-role", dMessage.role);

    /* Only what the agent wrote is markdown. The user's own message is shown
     * as they typed it, and an error is a line from a provider, not a
     * document: rendering either would change what the user is looking at. */
    if (dMessage.role === cRoleAgent) {
      const vBody = fCreateElement("div", "md");
      vBody.appendChild(fRenderMarkdown(dMessage.text));
      vBubble.appendChild(vBody);
    } else if (dMessage.role === cRoleRun) {
      /* Markdown like any other answer, under a line saying that nobody
       * asked for it - otherwise it reads as a reply to whatever was said
       * above, which could have been days ago. */
      vBubble.appendChild(fCreateElement(
        "div", "chat-run-heading",
        dMessage.reason === "failed"
          ? fTranslate("chat.runFailed",
                       "A scheduled run did not finish. It reported:")
          : fTranslate("chat.runReport",
                       "A scheduled run. Nobody asked for this; it reported:")));
      const vRunBody = fCreateElement("div", "md");
      vRunBody.appendChild(fRenderMarkdown(dMessage.text));
      vBubble.appendChild(vRunBody);
    } else if (dMessage.role === cRoleCard) {
      vBubble.appendChild(fBuildCardAnnouncement(dMessage));
    } else if (dMessage.reason && dChatErrorReasons[dMessage.reason]) {
      const lReason = dChatErrorReasons[dMessage.reason];
      vBubble.appendChild(document.createTextNode(
        fTranslate(lReason[0], lReason[1])));
    } else {
      vBubble.appendChild(document.createTextNode(dMessage.text || ""));
    }
    if (dMessage.pending) { vBubble.setAttribute("data-pending", "true"); }

    const lMetaParts = [];
    if (dMessage.at) {
      /* A message that came in some other way says so next to its time, not on
       * a line of its own: it is the same kind of fact as when it was sent,
       * and a line above the timestamp read as part of the message. */
      let vWhen = dMessage.at.replace("T", " ").replace("Z", "");
      if (dMessage.source && dChatSources[dMessage.source]) {
        const lSource = dChatSources[dMessage.source];
        vWhen += " (" + fTranslate(lSource[0], lSource[1]) + ")";
      }
      lMetaParts.push(vWhen);
    } else if (dMessage.source && dChatSources[dMessage.source]) {
      const lSource = dChatSources[dMessage.source];
      lMetaParts.push("(" + fTranslate(lSource[0], lSource[1]) + ")");
    }
    const vShowCost = fReadInterfacePreference("boa.showChatCost", "1") === "1";
    if (vShowCost && dMessage.tokens) {
      lMetaParts.push(fTranslate("chat.tokens", "{tokens} tokens")
        .replace("{tokens}", dMessage.tokens));
    }
    if (vShowCost && dMessage.steps) {
      lMetaParts.push(fTranslate("chat.steps", "{steps} steps")
        .replace("{steps}", dMessage.steps));
    }
    if (lMetaParts.length > 0) {
      vBubble.appendChild(fCreateElement("div", "chat-meta", lMetaParts.join(" · ")));
    }

    /* A run that a ceiling cut short says so. Without this the answer is
     * whatever the agent said on its way in - "I am going to check the
     * system" - and it reads as an agent that did nothing. Shown whatever the
     * cost preference says: this is not about the cost, it is about the answer
     * being incomplete. */
    if (dMessage.ceiling) {
      const dCeilingText = {
        tokens: ["chat.ceilingTokens",
                 "Stopped at its token ceiling, so this answer may be cut short. Raise it under Model."],
        steps: ["chat.ceilingSteps",
                "Stopped at its step ceiling, so this answer may be cut short. Raise it under Model."],
        time: ["chat.ceilingTime",
               "Stopped at its time ceiling, so this answer may be cut short. Raise it under Model."],
      }[dMessage.ceiling];
      if (dCeilingText) {
        vBubble.appendChild(fCreateElement(
          "div", "chat-ceiling",
          fTranslate(dCeilingText[0], dCeilingText[1])));
      }
    }

    vLog.appendChild(vBubble);
  });

  if (pPending) {
    const vWaiting = fCreateElement("div", "chat-message");
    vWaiting.setAttribute("data-role", "agent");
    vWaiting.setAttribute("data-pending", "true");
    vWaiting.appendChild(fBuildTypingIndicator());
    vLog.appendChild(vWaiting);
  }

  if (vWasAtBottom) { vLog.scrollTop = vLog.scrollHeight; }
}

function fIsCurrentAgentEnabled() {
  return !dCurrentAgent || dCurrentAgent.enabled !== false;
}

function fSetComposerEnabled(pEnabled) {
  /* A switched-off agent never answers, so the composer stays closed whatever
   * else is going on: letting the message be sent would leave it pending for
   * ever with nothing running to pick it up. */
  const vAgentIsOff = !fIsCurrentAgentEnabled();
  const vAllowed = pEnabled && !vAgentIsOff;

  document.getElementById("vChatInput").disabled = vAgentIsOff;
  document.getElementById("vChatSendButton").disabled = !vAllowed;
  document.getElementById("vChatDisabledNotice").hidden = !vAgentIsOff;

  let vHint = "";
  if (vAgentIsOff) {
    vHint = "";
  } else if (!pEnabled) {
    vHint = fTranslate("chat.working",
      "The agent is working. It may take a few minutes.");
  } else if (fGetSendOnEnter()) {
    vHint = fTranslate("chat.enterSends",
      "Enter sends · Shift+Enter for a new line");
  } else {
    vHint = fTranslate("chat.enterNewline",
      "Enter starts a new line · use the button to send");
  }
  document.getElementById("vChatHint").textContent = vHint;
}

async function fRefreshChat(pAgentId) {
  try {
    const dResult = await fCallApi(
      "/agents/" + encodeURIComponent(pAgentId) + "/chat"
    );
    fRenderChat(dResult.messages || [], dResult.pending);
    fSetComposerEnabled(!dResult.pending);
    return dResult.pending;
  } catch (vError) {
    fShowError(vError);
    return false;
  }
}

function fStartChatPolling(pAgentId) {
  fStopChatPolling();
  vChatPollTimer = window.setInterval(async function () {
    const vPending = await fRefreshChat(pAgentId);
    /* Nothing is waiting, so stop asking. Polling an idle chat for ever would
     * keep a laptop awake for no reason. */
    if (!vPending) {
      fStopChatPolling();
      /* The answer is in: stop the ring now rather than on the next pass, so
       * that the reply and the ring agree on screen. */
      fRefreshAgentActivity();
    }
  }, cChatPollMilliseconds);
}

/* A run this screen did not start - a card that came due, or the agent's own
 * crontab - is announced in the chat by the backend. The sidebar already asks
 * every few seconds which agents are working, so that same answer is what tells
 * the open conversation to catch up, rather than a second timer polling a chat
 * where nothing is happening. */
window.fOnAgentActivity = function (lAgents) {
  if (!dCurrentAgent || vChatPollTimer !== null) { return; }
  if (document.getElementById("vChatPanel").hidden) { return; }
  const dAgent = lAgents.find(function (dOne) {
    return dOne.id === dCurrentAgent.id;
  });
  if (dAgent && dAgent.running) { fStartChatPolling(dCurrentAgent.id); }
};

function fStopChatPolling() {
  if (vChatPollTimer !== null) {
    window.clearInterval(vChatPollTimer);
    vChatPollTimer = null;
  }
}

async function fSendChatMessage(pEvent) {
  pEvent.preventDefault();
  if (!dCurrentAgent) { return; }

  const vInput = document.getElementById("vChatInput");
  const vMessage = vInput.value.trim();
  if (!vMessage) { return; }

  fSetComposerEnabled(false);
  try {
    await fCallApi(
      "/agents/" + encodeURIComponent(dCurrentAgent.id) + "/chat",
      "POST", { message: vMessage }
    );
    vInput.value = "";
    await fRefreshChat(dCurrentAgent.id);
    fStartChatPolling(dCurrentAgent.id);
    /* The run has just started, so the ring should already be turning. Waiting
     * for the sidebar's own timer would leave up to five seconds in which the
     * user pressed send and nothing anywhere said so. */
    fRefreshAgentActivity();
  } catch (vError) {
    fShowError(vError);
    fSetComposerEnabled(true);
  }
}

async function fClearChat() {
  if (!dCurrentAgent) { return; }
  const vConfirmed = await fConfirm({
    title: fTranslate("chat.clear", "Clear chat"),
    message: fTranslate("chat.clearConfirm",
      "Delete the whole conversation with this agent?"),
    confirmLabel: fTranslate("common.delete", "Delete"),
    danger: true,
  });
  if (!vConfirmed) { return; }
  try {
    await fCallApi(
      "/agents/" + encodeURIComponent(dCurrentAgent.id) + "/chat", "DELETE"
    );
    vLastRenderedChatSignature = "";
    await fRefreshChat(dCurrentAgent.id);
  } catch (vError) {
    fShowError(vError);
  }
}

/* Agent loading ------------------------------------------------------------- */

async function fLoadAgent(pAgentId) {
  const vForm = document.getElementById("vAgentForm");
  const vEmptyState = document.getElementById("vAgentEmptyState");
  const vHeaderActions = document.getElementById("vAgentHeaderActions");
  const vChatPanel = document.getElementById("vChatPanel");

  if (!pAgentId) {
    vForm.hidden = true;
    vChatPanel.hidden = true;
    vEmptyState.hidden = false;
    vHeaderActions.hidden = true;
    fStopChatPolling();
    return;
  }

  let dResult;
  try {
    dResult = await fCallApi("/agents/" + encodeURIComponent(pAgentId));
  } catch (vError) {
    fShowError(vError);
    return;
  }

  dCurrentAgent = dResult.info || {};
  const dProvider = dCurrentAgent.provider || {};
  const dLimits = dCurrentAgent.limits || {};

  document.getElementById("vAgentTitle").textContent = dCurrentAgent.name || pAgentId;
  document.getElementById("vAgentIdentityHint").textContent =
    fTranslate("agents.identityHint", "Agent {id} runs as the system user {user}. Its home is {home}.")
      .replace("{id}", dCurrentAgent.id)
      .replace("{user}", dCurrentAgent.system_user)
      .replace("{home}", dCurrentAgent.home || "");

  document.getElementById("vNameInput").value = dCurrentAgent.name || "";
  document.getElementById("vDescriptionInput").value = dCurrentAgent.description || "";
  document.getElementById("vEnabledInput").checked = dCurrentAgent.enabled !== false;
  /* Rebuilt per agent: the list depends on which keys are configured now, and
   * this agent's own provider has to be in it whatever the keys say. */
  fRenderProviderOptions(dProvider.name || "");
  document.getElementById("vProviderInput").value = dProvider.name || "ollama";
  document.getElementById("vModelInput").value = dProvider.model || "";
  document.getElementById("vBaseUrlInput").value = dProvider.base_url || "";
  fShowBaseUrlField("vBaseUrlField", dProvider.name || "");
  document.getElementById("vMaxTokensInput").value = dLimits.max_tokens_per_run || 16384;
  document.getElementById("vMaxStepsInput").value = dLimits.max_steps_per_run || 25;
  document.getElementById("vTimeoutInput").value = dLimits.timeout_seconds || 300;
  document.getElementById("vMaxRunsInput").value = dLimits.max_runs_per_day || 48;
  document.getElementById("vKanbanEnabledInput").checked =
    dCurrentAgent.kanban_enabled !== false;
  document.getElementById("vSystemPromptInput").value = dResult.system_prompt || "";
  fRenderMemory(dResult.memory || "");
  document.getElementById("vCrontabInput").value = dResult.crontab || "";
  document.getElementById("vCrontabExample").textContent =
    fTranslate("agents.crontabExample", "Example, every hour:") +
    " 0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id " +
    dCurrentAgent.id;

  const dSelectedProvider = lAvailableProviders.find(function (dCandidate) {
    return dCandidate.name === (dProvider.name || "");
  });
  if (dSelectedProvider) { fRenderModelOptions(dSelectedProvider); }

  const dFallback = dCurrentAgent.fallback_provider || {};
  fRenderProviderOptions(dFallback.name || "", "vFallbackProviderInput", true);
  document.getElementById("vFallbackProviderInput").value = dFallback.name || "";
  document.getElementById("vFallbackModelInput").value = dFallback.model || "";
  document.getElementById("vFallbackBaseUrlInput").value = dFallback.base_url || "";
  fShowBaseUrlField("vFallbackBaseUrlField", dFallback.name || "");
  const dSelectedFallback = lAvailableProviders.find(function (dCandidate) {
    return dCandidate.name === (dFallback.name || "");
  });
  fRenderModelOptions(dSelectedFallback || {}, "vFallbackModelOptions",
                      "vFallbackModelHint");
  /* An agent saved before this check existed can already have the pair set
   * the same way, so the warning is worked out on load as well as on edit. */
  fUpdateFallbackWarning();

  fRenderToolCheckboxes(dCurrentAgent.tools || []);
  fRenderSkillCheckboxes(dCurrentAgent.skills || []);
  fRenderChannelCheckboxes(dCurrentAgent.channels || []);
  fRenderUsage(dResult.usage || {});
  fLoadRunHistory(dCurrentAgent.id);

  /* Every field now holds what the server sent, which is what the next Save
   * is compared against. Taken here and not in fSaveAgent, because Save also
   * reloads the agent and would otherwise compare against itself. */
  fRememberAgentForm();

  /* Clicking an agent opens its chat; the wrench opens its settings. */
  const vMode = fGetAgentMode();
  const vIsNew = fIsNewAgent();
  vEmptyState.hidden = true;
  vHeaderActions.hidden = false;
  document.getElementById("vClearChatButton").hidden = vMode !== "chat";

  /* A brand new agent has nothing worth keeping yet, so Discard becomes
   * Cancel, and Cancel deletes it. */
  document.getElementById("vReloadAgentButton").hidden = vIsNew;
  document.getElementById("vCancelNewAgentButton").hidden = !vIsNew;

  if (vMode === "settings") {
    vForm.hidden = false;
    vChatPanel.hidden = true;
    fSelectAgentTab(fGetAgentSettingsTab());
    fStopChatPolling();
  } else {
    vForm.hidden = true;
    vChatPanel.hidden = false;
    vLastRenderedChatSignature = "";
    const vPending = await fRefreshChat(pAgentId);
    if (vPending) { fStartChatPolling(pAgentId); }
    document.getElementById("vChatInput").focus();
  }
}

function fCollectGranted(pPrefix, lCandidates, pKeyName) {
  const lGranted = [];
  lCandidates.forEach(function (dCandidate) {
    const vName = dCandidate[pKeyName];
    const vInput = document.getElementById(pPrefix + vName.replace(/\./g, "_"));
    if (vInput && vInput.checked) { lGranted.push(vName); }
  });
  return lGranted;
}

function fRenderMemory(pMemory) {
  document.getElementById("vMemoryInput").value = pMemory;
  document.getElementById("vMemorySize").textContent =
    fTranslate("agents.memorySize", "{count} characters. All of it is sent on every call.")
      .replace("{count}", pMemory.length);
}

/* What this form would send if it were saved right now.
 *
 * One function, called both to save and to take the snapshot the next Save is
 * compared against: two readers of the same form that drifted apart would
 * report "no changes" on a field one of them never looked at, which is the
 * worst possible way to be wrong about it.
 */
function fCollectAgentPayload() {
  const dInfo = {
    name: document.getElementById("vNameInput").value,
    description: document.getElementById("vDescriptionInput").value,
    enabled: document.getElementById("vEnabledInput").checked,
    kanban_enabled: document.getElementById("vKanbanEnabledInput").checked,
    tools: fCollectGranted("vTool_", lAvailableTools, "name"),
    skills: fCollectGranted("vSkill_", lAvailableSkills, "id"),
    channels: fCollectGranted("vChannel_", lAvailableChannels, "name"),
    provider: {
      name: document.getElementById("vProviderInput").value,
      model: document.getElementById("vModelInput").value,
      base_url: document.getElementById("vBaseUrlInput").value,
    },
    fallback_provider: {
      name: document.getElementById("vFallbackProviderInput").value,
      model: document.getElementById("vFallbackModelInput").value,
      base_url: document.getElementById("vFallbackBaseUrlInput").value,
    },
    limits: {
      max_tokens_per_run: Number(document.getElementById("vMaxTokensInput").value),
      max_steps_per_run: Number(document.getElementById("vMaxStepsInput").value),
      timeout_seconds: Number(document.getElementById("vTimeoutInput").value),
      max_runs_per_day: Number(document.getElementById("vMaxRunsInput").value),
    },
  };

  return {
    info: dInfo,
    system_prompt: document.getElementById("vSystemPromptInput").value,
    crontab: document.getElementById("vCrontabInput").value,
    memory: document.getElementById("vMemoryInput").value,
  };
}

/* The form as it was loaded, or as it was last saved. */
let vAgentBaseline = null;

function fRememberAgentForm() {
  vAgentBaseline = JSON.stringify(fCollectAgentPayload());
}

async function fSaveAgent(pEvent) {
  pEvent.preventDefault();
  if (!dCurrentAgent) { return; }

  const dPayload = fCollectAgentPayload();

  /* A new agent is saved even when nothing was touched: the form is holding
   * the example's own values, pressing Save is how they are accepted, and it
   * is what takes the user to the chat. Everywhere else, a Save that would
   * write the same values says so instead. */
  if (!fIsNewAgent() && fIsUnchanged(vAgentBaseline, dPayload)) {
    fShowNothingToSave();
    return;
  }

  try {
    await fCallApi("/agents/" + encodeURIComponent(dCurrentAgent.id), "PUT",
                   dPayload);

    if (fIsNewAgent()) {
      /* It is configured now, so it stops being new and the chat is what the
       * user actually wanted. */
      window.location.href = fBuildAgentUrl(dCurrentAgent.id, "chat");
      return;
    }

    fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
    await fRenderSidebar();
    await fLoadAgent(dCurrentAgent.id);
  } catch (vError) {
    fShowError(vError);
  }
}

async function fCancelNewAgent() {
  if (!dCurrentAgent) { return; }
  const vConfirmed = await fConfirm({
    title: fTranslate("agents.cancelNew", "Cancel and delete this agent"),
    message: fTranslate("agents.cancelNewConfirm",
      "Cancel? This deletes the agent that was just created, along with its " +
      "Linux user and its home directory."),
    confirmLabel: fTranslate("common.delete", "Delete"),
    danger: true,
  });
  if (!vConfirmed) { return; }
  try {
    await fCallApi("/agents/" + encodeURIComponent(dCurrentAgent.id), "DELETE");
    window.location.href = "/";
  } catch (vError) {
    fShowError(vError);
  }
}

async function fRunAgentNow() {
  if (!dCurrentAgent) { return; }
  try {
    await fCallApi("/agents/" + encodeURIComponent(dCurrentAgent.id) + "/run", "POST");
    fShowNotice(
      fTranslate("agents.runStarted", "Run started. It may take a few minutes."), "ok"
    );
    fRefreshAgentActivity();
  } catch (vError) {
    fShowError(vError);
  }
}

async function fDeleteAgent() {
  if (!dCurrentAgent) { return; }
  /* Typing the name is deliberate friction: this deletes a Linux user and a
   * home directory, and a single misplaced click should not be enough. */
  const vConfirmation = await fPrompt({
    title: fTranslate("agents.delete", "Delete"),
    message: fTranslate("agents.deleteConfirm",
      "This deletes the agent, its Linux user, its home directory and its crontab. " +
      "It cannot be undone. Type the agent name to confirm:"),
    placeholder: dCurrentAgent.name,
    confirmLabel: fTranslate("common.delete", "Delete"),
    danger: true,
  });
  if (vConfirmation !== dCurrentAgent.name) {
    if (vConfirmation !== null) {
      fShowNotice(fTranslate("agents.deleteCancelled", "Name did not match. Nothing was deleted."), "error");
    }
    return;
  }
  try {
    await fCallApi("/agents/" + encodeURIComponent(dCurrentAgent.id), "DELETE");
    window.location.href = "/";
  } catch (vError) {
    fShowError(vError);
  }
}

document.addEventListener("DOMContentLoaded", async function () {
  await fWaitForTranslations();
  document.getElementById("vAgentForm").addEventListener("submit", fSaveAgent);
  document.getElementById("vChatForm").addEventListener("submit", fSendChatMessage);
  document.getElementById("vClearChatButton").addEventListener("click", fClearChat);

  document.getElementById("vCancelNewAgentButton")
    .addEventListener("click", fCancelNewAgent);

  document.querySelectorAll("[data-agent-tab]").forEach(function (vButton) {
    vButton.addEventListener("click", function () {
      fSelectAgentTab(vButton.getAttribute("data-agent-tab"));
    });
  });

  /* With "send on Enter" on - the default - Enter sends and Shift+Enter breaks
   * the line, which is what fingers expect. With it off, Enter just breaks the
   * line and the button is the only way to send. */
  document.getElementById("vChatInput").addEventListener("keydown", function (pEvent) {
    if (pEvent.key !== "Enter") { return; }
    if (!fGetSendOnEnter()) { return; }
    if (pEvent.shiftKey) { return; }
    pEvent.preventDefault();
    document.getElementById("vChatForm").requestSubmit();
  });
  document.getElementById("vRunNowButton").addEventListener("click", fRunAgentNow);
  document.getElementById("vDeleteAgentButton").addEventListener("click", fDeleteAgent);
  document.getElementById("vReloadAgentButton").addEventListener("click", function () {
    fLoadAgent(fGetSelectedAgentId());
  });

  await fRenderSidebar();
  try {
    await fLoadReferenceData();
  } catch (vError) {
    fShowError(vError);
  }
  await fLoadAgent(fGetSelectedAgentId());
});
