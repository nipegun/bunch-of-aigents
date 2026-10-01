/* Server-wide speech recognition; credentials remain in the API key store. */
let dAudioData = null;
let vAudioPoll = null;
let vAudioBound = false;

function fAudioElement(pName) { return document.getElementById("vAudio" + pName); }

function fFillAudioForm() {
  const dSettings = dAudioData.settings;
  const dFields = {Engine: "engine", Provider: "provider", ApiModel: "api_model",
    LocalModel: "local_model", Language: "language", MaxSeconds: "max_seconds", Threads: "threads"};
  Object.keys(dFields).forEach(function (vName) { fAudioElement(vName).value = dSettings[dFields[vName]]; });
  fAudioElement("Keep").checked = dSettings.keep_audio;
  fAudioElement("Saved").textContent = "";
  if (!dSettings.provider && dAudioData.providers.length) {
    fAudioElement("Provider").value = dAudioData.providers[0].id;
    fUpdateAudioProvider(true);
  } else { fUpdateAudioProvider(false); }
  fUpdateAudioControls();
}

function fUpdateAudioProvider(pChooseDefault) {
  const dProvider = dAudioData.providers.find(function (dItem) { return dItem.id === fAudioElement("Provider").value; });
  fClear(fAudioElement("ApiModels"));
  if (dProvider) {
    dProvider.models.forEach(function (vModel) {
      const vOption = document.createElement("option");
      vOption.value = vModel;
      fAudioElement("ApiModels").appendChild(vOption);
    });
    if (pChooseDefault) { fAudioElement("ApiModel").value = dProvider.models[0] || ""; }
  }
}

function fUpdateAudioControls() {
  if (!dAudioData) { return; }
  const vEngine = fAudioElement("Engine").value;
  fAudioElement("Local").hidden = vEngine !== "local";
  fAudioElement("Api").hidden = vEngine !== "api";
  fAudioElement("Options").hidden = vEngine === "disabled";
  const dModel = dAudioData.local.models.find(function (dItem) { return dItem.id === fAudioElement("LocalModel").value; });
  const vState = dModel ? dModel.state : "missing";
  const vInstalled = dAudioData.local.installed && dAudioData.decoder_installed;
  fAudioElement("Installation").textContent = vInstalled
    ? "whisper.cpp " + dAudioData.local.version + " · " + dAudioData.local.directory
    : fTranslate("audio.installMissing", "Run the BoA installer with --update to install whisper.cpp and the audio decoder.");
  const dStates = {installed: ["audio.installed", "Installed"], missing: ["audio.missing", "Not downloaded"],
    queued: ["audio.queued", "Queued"], downloading: ["audio.downloading", "Downloading"], failed: ["audio.failed", "Download failed"]};
  const lState = dStates[vState] || dStates.missing;
  let vStatus = fTranslate(lState[0], lState[1]);
  if (dModel && dModel.english_only) { vStatus += " · " + fTranslate("audio.englishOnly", "English only"); }
  if (dModel && dModel.error) { vStatus += " · " + dModel.error; }
  fAudioElement("ModelStatus").textContent = vStatus;
  fAudioElement("ModelStatus").setAttribute("data-state", vState === "installed" ? "good" : "");
  const vDownloading = vState === "downloading" || vState === "queued";
  fAudioElement("Download").disabled = !vInstalled || vState === "installed" || vDownloading;
  fAudioElement("Progress").hidden = !vDownloading;
  fAudioElement("Progress").value = dModel && dModel.total ? 100 * dModel.downloaded / dModel.total : 0;
  fAudioElement("NoProviders").hidden = dAudioData.providers.length > 0;
  fAudioElement("ApiModel").required = vEngine === "api";
  fAudioElement("Provider").required = vEngine === "api";
}

function fScheduleAudioPoll() {
  window.clearTimeout(vAudioPoll);
  if (!dAudioData.local.models.some(function (dModel) { return ["queued", "downloading"].includes(dModel.state); })) { return; }
  vAudioPoll = window.setTimeout(async function () {
    try {
      const dFresh = await fCallApi("/audio");
      dAudioData.local = dFresh.local;
      fUpdateAudioControls();
      fScheduleAudioPoll();
    } catch (vError) { fShowError(vError); }
  }, 2000);
}

async function fLoadAudioSettings() {
  dAudioData = await fCallApi("/audio");
  fClear(fAudioElement("LocalModel"));
  dAudioData.local.models.forEach(function (dModel) {
    const vOption = document.createElement("option");
    vOption.value = dModel.id;
    vOption.textContent = dModel.id + " · " + Math.ceil(dModel.size / 1048576) + " MiB";
    fAudioElement("LocalModel").appendChild(vOption);
  });
  fClear(fAudioElement("Provider"));
  dAudioData.providers.forEach(function (dProvider) {
    const vOption = document.createElement("option");
    vOption.value = dProvider.id;
    vOption.textContent = dProvider.name;
    fAudioElement("Provider").appendChild(vOption);
  });
  fFillAudioForm();
  fScheduleAudioPoll();
  if (vAudioBound) { return; }
  vAudioBound = true;
  fAudioElement("Engine").addEventListener("change", fUpdateAudioControls);
  fAudioElement("LocalModel").addEventListener("change", fUpdateAudioControls);
  fAudioElement("Provider").addEventListener("change", function () { fUpdateAudioProvider(true); });
  fAudioElement("Discard").addEventListener("click", fFillAudioForm);
  fAudioElement("Form").addEventListener("input", function () { fAudioElement("Saved").textContent = ""; });
  fAudioElement("Download").addEventListener("click", async function () {
    fAudioElement("Download").disabled = true;
    try {
      const vModel = fAudioElement("LocalModel").value;
      const dResult = await fCallApi("/audio/models/" + encodeURIComponent(vModel) + "/install", "POST", {});
      Object.assign(dAudioData.local.models.find(function (dModel) { return dModel.id === vModel; }), dResult.download);
      fUpdateAudioControls();
      fScheduleAudioPoll();
    } catch (vError) { fShowError(vError); fUpdateAudioControls(); }
  });
  fAudioElement("Form").addEventListener("submit", async function (pEvent) {
    pEvent.preventDefault();
    const dSettings = {engine: fAudioElement("Engine").value, provider: fAudioElement("Provider").value,
      api_model: fAudioElement("ApiModel").value.trim(), local_model: fAudioElement("LocalModel").value,
      language: fAudioElement("Language").value.trim().toLowerCase(), max_seconds: Number(fAudioElement("MaxSeconds").value),
      threads: Number(fAudioElement("Threads").value), keep_audio: fAudioElement("Keep").checked};
    try {
      const dResult = await fCallApi("/audio", "PUT", dSettings);
      dAudioData.settings = dResult.settings;
      fAudioElement("Saved").textContent = fTranslate("common.saved", "Settings saved");
      fAudioElement("Saved").setAttribute("data-state", "good");
    } catch (vError) { fShowError(vError); }
  });
}
