#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Root-only account recovery, with a private append-only installation record.

SQLite is opened in a separate process running as boa, so recovery does not
leave root-owned WAL or SHM files that prevent the web service from logging in.
Only the root parent holds the installation log descriptor.

`boa fingerprint` prints the SHA-256 fingerprint of the certificate the web
interface serves, to compare with the one the browser shows before logging in.
"""

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import warnings

if __name__ == "__main__" and not __package__:
  sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core import paths
from backend.web import auth

cMaxPasswordBytes = 64 * 1024
cWorkerTimeoutSeconds = 60
cWorkerArgument = "--password-worker"
cCertificateName = "fullchain.pem"
cMaxCertificateBytes = 1024 * 1024
cCertificatePattern = re.compile(
  r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", re.S)


class CliError(RuntimeError):
  """An administrative operation could not be completed."""


def fReadNewPassword(pFromStdin=False):
  """Read a password without putting it in command arguments or shell history."""
  if pFromStdin:
    vRaw = sys.stdin.buffer.readline(cMaxPasswordBytes + 2)
    if not vRaw:
      raise CliError("No password was received on standard input.")
    vPassword = vRaw.removesuffix(b"\n").removesuffix(b"\r").decode("utf-8")
  else:
    with warnings.catch_warnings():
      warnings.simplefilter("error", getpass.GetPassWarning)
      try:
        vPassword = getpass.getpass("New password (at least %d characters): " % auth.cMinimumPasswordLength)
        vConfirmation = getpass.getpass("Repeat the new password: ")
      except (getpass.GetPassWarning, EOFError) as vError:
        raise CliError("Use an interactive terminal, or explicitly use --password-stdin.") from vError
    if vPassword != vConfirmation:
      raise CliError("The passwords do not match. Nothing was changed.")
  if len(vPassword.encode("utf-8")) > cMaxPasswordBytes:
    raise CliError("The password exceeds the 64 KiB input limit.")
  return auth.fValidatePassword(vPassword)


@contextmanager
def fOpenInstallLog():
  """Open the existing log without truncating it or following a substituted link."""
  vFlags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
  vBaseDescriptor = os.open(paths.fGetBaseDir(), vFlags)
  vDirectoryDescriptor = None
  vDescriptor = None
  try:
    vDirectoryDescriptor = os.open("logs", vFlags, dir_fd=vBaseDescriptor)
    vWriteFlags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
      vDescriptor = os.open("install.log", vWriteFlags | os.O_CREAT | os.O_EXCL,
                            0o600, dir_fd=vDirectoryDescriptor)
      os.fchown(vDescriptor, 0, 0)
      os.fchmod(vDescriptor, 0o600)
    except FileExistsError:
      vDescriptor = os.open("install.log", vWriteFlags, dir_fd=vDirectoryDescriptor)
    dStat = os.fstat(vDescriptor)
    if (not stat.S_ISREG(dStat.st_mode) or dStat.st_uid != 0
        or dStat.st_gid != 0 or dStat.st_nlink != 1
        or stat.S_IMODE(dStat.st_mode) != 0o600):
      raise CliError("install.log must be a regular root:root file with mode 0600 and a single link.")
    fcntl.flock(vDescriptor, fcntl.LOCK_EX)
    yield vDescriptor
    dCurrent = os.stat("install.log", dir_fd=vDirectoryDescriptor, follow_symlinks=False)
    if (dCurrent.st_dev, dCurrent.st_ino) != (dStat.st_dev, dStat.st_ino):
      raise CliError("install.log was replaced while recording the password change.")
    os.fsync(vDirectoryDescriptor)
  finally:
    for vOpenDescriptor in (vDescriptor, vDirectoryDescriptor, vBaseDescriptor):
      if vOpenDescriptor is not None:
        os.close(vOpenDescriptor)


def fPasswordWorker(pBaseDir):
  """Private child entry point: change the account while running as boa."""
  try:
    vUser = pwd.getpwnam(paths.cAppUser)
    if os.getuid() != vUser.pw_uid or os.geteuid() != vUser.pw_uid or vUser.pw_uid == 0:
      raise CliError("The password worker must run as the boa service user.")
    os.environ["BOA_BASE_DIR"] = pBaseDir
    vRaw = sys.stdin.buffer.read(cMaxPasswordBytes * 6 + 1024)
    dRequest = json.loads(vRaw)
    vPassword = auth.fValidatePassword(dRequest["password"])
    if len(vPassword.encode("utf-8")) > cMaxPasswordBytes:
      raise CliError("The password exceeds the input limit.")
    dAdministrator = auth.fGetAdministrator()
    if not dAdministrator:
      raise CliError("The installation has no administrator account.")
    if not isinstance(dAdministrator["email"], str) or len(dAdministrator["email"]) > 4096:
      raise CliError("The administrator email stored in the database is invalid.")
    auth.fChangePassword(vPassword)
    print(json.dumps({"email": dAdministrator["email"]}, ensure_ascii=True))
    return 0
  except Exception as vError:
    # Never include the supplied password in a diagnostic or a command line.
    print(json.dumps({"error": str(vError)[:1000]}, ensure_ascii=True))
    return 1


def fChangePasswordAsService(pPassword):
  """Use the same password policy and session revocation as the web interface."""
  vUser = pwd.getpwnam(paths.cAppUser)
  if vUser.pw_uid == 0:
    raise CliError("The boa service user must not be root.")
  vResult = subprocess.run(
    [sys.executable, "-I", "-B", str(Path(__file__).resolve()), cWorkerArgument,
     os.path.abspath(paths.fGetBaseDir())],
    input=json.dumps({"password": pPassword}, ensure_ascii=True).encode("utf-8"),
    capture_output=True, timeout=cWorkerTimeoutSeconds,
    user=vUser.pw_uid, group=vUser.pw_gid, extra_groups=[], cwd="/",
    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, close_fds=True,
  )
  try:
    dResult = json.loads(vResult.stdout)
  except (ValueError, UnicodeDecodeError) as vError:
    raise CliError("The password change could not be verified. Check the installation and try again.") from vError
  if vResult.returncode or not isinstance(dResult, dict) or not isinstance(dResult.get("email"), str):
    raise CliError(dResult.get("error", "The password could not be changed.")
                   if isinstance(dResult, dict) else "The password could not be changed.")
  return dResult["email"]


def fAppendPasswordRecord(pDescriptor, pEmail, pPassword):
  """Keep an unambiguous, single-line record, including the recoverable password."""
  dRecord = {
    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "event": "administrator_password_changed",
    "source": "boa passwd",
    "email": pEmail,
    "password": pPassword,
    "sessions_revoked": True,
  }
  vData = ("\n" + json.dumps(dRecord, ensure_ascii=False) + "\n").encode("utf-8")
  while vData:
    vWritten = os.write(pDescriptor, vData)
    if vWritten <= 0:
      raise OSError("The installation log could not be written.")
    vData = vData[vWritten:]
  os.fsync(pDescriptor)


def fResetPassword(pPassword):
  """Validate the destination before changing the password; report partial failures."""
  if os.geteuid() != 0:
    raise CliError("Run boa passwd as root.")
  auth.fValidatePassword(pPassword)
  vChanged = False
  try:
    with fOpenInstallLog() as vDescriptor:
      vEmail = fChangePasswordAsService(pPassword)
      vChanged = True
      fAppendPasswordRecord(vDescriptor, vEmail, pPassword)
  except Exception as vError:
    if vChanged:
      raise CliError("The password was changed, but its record could not be saved in install.log. "
                     "Keep the new password and check the log before retrying.") from vError
    raise
  return vEmail


def fCertificateFingerprint(pText):
  """SHA-256 of the first certificate in PEM text, as a browser shows it."""
  vMatch = cCertificatePattern.search(pText)
  if not vMatch:
    raise CliError("There is no certificate in %s." % (cCertificateName,))
  try:
    vDer = base64.b64decode("".join(vMatch.group(1).split()), validate=True)
  except ValueError as vError:
    raise CliError("The certificate in %s cannot be read." % (cCertificateName,)) from vError
  vDigest = hashlib.sha256(vDer).hexdigest().upper()
  return ":".join(vDigest[vIndex:vIndex + 2] for vIndex in range(0, len(vDigest), 2))


def fCertificateNames(pPath):
  """The subject and the names of the certificate, as openssl prints them."""
  try:
    vResult = subprocess.run(
      ["openssl", "x509", "-in", pPath, "-noout", "-subject", "-ext", "subjectAltName"],
      capture_output=True, text=True, timeout=10)
  except (OSError, subprocess.SubprocessError):
    return ""
  return vResult.stdout.strip() if vResult.returncode == 0 else ""


def fShowFingerprint():
  """Print what a browser must show before the password is typed into it.

  The certificate the installer generates is signed by nobody, so the
  browser cannot say whether the server it reached is this one. This,
  read on the machine itself, can: the fingerprint in the browser's
  certificate details has to be this one.
  """
  vPath = os.path.join(paths.fGetCertificatesDir(), cCertificateName)
  vDescriptor = os.open(vPath, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
  with os.fdopen(vDescriptor, "rb") as vFile:
    if not stat.S_ISREG(os.fstat(vFile.fileno()).st_mode):
      raise CliError("%s is not a regular file." % (vPath,))
    vText = vFile.read(cMaxCertificateBytes + 1).decode("ascii", errors="replace")
  if len(vText) > cMaxCertificateBytes:
    raise CliError("%s is too large to be a certificate." % (vPath,))
  print("Certificate: %s" % (vPath,))
  vNames = fCertificateNames(vPath)
  if vNames:
    print(vNames)
  print("SHA-256 fingerprint: %s" % (fCertificateFingerprint(vText),))
  print("Before logging in, check that the browser shows this same fingerprint "
        "in the certificate's details.")
  return 0


def fMain(plArguments=None):
  lArguments = list(sys.argv[1:] if plArguments is None else plArguments)
  if len(lArguments) == 2 and lArguments[0] == cWorkerArgument:
    return fPasswordWorker(lArguments[1])
  vParser = argparse.ArgumentParser(prog="boa", description="Administer this BoA installation.")
  vCommands = vParser.add_subparsers(dest="command", required=True)
  vPassword = vCommands.add_parser("passwd", help="Reset the web administrator password and record it in install.log.")
  vPassword.add_argument("--password-stdin", action="store_true",
                          help="Read one UTF-8 password line from standard input instead of prompting twice.")
  vCommands.add_parser("fingerprint", help="Show the SHA-256 fingerprint of the certificate the web interface serves.")
  dArguments = vParser.parse_args(lArguments)
  if dArguments.command == "fingerprint":
    try:
      return fShowFingerprint()
    except (CliError, OSError) as vError:
      print("Error: %s" % vError, file=sys.stderr)
      return 1
  try:
    if os.geteuid() != 0:
      raise CliError("Run boa passwd as root.")
    vPassword = fReadNewPassword(dArguments.password_stdin)
    vEmail = fResetPassword(vPassword)
    print("Password changed for %s. Previous sessions have been revoked." % json.dumps(vEmail, ensure_ascii=False))
    print("The new credentials were appended to %s." % os.path.join(paths.fGetBaseDir(), "logs", "install.log"))
    return 0
  except KeyboardInterrupt:
    print("\nPassword reset interrupted.", file=sys.stderr)
    return 130
  except (CliError, OSError, ValueError, KeyError, subprocess.SubprocessError) as vError:
    print("Error: %s" % vError, file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(fMain())
