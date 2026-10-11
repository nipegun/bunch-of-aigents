/* Scripts are saved individually, as the selected agent. Code is always text. */

let vScriptsAgentId = "";
let vScriptsGeneration = 0;
let vScriptsListRequest = 0;
let vScriptRowSequence = 0;
let dScriptRows = new Map();
const cNewScriptCode = "#!/bin/bash\n\n";

function fResetScripts() {
  vScriptsGeneration += 1;
  vScriptsListRequest += 1;
  vScriptsAgentId = "";
  dScriptRows = new Map();
  document.getElementById("vScriptsList").replaceChildren();
  document.getElementById("vScriptsStatus").textContent = "";
  document.getElementById("vScriptsDirectory").textContent = "";
  document.getElementById("vScriptsSort").value = "name-asc";
  fCloseNewScript();
}

function fScriptsAreCurrent(pAgentId, pGeneration) {
  return vScriptsAgentId === pAgentId && vScriptsGeneration === pGeneration
    && dCurrentAgent && dCurrentAgent.id === pAgentId;
}

function fScriptUrl(pAgentId, pName) {
  return "/agents/" + encodeURIComponent(pAgentId) + "/scripts"
    + (pName === undefined ? "" : "/" + encodeURIComponent(pName));
}

function fScriptButton(pKey, pFallback, pHandler, pPrimary) {
  const vButton = fCreateElement("button", "button" + (pPrimary ? " button-primary" : ""),
    fTranslate(pKey, pFallback));
  vButton.type = "button";
  vButton.dataset.i18n = pKey;
  vButton.addEventListener("click", pHandler);
  return vButton;
}

function fSetScriptExpanded(pRow, pExpanded) {
  pRow.body.hidden = !pExpanded;
  pRow.toggle.setAttribute("aria-expanded", String(pExpanded));
  pRow.toggle.dataset.i18n = pExpanded ? "scripts.hide" : "scripts.show";
  pRow.toggle.textContent = pExpanded
    ? fTranslate("scripts.hide", "Hide code") : fTranslate("scripts.show", "Show code");
}

function fSetScriptEditing(pRow, pEditing) {
  pRow.editing = pEditing;
  pRow.pre.hidden = pEditing;
  pRow.editor.hidden = !pEditing;
  pRow.edit.hidden = pEditing;
  pRow.save.hidden = !pEditing;
  pRow.cancel.hidden = !pEditing;
  if (pEditing) { pRow.editor.focus(); }
}

function fSetScriptContent(pRow, pScript) {
  pRow.content = pScript.content;
  pRow.revision = pScript.revision;
  pRow.bytes = pScript.bytes;
  pRow.modified = pScript.modified;
  pRow.pre.textContent = pScript.content;
  pRow.editor.value = pScript.content;
}

async function fToggleScript(pRow) {
  if (!pRow.body.hidden) {
    fSetScriptExpanded(pRow, false);
    return;
  }
  // Hiding code does not discard an editor's draft.
  if (pRow.editing) { fSetScriptExpanded(pRow, true); return; }
  pRow.toggle.disabled = true;
  try {
    const dScript = await fCallApi(fScriptUrl(pRow.agentId, pRow.name));
    if (!fScriptsAreCurrent(pRow.agentId, pRow.generation)) { return; }
    fSetScriptContent(pRow, dScript);
    fSetScriptExpanded(pRow, true);
  } catch (vError) {
    if (fScriptsAreCurrent(pRow.agentId, pRow.generation)) { fShowError(vError); }
  } finally {
    pRow.toggle.disabled = false;
  }
}

function fMakeScriptRow(pScript) {
  const dRow = Object.assign({}, pScript, {
    agentId: vScriptsAgentId, generation: vScriptsGeneration, editing: false,
  });
  const vId = "vScriptCode" + (++vScriptRowSequence);
  dRow.heading = fCreateElement("tr", "script-heading", "");
  dRow.heading.dataset.scriptName = dRow.name;
  const vNameCell = fCreateElement("td", "script-name-cell", "");
  vNameCell.appendChild(fCreateElement("code", "script-name", dRow.name));
  const vActions = fCreateElement("td", "script-toggle-cell", "");
  dRow.toggle = fScriptButton("scripts.show", "Show code", function () { fToggleScript(dRow); });
  dRow.toggle.setAttribute("aria-controls", vId);
  dRow.toggle.setAttribute("aria-expanded", "false");
  vActions.appendChild(dRow.toggle);
  dRow.heading.append(vNameCell, vActions);

  dRow.body = fCreateElement("tr", "script-body", "");
  dRow.body.id = vId;
  dRow.body.hidden = true;
  const vCell = fCreateElement("td", "", "");
  vCell.colSpan = 2;
  dRow.pre = fCreateElement("pre", "script-code", "");
  dRow.editor = fCreateElement("textarea", "script-code-input", "");
  dRow.editor.dir = "ltr";
  dRow.editor.spellcheck = false;
  dRow.editor.setAttribute("aria-label", dRow.name);
  dRow.editor.hidden = true;
  const vButtons = fCreateElement("div", "form-actions script-code-actions", "");
  dRow.edit = fScriptButton("scripts.edit", "Edit code", function () { fSetScriptEditing(dRow, true); });
  dRow.save = fScriptButton("scripts.save", "Save script", function () { fSaveScriptRow(dRow); }, true);
  dRow.cancel = fScriptButton("common.cancel", "Cancel", function () {
    dRow.editor.value = dRow.content;
    fSetScriptEditing(dRow, false);
  });
  dRow.hide = fScriptButton("scripts.hide", "Hide code", function () {
    fSetScriptExpanded(dRow, false);
    dRow.toggle.focus();
  });
  dRow.save.hidden = true;
  dRow.cancel.hidden = true;
  vButtons.append(dRow.edit, dRow.save, dRow.cancel, dRow.hide);
  vCell.append(dRow.pre, dRow.editor, vButtons);
  dRow.body.appendChild(vCell);
  return dRow;
}

function fSortScripts() {
  const [vField, vOrder] = document.getElementById("vScriptsSort").value.split("-");
  const vCollator = new Intl.Collator(document.documentElement.lang || "en-US", {sensitivity: "base"});
  const lRows = Array.from(dScriptRows.values());
  lRows.sort(function (pFirst, pSecond) {
    const vByName = vCollator.compare(pFirst.name, pSecond.name)
      || pFirst.name.localeCompare(pSecond.name);
    const vComparison = vField === "name" ? vByName : pFirst[vField] - pSecond[vField];
    return vComparison ? vComparison * (vOrder === "desc" ? -1 : 1) : vByName;
  });
  const vFragment = document.createDocumentFragment();
  lRows.forEach(function (dRow) { vFragment.append(dRow.heading, dRow.body); });
  document.getElementById("vScriptsList").replaceChildren(vFragment);
}

async function fLoadScripts(pAgentId) {
  if (vScriptsAgentId && vScriptsAgentId !== pAgentId) { fResetScripts(); }
  vScriptsAgentId = pAgentId;
  const vGeneration = vScriptsGeneration;
  const vRequest = ++vScriptsListRequest;
  const vStatus = document.getElementById("vScriptsStatus");
  vStatus.textContent = fTranslate("scripts.loading", "Loading scripts…");
  try {
    const dResult = await fCallApi(fScriptUrl(pAgentId));
    if (!fScriptsAreCurrent(pAgentId, vGeneration) || vRequest !== vScriptsListRequest) { return; }
    document.getElementById("vScriptsDirectory").textContent =
      fTranslate("scripts.directory", "Your agent keeps its scripts in {path}.")
        .replace("{path}", dResult.directory + "/");
    const dNextRows = new Map();
    (dResult.scripts || []).forEach(function (dScript) {
      const dRow = dScriptRows.get(dScript.name) || fMakeScriptRow(dScript);
      dRow.bytes = dScript.bytes;
      dRow.modified = dScript.modified;
      dNextRows.set(dScript.name, dRow);
    });
    // A file removed outside the page must not take an unsaved draft with it.
    dScriptRows.forEach(function (dRow, vName) {
      if (dRow.editing && !dNextRows.has(vName)) { dNextRows.set(vName, dRow); }
    });
    dScriptRows = dNextRows;
    fSortScripts();
    vStatus.textContent = dScriptRows.size ? "" : fTranslate("scripts.empty", "No scripts yet.");
  } catch (vError) {
    if (fScriptsAreCurrent(pAgentId, vGeneration) && vRequest === vScriptsListRequest) {
      vStatus.textContent = vError.message;
    }
  }
}

function fValidateScriptCode(pContent) {
  if (!pContent.trim()) { throw new Error(fTranslate("error.scriptEmpty", "Enter the script code.")); }
  const vLimit = Number(document.getElementById("vScriptsPanel").dataset.maxBytes);
  if (new TextEncoder().encode(pContent).length > vLimit) {
    throw new Error(fTranslate("error.scriptTooLarge", "The script exceeds {limit} bytes.").replace("{limit}", vLimit));
  }
}

async function fSaveScriptRow(pRow) {
  if (pRow.saving || !fScriptsAreCurrent(pRow.agentId, pRow.generation)) { return; }
  pRow.saving = true;
  pRow.save.disabled = true;
  pRow.cancel.disabled = true;
  pRow.editor.disabled = true;
  try {
    const vContent = pRow.editor.value;
    fValidateScriptCode(vContent);
    const dSaved = await fCallApi(fScriptUrl(pRow.agentId, pRow.name), "PUT", {
      content: vContent, revision: pRow.revision,
    });
    if (!fScriptsAreCurrent(pRow.agentId, pRow.generation)) { return; }
    vScriptsListRequest += 1;
    fSetScriptContent(pRow, dSaved);
    fSetScriptEditing(pRow, false);
    fSortScripts();
    document.getElementById("vScriptsStatus").textContent = "";
    fShowNotice(fTranslate("scripts.saved", "Script saved."), "ok");
  } catch (vError) {
    if (fScriptsAreCurrent(pRow.agentId, pRow.generation)) { fShowError(vError); }
  } finally {
    pRow.saving = false;
    pRow.save.disabled = false;
    pRow.cancel.disabled = false;
    pRow.editor.disabled = false;
  }
}

function fCloseNewScript() {
  document.getElementById("vNewScriptEditor").hidden = true;
  document.getElementById("vNewScriptName").value = "";
  document.getElementById("vNewScriptCode").value = cNewScriptCode;
  ["vCreateScriptButton", "vCancelScriptButton", "vNewScriptName", "vNewScriptCode"].forEach(function (vId) {
    document.getElementById(vId).disabled = false;
  });
}

async function fCreateScript() {
  const vAgentId = vScriptsAgentId;
  const vGeneration = vScriptsGeneration;
  const vButton = document.getElementById("vCreateScriptButton");
  if (vButton.disabled || !fScriptsAreCurrent(vAgentId, vGeneration)) { return; }
  try {
    const vName = document.getElementById("vNewScriptName").value.trim();
    const vContent = document.getElementById("vNewScriptCode").value;
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(vName)) {
      throw new Error(fTranslate("error.scriptNameInvalid", "Choose a valid script name."));
    }
    fValidateScriptCode(vContent);
    ["vCreateScriptButton", "vCancelScriptButton", "vNewScriptName", "vNewScriptCode"].forEach(function (vId) {
      document.getElementById(vId).disabled = true;
    });
    const dSaved = await fCallApi(fScriptUrl(vAgentId), "POST", {name: vName, content: vContent});
    if (!fScriptsAreCurrent(vAgentId, vGeneration)) { return; }
    vScriptsListRequest += 1;
    const dRow = fMakeScriptRow(dSaved);
    fSetScriptContent(dRow, dSaved);
    fSetScriptExpanded(dRow, true);
    dScriptRows.set(dSaved.name, dRow);
    fSortScripts();
    fCloseNewScript();
    document.getElementById("vScriptsStatus").textContent = "";
    fShowNotice(fTranslate("scripts.created", "Script created."), "ok");
    dRow.toggle.focus();
  } catch (vError) {
    if (fScriptsAreCurrent(vAgentId, vGeneration)) { fShowError(vError); }
  } finally {
    if (fScriptsAreCurrent(vAgentId, vGeneration)) {
      ["vCreateScriptButton", "vCancelScriptButton", "vNewScriptName", "vNewScriptCode"].forEach(function (vId) {
        document.getElementById(vId).disabled = false;
      });
    }
  }
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("vScriptsSort").addEventListener("change", fSortScripts);
  document.getElementById("vNewScriptButton").addEventListener("click", function () {
    document.getElementById("vNewScriptEditor").hidden = false;
    document.getElementById("vNewScriptName").focus();
  });
  document.getElementById("vCancelScriptButton").addEventListener("click", fCloseNewScript);
  document.getElementById("vCreateScriptButton").addEventListener("click", fCreateScript);
  document.getElementById("vNewScriptName").addEventListener("keydown", function (pEvent) {
    if (pEvent.key === "Enter") { pEvent.preventDefault(); fCreateScript(); }
  });
});
