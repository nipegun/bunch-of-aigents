/* Per-agent Samba settings. The server owns the share name and folder path. */

let dCurrentSamba = null;
let vSambaLoadSequence = 0;

function fResetSambaSettings() {
  vSambaLoadSequence += 1;
  dCurrentSamba = null;
  document.getElementById("vSambaFields").disabled = true;
  document.getElementById("vSambaPassword").value = "";
  document.getElementById("vSambaStatus").textContent = "";
}

function fUpdateSambaControls() {
  const vGuest = document.getElementById("vSambaAccess").value === "guest";
  document.getElementById("vSambaCredentials").hidden = vGuest;
  document.getElementById("vSambaPassword").disabled = vGuest;
  if (!dCurrentSamba) { return; }
  const vStatus = !dCurrentSamba.installed
    ? fTranslate("samba.notInstalled", "Samba is not installed yet. Update this installation to enable it.")
    : (dCurrentSamba.running
      ? fTranslate("samba.running", "Samba is running.")
      : fTranslate("samba.stopped", "Samba is stopped. Settings will apply when the service starts."));
  document.getElementById("vSambaStatus").textContent = vStatus;
  document.getElementById("vSambaPasswordHint").textContent = dCurrentSamba.password_set
    ? fTranslate("samba.passwordKeep", "A password is set. Leave this empty to keep it; enter at least 8 characters to change it.")
    : fTranslate("samba.passwordNeeded", "Set a Samba password of at least 8 characters before connecting. This does not change the Linux password.");
}

async function fLoadSambaSettings() {
  if (!dCurrentAgent || dCurrentSamba) { return; }
  const vAgentId = dCurrentAgent.id;
  const vSequence = ++vSambaLoadSequence;
  const vStatus = document.getElementById("vSambaStatus");
  vStatus.textContent = fTranslate("samba.loading", "Loading Samba settings…");
  try {
    const dResult = await fCallApi("/agents/" + encodeURIComponent(vAgentId) + "/samba");
    if (vSequence !== vSambaLoadSequence || !dCurrentAgent || dCurrentAgent.id !== vAgentId) { return; }
    dCurrentSamba = dResult;
    const dSettings = dResult.settings;
    document.getElementById("vSambaShareName").value = dResult.share_name;
    document.getElementById("vSambaPath").value = dResult.path;
    document.getElementById("vSambaUsername").value = dResult.username;
    document.getElementById("vSambaWindowsPath").value = "\\\\" + window.location.hostname + "\\" + dResult.share_name;
    document.getElementById("vSambaUrl").value = "smb://" + window.location.hostname + "/" + dResult.share_name;
    document.getElementById("vSambaEnabled").checked = dSettings.enabled;
    document.getElementById("vSambaPermissions").value = dSettings.read_only ? "read" : "write";
    document.getElementById("vSambaAccess").value = dSettings.guest_ok ? "guest" : "user";
    document.getElementById("vSambaBrowseable").checked = dSettings.browseable;
    document.getElementById("vSambaComment").value = dSettings.comment;
    document.getElementById("vSambaCreateMask").value = dSettings.create_mask;
    document.getElementById("vSambaDirectoryMask").value = dSettings.directory_mask;
    document.getElementById("vSambaPassword").value = "";
    document.getElementById("vSambaFields").disabled = !dResult.installed;
    fUpdateSambaControls();
    // Add the loaded values to the snapshot without erasing edits in other tabs.
    if (vAgentBaseline !== null) {
      const dBaseline = JSON.parse(vAgentBaseline);
      const dSamba = fCollectSambaSettings();
      if (dSamba) { dBaseline.samba = dSamba; }
      vAgentBaseline = JSON.stringify(dBaseline);
    }
  } catch (vError) {
    if (vSequence === vSambaLoadSequence) {
      vStatus.textContent = vError.message || String(vError);
    }
  }
}

function fCollectSambaSettings() {
  if (!dCurrentSamba || !dCurrentSamba.installed) { return null; }
  const dSettings = {
    enabled: document.getElementById("vSambaEnabled").checked,
    read_only: document.getElementById("vSambaPermissions").value === "read",
    guest_ok: document.getElementById("vSambaAccess").value === "guest",
    browseable: document.getElementById("vSambaBrowseable").checked,
    comment: document.getElementById("vSambaComment").value,
    create_mask: document.getElementById("vSambaCreateMask").value,
    directory_mask: document.getElementById("vSambaDirectoryMask").value,
  };
  const vPassword = document.getElementById("vSambaPassword").value;
  if (vPassword && !dSettings.guest_ok) { dSettings.password = vPassword; }
  return dSettings;
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("vSambaAccess").addEventListener("change", fUpdateSambaControls);
});
