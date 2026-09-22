/* Settings, in tabs.
 *
 * The tab lives in the URL rather than in a variable, so a reload, a bookmark
 * and the back button all land where the user was. Each panel loads its own
 * data the first time it is opened: reading the machine and listing the
 * channels are requests nobody needs until they look at that section.
 */

const cDefaultTab = "system";
const lTabs = ["system", "account", "email", "keys", "channels", "audio", "tools", "agents",
               "chat", "kanban", "interface"];
const sLoadedTabs = new Set();

const dChannelFields = {
  telegram: ["bot_token", "chat_id"],
  discord: ["bot_token", "channel_id", "webhook_url"],
  mattermost: ["webhook_url", "channel", "username"],
  x: ["bearer_token"],
};

/* Which of those are credentials. They are password boxes, the server never
 * sends them back, and an empty one means "leave it as it is". A webhook URL
 * is one: it authenticates by being known. Everything else is shown filled
 * in, because a channel pointed at the wrong chat looks exactly like a
 * channel that is not working. */
const lSecretChannelFields = ["bot_token", "webhook_url", "bearer_token"];

/* A line under the title, for a channel where the fields do not explain
 * themselves. Discord has two ways in and they are not equivalent. */
const dChannelHints = {
  discord: ["settings.channelHintDiscord",
            "A bot (bot_token and channel_id) sends and receives. " +
            "A webhook (webhook_url) only sends."],
};

/* Switches a channel can have, as opposed to values it is given. Telegram and
 * Discord are the channels messages can arrive through, and listening is
 * separate from sending on purpose: an installation can have agents that
 * write to a channel without anybody being able to write back. */
const dChannelSwitches = {
  telegram: [["listen", "settings.channelListenTelegram",
              "Let me answer agents from Telegram. Reply to an agent's message, " +
              "or start one with @name."]],
  discord: [["listen", "settings.channelListenDiscord",
             "Let me answer agents from Discord. Reply to an agent's message, " +
             "or start one with @name."]],
};

/* Interface preferences kept in this browser, next to the language. */
const cKanbanLimitKey = "boa.kanbanLimit";
const cShowDeletedKey = "boa.showDeleted";
const cShowChatCostKey = "boa.showChatCost";

function fReadPreference(pKey, pDefault) {
  try {
    const vStored = window.localStorage.getItem(pKey);
    if (vStored === null) { return pDefault; }
    return vStored;
  } catch (vError) {
    return pDefault;
  }
}

function fWritePreference(pKey, pValue) {
  try {
    window.localStorage.setItem(pKey, String(pValue));
  } catch (vError) {
    /* A preference that cannot be stored applies to this page only. */
  }
}

/* Tabs ---------------------------------------------------------------------- */

function fGetCurrentTab() {
  const vTab = new URLSearchParams(window.location.search).get("tab");
  return lTabs.indexOf(vTab) !== -1 ? vTab : cDefaultTab;
}

function fSelectTab(pTab, pUpdateHistory) {
  const vTab = lTabs.indexOf(pTab) !== -1 ? pTab : cDefaultTab;

  document.querySelectorAll("#vSettingsTabs .tab").forEach(function (vButton) {
    vButton.setAttribute("aria-selected",
      vButton.getAttribute("data-tab") === vTab ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel[data-panel]").forEach(function (vPanel) {
    vPanel.hidden = vPanel.getAttribute("data-panel") !== vTab;
  });

  if (pUpdateHistory) {
    const vQuery = new URLSearchParams(window.location.search);
    vQuery.set("tab", vTab);
    window.history.replaceState({}, "", "?" + vQuery.toString());
  }

  fLoadTab(vTab);
}

async function fLoadTab(pTab) {
  if (pTab === "audio") {
    try { await fLoadAudioSettings(); } catch (vError) { fShowError(vError); }
    return;
  }
  if (sLoadedTabs.has(pTab)) {
    if (pTab === "tools") {
      /* The language may have changed on the Interface tab. */
      fRenderToolTabs();
      fSelectToolFamily(fGetCurrentFamily(fGroupLoadedTools()), false);
    }
    return;
  }
  sLoadedTabs.add(pTab);
  try {
    if (pTab === "system") { await fRenderSystem(); }
    if (pTab === "keys") { await fRenderApiKeyForms(); }
    if (pTab === "channels") { await fRenderChannelForms(); }
    if (pTab === "tools") { await fRenderTools(); }
    if (pTab === "kanban") { await fRenderDeletedCards(); }
    if (pTab === "interface") { await fRenderThemeOptions(); }
    if (pTab === "agents") { await fLoadAgentSettings(); }
  } catch (vError) {
    sLoadedTabs.delete(pTab);
    fShowError(vError);
  }
}

/* Operating system ---------------------------------------------------------- */

function fFormatUptime(pSeconds) {
  const vDays = Math.floor(pSeconds / 86400);
  const vHours = Math.floor((pSeconds % 86400) / 3600);
  const vMinutes = Math.floor((pSeconds % 3600) / 60);
  if (vDays > 0) { return vDays + "d " + vHours + "h"; }
  if (vHours > 0) { return vHours + "h " + vMinutes + "m"; }
  return vMinutes + "m";
}

function fAddTableRow(pTableBody, pLabel, pValue, pState) {
  const vRow = document.createElement("tr");
  vRow.appendChild(fCreateElement("th", "", pLabel));
  const vCell = fCreateElement("td", "", pValue);
  if (pState) { vCell.setAttribute("data-state", pState); }
  vRow.appendChild(vCell);
  pTableBody.appendChild(vRow);
}

async function fRenderSystem() {
  const dResult = await fCallApi("/system");
  const dSystem = dResult.system;

  const vTable = document.getElementById("vSystemTable");
  fClear(vTable);

  fAddTableRow(vTable, fTranslate("settings.sysOs", "Operating system"),
    dSystem.os.name);
  fAddTableRow(vTable, fTranslate("settings.sysKernel", "Kernel"),
    dSystem.os.kernel + " · " + dSystem.os.architecture);
  fAddTableRow(vTable, fTranslate("settings.sysHost", "Hostname"),
    dSystem.os.hostname);
  fAddTableRow(vTable, fTranslate("settings.sysUptime", "Uptime"),
    fFormatUptime(dSystem.os.uptime_seconds));
  fAddTableRow(vTable, fTranslate("settings.sysTime", "Server time"),
    dSystem.os.time);

  const dMemory = dSystem.memory;
  fAddTableRow(vTable, fTranslate("settings.sysMemory", "Memory"),
    fTranslate("settings.sysMemoryValue",
      "{available} MB available of {total} MB · {percent}% in use")
      .replace("{available}", dMemory.available_mb)
      .replace("{total}", dMemory.total_mb)
      .replace("{percent}", dMemory.used_percent),
    dMemory.used_percent > 85 ? "bad" : "good");

  if (dMemory.swap_total_mb > 0) {
    fAddTableRow(vTable, fTranslate("settings.sysSwap", "Swap"),
      dMemory.swap_used_mb + " MB / " + dMemory.swap_total_mb + " MB");
  }

  const dLoad = dSystem.load;
  fAddTableRow(vTable, fTranslate("settings.sysLoad", "Load average"),
    dLoad.one + " · " + dLoad.five + " · " + dLoad.fifteen + "   " +
    fTranslate("settings.sysCores", "({cores} cores)")
      .replace("{cores}", dLoad.cores),
    dLoad.one > dLoad.cores ? "bad" : "good");

  const dDisk = dSystem.disk;
  fAddTableRow(vTable, fTranslate("settings.sysDisk", "Disk"),
    fTranslate("settings.sysDiskValue",
      "{free} GB free of {total} GB · {percent}% in use")
      .replace("{free}", dDisk.free_gb)
      .replace("{total}", dDisk.total_gb)
      .replace("{percent}", dDisk.used_percent),
    dDisk.used_percent > 85 ? "bad" : "good");

  fAddTableRow(vTable, fTranslate("settings.sysInstall", "Installation"),
    dSystem.installation.base_dir + " · " + dSystem.installation.size_mb + " MB");
  fAddTableRow(vTable, fTranslate("settings.sysPython", "Python"),
    dSystem.python.version);
  fAddTableRow(vTable, fTranslate("settings.sysPorts", "Ports"),
    dSystem.installation.https_port + " (HTTPS) · " +
    dSystem.installation.http_port + " (HTTP)");

  const vServices = document.getElementById("vServicesTable");
  fClear(vServices);
  dSystem.services.forEach(function (dService) {
    fAddTableRow(vServices, dService.name, dService.state,
      dService.active ? "good" : "bad");
  });
}

/* Themes --------------------------------------------------------------------- */

function fDescribeTheme(dTheme) {
  /* The NAME is not translated, and that part of the old comment still holds:
   * a theme is somebody's palette with a name, and translating "Nord" would
   * help nobody find it.
   *
   * The rest of the line is prose the user reads - "light", and a sentence
   * saying what the palette is for - and it stayed English in every language
   * because it came out of the CSS file as data. It is translated the same
   * way a tool's description is: by a key built from the identifier, with the
   * file's own English as the fallback. A theme somebody drops into the
   * themes directory has no key and keeps its English, which is the same
   * bargain the tools make. */
  if (!dTheme) { return ""; }
  const lParts = [];
  if (dTheme.scheme) {
    lParts.push(fTranslate("theme.scheme." + dTheme.scheme, dTheme.scheme));
  }
  if (dTheme.description) {
    lParts.push(fTranslate("theme.desc." + dTheme.id, dTheme.description));
  }
  return lParts.join(" · ");
}

async function fRenderThemeOptions() {
  const vSelect = document.getElementById("vThemeInput");
  const vHint = document.getElementById("vThemeHint");
  const dResult = await fCallApi("/themes");
  const lThemes = dResult.themes || [];
  const vCurrent = fGetTheme();

  fClear(vSelect);
  lThemes.forEach(function (dTheme) {
    const vOption = document.createElement("option");
    vOption.value = dTheme.id;
    vOption.textContent = dTheme.name;
    vSelect.appendChild(vOption);
  });

  /* A theme that was chosen and then uninstalled: say so rather than silently
   * showing the first one in the list, which would look like the choice was
   * never made. */
  if (!lThemes.some(function (dTheme) { return dTheme.id === vCurrent; })) {
    const vOption = document.createElement("option");
    vOption.value = vCurrent;
    vOption.textContent = vCurrent + " " +
      fTranslate("settings.themeMissing", "(not installed)");
    vSelect.appendChild(vOption);
  }
  vSelect.value = vCurrent;

  function fShowDescription() {
    vHint.textContent = fDescribeTheme(lThemes.find(function (dTheme) {
      return dTheme.id === vSelect.value;
    }));
  }
  fShowDescription();

  vSelect.addEventListener("change", function () {
    /* Applied on the spot but not stored: a theme is the one setting whose
     * result the user can judge only by looking at it, and Discard has to be
     * able to take it back. The panel's own change handler does the applying;
     * this only keeps the description under the picker honest. */
    fShowDescription();
  });

  /* The picker is filled in here, so the panel's baseline can only be taken
   * once that has happened. */
  fLoadPreferencePanel("interface");
}


/* API keys ------------------------------------------------------------------ */

async function fRenderApiKeyForms() {
  const vContainer = document.getElementById("vApiKeyForms");
  const dResult = await fCallApi("/keys");
  const lSelfHosted = dResult.self_hosted || [];

  fClear(vContainer);
  (dResult.keys || []).forEach(function (dKey) {
    /* Self-hosted providers need no key, so offering a box for one would only
     * invite somebody to fill it in. */
    if (lSelfHosted.indexOf(dKey.provider) !== -1) { return; }

    const vForm = document.createElement("form");
    vForm.className = "panel channel-form";

    vForm.appendChild(
      fCreateElement("h2", "panel-title", fDescribeProviderName(dKey.provider)));

    /* Green when a key is stored: with eight providers listed one under the
     * other, "is this one set up?" is the only question this line answers, and
     * a colour answers it without reading. No red for the empty ones - most
     * installations use one or two providers, and a screen of red would be
     * reporting a problem that is not there. */
    const vKeyState = fCreateElement("p", "field-hint",
      dKey.configured
        ? fTranslate("settings.keySet", "A key is stored, ending in {hint}.")
            .replace("{hint}", dKey.hint)
        : fTranslate("settings.keyMissing", "No key stored."));
    if (dKey.configured) { vKeyState.setAttribute("data-state", "good"); }
    vForm.appendChild(vKeyState);

    const vField = fCreateElement("div", "field");
    const vLabel = document.createElement("label");
    vLabel.textContent = fTranslate("settings.keyLabel", "API key");
    vLabel.setAttribute("for", "vApiKey_" + dKey.provider);
    vField.appendChild(vLabel);

    const vInput = document.createElement("input");
    vInput.id = "vApiKey_" + dKey.provider;
    vInput.type = "password";
    vInput.autocomplete = "off";
    /* The key never comes back from the server, so an empty box means "leave
     * it as it is" rather than "delete it".
     *
     * One provider stores two values in one box - Cloudflare needs the
     * account id as well as the token, because its address is built from it -
     * and the box says so rather than leaving it to be discovered on the
     * first failed run. */
    const vKeyFormat = fDescribeProviderKeyFormat(dKey.provider);
    vInput.placeholder = dKey.configured
      ? "••••••••"
      : (vKeyFormat
          || fTranslate("settings.keyPlaceholder", "Paste the key here"));
    vField.appendChild(vInput);
    if (vKeyFormat) {
      vField.appendChild(fCreateElement("p", "field-hint", vKeyFormat));
    }
    vForm.appendChild(vField);

    const vActions = fCreateElement("div", "form-actions");
    const vSaveButton = fCreateElement("button", "button", fTranslate("common.save", "Save"));
    vSaveButton.type = "submit";
    vActions.appendChild(vSaveButton);

    if (dKey.configured) {
      const vRemoveButton = fCreateElement("button", "button button-danger",
        fTranslate("settings.keyRemove", "Remove"));
      vRemoveButton.type = "button";
      vRemoveButton.addEventListener("click", async function () {
        const vConfirmed = await fConfirm({
          title: fTranslate("settings.keyRemove", "Remove"),
          message: fTranslate("settings.keyRemoveConfirm",
            "Remove the stored key for {provider}? Agents using it will stop working.")
            .replace("{provider}", fDescribeProviderName(dKey.provider)),
          confirmLabel: fTranslate("settings.keyRemove", "Remove"),
          danger: true,
        });
        if (!vConfirmed) { return; }
        try {
          await fCallApi("/keys/" + dKey.provider, "PUT", { api_key: "" });
          fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
          sLoadedTabs.delete("keys");
          await fLoadTab("keys");
        } catch (vError) {
          fShowError(vError);
        }
      });
      vActions.appendChild(vRemoveButton);
    }
    vForm.appendChild(vActions);

    vForm.addEventListener("submit", async function (pEvent) {
      pEvent.preventDefault();
      const vValue = vInput.value.trim();
      if (!vValue) {
        fShowNothingToSave();
        return;
      }
      try {
        await fCallApi("/keys/" + dKey.provider, "PUT", { api_key: vValue });
        vInput.value = "";
        fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
        sLoadedTabs.delete("keys");
        await fLoadTab("keys");
      } catch (vError) {
        fShowError(vError);
      }
    });

    vContainer.appendChild(vForm);
  });
}

/* Channels ------------------------------------------------------------------ */

async function fRenderChannelForms() {
  const vContainer = document.getElementById("vChannelForms");
  const dResult = await fCallApi("/channels");

  fClear(vContainer);
  (dResult.channels || []).forEach(function (dChannel) {
    const vForm = document.createElement("form");
    vForm.className = "panel channel-form";

    vForm.appendChild(
      fCreateElement("h2", "panel-title", fDescribeChannelName(dChannel.name)));

    const vChannelState = fCreateElement("p", "field-hint",
      dChannel.configured
        ? fTranslate("settings.channelConfigured", "Configured.")
        : fTranslate("settings.channelMissing", "Not configured."));
    if (dChannel.configured) { vChannelState.setAttribute("data-state", "good"); }
    vForm.appendChild(vChannelState);

    const lHint = dChannelHints[dChannel.name];
    if (lHint) {
      vForm.appendChild(
        fCreateElement("p", "field-hint", fTranslate(lHint[0], lHint[1])));
    }

    const dValues = dChannel.values || {};
    (dChannelFields[dChannel.name] || []).forEach(function (vFieldName) {
      const vField = fCreateElement("div", "field");
      const vLabel = document.createElement("label");
      vLabel.textContent = vFieldName;
      vLabel.setAttribute("for", "vChannelField_" + dChannel.name + "_" + vFieldName);
      vField.appendChild(vLabel);

      const vSecret = lSecretChannelFields.indexOf(vFieldName) !== -1;
      const vInput = document.createElement("input");
      vInput.id = "vChannelField_" + dChannel.name + "_" + vFieldName;
      /* Secrets never come back from the server, so those fields start empty
       * and an empty one means "leave it as it is". The rest start filled in,
       * which is also what makes it possible to clear one: an empty box that
       * was never filled cannot tell "unchanged" from "delete this". */
      vInput.type = vSecret ? "password" : "text";
      vInput.autocomplete = "off";
      vInput.value = vSecret ? "" : (dValues[vFieldName] || "");
      vInput.placeholder = (vSecret && dChannel.configured) ? "••••••••" : "";
      vField.appendChild(vInput);
      vForm.appendChild(vField);
    });

    (dChannelSwitches[dChannel.name] || []).forEach(function (lSwitch) {
      const vRow = fCreateElement("div", "checkbox-row");
      const vInput = document.createElement("input");
      vInput.type = "checkbox";
      vInput.id = "vChannelSwitch_" + dChannel.name + "_" + lSwitch[0];
      vInput.checked = !!dChannel[lSwitch[0]];
      vRow.appendChild(vInput);

      const vLabel = document.createElement("label");
      vLabel.setAttribute("for", vInput.id);
      vLabel.textContent = fTranslate(lSwitch[1], lSwitch[2]);
      vRow.appendChild(vLabel);
      vForm.appendChild(vRow);
    });

    const vButton = fCreateElement("button", "button", fTranslate("common.save", "Save"));
    vButton.type = "submit";
    vForm.appendChild(vButton);

    vForm.addEventListener("submit", async function (pEvent) {
      pEvent.preventDefault();
      const dPayload = { enabled: true };
      let vHasValue = false;
      (dChannelFields[dChannel.name] || []).forEach(function (vFieldName) {
        const vValue = document.getElementById(
          "vChannelField_" + dChannel.name + "_" + vFieldName
        ).value;
        /* A secret travels only when somebody typed one. Everything else
         * travels as it stands, empty included, because the box was shown
         * with what is stored in it and emptying it is how you clear it. */
        if (lSecretChannelFields.indexOf(vFieldName) !== -1) {
          if (vValue) { dPayload[vFieldName] = vValue; vHasValue = true; }
        } else {
          dPayload[vFieldName] = vValue;
          if (vValue !== (dValues[vFieldName] || "")) { vHasValue = true; }
        }
      });
      /* A switch always travels, and always counts as something to save: it is
       * the one thing on this form that can be changed by leaving every box
       * empty, and the server merges rather than replaces, so sending it on its
       * own does not disturb the credentials. */
      (dChannelSwitches[dChannel.name] || []).forEach(function (lSwitch) {
        dPayload[lSwitch[0]] = document.getElementById(
          "vChannelSwitch_" + dChannel.name + "_" + lSwitch[0]
        ).checked;
        vHasValue = true;
      });
      if (!vHasValue) {
        fShowNothingToSave();
        return;
      }
      try {
        await fCallApi("/channels/" + dChannel.name, "PUT", dPayload);
        fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
        sLoadedTabs.delete("channels");
        await fLoadTab("channels");
      } catch (vError) {
        fShowError(vError);
      }
    });

    vContainer.appendChild(vForm);
  });
}

/* Kanban -------------------------------------------------------------------- */

async function fRenderDeletedCards() {
  const vPanel = document.getElementById("vDeletedCardsPanel");
  const vShow = fReadPreference(cShowDeletedKey, "0") === "1";
  vPanel.hidden = !vShow;
  if (!vShow) { return; }

  const dResult = await fCallApi("/kanban/deleted");
  const vTable = document.getElementById("vDeletedCardsTable");
  fClear(vTable);

  const lDeleted = dResult.deleted || [];
  if (lDeleted.length === 0) {
    const vRow = document.createElement("tr");
    const vCell = fCreateElement("td", "empty",
      fTranslate("settings.noDeleted", "Nothing has been deleted."));
    vCell.colSpan = 3;
    vRow.appendChild(vCell);
    vTable.appendChild(vRow);
    return;
  }

  lDeleted.forEach(function (dCard) {
    const vRow = document.createElement("tr");
    vRow.appendChild(fCreateElement("td", "", "#" + dCard.id + " " + dCard.title));
    vRow.appendChild(fCreateElement("td", "", dCard.deleted_by));
    vRow.appendChild(fCreateElement("td", "", dCard.deleted_at));
    vTable.appendChild(vRow);
  });
}

/* Account and SMTP ---------------------------------------------------------- */

/* What each server-backed form would send if it were saved right now, and
 * what it held when it was loaded or last saved.
 *
 * The stored passwords never come back from the server, so an empty password
 * box means "leave it alone" - which is why it counts as part of the snapshot
 * rather than being ignored: typing one and typing it again is a change, and
 * leaving it empty twice is not.
 */
const dFormCollectors = {
  account: function () {
    return {
      email: document.getElementById("vAccountEmailInput").value,
      password: document.getElementById("vAccountPasswordInput").value,
    };
  },
  imap: function () {
    return {
      imap_host: document.getElementById("vImapHostInput").value,
      imap_port: document.getElementById("vImapPortInput").value,
      imap_user: document.getElementById("vImapUserInput").value,
      imap_ssl: document.getElementById("vImapSslInput").checked ? "1" : "0",
      mail_forward_allowed: document.getElementById("vForwardAllowedInput").value,
      imap_password: document.getElementById("vImapPasswordInput").value,
    };
  },
  smtp: function () {
    return {
      smtp_host: document.getElementById("vSmtpHostInput").value,
      smtp_port: document.getElementById("vSmtpPortInput").value,
      smtp_user: document.getElementById("vSmtpUserInput").value,
      smtp_password: document.getElementById("vSmtpPasswordInput").value,
    };
  },
};

const dFormBaselines = {};

function fRememberForm(pName) {
  dFormBaselines[pName] = JSON.stringify(dFormCollectors[pName]());
}

function fRememberEveryForm() {
  Object.keys(dFormCollectors).forEach(fRememberForm);
}

/* True when Save would write exactly what is already stored, and the message
 * to show instead has been shown. */
function fSaveWouldChangeNothing(pName) {
  if (!fIsUnchanged(dFormBaselines[pName], dFormCollectors[pName]())) {
    return false;
  }
  fShowNothingToSave();
  return true;
}

async function fLoadSettings() {
  try {
    const dResult = await fCallApi("/settings");
    document.getElementById("vAccountEmailInput").value = dResult.email || "";
    const dSettings = dResult.settings || {};
    document.getElementById("vSmtpHostInput").value = dSettings.smtp_host || "";
    document.getElementById("vSmtpPortInput").value = dSettings.smtp_port || "";
    document.getElementById("vSmtpUserInput").value = dSettings.smtp_user || "";

    document.getElementById("vImapHostInput").value = dSettings.imap_host || "";
    document.getElementById("vImapPortInput").value = dSettings.imap_port || "";
    document.getElementById("vImapUserInput").value = dSettings.imap_user || "";
    document.getElementById("vImapSslInput").checked =
      (dSettings.imap_ssl || "1") !== "0";
    document.getElementById("vForwardAllowedInput").value =
      dSettings.mail_forward_allowed || "";

    /* A stored password never comes back, so the only thing to show is
     * whether there is one. Same line as the API keys, same reason. */
    fShowPasswordState("vSmtpPasswordState", dSettings.smtp_password_set === "1");
    fShowPasswordState("vImapPasswordState", dSettings.imap_password_set === "1");
  } catch (vError) {
    fShowError(vError);
  }

  /* The browser's own preferences, and the baseline each panel compares
   * against to know whether anything has been edited. Interface waits: its
   * theme picker is filled in when that tab is first opened. */
  document.getElementById("vLanguageInput").value = fGetLanguage();
  fLoadPreferencePanel("chat");
  fLoadPreferencePanel("kanban");

  /* And the forms that live on the server, now that every box holds what it
   * sent. */
  fRememberEveryForm();
}

/* Save and Discard, on every tab that holds editable settings ---------------
 *
 * Chat, Kanban and Interface are preferences kept in this browser, and they
 * used to be written the moment a box was ticked. That made them the odd ones
 * out: every other screen in the application - an agent's settings, the
 * account, the mail server - is edited and then saved, so a tab with no Save
 * button reads as one that has not finished loading.
 *
 * They are still applied on the spot, because a theme and a language are
 * settings whose result can only be judged by looking at them. What changed is
 * that applying and keeping are now two different things: Save writes them,
 * Discard puts back what was written last, and until one of the two is pressed
 * the tab says it has unsaved changes.
 */

/* One entry per panel: how to read the stored values, how to show a set of
 * values without storing them, and how to store them. Adding a browser
 * preference means adding a field here, not another change handler. */
const dPreferencePanels = {
  agents: {
    fRead: function () {
      return { language: vStoredAgentLanguage };
    },
    fShow: function (dValues) {
      document.getElementById("vAgentLanguageInput").value = dValues.language;
    },
    fCollect: function () {
      return { language: document.getElementById("vAgentLanguageInput").value };
    },
    fWrite: function (dValues) {
      /* Written through the API, not into localStorage: every agent in the
       * installation reads it, including the ones nobody is watching. */
      vStoredAgentLanguage = dValues.language;
      fCallApi("/settings", "PUT", {
        settings: { agent_language: dValues.language }
      }).catch(fShowError);
    },
  },

  chat: {
    fRead: function () {
      return {
        sendOnEnter: fGetSendOnEnter(),
        showCost: fReadPreference(cShowChatCostKey, "1") === "1",
      };
    },
    fShow: function (dValues) {
      document.getElementById("vSendOnEnterInput").checked = dValues.sendOnEnter;
      document.getElementById("vShowChatCostInput").checked = dValues.showCost;
    },
    fCollect: function () {
      return {
        sendOnEnter: document.getElementById("vSendOnEnterInput").checked,
        showCost: document.getElementById("vShowChatCostInput").checked,
      };
    },
    fWrite: function (dValues) {
      fSetSendOnEnter(dValues.sendOnEnter);
      fWritePreference(cShowChatCostKey, dValues.showCost ? "1" : "0");
    },
  },

  kanban: {
    fRead: function () {
      return {
        limit: fReadPreference(cKanbanLimitKey, "50"),
        showDeleted: fReadPreference(cShowDeletedKey, "0") === "1",
      };
    },
    fShow: function (dValues) {
      document.getElementById("vKanbanLimitInput").value = dValues.limit;
      document.getElementById("vShowDeletedInput").checked = dValues.showDeleted;
    },
    fCollect: function () {
      const vLimit = Math.max(5, Math.min(
        Number(document.getElementById("vKanbanLimitInput").value) || 50, 500));
      return {
        limit: String(vLimit),
        showDeleted: document.getElementById("vShowDeletedInput").checked,
      };
    },
    fWrite: function (dValues) {
      fWritePreference(cKanbanLimitKey, dValues.limit);
      fWritePreference(cShowDeletedKey, dValues.showDeleted ? "1" : "0");
    },
    fPreview: async function (dValues) {
      /* The deleted-cards panel is part of this tab, so it follows the tick
       * straight away rather than waiting to be saved. */
      document.getElementById("vKanbanLimitInput").value = dValues.limit;
      sLoadedTabs.delete("kanban");
      await fRenderDeletedCards();
    },
  },

  interface: {
    fRead: function () {
      return {
        theme: fGetTheme(),
        language: fGetLanguage(),
        noticeSeconds: fGetNoticeSeconds(),
        offerExamples: fGetOfferExamples(),
      };
    },
    fShow: function (dValues) {
      document.getElementById("vThemeInput").value = dValues.theme;
      document.getElementById("vLanguageInput").value = dValues.language;
      document.getElementById("vNoticeSecondsInput").value =
        dValues.noticeSeconds;
      document.getElementById("vOfferExamplesInput").checked =
        dValues.offerExamples;
    },
    fCollect: function () {
      const vSeconds = Math.max(cMinNoticeSeconds, Math.min(
        Number(document.getElementById("vNoticeSecondsInput").value)
          || cDefaultNoticeSeconds,
        cMaxNoticeSeconds));
      return {
        theme: document.getElementById("vThemeInput").value,
        language: document.getElementById("vLanguageInput").value,
        noticeSeconds: vSeconds,
        offerExamples: document.getElementById("vOfferExamplesInput").checked,
      };
    },
    fWrite: function (dValues) {
      fSetTheme(dValues.theme);
      fSetLanguage(dValues.language);
      fSetNoticeSeconds(dValues.noticeSeconds);
      fWritePreference(cOfferExamplesKey, dValues.offerExamples ? "1" : "0");
    },
    fPreview: async function (dValues) {
      /* Applied without being stored: a theme and a language are judged by
       * looking at them, and Discard has to be able to take them back. */
      fApplyTheme(dValues.theme);
      await fApplyLanguage(dValues.language);
    },
  },
};

/* Agents ---------------------------------------------------------------------
 *
 * The one panel here whose value is kept on the SERVER rather than in this
 * browser, and it has to be: it is read by a run that cron started, which has
 * no browser to read a preference out of.
 */
let vStoredAgentLanguage = "";

async function fLoadAgentSettings() {
  const dResult = await fCallApi("/settings");
  vStoredAgentLanguage = String(
    (dResult.settings || {}).agent_language || "");
  fLoadPreferencePanel("agents");
}

/* What was on screen when the panel was last loaded or saved. Comparing
 * against this is what tells a real edit from a click that changed nothing. */
const dPanelBaselines = {};

function fMarkPanelState(pPanel) {
  const dPanel = dPreferencePanels[pPanel];
  const vHint = document.querySelector('[data-unsaved="' + pPanel + '"]');
  if (!dPanel || !vHint) { return; }
  const vChanged = JSON.stringify(dPanel.fCollect())
    !== JSON.stringify(dPanelBaselines[pPanel]);
  vHint.hidden = !vChanged;
}

function fLoadPreferencePanel(pPanel) {
  const dPanel = dPreferencePanels[pPanel];
  if (!dPanel) { return; }
  dPanel.fShow(dPanel.fRead());
  dPanelBaselines[pPanel] = dPanel.fCollect();
  fMarkPanelState(pPanel);
}

async function fDiscardPreferencePanel(pPanel) {
  const dPanel = dPreferencePanels[pPanel];
  if (!dPanel) { return; }
  const dStored = dPanel.fRead();
  dPanel.fShow(dStored);
  if (dPanel.fPreview) { await dPanel.fPreview(dStored); }
  dPanelBaselines[pPanel] = dPanel.fCollect();
  fMarkPanelState(pPanel);
}

function fSavePreferencePanel(pPanel) {
  const dPanel = dPreferencePanels[pPanel];
  if (!dPanel) { return; }
  const dValues = dPanel.fCollect();

  /* The baseline these panels already keep, to decide whether the tab says it
   * has unsaved changes, answers this question too. */
  if (fIsUnchanged(JSON.stringify(dPanelBaselines[pPanel]), dValues)) {
    fShowNothingToSave();
    return;
  }

  dPanel.fShow(dValues);
  dPanel.fWrite(dValues);
  dPanelBaselines[pPanel] = dPanel.fCollect();
  fMarkPanelState(pPanel);
  fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
}

function fWireBrowserPreferencePanels() {
  Object.keys(dPreferencePanels).forEach(function (vPanel) {
    const dPanel = dPreferencePanels[vPanel];
    const vSection = document.querySelector('[data-panel="' + vPanel + '"]');
    if (!vSection) { return; }

    vSection.querySelectorAll("input, select").forEach(function (vField) {
      vField.addEventListener("change", async function () {
        if (dPanel.fPreview) { await dPanel.fPreview(dPanel.fCollect()); }
        fMarkPanelState(vPanel);
      });
    });
  });

  /* Account and Email save through their own forms, so their Discard only has
   * to put the stored values back on screen. */
  document.querySelectorAll("[data-save]").forEach(function (vButton) {
    vButton.addEventListener("click", function () {
      fSavePreferencePanel(vButton.getAttribute("data-save"));
    });
  });
  document.querySelectorAll("[data-discard]").forEach(function (vButton) {
    vButton.addEventListener("click", async function () {
      const vPanel = vButton.getAttribute("data-discard");
      if (vPanel === "audio") { return; } // Managed by settings_audio.js.
      if (dPreferencePanels[vPanel]) {
        await fDiscardPreferencePanel(vPanel);
      } else {
        await fLoadSettings();
      }
    });
  });
}


async function fSaveAccount(pEvent) {
  pEvent.preventDefault();
  if (fSaveWouldChangeNothing("account")) { return; }

  const dPayload = { email: document.getElementById("vAccountEmailInput").value };
  const vPassword = document.getElementById("vAccountPasswordInput").value;
  const vCurrentPassword = document.getElementById("vCurrentPasswordInput").value;
  if (vPassword) {
    /* Asked for here as well as required by the server, so that the answer to
     * "why was this refused" is a box to fill in rather than an error. */
    if (!vCurrentPassword) {
      fShowError(fTranslate(
        "settings.currentPasswordNeeded",
        "Type your current password to change it."));
      return;
    }
    dPayload.password = vPassword;
    dPayload.current_password = vCurrentPassword;
  }
  try {
    await fCallApi("/settings", "PUT", dPayload);
    document.getElementById("vAccountPasswordInput").value = "";
    document.getElementById("vCurrentPasswordInput").value = "";
    fRememberForm("account");
    fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
  } catch (vError) {
    fShowError(vError);
  }
}

function fShowPasswordState(pElementId, pIsSet) {
  const vElement = document.getElementById(pElementId);
  if (!vElement) { return; }
  vElement.textContent = pIsSet
    ? fTranslate("settings.passwordStored",
                 "A password is stored. Leave the box empty to keep it.")
    : fTranslate("settings.passwordMissing", "No password stored.");
  if (pIsSet) {
    vElement.setAttribute("data-state", "good");
  } else {
    vElement.removeAttribute("data-state");
  }
}

async function fSaveImap(pEvent) {
  pEvent.preventDefault();
  if (fSaveWouldChangeNothing("imap")) { return; }

  const dSettings = {
    imap_host: document.getElementById("vImapHostInput").value,
    imap_port: document.getElementById("vImapPortInput").value,
    imap_user: document.getElementById("vImapUserInput").value,
    imap_ssl: document.getElementById("vImapSslInput").checked ? "1" : "0",
    mail_forward_allowed: document.getElementById("vForwardAllowedInput").value,
  };
  /* Sent only when something was typed: an empty box means "I did not change
   * it", which is the only reading that works when the stored one is never
   * shown back. */
  const vPassword = document.getElementById("vImapPasswordInput").value;
  if (vPassword) { dSettings.imap_password = vPassword; }
  try {
    await fCallApi("/settings", "PUT", { settings: dSettings });
    document.getElementById("vImapPasswordInput").value = "";
    fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
    /* Reloading takes the new snapshot: every box then holds what the server
     * has, which is what the next Save is compared against. */
    await fLoadSettings();
  } catch (vError) {
    fShowError(vError);
  }
}

async function fSaveSmtp(pEvent) {
  pEvent.preventDefault();
  if (fSaveWouldChangeNothing("smtp")) { return; }

  const dSettings = {
    smtp_host: document.getElementById("vSmtpHostInput").value,
    smtp_port: document.getElementById("vSmtpPortInput").value,
    smtp_user: document.getElementById("vSmtpUserInput").value,
    smtp_configured: "1",
  };
  const vPassword = document.getElementById("vSmtpPasswordInput").value;
  if (vPassword) { dSettings.smtp_password = vPassword; }
  try {
    await fCallApi("/settings", "PUT", { settings: dSettings });
    document.getElementById("vSmtpPasswordInput").value = "";
    fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
    await fLoadSettings();
  } catch (vError) {
    fShowError(vError);
  }
}

document.addEventListener("DOMContentLoaded", async function () {
  await fWaitForTranslations();

  document.querySelectorAll("#vSettingsTabs .tab").forEach(function (vButton) {
    vButton.addEventListener("click", function () {
      fSelectTab(vButton.getAttribute("data-tab"), true);
    });
  });

  document.getElementById("vAccountForm").addEventListener("submit", fSaveAccount);
  document.getElementById("vSmtpForm").addEventListener("submit", fSaveSmtp);
  document.getElementById("vImapForm").addEventListener("submit", fSaveImap);

  fWireBrowserPreferencePanels();

  await fRenderSidebar();
  await fLoadSettings();
  fSelectTab(fGetCurrentTab(), false);
});
