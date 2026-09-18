/* The tools page: what is installed on the server.
 *
 * One tab per family rather than one long list. There are fifteen tools now
 * and each one carries a table of arguments, so the flat list was several
 * screens of scrolling to find out whether `mail.move` exists.
 *
 * The families are whatever is installed in /opt/boa/tools/, so the tabs are
 * built here and not written into the template. The open one lives in the URL
 * (`/tools/?family=mail`), like every other set of tabs in the application:
 * a reload, a bookmark and the back button all keep the section.
 */

/* Families with no heading of their own share one tab. A file somebody
 * dropped into /opt/boa/tools/ is still a tool all the way to the interface,
 * so its family is named on its own box inside that tab - but it does not get
 * a tab of its own, or the row would grow with every one-off script. */
const cOtherFamily = "other";

let ldLoadedTools = [];

function fGetToolFamily(dTool) {
  return String(dTool.name || "").split(".")[0];
}

/* Known families in the order their headings read, then Others last: it is
 * the catch-all, and a catch-all in the middle of the row reads as a family
 * of its own. */
function fGroupLoadedTools() {
  const dGroups = {};
  ldLoadedTools.forEach(function (dTool) {
    const vSection = fGetToolSection(fGetToolFamily(dTool));
    const vKey = fIsKnownToolSection(vSection) ? vSection : cOtherFamily;
    if (!dGroups[vKey]) { dGroups[vKey] = []; }
    dGroups[vKey].push(dTool);
  });

  const lKnown = Object.keys(dGroups).filter(function (vKey) {
    return vKey !== cOtherFamily;
  }).map(function (vKey) {
    return { family: vKey, title: fDescribeToolFamilyName(vKey),
             tools: dGroups[vKey] };
  }).sort(function (dLeft, dRight) {
    return dLeft.title.localeCompare(dRight.title);
  });

  if (dGroups[cOtherFamily]) {
    lKnown.push({
      family: cOtherFamily,
      title: fTranslate("tools.familyOther", "Others"),
      tools: dGroups[cOtherFamily],
    });
  }
  return lKnown;
}

function fGetCurrentFamily(lGroups) {
  const vAsked = new URLSearchParams(window.location.search).get("family");
  const lNames = lGroups.map(function (dGroup) { return dGroup.family; });
  return lNames.indexOf(vAsked) !== -1 ? vAsked : (lNames[0] || "");
}

function fBuildToolPanel(dTool, pShowFamily) {
  const vPanel = fCreateElement("div", "panel");
  const vTitle = fCreateElement("h2", "panel-title", dTool.name);
  /* Inside Others the family is the only thing that says where a tool came
   * from, so it is named on the box: the tab cannot name it for six of them
   * at once. */
  if (pShowFamily) {
    vTitle.appendChild(fCreateElement("span", "tool-family-tag",
                                      fGetToolFamily(dTool)));
  }
  vPanel.appendChild(vTitle);
  vPanel.appendChild(fCreateElement("p", "panel-hint", fDescribeTool(dTool)));

  const lProperties = Object.keys((dTool.schema && dTool.schema.properties) || {});
  if (lProperties.length > 0) {
    const vWrap = fCreateElement("div", "table-wrap");
    const vTable = document.createElement("table");
    const vHead = document.createElement("thead");
    const vHeadRow = document.createElement("tr");
    [
      fTranslate("tools.argument", "Argument"),
      fTranslate("tools.type", "Type"),
      fTranslate("tools.required", "Required"),
      fTranslate("tools.meaning", "Meaning"),
    ].forEach(function (vLabel) {
      vHeadRow.appendChild(fCreateElement("th", "", vLabel));
    });
    vHead.appendChild(vHeadRow);
    vTable.appendChild(vHead);

    const vBody = document.createElement("tbody");
    const lRequired = dTool.schema.required || [];
    lProperties.forEach(function (vProperty) {
      const dProperty = dTool.schema.properties[vProperty];
      const vRow = document.createElement("tr");
      vRow.appendChild(fCreateElement("td", "", vProperty));
      vRow.appendChild(fCreateElement("td", "", dProperty.type || ""));
      vRow.appendChild(fCreateElement(
        "td", "",
        lRequired.indexOf(vProperty) !== -1
          ? fTranslate("tools.yes", "yes") : ""
      ));
      vRow.appendChild(fCreateElement(
        "td", "", fDescribeToolArgument(dTool, vProperty, dProperty.description)));
      vBody.appendChild(vRow);
    });
    vTable.appendChild(vBody);
    vWrap.appendChild(vTable);
    vPanel.appendChild(vWrap);
  }
  return vPanel;
}

function fSelectToolFamily(pFamily, pUpdateHistory) {
  const lGroups = fGroupLoadedTools();
  const vFamily = lGroups.some(function (dGroup) {
    return dGroup.family === pFamily;
  }) ? pFamily : fGetCurrentFamily(lGroups);

  document.querySelectorAll("#vToolTabs .tab").forEach(function (vButton) {
    vButton.setAttribute("aria-selected",
      vButton.getAttribute("data-family") === vFamily ? "true" : "false");
  });

  if (pUpdateHistory) {
    const vQuery = new URLSearchParams(window.location.search);
    vQuery.set("family", vFamily);
    window.history.replaceState({}, "", "?" + vQuery.toString());
  }

  const vList = document.getElementById("vToolList");
  fClear(vList);
  const dGroup = lGroups.filter(function (dEntry) {
    return dEntry.family === vFamily;
  })[0];
  if (!dGroup) { return; }

  dGroup.tools.slice().sort(function (dLeft, dRight) {
    return dLeft.name.localeCompare(dRight.name);
  }).forEach(function (dTool) {
    vList.appendChild(fBuildToolPanel(dTool, vFamily === cOtherFamily));
  });
}

function fRenderToolTabs() {
  const vTabs = document.getElementById("vToolTabs");
  fClear(vTabs);
  const lGroups = fGroupLoadedTools();

  /* One family is not a choice, so there is nothing to choose between: the
   * row would be a single button that does nothing. */
  vTabs.hidden = lGroups.length < 2;

  lGroups.forEach(function (dGroup) {
    const vButton = fCreateElement("button", "tab", dGroup.title);
    vButton.type = "button";
    vButton.setAttribute("role", "tab");
    vButton.setAttribute("data-family", dGroup.family);
    vButton.appendChild(fCreateElement("span", "tab-count",
                                       String(dGroup.tools.length)));
    vButton.addEventListener("click", function () {
      fSelectToolFamily(dGroup.family, true);
    });
    vTabs.appendChild(vButton);
  });
}

async function fRenderTools() {
  const vList = document.getElementById("vToolList");
  const vErrors = document.getElementById("vToolErrors");
  let dResult;
  try {
    dResult = await fCallApi("/tools");
  } catch (vError) {
    fShowError(vError);
    return;
  }

  fClear(vErrors);
  (dResult.errors || []).forEach(function (vMessage) {
    vErrors.appendChild(fCreateElement("div", "notice notice-error", vMessage));
  });

  ldLoadedTools = dResult.tools || [];
  fClear(vList);
  if (ldLoadedTools.length === 0) {
    document.getElementById("vToolTabs").hidden = true;
    vList.appendChild(fCreateElement(
      "p", "empty", fTranslate("tools.none", "No tools installed on the server.")
    ));
    return;
  }

  fRenderToolTabs();
  fSelectToolFamily(fGetCurrentFamily(fGroupLoadedTools()), false);
}

document.addEventListener("DOMContentLoaded", async function () {
  await fWaitForTranslations();
  await fRenderSidebar();
  await fRenderTools();
});
