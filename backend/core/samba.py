#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""One Samba share per agent, managed only by the privileged executor.

The share name and path come from the agent id, never from a browser-supplied
path. Passwords go directly to Samba's private passdb over stdin; info.json
contains only share settings. BoA runs its own smbd instance and has no homes
service that could expose the rest of an agent's home.
"""

import argparse
from contextlib import contextmanager
import fcntl
import os
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.dont_write_bytecode = True

from backend.core import agents
from backend.core import paths

cSmbdCommand = "/usr/sbin/smbd"
cSmbpasswdCommand = "/usr/bin/smbpasswd"
cPdbeditCommand = "/usr/bin/pdbedit"
cSmbcontrolCommand = "/usr/bin/smbcontrol"
cTestparmCommand = "/usr/bin/testparm"
cNetCommand = "/usr/bin/net"
cTdbBackupCommand = "/usr/bin/tdbbackup"
cRuntimeDir = "/run/boa-samba"
cTimeoutSeconds = 20
cMaskPattern = re.compile(r"^0?[0-7]{3}$")


def fGetServerDir():
  return os.path.join(paths.fGetBaseDir(), "samba")


def fGetConfigPath():
  return os.path.join(fGetServerDir(), "smb.conf")


def fGetSharePath(pAgentId):
  return os.path.join(paths.fGetAgentHome(pAgentId), "samba")


def fIsConfigured():
  return os.path.isfile(fGetConfigPath()) and os.path.isfile(cSmbdCommand)


def fRun(pCommand, pInput=None, pCheck=True):
  """Run a fixed Samba command. Passwords never appear in its arguments."""
  vResult = subprocess.run(pCommand, input=pInput, capture_output=True, text=True,
                            timeout=cTimeoutSeconds, check=False,
                            env=dict(os.environ, LC_ALL="C"))
  if pCheck and vResult.returncode:
    raise RuntimeError("Samba command failed: %s" % (
      (vResult.stderr or vResult.stdout or os.path.basename(pCommand[0])).strip()[:500],))
  return vResult


def fValidateSettings(pIncoming, pCurrent=None):
  """Keep the share schema closed: no arbitrary smb.conf directives."""
  if not isinstance(pIncoming, dict):
    raise ValueError("Samba settings must be an object")
  if set(pIncoming) - set(agents.dDefaultSambaSettings) - {"password"}:
    raise ValueError("Unknown Samba setting")
  dSettings = dict(agents.dDefaultSambaSettings)
  dSettings.update(pCurrent or {})
  dSettings.update({vKey: vValue for vKey, vValue in pIncoming.items() if vKey != "password"})
  for vKey in ("enabled", "read_only", "browseable", "guest_ok"):
    if not isinstance(dSettings[vKey], bool):
      raise ValueError("%s must be a boolean" % (vKey,))
  for vKey in ("create_mask", "directory_mask"):
    vMask = dSettings[vKey]
    if not isinstance(vMask, str) or not cMaskPattern.fullmatch(vMask):
      raise ValueError("%s must be an octal permission such as 0600 or 0700" % (vKey,))
    dSettings[vKey] = "%04o" % int(vMask, 8)
  vComment = dSettings["comment"]
  if not isinstance(vComment, str) or len(vComment) > 160 \
     or any(vChar in vComment for vChar in ("\r", "\n", "\0", "\\", "%")):
    raise ValueError("The Samba description must be one line without backslashes or percent signs")
  return dSettings


def fValidatePassword(pPassword):
  if not isinstance(pPassword, str):
    raise ValueError("The Samba password must be text")
  if pPassword and (len(pPassword) < 8 or len(pPassword.encode("utf-8")) > 512
                   or any(vChar in pPassword for vChar in ("\r", "\n", "\0"))):
    raise ValueError("The Samba password must have at least 8 characters and contain no line breaks")
  return pPassword


def fEnsureShareDirectory(pAgentId):
  """Create samba/ through an open home directory, never chown a symlink."""
  vUser = pwd.getpwnam(paths.fGetAgentSystemUser(pAgentId))
  vHome = os.open(paths.fGetAgentHome(pAgentId), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
  try:
    if os.fstat(vHome).st_uid != vUser.pw_uid:
      raise PermissionError("The agent home does not belong to its system user")
    try:
      os.mkdir("samba", 0o700, dir_fd=vHome)
    except FileExistsError:
      pass
    vDirectory = os.open("samba", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=vHome)
    try:
      if os.fstat(vDirectory).st_uid not in (0, vUser.pw_uid):
        raise PermissionError("The Samba directory belongs to another user")
      os.fchown(vDirectory, vUser.pw_uid, vUser.pw_gid)
      os.fchmod(vDirectory, 0o700)
    finally:
      os.close(vDirectory)
  finally:
    os.close(vHome)


def fCheckShareDirectory(pAgentId):
  """Reject a replaced share root at connection time, not just when saving."""
  vUser = pwd.getpwnam(paths.fGetAgentSystemUser(pAgentId))
  vHome = os.open(paths.fGetAgentHome(pAgentId), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
  try:
    if os.fstat(vHome).st_uid != vUser.pw_uid:
      raise PermissionError("The agent home belongs to another user")
    vDirectory = os.open("samba", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=vHome)
    try:
      dOpened = os.fstat(vDirectory)
      dCurrent = os.stat("samba", dir_fd=vHome, follow_symlinks=False)
      if dOpened.st_uid != vUser.pw_uid or (dOpened.st_dev, dOpened.st_ino) != (dCurrent.st_dev, dCurrent.st_ino):
        raise PermissionError("The share directory was replaced or belongs to another user")
    finally:
      os.close(vDirectory)
  finally:
    os.close(vHome)


def fEnsureServerDirectories():
  for vDirectory in (fGetServerDir(), os.path.join(fGetServerDir(), "private"),
                     os.path.join(fGetServerDir(), "state"),
                     os.path.join(fGetServerDir(), "cache"),
                     os.path.join(fGetServerDir(), "logs"), cRuntimeDir):
    os.makedirs(vDirectory, mode=0o700, exist_ok=True)
    vDescriptor = os.open(vDirectory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
      if os.fstat(vDescriptor).st_uid != os.geteuid():
        raise PermissionError("The Samba server directory must belong to root")
      os.fchmod(vDescriptor, 0o700)
    finally:
      os.close(vDescriptor)


@contextmanager
def fServerLock():
  vDescriptor = os.open(os.path.join(fGetServerDir(), "settings.lock"),
                        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
  try:
    fcntl.flock(vDescriptor, fcntl.LOCK_EX)
    yield
  finally:
    os.close(vDescriptor)


def fBuildConfiguration(pOverrides=None, pExcluded=None):
  """Generate the isolated server configuration from protected agent settings."""
  vDirectory = fGetServerDir()
  lLines = [
    "# BOA-MANAGED. Set each share in the agent's Samba tab.",
    "[global]", "  server role = standalone server", "  security = user",
    "  workgroup = WORKGROUP", "  netbios name = BOA",
    "  server string = Bunch of AIgents", "  server min protocol = SMB2_02",
    "  smb ports = 445", "  disable netbios = yes", "  map to guest = Bad User",
    "  unix password sync = no", "  pam password change = no",
    "  load printers = no", "  printcap name = /dev/null", "  printing = bsd",
    "  disable spoolss = yes", "  usershare max shares = 0",
    "  allow insecure wide links = no", "  log level = 1", "  max log size = 1000",
    "  log file = %s/logs/smbd.log" % (vDirectory,),
    "  private dir = %s/private" % (vDirectory,),
    "  state directory = %s/state" % (vDirectory,),
    "  cache directory = %s/cache" % (vDirectory,),
    "  lock directory = %s" % (cRuntimeDir,),
    "  pid directory = %s" % (cRuntimeDir,),
    "  ncalrpc dir = %s/ncalrpc" % (cRuntimeDir,),
    "  passdb backend = tdbsam:%s/private/passdb.tdb" % (vDirectory,), "",
  ]
  dOverrides = pOverrides or {}
  sExcluded = set(pExcluded or [])
  for dAgent in agents.fListIndexedAgents():
    vAgentId = paths.fNormalizeAgentId(dAgent["id"])
    if vAgentId in sExcluded:
      continue
    dInfo = agents.fReadAgentInfo(vAgentId)
    dSettings = fValidateSettings(dOverrides.get(vAgentId, dInfo.get("samba") or {}))
    vUser = paths.fGetAgentSystemUser(vAgentId)
    vGuard = shlex.join([os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3"), "-I",
      os.path.join(paths.fGetWebAppDir(), "backend", "core", "samba.py"),
      "--check-share", vAgentId])
    lLines.extend([
      "[%s]" % (vUser,), "  path = %s" % (fGetSharePath(vAgentId),),
      "  available = %s" % ("yes" if dSettings["enabled"] else "no"),
      "  read only = %s" % ("yes" if dSettings["read_only"] else "no"),
      "  browseable = %s" % ("yes" if dSettings["browseable"] else "no"),
      "  guest ok = %s" % ("yes" if dSettings["guest_ok"] else "no"),
      "  guest only = %s" % ("yes" if dSettings["guest_ok"] else "no"),
      "  force user = %s" % (vUser,), "  force group = %s" % (vUser,),
      "  follow symlinks = no", "  wide links = no", "  nt acl support = no",
      "  root preexec = %s" % (vGuard,), "  root preexec close = yes",
      "  create mask = %s" % dSettings["create_mask"],
      "  force create mode = %s" % dSettings["create_mask"],
      "  directory mask = %s" % dSettings["directory_mask"],
      "  force directory mode = %s" % dSettings["directory_mask"],
      "  comment = %s" % dSettings["comment"],
    ])
    if not dSettings["guest_ok"]:
      lLines.append("  valid users = %s" % (vUser,))
    lLines.append("")
  return "\n".join(lLines)


def fWriteConfiguration(pText):
  """Validate a new complete configuration before replacing the live one."""
  vDescriptor, vTemporary = tempfile.mkstemp(prefix="smb-", dir=fGetServerDir())
  try:
    with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
      vFile.write(pText)
    os.chmod(vTemporary, 0o600)
    fRun([cTestparmCommand, "--suppress-prompt", vTemporary])
    os.replace(vTemporary, fGetConfigPath())
  finally:
    if os.path.exists(vTemporary):
      os.unlink(vTemporary)


def fIsRunning():
  try:
    with open(os.path.join(cRuntimeDir, "smbd.pid"), encoding="ascii") as vFile:
      vPid = int(vFile.read().strip())
    if vPid <= 1:
      return False
    os.kill(vPid, 0)
    return True
  except (OSError, ValueError):
    return False


def fReload(pShareName=None):
  if not fIsRunning():
    return
  fRun([cSmbcontrolCommand, "--configfile=" + fGetConfigPath(), "smbd", "reload-config"])
  if pShareName:
    # Existing clients must reconnect under the newly saved permissions.
    fRun([cSmbcontrolCommand, "--configfile=" + fGetConfigPath(),
          "smbd", "close-share", pShareName])


def fHasPassword(pAgentId):
  if not fIsConfigured():
    return False
  vUser = paths.fGetAgentSystemUser(pAgentId)
  vResult = fRun([cPdbeditCommand, "--configfile=" + fGetConfigPath(),
                  "--list", "--user=" + vUser], pCheck=False)
  return vResult.returncode == 0 and any(
    vLine.startswith(vUser + ":") for vLine in vResult.stdout.splitlines())


def fReadSettings(pAgentId):
  dInfo = agents.fReadAgentInfo(pAgentId)
  return {"settings": fValidateSettings(dInfo.get("samba") or {}),
          "share_name": paths.fGetAgentSystemUser(pAgentId),
          "username": paths.fGetAgentSystemUser(pAgentId),
          "path": fGetSharePath(pAgentId), "password_set": fHasPassword(pAgentId),
          "installed": fIsConfigured(), "running": fIsRunning()}


def fSetPassword(pAgentId, pPassword):
  vUser = paths.fGetAgentSystemUser(pAgentId)
  fRun([cSmbpasswdCommand, "-c", fGetConfigPath(), "-s", "-a", vUser],
        pInput=pPassword + "\n" + pPassword + "\n")
  fRun([cSmbpasswdCommand, "-c", fGetConfigPath(), "-e", vUser])


def fSaveSettings(pAgentId, pIncoming):
  if not fIsConfigured():
    raise RuntimeError("Samba is not installed for BoA. Run the installer with --update")
  with fServerLock():
    dInfo = agents.fReadAgentInfo(pAgentId)
    dSettings = fValidateSettings(pIncoming, dInfo.get("samba"))
    vPassword = fValidatePassword(pIncoming.get("password", ""))
    fEnsureShareDirectory(pAgentId)
    if dSettings == fValidateSettings(dInfo.get("samba") or {}) and not vPassword:
      return fReadSettings(pAgentId)
    with open(fGetConfigPath(), encoding="utf-8") as vFile:
      vPreviousConfig = vFile.read()
    dPreviousInfo = dict(dInfo)
    try:
      fWriteConfiguration(fBuildConfiguration({pAgentId: dSettings}))
      dInfo["samba"] = dSettings
      agents.fWriteAgentInfo(pAgentId, dInfo)
      if vPassword:
        fSetPassword(pAgentId, vPassword)
      fReload(paths.fGetAgentSystemUser(pAgentId))
    except Exception:
      agents.fWriteAgentInfo(pAgentId, dPreviousInfo)
      fWriteConfiguration(vPreviousConfig)
      fReload(paths.fGetAgentSystemUser(pAgentId))
      raise
    return fReadSettings(pAgentId)


def fProvisionAgent(pAgentId):
  """A new agent always gets its folder, and an installed server gets its share."""
  fEnsureShareDirectory(pAgentId)
  if fIsConfigured():
    with fServerLock():
      fWriteConfiguration(fBuildConfiguration())
      fReload()


def fRemoveAgent(pAgentId):
  if not fIsConfigured():
    return
  with fServerLock():
    # A simultaneous save of another agent must not recreate this share
    # between removing it here and removing the agent from the index.
    try:
      dInfo = agents.fReadAgentInfo(pAgentId)
    except ValueError:
      dInfo = None
    if dInfo is not None:
      dSettings = fValidateSettings(dInfo.get("samba") or {})
      dSettings["enabled"] = False
      dInfo["samba"] = dSettings
      agents.fWriteAgentInfo(pAgentId, dInfo)
    fWriteConfiguration(fBuildConfiguration(pExcluded=[pAgentId]))
    fReload(paths.fGetAgentSystemUser(pAgentId))
    if fHasPassword(pAgentId):
      fRun([cSmbpasswdCommand, "-c", fGetConfigPath(), "-x",
            paths.fGetAgentSystemUser(pAgentId)])


def fSyncShares():
  """Create the folders and regenerate shares after install, update or restore."""
  fEnsureServerDirectories()
  with fServerLock():
    for dAgent in agents.fListIndexedAgents():
      fEnsureShareDirectory(dAgent["id"])
    fWriteConfiguration(fBuildConfiguration())
    fReload()


def fBackup(pDirectory):
  """Snapshot the native passdb with TDB locking, retaining account SIDs too."""
  os.makedirs(pDirectory, mode=0o700, exist_ok=True)
  if not fIsConfigured():
    return
  with fServerLock():
    # smbpasswd-format export can silently skip non-UID-based user RIDs.
    # Keep Samba's native database; tdbbackup makes a consistent snapshot
    # while smbd is running, unlike copying the live file directly.
    fRun([cPdbeditCommand, "--configfile=" + fGetConfigPath(), "--list"])
    vDatabase = os.path.join(fGetServerDir(), "private", "passdb.tdb")
    vSuffix = ".boa-backup-" + uuid.uuid4().hex
    vSnapshot = vDatabase + vSuffix
    vAccounts = os.path.join(pDirectory, "passdb.tdb")
    try:
      fRun([cTdbBackupCommand, "-s", vSuffix, vDatabase])
      shutil.copyfile(vSnapshot, vAccounts)
      os.chmod(vAccounts, 0o600)
    finally:
      if os.path.exists(vSnapshot):
        os.unlink(vSnapshot)
    vResult = fRun([cNetCommand, "--configfile=" + fGetConfigPath(), "getlocalsid"])
    vMatch = re.search(r"S-1-5-[0-9-]+", vResult.stdout)
    if vMatch:
      vSidPath = os.path.join(pDirectory, "localsid")
      with open(vSidPath, "w", encoding="ascii") as vFile:
        vFile.write(vMatch.group(0) + "\n")
      os.chmod(vSidPath, 0o600)


def fRestore(pDirectory):
  if fIsRunning():
    raise RuntimeError("Stop boa-samba before restoring its account database")
  fSyncShares()
  vAccounts = os.path.join(pDirectory, "passdb.tdb")
  if not os.path.isfile(vAccounts):
    return
  with fServerLock():
    vSidPath = os.path.join(pDirectory, "localsid")
    if os.path.isfile(vSidPath):
      with open(vSidPath, encoding="ascii") as vFile:
        vSid = vFile.read().strip()
      if not re.fullmatch(r"S-1-5-[0-9-]+", vSid):
        raise ValueError("The Samba backup has an invalid server SID")
      fRun([cNetCommand, "--configfile=" + fGetConfigPath(), "setlocalsid", vSid])
    # Replace rather than merge, so an existing username gets its original
    # password and SID back as well. Validate before replacing the live file.
    vDescriptor, vNewDatabase = tempfile.mkstemp(
      prefix="restore-", suffix=".tdb", dir=os.path.join(fGetServerDir(), "private"))
    os.close(vDescriptor)
    try:
      shutil.copyfile(vAccounts, vNewDatabase)
      os.chmod(vNewDatabase, 0o600)
      fRun([cTdbBackupCommand, "-v", vNewDatabase])
      fRun([cPdbeditCommand, "--configfile=" + fGetConfigPath(),
            "--option=passdb backend=tdbsam:" + vNewDatabase, "--list"])
      os.replace(vNewDatabase, os.path.join(fGetServerDir(), "private", "passdb.tdb"))
    finally:
      if os.path.exists(vNewDatabase):
        os.unlink(vNewDatabase)


def fMain():
  vParser = argparse.ArgumentParser(description="Manage the BoA Samba instance")
  vActions = vParser.add_mutually_exclusive_group(required=True)
  vActions.add_argument("--sync", action="store_true")
  vActions.add_argument("--backup")
  vActions.add_argument("--restore")
  vActions.add_argument("--check-share")
  vArguments = vParser.parse_args()
  if os.geteuid() != 0:
    vParser.error("Run this as root")
  if vArguments.check_share:
    try:
      fCheckShareDirectory(vArguments.check_share)
    except (OSError, ValueError, KeyError):
      return 1
    return 0
  if vArguments.sync:
    fSyncShares()
  elif vArguments.backup:
    fBackup(vArguments.backup)
  else:
    fRestore(vArguments.restore)


if __name__ == "__main__":
  sys.exit(fMain())
