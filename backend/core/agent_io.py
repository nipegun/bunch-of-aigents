"""Installing, importing and exporting agents. Runs in the web application.

Everything that touches an agent goes through the executor, as the rest of
the web application does: the agent is created by create_agent, its memory
written by write_memory, its home files by agent_home and its library by the
RAG verbs, each of them running as the agent. This module only decides the
order, and undoes the agent when a later step fails.

An import of a .zip happens in three moments, because a library can weigh
hundreds of MiB and no single request may take that long:

  1. the browser uploads the .zip in chunks into /opt/boa/imports/<id>/;
  2. it is checked whole, and what it would install is shown to the user;
  3. once the user confirms, it is installed by a thread of this process,
     which writes its progress into job.json for the browser to poll.
"""

import base64
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile

from backend.core import agent_package
from backend.core import agents
from backend.core import exec_client
from backend.core import paths
from backend.core import rag_settings
from backend.core import rag_store
from backend.core import tool_registry

cUploadChunkBytes = rag_settings.cUploadChunkBytes
cHomeChunkBytes = 1024 * 1024
cImportIdPattern = re.compile(r"^[a-f0-9]{32}$")
cJobName = "job.json"
cPackageName = "package.zip"
# An import nobody finished is removed after this long.
cStaleSeconds = 24 * 3600
# A job whose thread has not written for this long died with its process.
cHeartbeatSeconds = 180
# The line of a crontab this application writes for an agent: five fields,
# the interpreter, the runner, and the agent it belongs to.
cScheduleLinePattern = re.compile(
  r"^\s*(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+\S+\s+\S*runner\.py\s+--agent-id\s+(\S+)\s*$")


def fInstalledToolNames():
  dTools, _ = tool_registry.fLoadAllTools()
  return sorted(dTools)


# ----------------------------------------------------------------- install --

def fInstallPackage(pSource, pPackage, pName="", pLanguage="", fProgress=None):
  """Create an agent from a checked package. Returns its id.

  The agent is created switched off whatever the package says: it has come
  from somewhere else, and it runs only when its owner here says so.
  """
  fReport = fProgress or (lambda pStep, pDone=0, pTotal=0: None)
  dProvider = pPackage["provider"] or {}
  fReport("agent")
  dResult = exec_client.fCreateAgent(
    pName=agents.fValidateAgentName(pName or pPackage["name"]),
    pDescription=agent_package.fPickDescription(pPackage["description"], pLanguage),
    pProvider=dProvider.get("name") or "ollama",
    pModel=dProvider.get("model", ""),
    pBaseUrl=dProvider.get("base_url", ""),
    pSystemPrompt=pPackage["system_prompt"],
    pTools=pPackage["tools"],
    pSkills=pPackage["skills"],
    pLimits=pPackage["limits"] or None,
    pEnabled=False,
    pRag=pPackage["rag"],
    pSchedules=pPackage["schedules"],
  )
  vAgentId = dResult["agent_id"]
  try:
    dInfo = {}
    if not pPackage["kanban_enabled"]:
      dInfo["kanban_enabled"] = False
    if pPackage["fallback_provider"] and pPackage["fallback_provider"]["name"]:
      dInfo["fallback_provider"] = pPackage["fallback_provider"]
    if dInfo:
      exec_client.fWriteAgentInfo(vAgentId, dInfo)
    if pPackage["memory"] is not None:
      fReport("memory")
      exec_client.fWriteMemory(vAgentId, pPackage["memory"])
    lHome = pPackage["home"]
    for vIndex, dFile in enumerate(lHome):
      fReport("home", vIndex, len(lHome))
      fCopyHomeFile(pSource, vAgentId, dFile)
    lDocuments = pPackage["rag_documents"]
    for vIndex, dDocument in enumerate(lDocuments):
      fReport("rag", vIndex, len(lDocuments))
      fCopyRagDocument(pSource, vAgentId, dDocument)
  except BaseException:
    # Half an agent is worse than none: the user would find something that
    # looks installed and is missing its library.
    try:
      exec_client.fDeleteAgent(vAgentId)
    except Exception:
      pass
    raise
  fReport("done", 1, 1)
  return vAgentId


def fCopyHomeFile(pSource, pAgentId, pFile):
  vOffset = 0
  vBuffer = b""
  for vData in pSource.fChunks(pFile["member"]):
    vBuffer += vData
    while len(vBuffer) >= cHomeChunkBytes:
      exec_client.fAgentHome(pAgentId, "write", {"path": pFile["path"], "offset": vOffset,
        "data": base64.b64encode(vBuffer[:cHomeChunkBytes]).decode(), "mode": pFile["mode"]})
      vOffset += cHomeChunkBytes
      vBuffer = vBuffer[cHomeChunkBytes:]
  if vBuffer or vOffset == 0:
    exec_client.fAgentHome(pAgentId, "write", {"path": pFile["path"], "offset": vOffset,
      "data": base64.b64encode(vBuffer).decode(), "mode": pFile["mode"]})


def fCopyRagDocument(pSource, pAgentId, pDocument):
  """Upload one original the way the RAG tab does, then its information."""
  dUpload = exec_client.fRag(pAgentId, "begin", {"name": pDocument["name"], "size": pDocument["size"]})
  vDocumentId = dUpload["document_id"]
  vOffset = 0
  vBuffer = b""
  for vData in pSource.fChunks(pDocument["file"]):
    vBuffer += vData
    while len(vBuffer) >= cUploadChunkBytes:
      exec_client.fRag(pAgentId, "chunk", {"id": vDocumentId, "offset": vOffset,
        "data": base64.b64encode(vBuffer[:cUploadChunkBytes]).decode()})
      vOffset += cUploadChunkBytes
      vBuffer = vBuffer[cUploadChunkBytes:]
  if vBuffer:
    exec_client.fRag(pAgentId, "chunk", {"id": vDocumentId, "offset": vOffset,
      "data": base64.b64encode(vBuffer).decode()})
  dFinished = exec_client.fRag(pAgentId, "finish", {"id": vDocumentId})
  vKept = dFinished.get("duplicate") or vDocumentId
  if pDocument["metadata"]:
    exec_client.fRag(pAgentId, "action", {"id": vKept, "action": "metadata",
                                          "metadata": pDocument["metadata"]})


# ------------------------------------------------------------------ imports --

def fImportDir(pImportId):
  if not cImportIdPattern.match(str(pImportId or "")):
    raise ValueError("Unknown import.")
  return Path(paths.fGetImportsDir()) / pImportId


def fReadJob(pImportId):
  vPath = fImportDir(pImportId) / cJobName
  try:
    dJob = json.loads(vPath.read_text(encoding="utf-8"))
  except (OSError, ValueError):
    raise ValueError("Unknown import.")
  if dJob.get("state") == "installing" and time.time() - dJob.get("heartbeat", 0) > cHeartbeatSeconds:
    dJob["state"] = "interrupted"
    dJob["error"] = "The installation stopped: the web application restarted while it ran."
  return dJob


def fWriteJob(pImportId, pJob):
  vDirectory = fImportDir(pImportId)
  dJob = dict(pJob, heartbeat=time.time())
  vTemporary = vDirectory / (cJobName + ".tmp")
  vTemporary.write_text(json.dumps(dJob, ensure_ascii=False), encoding="utf-8")
  os.replace(vTemporary, vDirectory / cJobName)
  return dJob


def fRemoveStaleImports():
  vRoot = Path(paths.fGetImportsDir())
  if not vRoot.is_dir():
    return
  for vDirectory in vRoot.iterdir():
    if not cImportIdPattern.match(vDirectory.name) or vDirectory.is_symlink():
      continue
    try:
      if time.time() - vDirectory.stat().st_mtime > cStaleSeconds:
        shutil.rmtree(vDirectory, ignore_errors=True)
    except OSError:
      pass


def fBeginImport(pName, pSize):
  if type(pSize) is not int or not 0 < pSize <= agent_package.cMaxPackageBytes:
    raise ValueError("The .zip is empty or larger than %d GiB." % (agent_package.cMaxPackageBytes // 1024 ** 3,))
  if not str(pName or "").lower().endswith(".zip"):
    raise ValueError("Choose a .zip exported from an agent.")
  vRoot = Path(paths.fGetImportsDir())
  if not vRoot.is_dir():
    raise ValueError("The imports directory %s does not exist. Run the installer with --update." % (vRoot,))
  fRemoveStaleImports()
  vImportId = uuid.uuid4().hex
  vDirectory = vRoot / vImportId
  vDirectory.mkdir(mode=0o700)
  vDescriptor = os.open(vDirectory / cPackageName, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
  os.close(vDescriptor)
  fWriteJob(vImportId, {"state": "uploading", "size": pSize, "received": 0})
  return {"import_id": vImportId, "chunk_bytes": cUploadChunkBytes}


def fUploadImportChunk(pImportId, pOffset, pData):
  dJob = fReadJob(pImportId)
  try:
    vData = base64.b64decode(pData or "", validate=True)
  except (ValueError, TypeError):
    raise ValueError("Invalid upload data.")
  if dJob["state"] != "uploading" or type(pOffset) is not int or not vData or len(vData) > cUploadChunkBytes:
    raise ValueError("Invalid upload chunk.")
  if pOffset != dJob["received"] or pOffset + len(vData) > dJob["size"]:
    raise ValueError("Resume the upload at byte %d." % (dJob["received"],))
  vDescriptor = os.open(fImportDir(pImportId) / cPackageName, os.O_WRONLY | os.O_NOFOLLOW)
  try:
    os.pwrite(vDescriptor, vData, pOffset)
  finally:
    os.close(vDescriptor)
  dJob["received"] = pOffset + len(vData)
  fWriteJob(pImportId, dJob)
  return {"received": dJob["received"]}


def fOpenImport(pImportId):
  """The checked package of an uploaded .zip, and its source."""
  try:
    vSource = agent_package.ZipSource(fImportDir(pImportId) / cPackageName)
  except (zipfile.BadZipFile, OSError) as vError:
    raise agent_package.PackageError("This is not a .zip that can be read: %s" % (vError,))
  try:
    return vSource, agent_package.fReadPackage(vSource, fInstalledToolNames())
  except BaseException:
    vSource.fClose()
    raise


def fFinishImport(pImportId, pLanguage=""):
  """Check the uploaded .zip whole, and say what it would install."""
  dJob = fReadJob(pImportId)
  if dJob["state"] not in ("uploading", "ready", "invalid"):
    raise ValueError("This import is already %s." % (dJob["state"],))
  if dJob["received"] != dJob["size"]:
    raise ValueError("The upload is incomplete.")
  try:
    vSource, dPackage = fOpenImport(pImportId)
  except agent_package.PackageError as vError:
    fWriteJob(pImportId, dict(dJob, state="invalid", error=str(vError)))
    raise
  vSource.fClose()
  dSummary = agent_package.fSummarise(dPackage, pLanguage)
  fWriteJob(pImportId, dict(dJob, state="ready", summary=dSummary))
  return dSummary


def fStartImport(pImportId, pName="", pLanguage=""):
  """Install a checked import in the background. Poll fReadJob for progress."""
  dJob = fReadJob(pImportId)
  if dJob["state"] != "ready":
    raise ValueError("This import is not ready to install (%s)." % (dJob["state"],))
  if pName:
    agents.fValidateAgentName(pName)
  # One installer per import, even with two workers and two clicks: whoever
  # creates the marker first installs.
  try:
    os.close(os.open(fImportDir(pImportId) / "install.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
  except FileExistsError:
    raise ValueError("This import is already being installed.")
  dJob = fWriteJob(pImportId, dict(dJob, state="installing", step="agent", done=0, total=0))
  vThread = threading.Thread(target=fRunImport, args=(pImportId, dJob, pName, pLanguage), daemon=True)
  vThread.start()
  return dJob


def fRunImport(pImportId, pJob, pName, pLanguage):
  dJob = dict(pJob)

  def fProgress(pStep, pDone=0, pTotal=0):
    dJob.update(step=pStep, done=pDone, total=pTotal)
    fWriteJob(pImportId, dJob)

  vSource = None
  try:
    vSource, dPackage = fOpenImport(pImportId)
    vAgentId = fInstallPackage(vSource, dPackage, pName, pLanguage, fProgress)
    dJob.update(state="installed", agent_id=vAgentId)
  except Exception as vError:
    dJob.update(state="failed", error=str(vError)[:1000])
  finally:
    if vSource is not None:
      vSource.fClose()
  # The .zip is not needed any more; the job stays for the browser to read,
  # until fRemoveStaleImports takes it.
  try:
    (fImportDir(pImportId) / cPackageName).unlink()
  except OSError:
    pass
  fWriteJob(pImportId, dJob)


def fCancelImport(pImportId):
  dJob = fReadJob(pImportId)
  if dJob["state"] == "installing":
    raise ValueError("An installation cannot be cancelled half-way.")
  shutil.rmtree(fImportDir(pImportId), ignore_errors=True)
  return {"removed": True}


# ------------------------------------------------------------------ export --

def fReadSchedules(pAgentId, pCrontab):
  """The schedules of the lines this application wrote to run the agent.

  Only those: any other line in the crontab is a command somebody typed, and
  a package that carried commands would run them on the machine it lands on.
  """
  lSchedules = []
  for vLine in str(pCrontab or "").splitlines():
    vMatch = cScheduleLinePattern.match(vLine)
    if vMatch and paths.fNormalizeAgentId(vMatch.group(2)) == paths.fNormalizeAgentId(pAgentId):
      try:
        lSchedules.append(agents.fValidateSchedule(vMatch.group(1)))
      except ValueError:
        continue
  return lSchedules


def fListRagDocuments(pAgentId):
  lDocuments = []
  vOffset = 0
  while True:
    dPage = exec_client.fRag(pAgentId, "list", {"offset": vOffset, "limit": 200})
    lDocuments += [dDocument for dDocument in dPage["documents"] if dDocument["state"] != "uploading"]
    vOffset += 200
    if vOffset >= dPage["totals"]["count"]:
      return lDocuments


def fPreviewExport(pAgentId):
  """What each export option would add, so the user sees it before choosing."""
  vMemory = exec_client.fReadMemory(pAgentId).get("memory", "")
  lHome = exec_client.fAgentHome(pAgentId, "list")["files"]
  lDocuments = fListRagDocuments(pAgentId)
  dInfo = exec_client.fReadAgentInfo(pAgentId).get("info") or {}
  dProvider = dInfo.get("provider") or {}
  return {
    "memory_characters": len(vMemory),
    "home_files": [{"path": dFile["path"], "size": dFile["size"]} for dFile in lHome[:500]],
    "home_count": len(lHome),
    "home_bytes": sum(dFile["size"] for dFile in lHome),
    "rag_documents": len(lDocuments),
    "rag_bytes": sum(dDocument["size"] for dDocument in lDocuments),
    "provider": {"name": dProvider.get("name", ""), "model": dProvider.get("model", "")},
  }


def fSafeMemberName(pName):
  vName = re.sub(r"[\x00-\x1f/\\]+", "_", str(pName)).strip(" .")
  return vName[:180] or "document"


class ZipStream:
  """The write end of a zip that is sent while it is being written."""

  def __init__(self):
    self.lChunks = []
    self.vPosition = 0

  def write(self, pData):
    self.lChunks.append(bytes(pData))
    self.vPosition += len(pData)
    return len(pData)

  def tell(self):
    return self.vPosition

  def flush(self):
    pass

  def fDrain(self):
    vData = b"".join(self.lChunks)
    self.lChunks = []
    return vData


def fBuildManifest(pAgentId, pInfo, pCrontab, pIncludeProvider):
  dManifest = {
    "format": agent_package.cFormatVersion,
    "name": pInfo.get("name", ""),
    "description": pInfo.get("description", ""),
    "tools": list(pInfo.get("tools") or []),
    "skills": list(pInfo.get("skills") or []),
    "schedules": fReadSchedules(pAgentId, pCrontab),
    "limits": {vKey: vValue for vKey, vValue in (pInfo.get("limits") or {}).items()
               if vKey in agents.dDefaultLimits},
    "rag": pInfo.get("rag") or rag_settings.fValidateSettings({}),
    "kanban_enabled": bool(pInfo.get("kanban_enabled", True)),
    "exported_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  }
  if pIncludeProvider:
    # Which provider and model, never the key: api_key_ref is left out here,
    # and the key itself is not something this process can read.
    for vKey in ("provider", "fallback_provider"):
      dProvider = pInfo.get(vKey) or {}
      if dProvider.get("name"):
        dManifest[vKey] = {"name": dProvider.get("name", ""), "model": dProvider.get("model", ""),
                           "base_url": dProvider.get("base_url", "")}
  return dManifest


def fExportAgent(pAgentId, pMemory=False, pHome=False, pProvider=False, pRag=False):
  """Yield the bytes of the agent's .zip while they are produced.

  Everything is read before the first byte is sent, except the contents of
  the home files and of the library, which are streamed: an agent with a
  library of hundreds of MiB is exported without holding it in memory.
  """
  dInfo = exec_client.fReadAgentInfo(pAgentId).get("info") or {}
  vPrompt = exec_client.fReadSystemPrompt(pAgentId).get("system_prompt", "")
  vCrontab = exec_client.fReadCrontab(pAgentId).get("crontab", "")
  dManifest = fBuildManifest(pAgentId, dInfo, vCrontab, pProvider)
  vMemory = exec_client.fReadMemory(pAgentId).get("memory", "") if pMemory else None
  lHome = exec_client.fAgentHome(pAgentId, "list")["files"] if pHome else []
  lDocuments = fListRagDocuments(pAgentId) if pRag else []

  vStream = ZipStream()
  with zipfile.ZipFile(vStream, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as vZip:
    vZip.writestr(agent_package.cManifestName,
                  json.dumps(dManifest, ensure_ascii=False, indent=2) + "\n")
    vZip.writestr(agent_package.cPromptName, vPrompt)
    if vMemory is not None:
      vZip.writestr(agent_package.cMemoryName, vMemory)
    yield vStream.fDrain()

    for dFile in lHome:
      vInfo = zipfile.ZipInfo(agent_package.cHomePrefix + dFile["path"])
      vInfo.external_attr = (0o100000 | dFile["mode"]) << 16
      vInfo.compress_type = zipfile.ZIP_DEFLATED
      with vZip.open(vInfo, "w", force_zip64=True) as vEntry:
        vOffset = 0
        while True:
          dChunk = exec_client.fAgentHome(pAgentId, "read", {"path": dFile["path"], "offset": vOffset})
          vData = base64.b64decode(dChunk["data"])
          if not vData:
            break
          vEntry.write(vData)
          vOffset += len(vData)
          yield vStream.fDrain()

    lIndex = []
    for vIndex, dDocument in enumerate(lDocuments, 1):
      vMember = "%s%04d-%s" % (agent_package.cRagFilesPrefix, vIndex, fSafeMemberName(dDocument["name"]))
      lIndex.append({"file": vMember, "name": dDocument["name"],
                     "metadata": {vKey: dDocument.get(vKey, "") for vKey in rag_store.lMetadataKeys}})
      # Deflated even though a PDF barely shrinks: written as a stream, an
      # entry's size is only known after it, and a stored entry of unknown
      # size is one that readers going through the file in order cannot skip.
      vInfo = zipfile.ZipInfo(vMember)
      vInfo.compress_type = zipfile.ZIP_DEFLATED
      with vZip.open(vInfo, "w", force_zip64=True) as vEntry:
        vOffset = 0
        while vOffset < dDocument["size"]:
          dChunk = exec_client.fRag(pAgentId, "content", {"id": dDocument["id"], "offset": vOffset})
          vData = base64.b64decode(dChunk["data"])
          if not vData:
            break
          vEntry.write(vData)
          vOffset += len(vData)
          yield vStream.fDrain()
    if lIndex:
      vZip.writestr(agent_package.cRagIndexName, json.dumps(lIndex, ensure_ascii=False, indent=2) + "\n")
  yield vStream.fDrain()


def fExportFileName(pInfo):
  vName = re.sub(r"[^A-Za-z0-9._-]+", "-", str(pInfo.get("name") or "agent")).strip("-.") or "agent"
  return "%s.zip" % (vName,)
