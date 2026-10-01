#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""The files an agent keeps in its home, read and written as that agent.

Used to put an agent's home into an export and to put it back on import. The
executor runs this module as the agent's own user, the way it runs the RAG
worker: root never walks a tree the agent can rearrange under it, and nothing
the agent itself could not read or write ends up read or written.

What is not the agent's to carry is left out in both directions:
  - what the system keeps there: the chat, the run journal, the API call
    records, the run lock and the chat attachments;
  - what has a place of its own in the package: memory.md and the library;
  - the browser profile, which holds logged-in sessions;
  - every hidden entry at the top of the home - .ssh, .bashrc and the like.
    An imported .ssh/authorized_keys would be a way in, and a shell start-up
    file runs code; neither is worth the rare legitimate use.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core import paths

sExcludedTopNames = {"chat.jsonl", "runs.jsonl", "api-calls.jsonl", "run.lock",
                     "memory.md", "rag", "attachments", "browser"}
cApiCallPattern = re.compile(r"^api-call-.*\.json$")
cMaxPathBytes = 512
cMaxFiles = 10000
# What one read or write moves. The request travels as JSON through the
# executor's socket, so it stays well under the 2 MiB a request may be.
cChunkBytes = 1024 * 1024
cMaxRequestBytes = 2 * 1024 * 1024
sOperations = {"list", "read", "write"}


def fIsExcluded(pTopName):
  """Whether an entry at the top of a home stays out of every package."""
  return (pTopName.startswith(".") or pTopName in sExcludedTopNames
          or bool(cApiCallPattern.match(pTopName)))


def fValidatePath(pPath):
  """A path relative to the home, or ValueError. Never a way out of it."""
  vPath = str(pPath or "")
  if (not vPath or len(vPath.encode("utf-8")) > cMaxPathBytes or "\\" in vPath
      or vPath.startswith("/") or any(ord(vChar) < 32 for vChar in vPath)):
    raise ValueError("Invalid home file path: %r" % (vPath[:80],))
  lParts = vPath.split("/")
  if any(vPart in ("", ".", "..") for vPart in lParts):
    raise ValueError("Invalid home file path: %r" % (vPath[:80],))
  if fIsExcluded(lParts[0]):
    raise ValueError("This file is not part of an agent's home in a package: %s" % (vPath,))
  return vPath


def fOpenParent(pHome, pPath, pCreate):
  """Open the directory holding pPath, one component at a time, no symlinks."""
  vDirectory = os.open(pHome, os.O_RDONLY | os.O_DIRECTORY)
  try:
    for vPart in pPath.split("/")[:-1]:
      if pCreate:
        try:
          os.mkdir(vPart, 0o700, dir_fd=vDirectory)
        except FileExistsError:
          pass
      vNext = os.open(vPart, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=vDirectory)
      os.close(vDirectory)
      vDirectory = vNext
  except BaseException:
    os.close(vDirectory)
    raise
  return vDirectory


def fList(pHome):
  """Every regular file of the home that a package may carry, with its size."""
  lFiles = []
  for vRoot, lDirectories, lNames, vDirectory in os.fwalk(pHome, follow_symlinks=False):
    vRelative = os.path.relpath(vRoot, pHome)
    if vRelative == ".":
      lDirectories[:] = sorted(v for v in lDirectories if not fIsExcluded(v))
      lNames = [v for v in lNames if not fIsExcluded(v)]
    else:
      lDirectories.sort()
    for vName in sorted(lNames):
      dStat = os.stat(vName, dir_fd=vDirectory, follow_symlinks=False)
      if not stat.S_ISREG(dStat.st_mode):
        continue
      vPath = vName if vRelative == "." else vRelative + "/" + vName
      try:
        fValidatePath(vPath)
      except ValueError:
        continue
      lFiles.append({"path": vPath, "size": dStat.st_size, "mode": dStat.st_mode & 0o777})
      if len(lFiles) > cMaxFiles:
        raise ValueError("The home has more than %d files; export it without them." % (cMaxFiles,))
  return {"files": lFiles}


def fRead(pHome, pPath, pOffset):
  vPath = fValidatePath(pPath)
  if type(pOffset) is not int or pOffset < 0:
    raise ValueError("Invalid offset.")
  vDirectory = fOpenParent(pHome, vPath, False)
  try:
    vFile = os.open(vPath.split("/")[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=vDirectory)
  finally:
    os.close(vDirectory)
  try:
    dStat = os.fstat(vFile)
    if not stat.S_ISREG(dStat.st_mode):
      raise ValueError("Not a regular file: %s" % (vPath,))
    vData = os.pread(vFile, cChunkBytes, pOffset)
  finally:
    os.close(vFile)
  return {"data": base64.b64encode(vData).decode(), "size": dStat.st_size, "mode": dStat.st_mode & 0o777}


def fWrite(pHome, pPath, pOffset, pData, pMode):
  """Write the next chunk of a file. Chunks arrive in order: offset 0 creates."""
  vPath = fValidatePath(pPath)
  try:
    vData = base64.b64decode(pData or "", validate=True)
  except (ValueError, TypeError):
    raise ValueError("Invalid file data.")
  if type(pOffset) is not int or pOffset < 0 or len(vData) > cChunkBytes:
    raise ValueError("Invalid chunk.")
  # Owner-only, with the execute bit kept for a script that had one.
  vMode = 0o700 if (int(pMode or 0) & 0o100) else 0o600
  vDirectory = fOpenParent(pHome, vPath, True)
  try:
    vFlags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_TRUNC if pOffset == 0 else 0)
    vFile = os.open(vPath.split("/")[-1], vFlags, vMode, dir_fd=vDirectory)
  finally:
    os.close(vDirectory)
  try:
    dStat = os.fstat(vFile)
    if not stat.S_ISREG(dStat.st_mode) or dStat.st_size != pOffset:
      raise ValueError("The file %s is not where this chunk expects it." % (vPath,))
    os.pwrite(vFile, vData, pOffset)
    os.fchmod(vFile, vMode)
  finally:
    os.close(vFile)
  return {"written": len(vData)}


def fDispatch(pAgentId, pOperation, pArguments):
  vHome = paths.fGetAgentHome(pAgentId)
  if pOperation == "list":
    return fList(vHome)
  if pOperation == "read":
    return fRead(vHome, pArguments.get("path"), pArguments.get("offset", 0))
  if pOperation == "write":
    return fWrite(vHome, pArguments.get("path"), pArguments.get("offset", 0),
                  pArguments.get("data"), pArguments.get("mode", 0))
  raise ValueError("Unknown home operation.")


def fBroker(pParams):
  """Run one operation as the agent. Called by the executor, as root."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vOperation = pParams.get("operation")
  if vOperation not in sOperations:
    raise ValueError("Unknown home operation.")
  dArguments = pParams.get("arguments") or {}
  if not isinstance(dArguments, dict):
    raise ValueError("Home arguments must be an object.")
  vPayload = json.dumps(dArguments).encode()
  if len(vPayload) > cMaxRequestBytes:
    raise ValueError("Home request is too large.")
  import pwd
  from backend.core.exec_daemon import fBuildAgentEnvironment
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  vUser = pwd.getpwnam(vSystemUser)
  lCommand = [sys.executable, "-m", "backend.core.agent_home",
              "--agent", vAgentId, "--operation", vOperation]
  try:
    vResult = subprocess.run(
      lCommand, input=vPayload, capture_output=True, timeout=50,
      user=vUser.pw_uid, group=vUser.pw_gid, extra_groups=[],
      cwd=paths.fGetAgentHome(vAgentId), env=fBuildAgentEnvironment(vSystemUser, vUser),
      start_new_session=True)
  except subprocess.TimeoutExpired as vError:
    raise ValueError("The home operation timed out.") from vError
  try:
    dResult = json.loads(vResult.stdout)
  except (ValueError, UnicodeDecodeError) as vError:
    raise ValueError("The home operation failed.") from vError
  if not dResult.get("ok"):
    raise ValueError(dResult.get("error") or "The home operation failed.")
  return dResult["result"]


def fMain():
  vParser = argparse.ArgumentParser()
  vParser.add_argument("--agent", required=True)
  vParser.add_argument("--operation", required=True)
  dArguments = vParser.parse_args()
  os.umask(0o077)
  resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
  try:
    vInput = sys.stdin.buffer.read(cMaxRequestBytes + 1)
    if len(vInput) > cMaxRequestBytes:
      raise ValueError("Home request is too large.")
    dResult = fDispatch(paths.fNormalizeAgentId(dArguments.agent), dArguments.operation,
                        json.loads(vInput or b"{}"))
    print(json.dumps({"ok": True, "result": dResult}, ensure_ascii=False))
    return 0
  except Exception as vError:
    print(json.dumps({"ok": False, "error": str(vError)[:1500]}))
    return 1


if __name__ == "__main__":
  raise SystemExit(fMain())
