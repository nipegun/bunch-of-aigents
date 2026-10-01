#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Install verified embedding weights and serve them over a local Unix socket."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import stat
import subprocess
import sys
import threading
import time
import tempfile
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from backend.core import rag_embeddings, rag_settings


# One download at a time, inside the privileged executor: the HTTP request
# that asks for it returns at once and the page polls the status file.
vDownloadPool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="rag-model")
vDownloadLock=threading.Lock()
dDownloads={}


def fModelPath(pModel):
  return rag_settings.fRuntimeDirectory()/"models"/pModel["file"]


def fIsModelInstalled(pModel):
  """Present at its catalogue size. The hash was checked before it got its name."""
  try:
    dStat=fModelPath(pModel).lstat()
  except OSError:
    return False
  return stat.S_ISREG(dStat.st_mode) and dStat.st_size==pModel["size"]


def fStatusPath(pModel):
  return rag_settings.fRuntimeDirectory()/"status"/(pModel["id"]+".json")


def fWriteStatus(pModel,pState,pDownloaded=0,pError=""):
  vPath=fStatusPath(pModel)
  vPath.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
  vTemporary=vPath.with_suffix(".json.tmp")
  vTemporary.write_text(json.dumps({"state":pState,"downloaded":pDownloaded,"total":pModel["size"],
    "error":str(pError)[:500],"pid":os.getpid(),"updated_at":int(time.time())})+"\n")
  os.chmod(vTemporary,0o644)
  os.replace(vTemporary,vPath)


def fReadStatus(pModel):
  if fIsModelInstalled(pModel):
    return {"state":"installed","downloaded":pModel["size"],"total":pModel["size"]}
  try:
    dStatus=json.loads(fStatusPath(pModel).read_text())
  except (OSError,ValueError):
    return {"state":"missing","downloaded":0,"total":pModel["size"]}
  if dStatus.get("state") in ("queued","downloading"):
    try:
      os.kill(int(dStatus["pid"]),0)
    except PermissionError:
      pass  # Alive, and not ours to signal.
    except (OSError,ValueError,KeyError):
      return {"state":"failed","downloaded":0,"total":pModel["size"],"error":"Download interrupted. Try again."}
  return dStatus


def fInstallModel(pModelId=None):
  """Download and verify one model's weights; the selected one by default.

  Network access is limited to this explicit installation operation, run by
  the installer or, for a model chosen in Settings -> RAG, by the executor.
  The file only gets its final name once its size and SHA-256 match.
  """
  dModel=rag_settings.fFindModel(pModelId) if pModelId else rag_settings.fSelectedModel()
  if dModel is None:
    raise ValueError("Unknown embedding model.")
  vPath=fModelPath(dModel)
  vPath.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
  if vPath.is_file() and vPath.stat().st_size==dModel["size"]:
    with vPath.open("rb") as vFile:
      if hashlib.file_digest(vFile,"sha256").hexdigest()==dModel["sha256"]:
        return fReadStatus(dModel)
  if shutil.disk_usage(vPath.parent).free<dModel["size"]+64*1024*1024:
    raise ValueError("There is not enough free disk space for this model.")
  vTemporary=vPath.with_suffix(".part")
  vDigest=hashlib.sha256()
  vBytes=0
  fWriteStatus(dModel,"downloading")
  try:
    vDescriptor=os.open(vTemporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    vRequest=Request(dModel["url"],headers={"User-Agent":"BoA-rag-models/1"})
    with os.fdopen(vDescriptor,"wb") as vFile, urlopen(vRequest,timeout=60) as vResponse:
      vLastUpdate=0.0
      while vChunk:=vResponse.read(1024*1024):
        vBytes+=len(vChunk)
        if vBytes>dModel["size"]:
          raise ValueError("Embedding model download exceeds its expected size.")
        vDigest.update(vChunk)
        vFile.write(vChunk)
        if time.monotonic()-vLastUpdate>=1:
          fWriteStatus(dModel,"downloading",vBytes)
          vLastUpdate=time.monotonic()
    if vBytes!=dModel["size"] or vDigest.hexdigest()!=dModel["sha256"]:
      raise ValueError("Embedding model SHA-256 verification failed.")
    os.chmod(vTemporary,0o644)
    os.replace(vTemporary,vPath)
    fWriteStatus(dModel,"installed",vBytes)
    return fReadStatus(dModel)
  except Exception as vError:
    fWriteStatus(dModel,"failed",vBytes,vError)
    raise
  finally:
    vTemporary.unlink(missing_ok=True)


def fStartModelDownload(pModelId):
  """Queue a download in the executor and return its status straight away."""
  dModel=rag_settings.fFindModel(pModelId)
  if dModel is None:
    raise ValueError("Unknown embedding model.")
  if fIsModelInstalled(dModel):
    return fReadStatus(dModel)
  with vDownloadLock:
    vFuture=dDownloads.get(dModel["id"])
    if vFuture is None or vFuture.done():
      fWriteStatus(dModel,"queued")
      dDownloads[dModel["id"]]=vDownloadPool.submit(fRunDownload,dModel["id"])
  return fReadStatus(dModel)


def fRunDownload(pModelId):
  try:
    return fInstallModel(pModelId)
  except Exception as vError:
    # fInstallModel already wrote the reason; this keeps the thread quiet.
    return {"state":"failed","error":str(vError)[:500]}


def fDescribe():
  dModel=rag_embeddings.fModel()
  dStatus={"model":dModel["name"],"model_id":dModel["id"],"fingerprint":dModel["sha256"],
    "installed":fIsModelInstalled(dModel),"local":True,"settings":rag_settings.fRuntimeSettings(),
    "ready":False,"serving":"",
    "models":[{"id":v["id"],"name":v["name"],"size":v["size"],"dimensions":v["dimensions"],
               "parameters":v["parameters"],"license":v["license"],"memory_mb":v["memory_mb"],
               "relative_indexing_time":v["relative_indexing_time"],"min_similarity":v["min_similarity"],
               **fReadStatus(v)} for v in rag_settings.fReadModelCatalogue()["models"]]}
  try:
    dStatus["serving"]=rag_embeddings.fServedModel()
    dStatus["ready"]=(rag_embeddings.fRequest("/health",pTimeout=2).get("status")=="ok"
      and dStatus["serving"]==dModel["id"])
  except ValueError:
    pass
  return dStatus


def fPrepareRestore(pAgentList):
  """Discard live RAG files before restoring a complete catalogue snapshot."""
  import pwd
  from backend.core import paths
  lAgents=[]
  for vLine in Path(pAgentList).read_text().splitlines():
    if not vLine.strip():continue
    lFields=vLine.split()
    if len(lFields)!=4 or paths.fGetAgentSystemUser(lFields[0])!=lFields[1]:
      raise ValueError("Invalid agent list in the backup.")
    lAgents.append(paths.fNormalizeAgentId(lFields[0]))
  for vAgentId in lAgents:
    vUid=pwd.getpwnam(paths.fGetAgentSystemUser(vAgentId)).pw_uid
    # OpenRC does not necessarily reap workers started in their own session.
    # Stop just these workers and their OCR children before replacing files.
    for vProc in Path("/proc").glob("[0-9]*"):
      try:
        if vProc.stat().st_uid!=vUid or b"\x00backend.core.rag_worker\x00" not in (vProc/"cmdline").read_bytes():
          continue
        vPid=int(vProc.name)
        if os.getpgid(vPid)==vPid:os.killpg(vPid,signal.SIGKILL)
        else:os.kill(vPid,signal.SIGKILL)
      except (OSError,ValueError):
        continue
    vHome=Path(paths.fGetAgentHome(vAgentId))
    if vHome.is_symlink():raise ValueError("An agent home is a symbolic link.")
    vRag=vHome/"rag"
    if vRag.is_symlink():vRag.unlink()
    elif vRag.exists():shutil.rmtree(vRag)
  (rag_settings.fRuntimeDirectory()/"settings.json").unlink(missing_ok=True)


def fServe():
  vDirectory=rag_settings.fRuntimeDirectory()
  vSocket=Path(rag_settings.cSocketPath)
  vSocket.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
  vSocket.unlink(missing_ok=True)
  dModel=rag_embeddings.fModel()
  dSettings=rag_settings.fRuntimeSettings()
  # The alias is what /v1/models reports, and what every client compares
  # with the model it expects before it trusts a vector.
  lCommand=[str(vDirectory/"bin"/"llama-server"),"--model",str(vDirectory/"models"/dModel["file"]),
    "--alias",dModel["id"],
    "--host",str(vSocket),"--embedding","--pooling",dModel["pooling"],"--ctx-size",str(dModel["context"]),
    "--batch-size",str(dModel["context"]),"--ubatch-size",str(dModel["context"]),"--parallel","1",
    "--threads",str(dSettings["threads"]),"--threads-batch",str(dSettings["threads"]),
    "--threads-http","4","--no-webui","--no-slots","--no-warmup"]
  vProcess=subprocess.Popen(lCommand)
  def fStop(pSignal,pFrame):
    if vProcess.poll() is None:
      vProcess.terminate()
  signal.signal(signal.SIGTERM,fStop)
  signal.signal(signal.SIGINT,fStop)
  try:
    while vProcess.poll() is None:
      if vSocket.exists():
        os.chmod(vSocket,0o666)
        break
      time.sleep(0.1)
    return vProcess.wait()
  finally:
    if vProcess.poll() is None:
      vProcess.terminate()
      vProcess.wait(timeout=15)
    vSocket.unlink(missing_ok=True)


def fMain():
  vParser=argparse.ArgumentParser()
  # Without a value, the model selected in Settings -> RAG.
  vParser.add_argument("--install-model",nargs="?",const="",default=None)
  vParser.add_argument("--serve",action="store_true")
  vParser.add_argument("--prepare-agents",action="store_true")
  vParser.add_argument("--backup")
  vParser.add_argument("--prepare-restore")
  dArguments=vParser.parse_args()
  if dArguments.prepare_restore:
    fPrepareRestore(dArguments.prepare_restore)
    return 0
  if dArguments.backup:
    from backend.core import paths, rag_exec
    import pwd
    vTarget=Path(dArguments.backup)
    # The root-owned parents cannot be exchanged for symlinks by an agent.
    # Let each child create its snapshot here rather than having root copy
    # a tree below an agent-owned directory.
    vScratch=Path(tempfile.mkdtemp(prefix="rag-backup-",dir=paths.fGetBaseDir()))
    vScratch.chmod(0o711)
    try:
      for vHome in sorted(Path(paths.fGetAgentsDir()).iterdir()):
        if len(vHome.name)!=3 or not vHome.name.isdigit() or vHome.is_symlink() or not (vHome/"rag").exists():
          continue
        dOwner=pwd.getpwnam(paths.fGetAgentSystemUser(vHome.name))
        vAgentTarget=vScratch/vHome.name
        vAgentTarget.mkdir(mode=0o711)
        (vAgentTarget/"rag").mkdir(mode=0o700)
        os.chown(vAgentTarget/"rag",dOwner.pw_uid,dOwner.pw_gid)
        rag_exec.fDispatch({"agent_id":vHome.name,"operation":"snapshot",
          "arguments":{"destination":str(vAgentTarget/"rag")}})
        os.chown(vAgentTarget,dOwner.pw_uid,dOwner.pw_gid)
        vAgentTarget.chmod(0o700)
      vTarget.rmdir()  # Created empty by the installer.
      os.replace(vScratch,vTarget)
    finally:
      if vScratch.exists(): shutil.rmtree(vScratch)
    return 0
  if dArguments.install_model is not None:
    fInstallModel(dArguments.install_model or None)
    return 0
  if dArguments.serve:
    return fServe()
  if dArguments.prepare_agents:
    from backend.core import paths, rag_exec
    for vHome in sorted(Path(paths.fGetAgentsDir()).iterdir()):
      if len(vHome.name)==3 and vHome.name.isdigit() and not vHome.is_symlink():
        rag_exec.fDispatch({"agent_id":vHome.name,"operation":"ensure"})
    return 0
  print(json.dumps(fDescribe()))
  return 0


if __name__=="__main__":
  raise SystemExit(fMain())
