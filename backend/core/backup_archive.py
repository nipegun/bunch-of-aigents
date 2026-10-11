#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Validate data-only backups before changing a running installation."""

import argparse
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import stat
import tarfile

cDataRoots = {"agents", "agents-config", "config", "certificates", "skills",
              "tools", "db", "kanban", "audio", "rag-runtime"}
cMetadata = {"manifest.txt", "agents.txt", "crontabs", "install.log.backup", "samba-backup"}
cRequired = {"manifest.txt", "agents.txt", "db/boa.sqlite", "kanban/kanban.sqlite"}
cMachineConfig = {"ports.conf", "browser.conf", "haproxy.cfg"}


def fValidate(pArchive):
  """A manifest describes a format, not authenticity; check every member."""
  dMembers = {}
  vTotal = 0
  for vMember in pArchive:
    vName = vMember.name.rstrip("/")
    vPath = PurePosixPath(vName)
    if (not vName or vPath.is_absolute() or ".." in vPath.parts
        or str(vPath) != vName or vPath.parts[0] not in cDataRoots | cMetadata):
      raise ValueError("Unexpected backup path: %s" % vName)
    if not (vMember.isdir() or vMember.isfile() or vMember.issym()):
      raise ValueError("Unsupported backup entry: %s" % vName)
    if vName in dMembers and not (vMember.isdir() and dMembers[vName].isdir()):
      raise ValueError("Duplicate backup file: %s" % vName)
    if vMember.mode & 0o7000:
      raise ValueError("Privileged file modes are not allowed")
    if vMember.issym():
      # Only links within one agent home are data; all shared trees are literal.
      if len(vPath.parts) < 3 or vPath.parts[0] != "agents":
        raise ValueError("Links are only allowed inside an agent home")
      vTarget = os.path.normpath(str(vPath.parent / vMember.linkname))
      if not vTarget.startswith("agents/%s/" % vPath.parts[1]):
        raise ValueError("Backup link leaves its agent home")
    if vPath.parts[0] == "rag-runtime" and vName not in ("rag-runtime", "rag-runtime/settings.json"):
      raise ValueError("A backup cannot install embedding executables")
    if vPath.parts[0] == "config" and len(vPath.parts) > 1 and vPath.parts[1] in cMachineConfig:
      raise ValueError("Machine configuration is not portable backup data")
    dMembers[vName] = vMember
    vTotal += vMember.size
    if len(dMembers) > 500000 or vTotal > 64 * 1024 ** 3:
      raise ValueError("Backup exceeds the restore limits")
  if not cRequired.issubset(dMembers):
    raise ValueError("Incomplete backup: manifest, agent list and both databases are required")
  for vName in cRequired:
    if not dMembers[vName].isfile():
      raise ValueError("Required backup entries must be regular files")

  def fText(pName):
    if dMembers[pName].size > 1024 * 1024:
      raise ValueError("Backup metadata is too large")
    with pArchive.extractfile(dMembers[pName]) as vFile:
      return vFile.read().decode("utf-8")

  dManifest = dict(vLine.split("=", 1) for vLine in fText("manifest.txt").splitlines() if "=" in vLine)
  if dManifest.get("format") != "1" or dManifest.get("base_dir") != os.environ.get("BOA_BASE_DIR", "/opt/boa"):
    raise ValueError("Unsupported backup manifest")
  sAgents = set()
  for vLine in fText("agents.txt").splitlines():
    lFields = vLine.split()
    if (len(lFields) != 4 or not re.fullmatch(r"[0-9]{3}", lFields[0])
        or lFields[1] != "agent-" + lFields[0]
        or not all(vField.isdigit() and 1000 <= int(vField) < 2 ** 31 for vField in lFields[2:])
        or lFields[0] in sAgents):
      raise ValueError("Invalid agent identity in backup")
    sAgents.add(lFields[0])
    try:
      vUser = pwd.getpwnam(lFields[1])
    except KeyError:
      continue
    if vUser.pw_uid < 1000 or vUser.pw_dir != "/opt/boa/agents/" + lFields[0]:
      raise ValueError("Existing account is not a dedicated agent")
  for vName in dMembers:
    lParts = PurePosixPath(vName).parts
    if lParts[0] in ("agents", "agents-config") and len(lParts) > 1 and lParts[1] not in sAgents:
      raise ValueError("Backup contains an unlisted agent")
    if lParts[0] == "crontabs" and len(lParts) > 1:
      if (len(lParts) != 2 or lParts[1] not in {"agent-" + vId for vId in sAgents}
          or not dMembers[vName].isfile()):
        raise ValueError("Only listed agents may have restored crontabs")
  return list(dMembers.values())


def fStage(pArchivePath, pDirectory):
  """Extract only into a newly created, root-private staging directory."""
  vDirectory = Path(pDirectory)
  vDirectory.mkdir(mode=0o700)
  with tarfile.open(pArchivePath, "r:gz") as vArchive:
    lMembers = fValidate(vArchive)
    vArchive.extractall(vDirectory, members=lMembers, filter="data")


def fSetOwners(pDirectory, pUid, pGid, pDirectoryMode=None):
  for vRoot, lDirectories, lFiles in os.walk(pDirectory, followlinks=False):
    os.chown(vRoot, pUid, pGid, follow_symlinks=False)
    if pDirectoryMode is not None:
      os.chmod(vRoot, pDirectoryMode)
    for vName in lFiles + lDirectories:
      os.chown(os.path.join(vRoot, vName), pUid, pGid, follow_symlinks=False)


def fInstall(pDirectory, pBaseDir):
  """Swap staged data under root-owned parents; never extract into live homes."""
  vStage, vBase = Path(pDirectory), Path(pBaseDir)
  vOld = vStage / "previous"
  vOld.mkdir(mode=0o700)
  vBoa = pwd.getpwnam("boa")
  for vName in cMachineConfig:
    vSource = vBase / "config" / vName
    if vSource.exists():
      with open(vSource, "rb") as vFile:
        (vStage / "config").mkdir(exist_ok=True)
        (vStage / "config" / vName).write_bytes(vFile.read(1024 * 1024))
  for vRootName in sorted(cDataRoots):
    vSource = vStage / vRootName
    if not vSource.exists():
      continue
    if not vSource.is_dir() or vSource.is_symlink():
      raise ValueError("Data roots must be literal directories")
    if vRootName == "rag-runtime":
      # The backup carries settings only. Preserve the installed executable,
      # weights and version marker when replacing that one data file.
      vTarget = vBase / vRootName
      if vTarget.is_symlink():
        raise ValueError("The embedding runtime directory is a symlink")
      vTarget.mkdir(mode=0o755, exist_ok=True)
      if (vSource / "settings.json").exists():
        os.replace(vSource / "settings.json", vTarget / "settings.json")
      else:
        (vTarget / "settings.json").unlink(missing_ok=True)
      continue
    if vRootName in ("agents", "agents-config"):
      (vBase / vRootName).mkdir(mode=0o711, exist_ok=True)
      (vOld / vRootName).mkdir()
      for vAgentDir in vSource.iterdir():
        vTarget = vBase / vRootName / vAgentDir.name
        vUser = pwd.getpwnam("agent-" + vAgentDir.name)
        if vRootName == "agents":
          fSetOwners(vAgentDir, vUser.pw_uid, vUser.pw_gid)
          vAgentDir.chmod(0o700)
        else:
          fSetOwners(vAgentDir, 0, vUser.pw_gid, 0o750)
          for vFile in vAgentDir.iterdir():
            if not vFile.is_file() or vFile.is_symlink():
              raise ValueError("Protected configuration must contain regular files")
            vFile.chmod(0o640)
        if vTarget.exists() or vTarget.is_symlink():
          os.replace(vTarget, vOld / vRootName / vAgentDir.name)
        os.replace(vAgentDir, vTarget)
    else:
      if vRootName in ("db", "kanban", "audio"):
        fSetOwners(vSource, vBoa.pw_uid, vBoa.pw_gid, 0o700)
      if vRootName == "certificates":
        fSetOwners(vSource, 0, vBoa.pw_gid, 0o750)
      vTarget = vBase / vRootName
      if vTarget.exists() or vTarget.is_symlink():
        os.replace(vTarget, vOld / vRootName)
      os.replace(vSource, vTarget)


def fMain():
  vParser = argparse.ArgumentParser()
  vParser.add_argument("operation", choices=("stage", "install"))
  vParser.add_argument("source")
  vParser.add_argument("destination")
  dArguments = vParser.parse_args()
  if dArguments.operation == "stage":
    fStage(dArguments.source, dArguments.destination)
  else:
    fInstall(dArguments.source, dArguments.destination)


if __name__ == "__main__":
  fMain()
