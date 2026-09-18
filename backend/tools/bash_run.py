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
import subprocess

from backend.core import paths

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


def fRunTool(pArguments, pContext):
  """Run one shell command and return its output."""
  vCommand = str(pArguments.get("command") or "").strip()
  if not vCommand:
    return "No command given."

  vTimeout = pArguments.get("timeout_seconds") or cDefaultTimeoutSeconds
  try:
    vTimeout = max(1, min(int(vTimeout), cMaxTimeoutSeconds))
  except (TypeError, ValueError):
    vTimeout = cDefaultTimeoutSeconds

  vWorkingDirectory = str(pArguments.get("working_directory") or "").strip()
  if not vWorkingDirectory:
    vWorkingDirectory = os.path.expanduser("~")
  if not os.path.isdir(vWorkingDirectory):
    return "Working directory does not exist: %s" % (vWorkingDirectory,)

  try:
    vCompleted = subprocess.run(
      ["/bin/bash", "-c", vCommand],
      capture_output=True,
      text=True,
      timeout=vTimeout,
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
    return "The command was killed after %d seconds." % (vTimeout,)
  except OSError as vError:
    return "Could not run the command: %s" % (vError,)

  lParts = ["exit code: %d" % (vCompleted.returncode,)]
  vStdout = (vCompleted.stdout or "").rstrip()
  vStderr = (vCompleted.stderr or "").rstrip()
  if vStdout:
    lParts.append("stdout:\n%s" % (fTruncateOutput(vStdout),))
  if vStderr:
    lParts.append("stderr:\n%s" % (fTruncateOutput(vStderr),))
  if not vStdout and not vStderr:
    lParts.append("(no output)")
  return "\n\n".join(lParts)
