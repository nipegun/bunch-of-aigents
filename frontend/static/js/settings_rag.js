/* Settings -> RAG: the local engine, its embedding model and its limits.
 * A model has to be downloaded before it can be chosen, and choosing it is
 * saved like the rest of the form, after saying what it sets in motion. */
let dRagRuntime = null;
let vRagModelPoll = null;
let vRagModelBound = false;

function fRagModel(pId) {
  return (dRagRuntime.models || []).find(function (dModel) { return dModel.id === pId; });
}

function fDescribeRagModel(dModel) {
  let vText = fTranslate("rag.modelInfo",
    "{parameters} parameters · {size} MiB to download · about {memory} MB of RAM while it runs · license: {license}")
    .replace("{parameters}", dModel.parameters)
    .replace("{size}", Math.ceil(dModel.size / 1048576))
    .replace("{memory}", Number(dModel.memory_mb).toLocaleString(document.documentElement.lang || undefined))
    .replace("{license}", dModel.license);
  if (dModel.relative_indexing_time > 1) {
    vText += " · " + fTranslate("rag.modelSlower",
      "indexes about {times} times slower than EmbeddingGemma on the same processor")
      .replace("{times}", dModel.relative_indexing_time);
  }
  return vText;
}

function fShowRagStatus() {
  const vStatus = document.getElementById("vRagRuntimeStatus");
  const dSelected = fRagModel(dRagRuntime.model_id);
  let vState = fTranslate("rag.engineUnavailable", "Local embedding engine unavailable");
  if (dRagRuntime.ready) {
    vState = fTranslate("rag.state.ready", "Ready");
  } else if (dRagRuntime.serving && dRagRuntime.serving !== dRagRuntime.model_id) {
    vState = fTranslate("rag.engineSwitching", "The engine is loading this model");
  }
  vStatus.textContent = (dSelected ? dSelected.name : dRagRuntime.model) + " · " + vState;
  vStatus.setAttribute("data-state", dRagRuntime.ready ? "good" : "");
}

function fUpdateRagModelControls() {
  const dModel = fRagModel(document.getElementById("vRagModel").value);
  if (!dModel) { return; }
  const dStates = {installed: ["rag.modelState.installed", "Downloaded"], missing: ["rag.modelState.missing", "Not downloaded"],
    queued: ["rag.modelState.queued", "Queued"], downloading: ["rag.modelState.downloading", "Downloading"],
    failed: ["rag.modelState.failed", "Download failed"]};
  const lState = dStates[dModel.state] || dStates.missing;
  let vStatus = fTranslate(lState[0], lState[1]);
  if (dModel.state === "downloading" && dModel.total) {
    vStatus += " · " + Math.floor(100 * dModel.downloaded / dModel.total) + "%";
  }
  if (dModel.error) { vStatus += " · " + dModel.error; }
  document.getElementById("vRagModelInfo").textContent = fDescribeRagModel(dModel);
  document.getElementById("vRagModelStatus").textContent = vStatus;
  document.getElementById("vRagModelStatus").setAttribute("data-state", dModel.state === "installed" ? "good" : "");
  const vDownloading = dModel.state === "downloading" || dModel.state === "queued";
  const vDownload = document.getElementById("vRagModelDownload");
  vDownload.hidden = dModel.state === "installed";
  vDownload.disabled = vDownloading;
  document.getElementById("vRagModelProgress").hidden = !vDownloading;
  document.getElementById("vRagModelProgress").value = dModel.total ? 100 * dModel.downloaded / dModel.total : 0;
}

function fScheduleRagModelPoll() {
  window.clearTimeout(vRagModelPoll);
  const vBusy = (dRagRuntime.models || []).some(function (dModel) {
    return dModel.state === "queued" || dModel.state === "downloading";
  });
  /* After a switch the engine takes a few seconds to load the new weights. */
  const vLoading = !dRagRuntime.ready && dRagRuntime.serving !== dRagRuntime.model_id;
  if (!vBusy && !vLoading) { return; }
  vRagModelPoll = window.setTimeout(async function () {
    try {
      const dFresh = await fCallApi("/rag");
      dRagRuntime.models = dFresh.models;
      dRagRuntime.ready = dFresh.ready;
      dRagRuntime.serving = dFresh.serving;
      fShowRagStatus();
      fUpdateRagModelControls();
      fScheduleRagModelPoll();
    } catch (vError) { fShowError(vError); }
  }, 2000);
}

async function fLoadRagRuntime() {
  dRagRuntime = await fCallApi("/rag");
  const vSelect = document.getElementById("vRagModel");
  vSelect.replaceChildren();
  (dRagRuntime.models || []).forEach(function (dModel) {
    const vOption = document.createElement("option");
    vOption.value = dModel.id;
    vOption.textContent = dModel.name;
    vSelect.appendChild(vOption);
  });
  vSelect.value = dRagRuntime.model_id;
  document.getElementById("vRagThreads").value = dRagRuntime.settings.threads;
  document.getElementById("vRagWorkers").value = dRagRuntime.settings.workers;
  document.getElementById("vRagDefaultLanguages").value = dRagRuntime.settings.ocr_languages;
  fShowRagStatus();
  fUpdateRagModelControls();
  fScheduleRagModelPoll();
  if (vRagModelBound) { return; }
  vRagModelBound = true;
  vSelect.addEventListener("change", fUpdateRagModelControls);
  document.getElementById("vRagModelDownload").addEventListener("click", async function () {
    const vModel = vSelect.value;
    document.getElementById("vRagModelDownload").disabled = true;
    try {
      const dResult = await fCallApi("/rag/models/" + encodeURIComponent(vModel) + "/install", "POST", {});
      Object.assign(fRagModel(vModel), dResult.download);
      fUpdateRagModelControls();
      fScheduleRagModelPoll();
    } catch (vError) { fShowError(vError); fUpdateRagModelControls(); }
  });
}

/* A new model is not a setting like the others: every library is indexed
 * again, which on a large one takes hours. Say so before doing it. */
async function fConfirmModelChange(pModel) {
  const dModel = fRagModel(pModel);
  if (!dModel || pModel === dRagRuntime.model_id) { return true; }
  if (dModel.state !== "installed") {
    fShowError(new Error(fTranslate("rag.modelDownloadFirst", "Download the model before choosing it.")));
    return false;
  }
  return await fConfirm({
    title: fTranslate("rag.modelChangeTitle", "Change the embedding model"),
    message: fTranslate("rag.modelChangeConfirm",
      "Every document of every agent will be indexed again with {model}. On a large library this takes hours, " +
      "and until each document is done it is found only by the words of a question. The minimum similarity of " +
      "the agents that kept the recommended value changes to the one measured for this model.")
      .replace("{model}", dModel.name),
    confirmLabel: fTranslate("rag.modelChangeButton", "Change model"),
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("vRagRuntimeDiscard").addEventListener("click", async function () {
    try { await fLoadRagRuntime(); } catch (vError) { fShowError(vError); }
  });
  document.getElementById("vRagRuntimeForm").addEventListener("submit", async function (pEvent) {
    pEvent.preventDefault();
    const vModel = document.getElementById("vRagModel").value;
    try {
      if (!await fConfirmModelChange(vModel)) { return; }
      await fCallApi("/rag", "PUT", {threads: Number(document.getElementById("vRagThreads").value),
        workers: Number(document.getElementById("vRagWorkers").value), ocr_languages: document.getElementById("vRagDefaultLanguages").value,
        model: vModel});
      fShowNotice(fTranslate("common.saved", "Settings saved"), "ok");
      await fLoadRagRuntime();
    } catch (vError) { fShowError(vError); }
  });
});
