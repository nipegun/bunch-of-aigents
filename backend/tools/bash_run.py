"""Tool: bash.run - run a shell command as the calling agent's own user.

This is the most powerful tool in the installation and also the simplest, for
one reason: the process running it is already `agent-xxx`. There is no
privilege to drop, no user to switch to, and nothing to sanitize for
injection - the command runs with exactly the permissions the agent has, which
is what the operating system was going to enforce anyway.

What this file adds is what the kernel does not: a timeout, an output cap, and
a working directory that defaults to the agent's own home.

Deliberately not here:

  - No command allowlist or denylist. A blocklist on a shell is theatre: an
    agent that can run `sh` can run anything the denylist names. The real
    boundary is the user account, and that boundary is real.
  - No sudo, no privilege escalation path. If a task needs root, the answer is
    that the agent cannot do it.
"""

import os
import signal
import subprocess
import threading

from backend.core import paths
from backend.core import tool_registry

cToolName = "bash.run"

cToolDescription = (
  "Run a shell command on the server as your own unprivileged user. You have "
  "no root access. Your home directory is your working directory unless you "
  "say otherwise. Output is returned as text, truncated if very long."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "description": "The shell command to run.",
    },
    "working_directory": {
      "type": "string",
      "description": "Directory to run in. Defaults to your home directory.",
    },
    "timeout_seconds": {
      "type": "integer",
      "description": "Seconds before the command is killed. Default 60, max 300.",
    },
  },
  "required": ["command"],
  "additionalProperties": False,
}

# Ceilings. A command that runs forever would hold the whole run hostage, and
# output that is never capped would fill the model's context with a log file.
cDefaultTimeoutSeconds = 60
cMaxTimeoutSeconds = 300
cMaxOutputCharacters = 20000

# How many BYTES of each stream are kept in memory while the command runs.
#
# cMaxOutputCharacters is what the model is shown, and it was applied after
# capture_output had already read everything: `cat /dev/urandom | base64` is
# bounded by the timeout and by nothing else, so the truncation happened after
# the memory had been spent. This is the limit that runs during the command
# rather than after it, and it is deliberately far above what is shown, so
# that the last part of a long log is still the real last part.
cMaxCapturedBytes = 4 * 1024 * 1024

# How long to wait for a killed process group to actually go.
cKillGraceSeconds = 5


def fTruncateOutput(pText, pLimit=cMaxOutputCharacters):
  """Return output cut to a limit, keeping both ends.

  Both ends, because the start of a build log says what ran and the end says
  how it failed; the middle is usually the part nobody needs.
  """
  vText = str(pText or "")
  if len(vText) <= pLimit:
    return vText
  vHalf = pLimit // 2
  return "%s\n\n[... %d characters omitted ...]\n\n%s" % (
    vText[:vHalf], len(vText) - pLimit, vText[-vHalf:]
  )


class CompletedCommand:
  """What fRunWithLimits hands back: the same three fields subprocess gives."""

  def __init__(self, pReturnCode, pStdout, pStderr, pTruncated=False):
    self.returncode = pReturnCode
    self.stdout = pStdout
    self.stderr = pStderr
    # Whether a stream hit cMaxCapturedBytes and stopped being collected.
    self.vTruncated = pTruncated


def fReadStream(pStream, plInto, pdState):
  """Read one stream to its end, keeping at most cMaxCapturedBytes of it."""
  try:
    while True:
      vChunk = pStream.read(65536)
      if not vChunk:
        break
      if pdState["bytes"] < cMaxCapturedBytes:
        plInto.append(vChunk)
        pdState["bytes"] += len(vChunk)
      else:
        # Still drained, never kept. A process whose pipe fills up blocks on
        # write and never reaches the exit this is waiting for.
        pdState["truncated"] = True
  except (OSError, ValueError):
    pass


def fRunWithLimits(plCommand, pTimeoutSeconds, **pdKeywords):
  """Run a command with a byte ceiling and a deadline that kills the group.

  `subprocess.run(capture_output=True, timeout=...)` was doing neither:

    The output was read whole and truncated afterwards, so the ceiling on what
    the model is shown was not a ceiling on what the machine holds. A command
    producing a gigabyte was bounded by its timeout and nothing else.

    The timeout killed the DIRECT child only. `bash -c 'sleep 999 &'` returns
    at once and leaves sleep behind; a command that backgrounds something
    survives its own deadline. The child gets its own process group here, and
    the whole group is signalled.
  """
  vProcess = subprocess.Popen(
    plCommand,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.DEVNULL,
    # Its own process group, so that killing it kills what it started.
    start_new_session=True,
    **pdKeywords
  )

  lOut, lErr = [], []
  dOutState = {"bytes": 0, "truncated": False}
  dErrState = {"bytes": 0, "truncated": False}
  lReaders = [
    threading.Thread(target=fReadStream,
                     args=(vProcess.stdout, lOut, dOutState)),
    threading.Thread(target=fReadStream,
                     args=(vProcess.stderr, lErr, dErrState)),
  ]
  for vReader in lReaders:
    vReader.daemon = True
    vReader.start()

  vTimedOut = False
  try:
    vProcess.wait(timeout=pTimeoutSeconds)
  except subprocess.TimeoutExpired:
    vTimedOut = True
    fKillProcessGroup(vProcess)

  for vReader in lReaders:
    vReader.join(timeout=cKillGraceSeconds)
  for vStream in (vProcess.stdout, vProcess.stderr):
    try:
      vStream.close()
    except OSError:
      pass

  if vTimedOut:
    raise subprocess.TimeoutExpired(plCommand, pTimeoutSeconds)

  return CompletedCommand(
    vProcess.returncode,
    b"".join(lOut).decode("utf-8", "replace"),
    b"".join(lErr).decode("utf-8", "replace"),
    dOutState["truncated"] or dErrState["truncated"],
  )


def fKillProcessGroup(pProcess):
  """Kill the whole group a command was given, not only the command.

  TERM first, because a shell script given a chance to clean up leaves less
  behind, then KILL for whatever ignored it.
  """
  try:
    vGroupId = os.getpgid(pProcess.pid)
  except OSError:
    vGroupId = None

  for vSignal in (signal.SIGTERM, signal.SIGKILL):
    if vGroupId is None:
      break
    try:
      os.killpg(vGroupId, vSignal)
    except OSError:
      break
    try:
      pProcess.wait(timeout=cKillGraceSeconds)
      break
    except subprocess.TimeoutExpired:
      continue

  try:
    pProcess.kill()
  except OSError:
    pass


def fRunTool(pArguments, pContext):
  """Run one shell command and return its output."""
  vCommand = str(pArguments.get("command") or "").strip()
  if not vCommand:
    raise tool_registry.ToolFailure("No command given.")

  vTimeout = pArguments.get("timeout_seconds") or cDefaultTimeoutSeconds
  try:
    vTimeout = max(1, min(int(vTimeout), cMaxTimeoutSeconds))
  except (TypeError, ValueError):
    vTimeout = cDefaultTimeoutSeconds

  vWorkingDirectory = str(pArguments.get("working_directory") or "").strip()
  if not vWorkingDirectory:
    vWorkingDirectory = os.path.expanduser("~")
  if not os.path.isdir(vWorkingDirectory):
    raise tool_registry.ToolFailure(
      "Working directory does not exist: %s" % (vWorkingDirectory,))

  try:
    vCompleted = fRunWithLimits(
      ["/bin/bash", "-c", vCommand],
      pTimeoutSeconds=vTimeout,
      cwd=vWorkingDirectory,
      # A fresh, minimal environment: the agent's own, not whatever the cron
      # daemon or the executor happened to pass down.
      env={
        "HOME": os.path.expanduser("~"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "SHELL": "/bin/bash",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": "dumb",
        "PYTHONDONTWRITEBYTECODE": "1",
        # So a script the agent wrote can drive the shared browser too.
        "PLAYWRIGHT_BROWSERS_PATH": paths.fGetPlaywrightDir(),
      },
    )
  except subprocess.TimeoutExpired:
    raise tool_registry.ToolFailure(
      "The command was killed after %d seconds." % (vTimeout,))
  except OSError as vError:
    raise tool_registry.ToolFailure(
      "Could not run the command: %s" % (vError,))

  lParts = ["exit code: %d" % (vCompleted.returncode,)]
  vStdout = (vCompleted.stdout or "").rstrip()
  vStderr = (vCompleted.stderr or "").rstrip()
  if vStdout:
    lParts.append("stdout:\n%s" % (fTruncateOutput(vStdout),))
  if vStderr:
    lParts.append("stderr:\n%s" % (fTruncateOutput(vStderr),))
  if not vStdout and not vStderr:
    lParts.append("(no output)")
  if getattr(vCompleted, "vTruncated", False):
    lParts.append(
      "[The command produced more than %d bytes. What is above is the "
      "beginning of it; the rest was read and thrown away rather than held "
      "in memory.]" % (cMaxCapturedBytes,))
  return "\n\n".join(lParts)
