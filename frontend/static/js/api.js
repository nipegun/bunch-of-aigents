/* Talking to /api/admin/.
 *
 * Every call goes through fCallApi, so a session that has expired produces one
 * redirect to the login page rather than a page full of silent failures.
 */

const cApiBase = "/api/admin";

async function fCallApi(pPath, pMethod, pBody) {
  const dOptions = {
    method: pMethod || "GET",
    headers: { "Accept": "application/json" },
    credentials: "same-origin",
  };
  if (pBody !== undefined) {
    dOptions.headers["Content-Type"] = "application/json";
    dOptions.body = JSON.stringify(pBody);
  }

  let vResponse;
  try {
    vResponse = await fetch(cApiBase + pPath, dOptions);
  } catch (vError) {
    throw new Error(fTranslate("error.unreachable", "Cannot reach the server."));
  }

  if (vResponse.status === 401) {
    window.location.href = "/login";
    throw new Error(fTranslate("error.notLoggedIn", "Not logged in"));
  }

  let dBody;
  try {
    dBody = await vResponse.json();
  } catch (vError) {
    throw new Error(fTranslate(
      "error.badResponse", "The server sent a response that is not JSON."));
  }

  if (!dBody.ok) {
    throw new Error(fDescribeApiError(dBody));
  }
  return dBody;
}

/* Turn an error the API returned into a sentence in the user's language.
 *
 * The API's own failures used to arrive as English prose and were shown as
 * they were: "The password must be at least 12 characters long" appeared in
 * the middle of a Spanish interface, because the only thing that crossed the
 * wire was the sentence.
 *
 * So a failure the interface has a wording for travels as a CODE plus its
 * parameters - the same shape a ceiling or a chat reason already travels in -
 * and the sentence is written here. `error` stays on the payload and is what
 * is shown when there is no code: a provider's own words, a mail server's
 * refusal, anything that came from outside and should not be invented a
 * translation for.
 */
function fDescribeApiError(dBody) {
  const vCode = dBody.code;
  if (vCode) {
    const vTemplate = fTranslate("error." + vCode, "");
    if (vTemplate) {
      return fFillParameters(vTemplate, dBody.params || {});
    }
  }
  return dBody.error || fTranslate("error.unknown", "Unknown error");
}

/* Replace {name} in a translated string with the values that came with it. */
function fFillParameters(pTemplate, dParameters) {
  let vText = String(pTemplate);
  Object.keys(dParameters || {}).forEach(function (vName) {
    vText = vText.split("{" + vName + "}").join(String(dParameters[vName]));
  });
  return vText;
}

/* Notices ------------------------------------------------------------------
 *
 * A saved message is a pop-up over the middle of the content column, not a
 * line at the top of it. The line was written where the user was not looking:
 * press Save at the bottom of the Tools tab of an agent and the confirmation
 * appeared several screens above, so saving looked like it did nothing.
 *
 * How long it stays is a preference of this browser, like the theme and the
 * language: three seconds is enough to read four words and too little to read
 * a sentence, and which of the two it is depends on the person.
 */

const cNoticeSecondsKey = "boa.noticeSeconds";
const cDefaultNoticeSeconds = 3;
const cMinNoticeSeconds = 1;
const cMaxNoticeSeconds = 30;

function fGetNoticeSeconds() {
  try {
    const vStored = Number(window.localStorage.getItem(cNoticeSecondsKey));
    if (!vStored) { return cDefaultNoticeSeconds; }
    return Math.max(cMinNoticeSeconds, Math.min(vStored, cMaxNoticeSeconds));
  } catch (vError) {
    /* Blocked storage means the default. */
    return cDefaultNoticeSeconds;
  }
}

function fSetNoticeSeconds(pSeconds) {
  const vSeconds = Math.max(cMinNoticeSeconds,
                            Math.min(Number(pSeconds) || cDefaultNoticeSeconds,
                                     cMaxNoticeSeconds));
  try {
    window.localStorage.setItem(cNoticeSecondsKey, String(vSeconds));
  } catch (vError) {
    /* A preference that cannot be stored applies to this page only. */
  }
  return vSeconds;
}

/* The close cross, drawn rather than typed.
 *
 * A "\u00d7" character sits wherever the font puts it: it is centred on the
 * maths axis, not in its own box, so it lands above the middle of the button
 * and no amount of centring the box moves it. Two lines in a square viewBox
 * are centred because the geometry says so, in every font and at every size.
 */
function fBuildCloseCross() {
  const cSvgNamespace = "http://www.w3.org/2000/svg";
  const vSvg = document.createElementNS(cSvgNamespace, "svg");
  vSvg.setAttribute("class", "notice-close-cross");
  vSvg.setAttribute("viewBox", "0 0 16 16");
  vSvg.setAttribute("aria-hidden", "true");
  vSvg.setAttribute("focusable", "false");

  [["4", "4", "12", "12"], ["12", "4", "4", "12"]].forEach(function (lPoints) {
    const vLine = document.createElementNS(cSvgNamespace, "line");
    vLine.setAttribute("x1", lPoints[0]);
    vLine.setAttribute("y1", lPoints[1]);
    vLine.setAttribute("x2", lPoints[2]);
    vLine.setAttribute("y2", lPoints[3]);
    vSvg.appendChild(vLine);
  });
  return vSvg;
}

/* The message on screen right now, so a second one replaces it instead of
 * stacking a pile of confirmations in the middle of the page. */
let dCurrentNotice = null;

function fHideNotice(pBox) {
  if (!pBox || !pBox.isConnected) { return; }
  if (pBox.vTimer) { window.clearTimeout(pBox.vTimer); }
  /* Removed after the fade rather than with it, so the message does not blink
   * out of existence the moment the timer runs down. */
  pBox.setAttribute("data-leaving", "1");
  window.setTimeout(function () { pBox.remove(); }, 200);
  if (dCurrentNotice === pBox) { dCurrentNotice = null; }
}

function fShowNotice(pMessage, pKind) {
  const vContainer = document.getElementById("vNotice");
  if (!vContainer) { return; }

  if (dCurrentNotice) { dCurrentNotice.remove(); }
  vContainer.innerHTML = "";

  const vBox = document.createElement("div");
  vBox.className = "notice notice-toast notice-" + (pKind || "ok");
  vBox.setAttribute("role", pKind === "error" ? "alert" : "status");

  const vText = document.createElement("div");
  vText.className = "notice-text";
  vText.textContent = pMessage;
  vBox.appendChild(vText);

  const vClose = document.createElement("button");
  vClose.type = "button";
  vClose.className = "notice-close";
  vClose.setAttribute("aria-label", fTranslate("common.close", "Close"));
  vClose.appendChild(fBuildCloseCross());
  vClose.addEventListener("click", function () { fHideNotice(vBox); });
  vBox.appendChild(vClose);

  vContainer.appendChild(vBox);
  dCurrentNotice = vBox;

  /* An error waits to be read and closed. Anything else goes on its own,
   * after the number of seconds this browser is set to. */
  if (pKind !== "error") {
    vBox.vTimer = window.setTimeout(function () {
      fHideNotice(vBox);
    }, fGetNoticeSeconds() * 1000);
  }
  return vBox;
}

function fShowError(pError) {
  fShowNotice(pError && pError.message ? pError.message : String(pError), "error");
}

/* A language file that will not load is now said out loud.
 *
 * i18n.js falls back to en-US when a catalogue 404s or will not parse, which
 * keeps the page readable and the `lang` attribute honest - and on its own
 * that is a language change that silently did nothing. The handler lives here
 * because this file has fShowNotice and i18n.js, which loads first, must not
 * depend on it.
 *
 * The message is deliberately not translated by key: the catalogue that would
 * hold that key is the one that failed to load. */
if (typeof fSetLoadFailureHandler === "function") {
  fSetLoadFailureHandler(function (pLanguage) {
    fShowNotice(
      "Could not load the " + pLanguage + " strings. Showing en-US.", "error");
  });
}

/* Pressing Save with nothing to save.
 *
 * Amber, and not the green of a save that happened: "Settings saved" after a
 * Save that wrote nothing is a sentence that is not true, and it is the one
 * sentence that would stop somebody noticing their edit never took. Not red
 * either - nothing went wrong, nothing happened.
 *
 * Here rather than on either page, because both say it and neither loads the
 * other's script.
 */
function fShowNothingToSave() {
  fShowNotice(fTranslate("common.nothingToSave", "No changes to save"), "warn");
}

/* Whether a form still holds what it held when it was loaded or last saved.
 * Compared as JSON so that the check is the whole payload rather than a list
 * of fields somebody has to remember to extend. */
function fIsUnchanged(pBaseline, pValues) {
  return pBaseline !== null && pBaseline === JSON.stringify(pValues);
}

/* Escape closes whatever is up, for the same reason the dialogs take it: a
 * box in the middle of the screen has to be dismissable without aiming. */
document.addEventListener("keydown", function (pEvent) {
  if (pEvent.key === "Escape" && dCurrentNotice) {
    fHideNotice(dCurrentNotice);
  }
});

/* Small DOM helpers -------------------------------------------------------- */

function fCreateElement(pTag, pClassName, pText) {
  const vElement = document.createElement(pTag);
  if (pClassName) { vElement.className = pClassName; }
  /* textContent, never innerHTML: card titles and agent names come from a
   * model and from the network, and neither is trusted markup. */
  if (pText !== undefined && pText !== null) { vElement.textContent = pText; }
  return vElement;
}

function fClear(pElement) {
  while (pElement.firstChild) { pElement.removeChild(pElement.firstChild); }
}

/* Sidebar ------------------------------------------------------------------ */

function fGetSelectedAgentId() {
  return new URLSearchParams(window.location.search).get("agent") || "";
}

/* Clicking an agent opens its chat; the wrench opens its settings. The mode
 * lives in the URL so a reload, a bookmark and the back button all keep it. */
function fGetAgentMode() {
  return new URLSearchParams(window.location.search).get("mode") === "settings"
    ? "settings" : "chat";
}

function fIsNewAgent() {
  return new URLSearchParams(window.location.search).get("new") === "1";
}

function fBuildAgentUrl(pAgentId, pMode) {
  const vQuery = new URLSearchParams({ agent: pAgentId });
  if (pMode === "settings") { vQuery.set("mode", "settings"); }
  return "/?" + vQuery.toString();
}

/* The wrench, drawn inline: the content security policy allows no external
 * origin, so there is no icon font and no CDN sprite to load. */
function fBuildWrenchIcon() {
  const cSvgNamespace = "http://www.w3.org/2000/svg";
  const vSvg = document.createElementNS(cSvgNamespace, "svg");
  vSvg.setAttribute("viewBox", "0 0 24 24");
  vSvg.setAttribute("width", "16");
  vSvg.setAttribute("height", "16");
  vSvg.setAttribute("aria-hidden", "true");
  vSvg.setAttribute("focusable", "false");

  const vPath = document.createElementNS(cSvgNamespace, "path");
  vPath.setAttribute("d",
    "M20.3 4.9a1 1 0 0 0-1.6-.3l-2.6 2.6-2.3-.4-.4-2.3 2.6-2.6a1 1 0 0 0-.3-1.6" +
    "A6 6 0 0 0 7.9 8.2L2.6 13.5a3.1 3.1 0 0 0 4.4 4.4l5.3-5.3a6 6 0 0 0 8-7.7z");
  vPath.setAttribute("fill", "currentColor");
  vSvg.appendChild(vPath);
  return vSvg;
}

/* The ring around the avatar carries two different facts, and they are drawn
 * differently on purpose: whether the agent is switched on is a colour (green
 * or red, and it does not move), whether it is working right now is movement
 * (the green ring turns clockwise). Colour tells the user what the agent is;
 * movement tells them what it is doing. A second static colour for "busy"
 * would have to be learnt, whereas something turning is read without being
 * taught. */
/* The travelling light, drawn inline for the same reason as the wrench: the
 * content security policy allows no external origin.
 *
 * An SVG rounded rectangle rather than a CSS ring, because it has to follow
 * the avatar's own outline. A rect laid over the border and stroked with a
 * dash keeps its shape still while the dash travels along it; anything
 * rotated turns the shape itself and stops matching the square underneath.
 *
 * The geometry is the avatar's: 28px across with a 2px border and a 7px
 * radius, so the stroke's centre line is inset by 1px and its radius is 6px.
 * `pathLength` rescales the outline to 100 units, which is what lets the
 * stylesheet talk in percentages of the perimeter.
 */
function fBuildAgentActivityArc() {
  const cSvgNamespace = "http://www.w3.org/2000/svg";
  const vSvg = document.createElementNS(cSvgNamespace, "svg");
  vSvg.setAttribute("class", "agent-avatar-arc");
  vSvg.setAttribute("viewBox", "0 0 28 28");
  vSvg.setAttribute("aria-hidden", "true");
  vSvg.setAttribute("focusable", "false");

  const vRect = document.createElementNS(cSvgNamespace, "rect");
  vRect.setAttribute("x", "1");
  vRect.setAttribute("y", "1");
  vRect.setAttribute("width", "26");
  vRect.setAttribute("height", "26");
  vRect.setAttribute("rx", "6");
  vRect.setAttribute("pathLength", "100");
  vSvg.appendChild(vRect);
  return vSvg;
}

function fSetAgentAvatarActivity(pAvatar, pEnabled, pRunning) {
  if (!pAvatar) { return; }
  const vRunning = pRunning === true;
  const vExistingArc = pAvatar.querySelector(".agent-avatar-arc");
  if (vRunning) {
    pAvatar.setAttribute("data-running", "true");
    /* Left alone when it is already there, so a refresh does not restart the
     * animation and leave the light jumping back to the corner. */
    if (!vExistingArc) { pAvatar.appendChild(fBuildAgentActivityArc()); }
  } else {
    pAvatar.removeAttribute("data-running");
    if (vExistingArc) { vExistingArc.remove(); }
  }
  /* Working beats on/off in the tooltip: a run in flight is the more
   * immediate fact, and an agent that is running is on by definition. */
  if (vRunning) {
    pAvatar.title = fTranslate("sidebar.working", "Working now");
  } else if (pEnabled) {
    pAvatar.title = fTranslate("sidebar.enabled", "Enabled");
  } else {
    pAvatar.title = fTranslate("sidebar.disabled", "Disabled");
  }
}

/* How often the sidebar asks who is busy. Faster than the status bar, because
 * this is the one thing on screen that does change from one moment to the
 * next; still slow enough that a page left open is not polling in a loop. */
const cAgentActivityRefreshMilliseconds = 5000;

/* Only the ring is repainted, never the list. Rebuilding the list on a timer
 * would take the focus off whatever the user was on and reset the scroll
 * position every few seconds, and an agent appearing or disappearing is not
 * something that happens on its own - it takes somebody pressing + or Delete,
 * and both of those redraw the sidebar themselves. */
async function fRefreshAgentActivity() {
  const vList = document.getElementById("vAgentList");
  if (!vList || document.hidden) { return; }
  let lAgents = [];
  try {
    const dResult = await fCallApi("/agents");
    lAgents = dResult.agents || [];
  } catch (vError) {
    /* Silent on purpose: this runs on a timer and nobody asked for it, so a
     * web application that is restarting must not fill the screen with
     * errors. The next pass picks it up again. */
    return;
  }
  lAgents.forEach(function (dAgent) {
    const vItem = vList.querySelector(
      '.agent-item[data-agent-id="' + dAgent.id + '"]');
    if (!vItem) { return; }
    fSetAgentAvatarActivity(
      vItem.querySelector(".agent-avatar"), dAgent.enabled, dAgent.running);
  });

  /* A page that cares about more than the rings gets told as well. The agent
   * page uses it to notice a run nobody on this screen started - a card that
   * came due - and to follow the conversation it opens. */
  if (typeof window.fOnAgentActivity === "function") {
    window.fOnAgentActivity(lAgents);
  }
}

/* The sidebar is redrawn on every page, because every page is a real page:
 * clicking Kanban asks the server for /kanban/ and the browser throws the old
 * document away, agent list included. That is the cost of having no build
 * step and no client-side router, and it is a cost worth paying - but it used
 * to show, because the list started as "Loading…" and only filled in once
 * /agents had answered.
 *
 * So the last list is kept in sessionStorage and drawn immediately, before the
 * request goes out. The page then looks continuous while navigating, and the
 * answer replaces it a moment later. sessionStorage and not localStorage: it
 * belongs to this tab and this session, and it goes when the tab does.
 *
 * It holds names and totals, which are on screen anyway - no tokens, no
 * configuration - and logging out clears it. */
const cSidebarCacheKey = "boa.sidebar";

function fReadSidebarCache() {
  try {
    const vStored = window.sessionStorage.getItem(cSidebarCacheKey);
    const lAgents = vStored ? JSON.parse(vStored) : null;
    return Array.isArray(lAgents) ? lAgents : null;
  } catch (vError) {
    /* Private window, storage disabled, or something else's data under our
     * key: the sidebar draws from the server either way. */
    return null;
  }
}

function fWriteSidebarCache(lAgents) {
  try {
    window.sessionStorage.setItem(cSidebarCacheKey, JSON.stringify(
      lAgents.map(function (dAgent) {
        return {
          id: dAgent.id, name: dAgent.name, enabled: dAgent.enabled,
          usage: dAgent.usage || {},
        };
      })));
  } catch (vError) {
    /* Storage full or refused. The sidebar still works; it just flashes. */
  }
}

function fClearSidebarCache() {
  try {
    window.sessionStorage.removeItem(cSidebarCacheKey);
  } catch (vError) {
    /* Nothing to do: if it cannot be removed it could not have been written. */
  }
}

async function fRenderSidebar() {
  const vList = document.getElementById("vAgentList");
  if (!vList) { return []; }

  /* Straight from the last page, so the list is there before the request is.
   * `running` is deliberately not cached: it is a fact about this instant, and
   * a ring left turning from the previous page would be a lie. */
  const lCached = fReadSidebarCache();
  if (lCached) { fDrawSidebar(vList, lCached); }

  let lAgents = [];
  try {
    const dResult = await fCallApi("/agents");
    lAgents = dResult.agents || [];
  } catch (vError) {
    fClear(vList);
    vList.appendChild(fCreateElement("li", "empty", vError.message));
    fClearSidebarCache();
    return [];
  }
  fWriteSidebarCache(lAgents);
  fDrawSidebar(vList, lAgents);
  return lAgents;
}

/* Draws one list of agents into the sidebar. Called twice per page:
 * once with what the last page saw, once with what the server says. */
function fDrawSidebar(vList, lAgents) {
  fClear(vList);
  if (lAgents.length === 0) {
    vList.appendChild(fCreateElement(
      "li", "empty",
      fTranslate("sidebar.noAgents", "No agents yet. Press + to create one.")
    ));
    return;
  }

  const vSelectedId = fGetSelectedAgentId();
  const vMode = fGetAgentMode();

  lAgents.forEach(function (dAgent) {
    const vItem = fCreateElement("li", "agent-item");
    vItem.setAttribute("data-agent-id", dAgent.id);
    if (dAgent.id === vSelectedId) { vItem.setAttribute("data-selected", "true"); }

    /* The box itself opens the chat. */
    const vButton = fCreateElement("button", "agent-button");
    vButton.type = "button";
    /* The name is cut to one line to keep every box the same height, so the
     * whole of it lives here instead. */
    vButton.title = dAgent.name;
    if (dAgent.id === vSelectedId) { vButton.setAttribute("aria-current", "true"); }

    const vAvatar = fCreateElement("span", "agent-avatar", dAgent.id);
    /* Green ring when the agent is on, red when it is off. */
    vAvatar.setAttribute("data-enabled", dAgent.enabled ? "true" : "false");
    fSetAgentAvatarActivity(vAvatar, dAgent.enabled, dAgent.running);
    vButton.appendChild(vAvatar);

    const vText = fCreateElement("div", "agent-text");
    vText.appendChild(fCreateElement("div", "agent-name", dAgent.name));
    const dUsage = dAgent.usage || {};
    const vRuns = dUsage.runs || 0;
    const vTokens = dUsage.total_tokens || 0;
    vText.appendChild(fCreateElement(
      "div", "agent-meta",
      fTranslate("sidebar.runs", "{runs} runs · {tokens} tokens")
        .replace("{runs}", vRuns).replace("{tokens}", vTokens)
    ));
    vButton.appendChild(vText);

    vButton.addEventListener("click", function () {
      window.location.href = fBuildAgentUrl(dAgent.id, "chat");
    });
    vItem.appendChild(vButton);

    /* The wrench opens the settings. A separate button, because one cannot be
     * nested inside another and because it needs its own label for anyone
     * navigating by keyboard or screen reader. */
    const vSettingsButton = fCreateElement("button", "agent-settings-button");
    vSettingsButton.type = "button";
    vSettingsButton.title = fTranslate("sidebar.settings", "Agent settings");
    vSettingsButton.setAttribute(
      "aria-label",
      fTranslate("sidebar.settingsFor", "Settings for {name}")
        .replace("{name}", dAgent.name)
    );
    /* Lit all the way round while this agent's settings are open, and pressing
     * it again goes back to the chat: the same button both ways, so there is
     * nothing to hunt for to get out. */
    const vIsOpen = dAgent.id === vSelectedId && vMode === "settings";
    vSettingsButton.setAttribute("aria-pressed", vIsOpen ? "true" : "false");
    vSettingsButton.appendChild(fBuildWrenchIcon());
    vSettingsButton.addEventListener("click", function (pEvent) {
      pEvent.stopPropagation();
      window.location.href = fBuildAgentUrl(dAgent.id, vIsOpen ? "chat" : "settings");
    });
    vItem.appendChild(vSettingsButton);

    vList.appendChild(vItem);
  });
}

/* The status bar ------------------------------------------------------------
 *
 * Everything here is true of the installation as a whole, which is why it sits
 * in one strip across the bottom rather than inside whichever page happens to
 * be open.
 */

const cStatusRefreshMilliseconds = 15000;

function fSetStatusItem(pElementId, pText, pState) {
  const vItem = document.getElementById(pElementId);
  if (!vItem) { return; }
  const vValue = vItem.querySelector(".status-value");
  if (vValue) { vValue.textContent = pText; }
  if (pState) { vItem.setAttribute("data-state", pState); }
}

function fSetStatusDot(pElementId, pUp) {
  const vItem = document.getElementById(pElementId);
  if (!vItem) { return; }
  const vDot = vItem.querySelector(".status-dot");
  if (vDot) { vDot.setAttribute("data-up", pUp ? "true" : "false"); }
  vItem.setAttribute("data-state", pUp ? "good" : "bad");
  vItem.title = pUp
    ? fTranslate("status.running", "Running")
    : fTranslate("status.down", "Not running");
}

async function fRefreshServiceStatus() {
  const vBar = document.getElementById("vStatusBar");
  if (!vBar) { return; }

  let dStatus;
  try {
    dStatus = (await fCallApi("/status")).status;
  } catch (vError) {
    fSetStatusDot("vStatusExecutor", false);
    fSetStatusDot("vStatusAgentApi", false);
    return;
  }

  fSetStatusDot("vStatusExecutor", dStatus.executor);
  fSetStatusDot("vStatusAgentApi", dStatus.agent_api);

  fSetStatusItem("vStatusAgents",
    fTranslate("status.agentsValue", "{enabled} of {total} on")
      .replace("{enabled}", dStatus.agents_enabled)
      .replace("{total}", dStatus.agents_total));

  const dBoard = dStatus.board || {};
  fSetStatusItem("vStatusBoard",
    fTranslate("status.boardValue", "{todo} to do · {doing} doing · {done} done")
      .replace("{todo}", dBoard.todo || 0)
      .replace("{doing}", dBoard.doing || 0)
      .replace("{done}", dBoard.done || 0));

  fSetStatusItem("vStatusTokens",
    fTranslate("status.tokensValue", "{tokens} in {runs} runs")
      .replace("{tokens}", (dStatus.tokens_today || 0).toLocaleString())
      .replace("{runs}", dStatus.runs_today || 0));
}

/* Whether the example agents are offered when creating one. Kept in this
 * browser, next to the theme and the language: it describes how this person
 * works on this machine, not anything about the installation. */
const cOfferExamplesKey = "boa.offerExamples";

function fGetOfferExamples() {
  try {
    return window.localStorage.getItem(cOfferExamplesKey) !== "0";
  } catch (vError) {
    /* Blocked storage means the default, which is to offer them. */
    return true;
  }
}

/* One line saying what an example comes with.
 *
 * Tools first, because that is the part that matters: an example is a set of
 * permissions as much as it is a prompt. They are listed by family rather
 * than one by one - "Email (4), Kanban (2)" is read at a glance, where nine
 * dotted names are not - and the schedule comes after, because an agent that
 * wakes itself up is worth knowing about before it does.
 */
function fDescribeTemplateTools(dTemplate) {
  const lTools = dTemplate.tools || [];
  const lParts = [];

  if (lTools.length > 0) {
    const dFamilies = {};
    lTools.forEach(function (vTool) {
      const vFamily = String(vTool).split(".")[0];
      dFamilies[vFamily] = (dFamilies[vFamily] || 0) + 1;
    });
    const lNames = Object.keys(dFamilies).map(function (vFamily) {
      return fDescribeToolFamilyName(vFamily) + " (" + dFamilies[vFamily] + ")";
    }).sort(function (vLeft, vRight) { return vLeft.localeCompare(vRight); });
    lParts.push(fTranslate("sidebar.templateTools", "Tools: {tools}")
      .replace("{tools}", lNames.join(", ")));
  }

  if (dTemplate.crontab) {
    lParts.push(fTranslate("sidebar.templateSchedule", "Wakes up: {schedule}")
      .replace("{schedule}", dTemplate.crontab));
  }
  return lParts.join(" · ");
}

/* The headings of the tool families, shared with the agent's Tools tab. Kept
 * here in api.js because both pages load it and neither loads the other's. */
/* A tool's family is the part of its name before the dot, and for most of
 * them that is also the section of the interface it belongs in. This maps the
 * exceptions: `web.fetch` and `rss.fetch` are two ways of reaching the same
 * place, and a section each would be two boxes with one tool in them saying
 * the same thing. A family with no entry here is its own section. */
const dToolSections = {
  cron: "automation",
  rss: "internet",
  script: "automation",
  web: "internet",
};

const dToolSectionNames = {
  automation: ["tools.familyAutomation", "Automation"],
  browser: ["tools.familyBrowser", "Browser"],
  bash: ["tools.familyBash", "Operating system"],
  channel: ["tools.familyChannel", "Channels"],
  image: ["tools.familyImage", "Images"],
  internet: ["tools.familyInternet", "Internet"],
  kanban: ["tools.familyKanban", "Kanban"],
  mail: ["tools.familyMail", "Email"],
  memory: ["tools.familyMemory", "Memory"],
  skill: ["tools.familySkill", "Skills"],
};

/* Names of things that are not ours to translate ---------------------------
 *
 * A channel and a provider are products with names their owners spell a
 * particular way, and "openai" or "vllm" in a box title reads as a database
 * column rather than as the thing it is. These are not i18n keys: DeepSeek is
 * DeepSeek in every language.
 *
 * What is not listed falls back to capitalising the first letter, which is
 * right for a plain name and wrong only for one that is spelled oddly - and a
 * channel or provider added later can be added here the day it looks wrong.
 */
const dChannelNames = {
  discord: "Discord",
  mattermost: "Mattermost",
  telegram: "Telegram",
  x: "X",
};

/* How each provider spells its own name. Anything not listed here is shown
 * capitalised, which is right for a provider whose name is one ordinary word
 * and wrong for the ones that write themselves in a particular way - which is
 * the whole reason for the list. */
const dProviderNames = {
  anthropic: "Anthropic",
  cerebras: "Cerebras",
  cloudflare: "Cloudflare Workers AI",
  cohere: "Cohere",
  deepinfra: "DeepInfra",
  deepseek: "DeepSeek",
  fireworks: "Fireworks AI",
  google: "Google",
  groq: "Groq",
  huggingface: "Hugging Face",
  inception: "Inception Labs",
  kimi: "Kimi",
  llamacpp: "llama.cpp",
  minimax: "MiniMax",
  mistral: "Mistral AI",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
  perplexity: "Perplexity",
  qwen: "Qwen",
  together: "Together AI",
  vercel: "Vercel AI Gateway",
  vllm: "vLLM",
  xai: "xAI",
  zai: "Z.ai",
};

/* Providers whose stored key is not a single opaque string. Not translated:
 * this is the shape of a credential, the same in every language, and getting
 * it wrong is a run that fails on its first call. */
const dProviderKeyFormats = {
  cloudflare: "account-id:api-token",
};

function fDescribeProviderKeyFormat(pName) {
  return dProviderKeyFormats[pName] || "";
}

function fCapitalise(pName) {
  const vName = String(pName || "");
  return vName ? vName.charAt(0).toUpperCase() + vName.slice(1) : vName;
}

function fDescribeChannelName(pName) {
  return dChannelNames[pName] || fCapitalise(pName);
}

function fDescribeProviderName(pName) {
  return dProviderNames[pName] || fCapitalise(pName);
}

/* What a tool and its arguments say, in the reader's language.
 *
 * The schema on the server stays in English and so does what is sent to the
 * model: an API whose field names are en-US described in Spanish would be a
 * translation of something that does not exist. This is only what a person
 * reads, under Settings > Tools and on an agent's Tools tab, and the two of them
 * ask through here so they cannot drift apart.
 *
 * The key is derived from the tool's own name, so a tool somebody dropped
 * into /opt/boa/tools/ has no translation and keeps its English - which is
 * what fTranslate does with a key it does not know, and the right answer for
 * a description nobody here wrote.
 */
function fDescribeTool(dTool) {
  return fTranslate("tools.desc." + dTool.name, dTool.description || "");
}

function fDescribeToolArgument(dTool, pArgument, pDescription) {
  return fTranslate("tools.arg." + dTool.name + "." + pArgument,
                    pDescription || "");
}

function fGetToolSection(pFamily) {
  return dToolSections[pFamily] || pFamily;
}

function fIsKnownToolSection(pSection) {
  return Object.prototype.hasOwnProperty.call(dToolSectionNames, pSection);
}

function fDescribeToolFamilyName(pFamily) {
  const vSection = fGetToolSection(pFamily);
  const lTitle = dToolSectionNames[vSection];
  return lTitle ? fTranslate(lTitle[0], lTitle[1]) : vSection;
}

/* The example agents live in backend/agents/examples/ on the server, one Markdown file
 * each, and a file dropped in there is a new example - there is no list in the
 * code to update. Chosen here, created by name: the server reads the file, so
 * the browser cannot hand a new agent tools or a schedule of its own. */
async function fChooseAgentTemplate() {
  if (!fGetOfferExamples()) { return ""; }

  let lTemplates = [];
  try {
    const dResult = await fCallApi("/agent-templates");
    lTemplates = dResult.templates || [];
  } catch (vError) {
    /* An example that cannot be listed is not a reason to stop somebody
     * creating an agent: fall through to the empty one. */
    return "";
  }
  if (lTemplates.length === 0) { return ""; }

  /* First, because it is the one choice that is always right: an example is a
   * shortcut to it, and somebody who already knows what they want should not
   * have to read nine of them to reach the plain one. The examples follow,
   * under it, in the order the server sent them. */
  const lChoices = [{
    id: "",
    name: fTranslate("sidebar.emptyAgent", "Empty agent"),
    description: fTranslate("sidebar.emptyAgentHint",
      "No prompt, no tools, no schedule. Write it yourself."),
  }];

  lTemplates.forEach(function (dTemplate) {
    lChoices.push({
      id: dTemplate.id,
      /* The NAME is the example's identifier - os-watcher, cert-watcher - and
       * stays as it is, like a tool's dotted name. The DESCRIPTION is a
       * sentence the user reads before choosing, and it came straight out of
       * the file's front matter in English whatever language the interface
       * was in. Translated by a key built from the id, with the file's own
       * English as the fallback: exactly what fDescribeTool does, so an
       * example somebody writes for their own installation keeps its own
       * words rather than disappearing. */
      name: dTemplate.name,
      description: fTranslate("template.desc." + dTemplate.id,
                              dTemplate.description),
      /* What it arrives able to do. An example is a set of permissions as
       * much as it is a prompt, and "Watches a mailbox" does not say that it
       * comes with mail.delete. Shown before the choice, not discovered
       * afterwards in the Tools tab. */
      detail: fDescribeTemplateTools(dTemplate),
    });
  });

  return await fChoose({
    title: fTranslate("sidebar.newAgent", "New agent"),
    message: fTranslate("sidebar.choosePrompt",
      "Start from an example, or from nothing. Either way you can change " +
      "everything afterwards, and nothing runs until you give it a model " +
      "and switch it on."),
    choices: lChoices,
  });
}

async function fCreateAgentFromPrompt() {
  const vTemplate = await fChooseAgentTemplate();
  /* null means the dialog was dismissed; "" means "empty agent". */
  if (vTemplate === null) { return; }

  const vName = await fPrompt({
    title: fTranslate("sidebar.newAgent", "New agent"),
    message: fTranslate("sidebar.namePrompt", "Name for the new agent:"),
    placeholder: fTranslate("sidebar.namePlaceholder", "News Miner"),
    confirmLabel: fTranslate("sidebar.create", "Create"),
    /* The example's own name, already filled in: it is the name most people
     * want, and it is still a field they can type over. */
    value: vTemplate || "",
  });
  if (!vName) { return; }
  try {
    const dResult = await fCallApi("/agents", "POST", {
      name: vName, template: vTemplate || undefined,
    });
    /* A new agent needs configuring before it is any use, so it opens straight
     * into its settings. `new=1` is what turns Discard into Cancel, which
     * deletes the agent again. */
    window.location.href =
      fBuildAgentUrl(dResult.agent_id, "settings") + "&new=1";
  } catch (vError) {
    fShowError(vError);
  }
}

async function fConfirmLogout() {
  const vConfirmed = await fConfirm({
    title: fTranslate("nav.logOut", "Log out"),
    message: fTranslate("nav.logOutConfirm", "Are you sure you want to log out?"),
    confirmLabel: fTranslate("nav.logOut", "Log out"),
  });
  if (vConfirmed) { window.location.href = "/logout"; }
}

document.addEventListener("DOMContentLoaded", function () {
  const vAddButton = document.getElementById("vAddAgentButton");
  if (vAddButton) { vAddButton.addEventListener("click", fCreateAgentFromPrompt); }

  const vLogoutButton = document.getElementById("vLogoutButton");
  if (vLogoutButton) { vLogoutButton.addEventListener("click", fConfirmLogout); }

  vTranslationsReady.then(fRefreshServiceStatus);
  /* Slow on purpose: nothing in the bar changes second to second, and an
   * interface that polls constantly keeps a laptop awake for nothing. */
  window.setInterval(fRefreshServiceStatus, cStatusRefreshMilliseconds);
  window.setInterval(fRefreshAgentActivity, cAgentActivityRefreshMilliseconds);
});
