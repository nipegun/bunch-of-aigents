/* The Export tab: what each option would add, and the download itself.
 *
 * The preview is asked for every time the tab opens, because a home and a
 * library change while nobody looks, and "Files in its home" is the one option
 * worth reading before ticking: it can hold things nobody meant to share. */
let vExportAgent = "";

function fExportMebibytes(pBytes) {
  return (Number(pBytes || 0) / 1048576).toFixed(1) + " MiB";
}

async function fLoadExportPreview(pAgent) {
  vExportAgent = pAgent;
  ["vExportMemoryHint", "vExportProviderHint", "vExportRagHint", "vExportHomeHint"].forEach(function (vId) {
    document.getElementById(vId).textContent = "…";
  });
  document.getElementById("vExportHomeList").hidden = true;
  try {
    const dPreview = await fCallApi("/agents/" + encodeURIComponent(pAgent) + "/export/preview");
    if (vExportAgent !== pAgent) { return; }
    document.getElementById("vExportMemoryHint").textContent =
      fTranslate("export.memoryHint", "{count} characters.").replace("{count}", dPreview.memory_characters);
    document.getElementById("vExportProviderHint").textContent = dPreview.provider.name
      ? fTranslate("export.providerHint", "{provider} / {model}. Never its key.")
        .replace("{provider}", dPreview.provider.name).replace("{model}", dPreview.provider.model || "-")
      : fTranslate("export.providerNone", "It has no provider yet.");
    document.getElementById("vExportRagHint").textContent =
      fTranslate("export.ragHint", "{count} documents, {size}. They are indexed again where they are imported.")
        .replace("{count}", dPreview.rag_documents).replace("{size}", fExportMebibytes(dPreview.rag_bytes));
    document.getElementById("vExportHomeHint").textContent =
      fTranslate("export.homeHint", "{count} files, {size}. They may hold things you would not share: check the list.")
        .replace("{count}", dPreview.home_count).replace("{size}", fExportMebibytes(dPreview.home_bytes));
    const vList = document.getElementById("vExportHomeFiles");
    vList.replaceChildren();
    dPreview.home_files.forEach(function (dFile) {
      const vItem = document.createElement("li");
      vItem.textContent = dFile.path + " · " + fExportMebibytes(dFile.size);
      vList.appendChild(vItem);
    });
    document.getElementById("vExportHomeList").hidden = dPreview.home_files.length === 0;
  } catch (vError) {
    fShowError(vError);
  }
}

/* A link, not a fetch: the .zip can weigh hundreds of MiB, and the browser
 * saves a download to disk as it arrives instead of holding it in memory. */
function fDownloadExport() {
  if (!dCurrentAgent) { return; }
  const vQuery = new URLSearchParams();
  [["memory", "vExportMemory"], ["provider", "vExportProvider"], ["rag", "vExportRag"],
   ["home", "vExportHome"]].forEach(function (lOption) {
    vQuery.set(lOption[0], document.getElementById(lOption[1]).checked ? "1" : "0");
  });
  const vLink = document.createElement("a");
  vLink.href = "/api/admin/agents/" + encodeURIComponent(dCurrentAgent.id) + "/export?" + vQuery.toString();
  vLink.download = "";
  document.body.appendChild(vLink);
  vLink.click();
  vLink.remove();
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("vExportButton").addEventListener("click", fDownloadExport);
});
