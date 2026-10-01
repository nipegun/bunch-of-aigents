#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Installed whisper.cpp and its verified model downloads.

The installer and the executor use the same catalogue and downloader. Model
names never become arbitrary URLs or paths supplied by the browser.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import threading
import time
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core import paths

cModelNamePattern = re.compile(r"[a-z][a-z0-9._-]{0,63}")
cChunkBytes = 1024 * 1024
cDefaultModel = "base"
vDownloadPool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper-model")
vDownloadLock = threading.Lock()
dDownloads = {}


def fGetDirectory():
  return Path(paths.fGetBaseDir()) / "whisper"


def fGetBinaryPath():
  return fGetDirectory() / "bin" / "whisper-cli"


def fReadCatalogue():
  with Path(__file__).with_name("whisper_models.json").open(encoding="utf-8") as vFile:
    return json.load(vFile)


def fValidateModelName(pName):
  if not isinstance(pName, str) or not cModelNamePattern.fullmatch(pName) or ".." in pName:
    raise ValueError("Invalid whisper.cpp model name.")
  return pName


def fGetModelPath(pName):
  return fGetDirectory() / "models" / ("ggml-" + fValidateModelName(pName) + ".bin")


def fGetModel(pName):
  fValidateModelName(pName)
  return next((dModel for dModel in fReadCatalogue()["models"]
               if dModel["id"] == pName), None)


def fIsInstalled():
  return fGetBinaryPath().is_file() and os.access(fGetBinaryPath(), os.X_OK)


def fIsModelInstalled(pName):
  vPath = fGetModelPath(pName)
  try:
    dStat = vPath.lstat()
    if not stat.S_ISREG(dStat.st_mode) or dStat.st_size < 1024:
      return False
    dModel = fGetModel(pName)
    return not dModel or dStat.st_size == dModel["size"]
  except OSError:
    return False


def fStatusPath(pName):
  return fGetDirectory() / "status" / (fValidateModelName(pName) + ".json")


def fWriteStatus(pName, pState, pDownloaded=0, pTotal=0, pError=""):
  vPath = fStatusPath(pName)
  vPath.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
  vTemporary = vPath.with_suffix(".json.tmp")
  with vTemporary.open("w", encoding="utf-8") as vFile:
    json.dump({"state": pState, "downloaded": pDownloaded, "total": pTotal,
               "error": str(pError)[:500], "pid": os.getpid(),
               "updated_at": int(time.time())}, vFile)
    vFile.write("\n")
  os.chmod(vTemporary, 0o644)
  os.replace(vTemporary, vPath)


def fReadStatus(pName):
  if fIsModelInstalled(pName):
    return {"state": "installed", "downloaded": fGetModelPath(pName).stat().st_size}
  try:
    with fStatusPath(pName).open(encoding="utf-8") as vFile:
      dStatus = json.load(vFile)
    if dStatus.get("state") in ("queued", "downloading"):
      try:
        os.kill(int(dStatus["pid"]), 0)
      except PermissionError:
        pass  # boa cannot signal the root executor, but it is still alive.
      except (OSError, ValueError, KeyError):
        return {"state": "failed", "error": "Download interrupted. Try again."}
    return dStatus
  except (OSError, ValueError):
    return {"state": "missing", "downloaded": 0}


def fListModels():
  ldModels = []
  sKnown = set()
  for dModel in fReadCatalogue()["models"]:
    sKnown.add(dModel["id"])
    ldModels.append({"id": dModel["id"], "size": dModel["size"],
                     "english_only": dModel["english_only"],
                     **fReadStatus(dModel["id"])})
  vDirectory = fGetDirectory() / "models"
  if vDirectory.is_dir():
    for vPath in sorted(vDirectory.glob("ggml-*.bin")):
      vName = vPath.name[5:-4]
      if (vName not in sKnown and cModelNamePattern.fullmatch(vName)
          and ".." not in vName and fIsModelInstalled(vName)):
        ldModels.append({"id": vName, "size": vPath.stat().st_size,
                         "english_only": ".en" in vName, "state": "installed"})
  return ldModels


def fDownloadModel(pName):
  """Download to a private partial file; expose it only after hash validation."""
  dModel = fGetModel(pName)
  if not dModel:
    raise ValueError("This model is not in the official whisper.cpp catalogue.")
  if fIsModelInstalled(pName):
    return fReadStatus(pName)
  if not fIsInstalled():
    raise ValueError("whisper.cpp is not installed. Run the BoA installer with --update.")
  vPath = fGetModelPath(pName)
  vPath.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
  if shutil.disk_usage(vPath.parent).free < dModel["size"] + 64 * cChunkBytes:
    raise ValueError("There is not enough free disk space for this model.")
  vPartial = vPath.with_suffix(".bin.part")
  vDownloaded = 0
  vDigest = hashlib.sha256()
  fWriteStatus(pName, "downloading", 0, dModel["size"])
  try:
    vDescriptor = os.open(vPartial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                          | os.O_NOFOLLOW, 0o600)
    with os.fdopen(vDescriptor, "wb") as vFile:
      vRequest = Request(dModel["url"], headers={"User-Agent": "BoA-whisper-models/1"})
      with urlopen(vRequest, timeout=120) as vResponse:
        vLastUpdate = 0.0
        while True:
          vChunk = vResponse.read(cChunkBytes)
          if not vChunk:
            break
          vDownloaded += len(vChunk)
          if vDownloaded > dModel["size"]:
            raise ValueError("The model download exceeded its expected size.")
          vDigest.update(vChunk)
          vFile.write(vChunk)
          if time.monotonic() - vLastUpdate >= 1:
            fWriteStatus(pName, "downloading", vDownloaded, dModel["size"])
            vLastUpdate = time.monotonic()
    if vDownloaded != dModel["size"] or vDigest.hexdigest() != dModel["sha256"]:
      raise ValueError("The model download failed its SHA-256 verification.")
    os.chmod(vPartial, 0o644)
    os.replace(vPartial, vPath)
    fWriteStatus(pName, "installed", vDownloaded, dModel["size"])
    return fReadStatus(pName)
  except Exception as vError:
    try:
      vPartial.unlink()
    except FileNotFoundError:
      pass
    fWriteStatus(pName, "failed", vDownloaded, dModel["size"], str(vError))
    raise


def fStartModelDownload(pName):
  """Queue one download in the privileged executor; the HTTP request stays short."""
  if not fGetModel(pName):
    raise ValueError("Unknown whisper.cpp model.")
  if fIsModelInstalled(pName):
    return fReadStatus(pName)
  with vDownloadLock:
    vFuture = dDownloads.get(pName)
    if vFuture is None or vFuture.done():
      fWriteStatus(pName, "queued", 0, fGetModel(pName)["size"])
      dDownloads[pName] = vDownloadPool.submit(fRunDownload, pName)
  return fReadStatus(pName)


def fRunDownload(pName):
  try:
    return fDownloadModel(pName)
  except Exception as vError:
    fWriteStatus(pName, "failed", pError=str(vError))
    return fReadStatus(pName)


def fDescribeInstallation():
  try:
    vVersion = (fGetDirectory() / "version").read_text().strip()
  except OSError:
    vVersion = ""
  return {"installed": fIsInstalled(), "version": vVersion,
          "directory": str(fGetDirectory()), "models": fListModels()}


def fMain(pArguments=None):
  vParser = argparse.ArgumentParser(description="Install a verified whisper.cpp model")
  vParser.add_argument("--install-model", required=True)
  dArguments = vParser.parse_args(pArguments)
  try:
    fDownloadModel(dArguments.install_model)
    print("Whisper model ready: " + dArguments.install_model)
    return 0
  except (OSError, ValueError) as vError:
    print("Cannot install Whisper model: %s" % (vError,), file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(fMain())
