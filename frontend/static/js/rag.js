/* Each async action holds its agent id, so changing the sidebar cannot send
 * the next upload chunk or a delete to a different agent. */
let vRagAgent = "";
let vRagOffset = 0;
let vRagPoll = null;
let vRagUploading = false;
let vRagUploadCancelled = false;
let dRagSettings = {};

function fRagPath(pAgent) { return "/agents/" + encodeURIComponent(pAgent) + "/rag"; }

function fRenderRagSettings(pSettings) {
  dRagSettings = pSettings || {};
  const dValues = {vRagMode: dRagSettings.mode || "mixed", vRagFileLimit: dRagSettings.max_file_mb || 128,
    vRagStorage: dRagSettings.max_storage_mb || 2048, vRagContext: dRagSettings.context_characters || 16000,
    vRagResults: dRagSettings.results || 8, vRagLanguages: dRagSettings.ocr_languages || "eng+spa",
    vRagSimilarity: dRagSettings.min_similarity === undefined ? 0.2 : dRagSettings.min_similarity};
  Object.keys(dValues).forEach(function (vId) { document.getElementById(vId).value = dValues[vId]; });
  fShowRagModeHint();
  document.getElementById("vRagEnabled").checked = dRagSettings.enabled === true;
  document.getElementById("vRagOcr").checked = dRagSettings.ocr !== false;
}

/* What the chosen answer mode does, under the list. The difference between
 * "documental" and "verified" is what is removed from an answer, and that is
 * not something a two-word label can say. */
const dRagModeHints = {
  mixed: "The agent may add general knowledge, kept apart from what the documents say.",
  documental: "The agent must search the library before answering. With no passage at all, it answers that the library does not cover the question.",
  verified: "Like the previous mode, and every paragraph of the answer must cite a passage that backs it. Paragraphs without a valid citation, or that the cited passage does not support, are removed before you see the answer."
};

function fShowRagModeHint() {
  const vMode = document.getElementById("vRagMode").value;
  document.getElementById("vRagModeHint").textContent =
    fTranslate("rag.modeHint." + vMode, dRagModeHints[vMode] || "");
}

/* Similarities are on each embedding model's own scale, so the number that
 * makes sense here depends on the model chosen in Settings -> RAG. */
function fShowRagSimilarityHint(dModel) {
  const vHint = document.getElementById("vRagSimilarityHint");
  if (!dModel) { vHint.textContent = ""; return; }
  vHint.textContent = fTranslate("rag.similarityHint", "Recommended with {model}: {value}.")
    .replace("{model}", dModel.name)
    .replace("{value}", Number(dModel.min_similarity).toLocaleString(document.documentElement.lang || undefined));
}

function fCollectRagSettings() {
  return Object.assign({}, dRagSettings, {enabled: document.getElementById("vRagEnabled").checked,
    mode: document.getElementById("vRagMode").value, max_file_mb: Number(document.getElementById("vRagFileLimit").value),
    max_storage_mb: Number(document.getElementById("vRagStorage").value),
    context_characters: Number(document.getElementById("vRagContext").value),
    results: Number(document.getElementById("vRagResults").value), ocr: document.getElementById("vRagOcr").checked,
    min_similarity: Number(document.getElementById("vRagSimilarity").value),
    ocr_languages: document.getElementById("vRagLanguages").value});
}

async function fLoadRag(pAgent, pReset) {
  if (pReset || vRagAgent !== pAgent) { vRagOffset = 0; }
  vRagAgent = pAgent;
  window.clearTimeout(vRagPoll);
  try {
    const dResult = await fCallApi(fRagPath(pAgent) + "?offset=" + vRagOffset);
    if (vRagAgent !== pAgent || !dCurrentAgent || dCurrentAgent.id !== pAgent) { return; }
    fShowRagSimilarityHint(dResult.embedding_model);
    const vImportErrors = document.getElementById("vRagImportErrors");
    vImportErrors.replaceChildren();
    const lImportErrors = (dResult.import_result || {}).errors;
    if (Array.isArray(lImportErrors)) {
      lImportErrors.forEach(function (dError) {
        const vError = document.createElement("p");
        vError.textContent = (dError.name || "") + ": " + (dError.error || "");
        vImportErrors.appendChild(vError);
      });
    }
    const vRoot = document.getElementById("vRagDocuments");
    if (vRoot.querySelector("details[open]")) { return; }
    vRoot.replaceChildren();
    dResult.documents.forEach(function (dDoc) {
      const vRow = document.createElement("div"); vRow.className = "panel";
      const vTitle = document.createElement("strong"); vTitle.textContent = dDoc.title || dDoc.name; vRow.appendChild(vTitle);
      if (dDoc.subtitle) {
        const vSubtitle = document.createElement("p"); vSubtitle.className = "rag-document-subtitle";
        vSubtitle.textContent = dDoc.subtitle; vRow.appendChild(vSubtitle);
      }
      const vInfo = document.createElement("p");
      vInfo.textContent = dDoc.name + " · " + (dDoc.size / 1048576).toFixed(1) + " MiB · " +
        fTranslate("rag.state." + dDoc.state, dDoc.state) + " " + dDoc.progress + "%";
      vRow.appendChild(vInfo);
      if (dDoc.error) { const vError = document.createElement("p"); vError.textContent = dDoc.error; vRow.appendChild(vError); }
      const vActions = document.createElement("div"); vActions.className = "form-actions";
      if (dDoc.state !== "uploading") {
        const vLink = document.createElement("a"); vLink.className = "button";
        vLink.textContent = fTranslate("rag.download", "Download");
        vLink.href = "/api/admin" + fRagPath(pAgent) + "/documents/" + dDoc.id + "/content";
        vActions.appendChild(vLink);
      }
      [["reindex", "rag.reindex", "Reindex"], ["cancel", "common.cancel", "Cancel"],
       ["delete", "common.delete", "Delete"]].forEach(function (lAction) {
        const vButton = document.createElement("button"); vButton.type = "button"; vButton.className = "button";
        vButton.textContent = fTranslate(lAction[1], lAction[2]);
        vButton.addEventListener("click", async function () {
          try {
            if (lAction[0] === "delete" && !await fConfirm({title: vButton.textContent,
              message: dDoc.name, confirmLabel: vButton.textContent, danger: true})) { return; }
            await fCallApi(fRagPath(pAgent) + "/documents/" + dDoc.id,
              lAction[0] === "delete" ? "DELETE" : "PUT", {action: lAction[0]});
            await fLoadRag(pAgent);
          } catch (vError) { fShowError(vError); }
        });
        vActions.appendChild(vButton);
      });
      vRow.appendChild(vActions); vRoot.appendChild(vRow);
      const vDetails = document.createElement("details");
      const vSummary = document.createElement("summary"); vSummary.textContent = fTranslate("rag.metadata", "Document information");
      vDetails.appendChild(vSummary);
      const dInputs = {};
      ["year", "title", "subtitle", "author", "version", "language", "tags"].forEach(function (vKey) {
        const vField = document.createElement("label"); vField.className = "field";
        vField.textContent = fTranslate("rag." + (vKey === "title" ? "documentTitle" : vKey), vKey);
        const vInput = document.createElement("input"); vInput.value = dDoc[vKey] || ""; vInput.maxLength = 500;
        if (vKey === "year") { vInput.inputMode = "numeric"; vInput.maxLength = 4; }
        vField.appendChild(vInput); vDetails.appendChild(vField); dInputs[vKey] = vInput;
      });
      const vSave = document.createElement("button"); vSave.type = "button"; vSave.className = "button";
      vSave.textContent = fTranslate("common.save", "Save");
      vSave.addEventListener("click", async function () {
        const dMetadata = {}; Object.keys(dInputs).forEach(function (vKey) { dMetadata[vKey] = dInputs[vKey].value; });
        try { await fCallApi(fRagPath(pAgent) + "/documents/" + dDoc.id, "PUT", {action: "metadata", metadata: dMetadata}); vDetails.open = false; await fLoadRag(pAgent); }
        catch (vError) { fShowError(vError); }
      });
      vDetails.appendChild(vSave);
      const vReplaceLabel = document.createElement("label"); vReplaceLabel.className = "field";
      vReplaceLabel.textContent = fTranslate("rag.replace", "Replace file");
      const vReplace = document.createElement("input"); vReplace.type = "file"; vReplace.accept = ".pdf,.epub,.txt,.md";
      vReplace.addEventListener("change", function () { if (vReplace.files[0]) { fUploadRag([vReplace.files[0]], dDoc.id, pAgent); } });
      vReplaceLabel.appendChild(vReplace); vDetails.appendChild(vReplaceLabel); vRow.appendChild(vDetails);
      /* Polling must not discard metadata while a person is editing it. */
      vDetails.addEventListener("toggle", function () {
        if (vDetails.open) { window.clearTimeout(vRagPoll); }
        else if (vDetails.isConnected) { fLoadRag(pAgent); }
      });
    });
    document.getElementById("vRagTotals").textContent = fTranslate("rag.totals", "{count} documents · {chunks} passages · {size} MiB")
      .replace("{count}", dResult.totals.count).replace("{chunks}", dResult.totals.chunks)
      .replace("{size}", (dResult.totals.bytes / 1048576).toFixed(1));
    document.getElementById("vRagPrevious").disabled = vRagOffset === 0;
    document.getElementById("vRagNext").disabled = vRagOffset + 100 >= dResult.totals.count;
    if (!document.querySelector('[data-agent-panel="rag"]').hidden) {
      vRagPoll = window.setTimeout(function () { fLoadRag(pAgent); }, 5000);
    }
  } catch (vError) { fShowError(vError); }
}

async function fUploadRag(pFiles, pReplaces, pAgent) {
  if (!dCurrentAgent || vRagUploading) { return; }
  const vAgent = pAgent || dCurrentAgent.id;
  const lFiles = pFiles || Array.from(document.getElementById("vRagFiles").files);
  vRagUploading = true; vRagUploadCancelled = false;
  document.getElementById("vRagCancelUpload").hidden = false;
  let vDocument = "";
  try {
    for (const vFile of lFiles) {
      if (vRagUploadCancelled) { break; }
      const dUpload = await fCallApi(fRagPath(vAgent) + "/documents", "POST", {name: vFile.name, size: vFile.size, replaces: pReplaces || ""});
      vDocument = dUpload.document_id;
      for (let vOffset = 0; vOffset < vFile.size; vOffset += dUpload.chunk_bytes) {
        if (vRagUploadCancelled) { throw new Error(fTranslate("common.cancel", "Cancel")); }
        const aBytes = new Uint8Array(await vFile.slice(vOffset, vOffset + dUpload.chunk_bytes).arrayBuffer());
        let vBinary = ""; aBytes.forEach(function (vByte) { vBinary += String.fromCharCode(vByte); });
        await fCallApi(fRagPath(vAgent) + "/documents/" + vDocument + "/upload", "PUT", {offset: vOffset, data: btoa(vBinary)});
        document.getElementById("vRagProgress").textContent = vFile.name + " · " + Math.round((vOffset + aBytes.length) / vFile.size * 100) + "%";
      }
      await fCallApi(fRagPath(vAgent) + "/documents/" + vDocument + "/upload", "POST", {});
      vDocument = "";
    }
    if (dCurrentAgent.id === vAgent) { await fLoadRag(vAgent); }
  } catch (vError) {
    if (vDocument) {
      try { await fCallApi(fRagPath(vAgent) + "/documents/" + vDocument, "DELETE"); } catch (vCleanupError) { fShowError(vCleanupError); }
    }
    fShowError(vError);
  } finally { vRagUploading = false; document.getElementById("vRagCancelUpload").hidden = true; }
}

async function fSearchRag() {
  if (!dCurrentAgent) { return; }
  const vAgent = dCurrentAgent.id;
  try {
    const dResult = await fCallApi(fRagPath(vAgent) + "/search", "POST", {query: document.getElementById("vRagQuery").value,
      filters: {version: document.getElementById("vRagFilterVersion").value, language: document.getElementById("vRagFilterLanguage").value}});
    if (dCurrentAgent.id !== vAgent) { return; }
    const vRoot = document.getElementById("vRagSearchResults"); vRoot.replaceChildren();
    dResult.sources.forEach(function (dSource) {
      const vLink = document.createElement("a"); vLink.href = dSource.url; vLink.textContent = dSource.title + " · " + dSource.location;
      const vText = document.createElement("pre"); vText.textContent = dSource.text; vText.style.whiteSpace = "pre-wrap";
      vRoot.append(vLink, vText);
    });
    if (!dResult.sources.length) { vRoot.textContent = fTranslate("rag.noSources", "No supporting passages were found."); }
  } catch (vError) { fShowError(vError); }
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("vRagUpload").addEventListener("click", function () { fUploadRag(); });
  document.getElementById("vRagMode").addEventListener("change", fShowRagModeHint);
  document.querySelectorAll('[data-agent-panel="rag"] input').forEach(function (vInput) {
    vInput.addEventListener("invalid", function () { fSelectAgentTab("rag"); });
  });
  document.getElementById("vRagCancelUpload").addEventListener("click", function () { vRagUploadCancelled = true; });
  document.getElementById("vRagRefresh").addEventListener("click", function () { if (dCurrentAgent) { fLoadRag(dCurrentAgent.id); } });
  document.getElementById("vRagImport").addEventListener("click", async function () {
    if (!dCurrentAgent) { return; }
    try { await fCallApi(fRagPath(dCurrentAgent.id) + "/import", "POST", {}); fShowNotice(fTranslate("rag.queued", "Import queued"), "ok"); }
    catch (vError) { fShowError(vError); }
  });
  document.getElementById("vRagSearch").addEventListener("click", fSearchRag);
  document.getElementById("vRagPrevious").addEventListener("click", function () { vRagOffset = Math.max(0, vRagOffset - 100); fLoadRag(vRagAgent); });
  document.getElementById("vRagNext").addEventListener("click", function () { vRagOffset += 100; fLoadRag(vRagAgent); });
});
