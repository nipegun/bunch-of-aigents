"""Privileged RAG broker: fixed commands, always running document code as its owner."""

import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import threading

from backend.core import paths, rag_settings

dWorkers={}
vWorkerLock=threading.Lock()
sOperations={"list","begin","chunk","finish","action","content","import","search","ensure","snapshot","snapshot_cleanup"}


def fCommand(pAgentId,pOperation):
  vAgentId=paths.fNormalizeAgentId(pAgentId)
  vUser=pwd.getpwnam(paths.fGetAgentSystemUser(vAgentId))
  from backend.core.exec_daemon import fBuildAgentEnvironment
  dEnvironment=fBuildAgentEnvironment(paths.fGetAgentSystemUser(vAgentId),vUser)
  # Limit native numerical libraries before they are imported in the child.
  dEnvironment.update({"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1"})
  return ([sys.executable,"-m","backend.core.rag_worker","--agent",vAgentId,"--operation",pOperation],
    {"user":vUser.pw_uid,"group":vUser.pw_gid,"extra_groups":[],
     "cwd":paths.fGetAgentHome(vAgentId),"env":dEnvironment,"start_new_session":True})


def fDispatch(pParams):
  vAgentId=paths.fNormalizeAgentId(pParams.get("agent_id"))
  vOperation=pParams.get("operation")
  if vOperation=="work":
    return fStartWork(vAgentId)
  if vOperation not in sOperations:
    raise ValueError("Unknown RAG operation.")
  dArguments=pParams.get("arguments") or {}
  if not isinstance(dArguments,dict):
    raise ValueError("RAG arguments must be an object.")
  vPayload=json.dumps(dArguments).encode()
  if len(vPayload)>1024*1024:
    raise ValueError("RAG request is too large.")
  lCommand,dOptions=fCommand(vAgentId,vOperation)
  try:
    vResult=subprocess.run(lCommand,input=vPayload,capture_output=True,timeout=50,**dOptions)
  except subprocess.TimeoutExpired as vError:
    raise ValueError("The RAG operation timed out. Check the local embedding service.") from vError
  try:
    dResult=json.loads(vResult.stdout)
  except (ValueError,UnicodeDecodeError) as vError:
    raise ValueError("The RAG process failed. Check the document and available memory.") from vError
  if not dResult.get("ok"):
    raise ValueError(dResult.get("error") or "RAG operation failed.")
  return dResult["result"]


def fStartWork(pAgentId):
  with vWorkerLock:
    for vId,vProcess in list(dWorkers.items()):
      if vProcess.poll() is not None:
        del dWorkers[vId]
    if pAgentId in dWorkers or len(dWorkers)>=rag_settings.fRuntimeSettings()["workers"]:
      return {"started":False}
    if not rag_settings.fDirectory(pAgentId).exists():
      return {"started":False}
    lCommand,dOptions=fCommand(pAgentId,"work")
    vProcess=subprocess.Popen(lCommand,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,**dOptions)
    dWorkers[pAgentId]=vProcess
    return {"started":True}


def fStopWork(pAgentId):
  import signal
  with vWorkerLock:
    vProcess=dWorkers.pop(pAgentId,None)
    if vProcess and vProcess.poll() is None:
      try:
        os.killpg(vProcess.pid,signal.SIGTERM)
      except ProcessLookupError:
        return
      try:
        vProcess.wait(timeout=5)
      except subprocess.TimeoutExpired:
        os.killpg(vProcess.pid,signal.SIGKILL)
        vProcess.wait()


def fRuntime(pParams):
  from backend.core import rag_runtime
  if "settings" in pParams:
    dSettings=pParams["settings"]
    dPrevious=rag_settings.fSelectedModel()
    dNext=rag_settings.fFindModel(dSettings.get("model",dPrevious["id"])) if isinstance(dSettings,dict) else None
    # Switching to weights that are not on disk would leave the engine with
    # nothing to load and every library waiting for it.
    if dNext is not None and not rag_runtime.fIsModelInstalled(dNext):
      raise ValueError("Download %s before choosing it." % dNext["name"])
    rag_settings.fSaveRuntimeSettings(dSettings)
    if dNext is not None and dNext["id"]!=dPrevious["id"]:
      fFollowModelSimilarity(dPrevious,dNext)
    # The process manager restarts the local engine with the new thread limit
    # or the new model. Each library notices a new model on its next pass and
    # indexes its documents again (rag_worker.fWork).
    if os.path.isdir("/run/systemd/system"):
      lCommand=["systemctl","restart","boa-embeddings.service"]
    else:
      lCommand=["rc-service","boa-embeddings","restart"]
    subprocess.run(lCommand,check=True,capture_output=True,timeout=30)
  return rag_runtime.fDescribe()


def fFollowModelSimilarity(pPrevious,pNext):
  """Move each agent still on the old model's minimum similarity to the new one's.

  Similarities are on each model's own scale: 0.2 is a sensible floor for one
  and lets unrelated passages through for another. An agent whose value is the
  old model's recommendation never chose it, so it follows the model; one set
  to anything else keeps its value.
  """
  from backend.core import agents
  for vHome in sorted(Path(paths.fGetAgentsDir()).iterdir()):
    if len(vHome.name)!=3 or not vHome.name.isdigit() or vHome.is_symlink():
      continue
    try:
      dInfo=agents.fReadAgentInfo(vHome.name)
    except (ValueError,RuntimeError):
      continue
    dRag=dInfo.get("rag")
    if not isinstance(dRag,dict) or dRag.get("min_similarity")!=pPrevious["min_similarity"]:
      continue
    dRag["min_similarity"]=pNext["min_similarity"]
    agents.fWriteAgentInfo(vHome.name,dInfo)
