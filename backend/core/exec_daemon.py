"""Privileged executor daemon.

This is the only component of Bunch of AIgents that runs as root. It exists
because three things in this application genuinely require privilege and
nothing else does:

  - creating and deleting the system user behind an agent,
  - installing an agent's crontab,
  - starting an agent run as that agent's own user.

The daemon exposes a closed vocabulary of verbs over a Unix socket. There is no
generic "run this command" verb, no shell is ever invoked, and every argument
that ends up in a path or a command line is validated first. An attacker who
reaches the socket can create an unprivileged agent; they cannot run code as
root.

Three layers keep agents away from the socket:

  1. The socket is 0660, owned by root:boa. Agent users are not in that group.
  2. SO_PEERCRED is checked on every connection: only root and the `boa` user
     are served, whatever the filesystem permissions happen to say.
  3. The runtime directory itself is 0750 root:boa.
"""

import grp
import json
import os
import pwd
import shutil
import socket
import socketserver
import struct
import subprocess
import sys
import tempfile

from backend.core import agents
from backend.core import chat
from backend.core import exec_protocol
from backend.core import memory
from backend.core import paths
from backend.core import run_journal
from backend.core import skills

# Commands the daemon is allowed to invoke. Absolute paths, because a daemon
# running as root must never depend on the PATH it happened to inherit.
cUserAddCommand = "/usr/sbin/useradd"
cUserDelCommand = "/usr/sbin/userdel"
cCrontabCommand = "/usr/bin/crontab"

# Shell given to agent users. Agents need a real shell: bash.run runs through
# it, and cron needs it to execute their scheduled jobs.
cAgentShell = "/bin/bash"

# Seconds a privileged subprocess may take before it is killed.
cSubprocessTimeoutSeconds = 60

# Longest crontab the daemon accepts, in bytes.
cMaxCrontabBytes = 64 * 1024

# Why a chat turn was closed without the agent having answered. The name
# travels, not the sentence: the interface writes that in the user's language.
cReasonCannotStart = "cannot_start"

# Longest chat message accepted. A question far bigger than this is a file,
# and a file belongs in the agent's home, not in a chat bubble.
cMaxChatMessageBytes = 8000

# Where a chat message can have come in through, other than the web interface
# it was typed into. A closed list because the value ends up in the chat file
# and then in the browser as a label: anything not on it is dropped.
lKnownChatSources = ["telegram"]


def fLogLine(pMessage):
  """Write one line to stderr, which systemd routes to the journal."""
  sys.stderr.write("%s\n" % (pMessage,))
  sys.stderr.flush()


def fGetPeerCredentials(pSocket):
  """Return (pid, uid, gid) of the process on the other end of the socket."""
  cStructFormat = "3i"
  vCredentials = pSocket.getsockopt(
    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(cStructFormat)
  )
  return struct.unpack(cStructFormat, vCredentials)


def fIsPeerAllowed(pUid):
  """Return True when the calling user may talk to the daemon.

  Only root and the web application user are served. This is checked even
  though the socket permissions already say the same thing, because a single
  mistaken chmod during an update should not open the daemon to every agent.
  """
  if pUid == 0:
    return True
  try:
    vAppUid = pwd.getpwnam(paths.cAppUser).pw_uid
  except KeyError:
    return False
  return pUid == vAppUid


def fRunPrivilegedCommand(pCommandArguments, pAsUser=None, pStdinText=None):
  """Run one command with no shell, optionally dropping to another user.

  Passing a list and never shell=True is what makes an agent name harmless even
  if validation upstream were ever bypassed.
  """
  dRunKeywords = {
    "capture_output": True,
    "text": True,
    "timeout": cSubprocessTimeoutSeconds,
    "check": False,
  }
  if pStdinText is not None:
    dRunKeywords["input"] = pStdinText
  if pAsUser is not None:
    try:
      vPasswordEntry = pwd.getpwnam(pAsUser)
    except KeyError:
      raise ValueError("System user %r does not exist" % (pAsUser,))
    dRunKeywords["user"] = vPasswordEntry.pw_uid
    dRunKeywords["group"] = vPasswordEntry.pw_gid
    dRunKeywords["extra_groups"] = []
    dRunKeywords["cwd"] = vPasswordEntry.pw_dir
    dRunKeywords["env"] = {
      "HOME": vPasswordEntry.pw_dir,
      "USER": pAsUser,
      "LOGNAME": pAsUser,
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "SHELL": cAgentShell,
      "PYTHONDONTWRITEBYTECODE": "1",
      "PLAYWRIGHT_BROWSERS_PATH": paths.fGetPlaywrightDir(),
    }
  try:
    vCompleted = subprocess.run(pCommandArguments, **dRunKeywords)
  except subprocess.TimeoutExpired:
    raise RuntimeError(
      "Command timed out after %d seconds: %s"
      % (cSubprocessTimeoutSeconds, pCommandArguments[0])
    )
  if vCompleted.returncode != 0:
    raise RuntimeError(
      "Command %s failed with code %d: %s"
      % (pCommandArguments[0], vCompleted.returncode,
         (vCompleted.stderr or "").strip())
    )
  return vCompleted.stdout or ""


def fBuildAgentEnvironment(pSystemUser, pPasswordEntry):
  """Return the environment an agent process runs with."""
  return {
    "HOME": pPasswordEntry.pw_dir,
    "USER": pSystemUser,
    "LOGNAME": pSystemUser,
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "SHELL": cAgentShell,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": paths.fGetWebAppDir(),
    "BOA_BASE_DIR": paths.fGetBaseDir(),
    # Where the shared browser lives. Without it Playwright looks in the
    # user's own cache, which for an agent is a home nothing ever wrote to.
    "PLAYWRIGHT_BROWSERS_PATH": paths.fGetPlaywrightDir(),
  }


def fRunAsAgent(pAgentId, pPasswordEntry, pFunction):
  """Run a function in a child process owned by the agent.

  Files inside an agent home must belong to the agent, and this daemon is
  root: writing directly would leave root-owned files in a 0700 directory the
  agent could then not rewrite. Forking and dropping first is simpler and
  harder to get wrong than writing and fixing up ownership afterwards.
  """
  vPid = os.fork()
  if vPid == 0:
    try:
      os.setgid(pPasswordEntry.pw_gid)
      os.setgroups([])
      os.setuid(pPasswordEntry.pw_uid)
      pFunction()
      os._exit(0)
    except Exception:
      os._exit(1)
  vWaitedPid, vStatus = os.waitpid(vPid, 0)
  if os.WEXITSTATUS(vStatus) != 0:
    raise RuntimeError("Could not write into the home of agent %s" % (pAgentId,))
  return True


def fVerbPing(pParams):
  """Answer a liveness check."""
  return {"pong": True, "uid": os.getuid()}


def fVerbCreateAgent(pParams):
  """Create the system user, home directory and configuration of a new agent."""
  vName = agents.fValidateAgentName(pParams.get("name"))
  vDescription = str(pParams.get("description") or "")
  vProvider = agents.fValidateProvider(pParams.get("provider") or "ollama")
  vModel = str(pParams.get("model") or "")
  vBaseUrl = str(pParams.get("base_url") or "")

  vAgentId = pParams.get("agent_id")
  if vAgentId is None:
    vAgentId = agents.fGetNextFreeAgentId()
  else:
    vAgentId = paths.fNormalizeAgentId(vAgentId)

  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  vHome = paths.fGetAgentHome(vAgentId)

  if os.path.exists(vHome):
    raise ValueError("Agent %s already exists" % (vAgentId,))

  fLogLine("Creating agent %s (%s)" % (vAgentId, vSystemUser))
  fRunPrivilegedCommand([
    cUserAddCommand,
    "--home-dir", vHome,
    "--create-home",
    "--shell", cAgentShell,
    vSystemUser,
  ])

  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)

    dInfo = agents.fBuildAgentInfo(
      vAgentId, vName, vDescription, vProvider, vModel, vBaseUrl
    )

    # An example agent brings its own tools, ceilings and switch. They are
    # applied on top of the defaults rather than instead of them, so a
    # template that says nothing about ceilings still gets the ordinary ones.
    lTools = pParams.get("tools")
    if isinstance(lTools, list):
      dInfo["tools"] = [str(vTool) for vTool in lTools]
    lSkills = pParams.get("skills")
    if isinstance(lSkills, list):
      # Only the ones this server actually has. A template naming a skill
      # nobody wrote yet creates the agent without it rather than failing.
      dInfo["skills"] = skills.fSelectInstalledSkills(lSkills)
    dLimits = pParams.get("limits")
    if isinstance(dLimits, dict):
      for vKey in agents.dDefaultLimits:
        if isinstance(dLimits.get(vKey), int):
          dInfo["limits"][vKey] = dLimits[vKey]
    if "enabled" in pParams:
      dInfo["enabled"] = bool(pParams.get("enabled"))

    # The drawer before anything goes in it, or the first write lands in the
    # home and the agent owns it.
    fEnsureAgentConfigDir(vAgentId, vPasswordEntry.pw_gid)

    agents.fWriteAgentInfo(vAgentId, dInfo)
    os.chown(paths.fGetAgentInfoPath(vAgentId), 0, vPasswordEntry.pw_gid)
    os.chmod(paths.fGetAgentInfoPath(vAgentId), 0o640)

    vSystemPrompt = pParams.get("system_prompt")
    if not vSystemPrompt:
      vSystemPrompt = fBuildDefaultSystemPrompt(vName, vDescription)
    fWriteAgentFile(
      paths.fGetAgentSystemPromptPath(vAgentId), vSystemPrompt,
      0, vPasswordEntry.pw_gid, 0o640
    )

    # The token an agent uses to call the agent API. It is how an agent posts
    # to a channel without ever being able to read that channel's credentials.
    # The token file is 0600 in the agent's home, so only its hash is indexed:
    # the agent API cannot read the file either.
    vApiToken = os.urandom(32).hex()
    fWriteAgentFile(
      paths.fGetAgentApiTokenPath(vAgentId), vApiToken + "\n",
      0, vPasswordEntry.pw_gid, 0o640
    )

    # An empty memory, so the agent has somewhere to write from its first run.
    fWriteAgentFile(
      memory.fGetMemoryPath(vAgentId), memory.cDefaultMemoryHeader,
      vPasswordEntry.pw_uid, vPasswordEntry.pw_gid, 0o600
    )

    os.chown(vHome, vPasswordEntry.pw_uid, vPasswordEntry.pw_gid)
    os.chmod(vHome, 0o700)

    agents.fIndexAgent(vAgentId, dInfo, vApiToken)

    # A template can come with a schedule. Installed last, because it runs
    # `crontab` as the agent, which needs the home to exist and be theirs.
    vCrontab = str(pParams.get("crontab") or "").strip()
    if vCrontab:
      fVerbWriteCrontab({
        "agent_id": vAgentId,
        "crontab": fBuildScheduleLine(vAgentId, vCrontab),
      })
  except Exception:
    # Never leave a half-created agent behind: a user with no info.json would
    # show up in the sidebar as an agent that cannot be configured or deleted.
    fLogLine("Rolling back the creation of agent %s" % (vAgentId,))
    fRemoveAgentUser(vSystemUser, vHome)
    raise

  return {"agent_id": vAgentId, "system_user": vSystemUser, "info": dInfo}


def fBuildScheduleLine(pAgentId, pSchedule):
  """Turn a five-field schedule into the crontab an agent runs itself with.

  A template says WHEN it should wake up, not how to start itself: the path to
  the interpreter and to the runner belong to the installation, and writing
  them into eight example files would mean eight places to fix when one of
  them moves.
  """
  vRunner = os.path.join(paths.fGetWebAppDir(), "backend", "core", "runner.py")
  vPython = os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3")
  # PYTHONPATH because cron hands over an environment with almost nothing in
  # it. The runner puts its own root on sys.path as well, so a crontab written
  # before this line still works - but a crontab that says what it needs is
  # one less thing to know when reading it.
  return (
    "# Installed with this agent. It only runs while the agent is enabled.\n"
    "PYTHONPATH=%s\n"
    "%s %s %s --agent-id %s\n"
    % (paths.fGetWebAppDir(), pSchedule, vPython, vRunner, pAgentId)
  )


def fBuildDefaultSystemPrompt(pName, pDescription):
  """Return the system prompt written into a new agent's home.

  Each rule is one line, however long. A prompt hard-wrapped at some column is
  harder to edit - every correction means rewrapping the paragraph - and the
  line breaks mean nothing to the model reading it. The text box in the web
  interface wraps it on screen without putting the breaks in the file.
  """
  lLines = [
    "# %s" % (pName,),
    "",
    str(pDescription or "You are an agent of this Bunch of AIgents installation."),
    "",
    "## Rules",
    "",
    " - You run as your own unprivileged system user. You have no root access and you do not need it. If a task seems to require root, say so instead of trying to work around it.",
    " - Record what you do on the kanban board, so the user can see real progress instead of having to ask.",
    " - Never claim a task is finished unless you verified it.",
    " - Answer in the language this prompt is written in. If the user writes to you in another language, answer in theirs.",
    "",
  ]
  return "\n".join(lLines)


def fEnsureAgentConfigDir(pAgentId, pGid):
  """Create the root-owned drawer inside an agent home, and return it.

  root:agent-xxx 0750: the agent may enter it and read what is in it, and
  cannot create, rename or delete anything there. That last part is why this
  exists at all - owning a file is not what decides whether it can be
  replaced, the write permission on its directory is. An agent that owned the
  directory could delete info.json and write its own, whoever owned the file.
  """
  vDirectory = paths.fGetAgentConfigDir(pAgentId)
  os.makedirs(vDirectory, exist_ok=True)
  os.chown(vDirectory, 0, pGid)
  os.chmod(vDirectory, 0o750)
  return vDirectory


def fProtectAgentFiles(pAgentId, pGid):
  """Move an existing agent's protected files into the drawer, as root.

  Called on every update, for agents created before this existed. Moving is
  what takes the file out of the agent's reach: a file that stays in a
  directory the agent can write is a file the agent can replace, whatever its
  own mode says.
  """
  vDirectory = fEnsureAgentConfigDir(pAgentId, pGid)
  lMoved = []
  for vFileName in paths.lProtectedAgentFiles:
    vOldPath = os.path.join(paths.fGetAgentHome(pAgentId), vFileName)
    vNewPath = os.path.join(vDirectory, vFileName)
    if os.path.exists(vOldPath) and not os.path.exists(vNewPath):
      os.replace(vOldPath, vNewPath)
      lMoved.append(vFileName)
    if os.path.exists(vNewPath):
      # root owns it, the agent's group reads it.
      os.chown(vNewPath, 0, pGid)
      os.chmod(vNewPath, 0o640)
  return lMoved


def fWriteAgentFile(pPath, pContent, pUid, pGid, pMode):
  """Write one file inside an agent home with explicit ownership and mode."""
  vDirectory = os.path.dirname(pPath)
  vHandle, vTempPath = tempfile.mkstemp(dir=vDirectory)
  try:
    with os.fdopen(vHandle, "w", encoding="utf-8") as vFile:
      vFile.write(pContent)
    os.chown(vTempPath, pUid, pGid)
    os.chmod(vTempPath, pMode)
    os.replace(vTempPath, pPath)
  except OSError as vError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    raise RuntimeError("Cannot write %s: %s" % (pPath, vError))


def fRemoveAgentUser(pSystemUser, pHome):
  """Delete an agent's system user, crontab and home directory."""
  # No crontab installed is the normal case, not an error, so the result is
  # not checked: what matters is that nothing is left pointing at a user that
  # is about to stop existing.
  fRemoveCrontab(pSystemUser)
  try:
    fRunPrivilegedCommand([cUserDelCommand, "--remove", pSystemUser])
  except (RuntimeError, ValueError) as vError:
    fLogLine("userdel failed for %s: %s" % (pSystemUser, vError))
  if os.path.isdir(pHome):
    shutil.rmtree(pHome, ignore_errors=True)


def fVerbDeleteAgent(pParams):
  """Delete an agent completely: user, crontab, home directory and index row."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  if vAgentId == paths.cOrchestratorId:
    raise ValueError("The orchestrating agent cannot be deleted")
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  vHome = paths.fGetAgentHome(vAgentId)
  fLogLine("Deleting agent %s (%s)" % (vAgentId, vSystemUser))
  fRemoveAgentUser(vSystemUser, vHome)
  agents.fUnindexAgent(vAgentId)
  return {"agent_id": vAgentId, "deleted": True}


def fRemoveCrontab(pSystemUser):
  """Delete one user's crontab, whichever cron is installed.

  Vixie cron, which Debian ships, deletes with `-r`. dcron, which Alpine
  ships, deletes with `-d` and answers `-r` with a usage message and exit code
  2 - so the crontab of a deleted agent used to survive it, pointing at a
  runner whose user no longer existed.

  Both are tried rather than detected: what decides it is the binary that
  happens to be installed, not the name of the distribution.
  """
  for vFlag in ("-r", "-d"):
    try:
      fRunPrivilegedCommand([cCrontabCommand, "-u", pSystemUser, vFlag])
      return True
    except (RuntimeError, ValueError):
      continue
  return False


def fVerbWriteCrontab(pParams):
  """Install an agent's crontab, naming the agent it belongs to.

  The crontab ends up owned by the agent either way. What changed is who runs
  the `crontab` binary: this daemon, as root, with `-u <agent>`, instead of
  dropping to the agent first.

  Dropping first was truer to the idea - the agent managing its own crontab,
  exactly as if somebody had logged in as it and typed `crontab -e` - and it
  worked on Debian, where `crontab` is setgid and every user may run it. On
  Alpine dcron ships it 4750 root:wheel, so an agent running it gets
  "Permission denied", and the only ways to make that work were to put every
  agent in `wheel` - the group that means sudo on most systems - or to loosen
  a setuid binary of the system's. Neither is worth it for a file this daemon
  can write itself.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  vCrontabText = str(pParams.get("crontab") or "")

  if len(vCrontabText.encode("utf-8")) > cMaxCrontabBytes:
    raise ValueError("Crontab is too large (limit is %d bytes)" % (cMaxCrontabBytes,))
  if "\x00" in vCrontabText:
    raise ValueError("Crontab contains a null byte")
  if vCrontabText and not vCrontabText.endswith("\n"):
    vCrontabText = vCrontabText + "\n"

  if not vCrontabText.strip():
    fRemoveCrontab(vSystemUser)
    return {"agent_id": vAgentId, "installed": False, "removed": True}

  fRunPrivilegedCommand(
    [cCrontabCommand, "-u", vSystemUser, "-"], pStdinText=vCrontabText
  )
  return {"agent_id": vAgentId, "installed": True, "removed": False}


def fVerbReadCrontab(pParams):
  """Return an agent's current crontab.

  Read with `-u`, as root, for the same reason it is written that way.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vCrontabText = fRunPrivilegedCommand([cCrontabCommand, "-u", vSystemUser, "-l"])
  except RuntimeError:
    # `crontab -l` exits non-zero when there is no crontab at all.
    vCrontabText = ""
  return {"agent_id": vAgentId, "crontab": vCrontabText}


def fListRunningAgentIds():
  """Return the id of every agent with a run in flight, as a sorted list.

  Asked of /proc rather than of a list this daemon keeps, because a run can
  also be started by the agent's own crontab, which never passes through here.
  Only root can read every process's command line, and this daemon is the one
  part that runs as root.

  One sweep answers for every agent at once, which is what makes it cheap
  enough for the sidebar to ask every few seconds: the alternative, one call
  per agent, walks /proc once per agent for the same answer.
  """
  vNeedle = "--agent-id"
  sAgentIds = set()
  for vEntry in os.listdir("/proc"):
    if not vEntry.isdigit():
      continue
    try:
      with open("/proc/%s/cmdline" % (vEntry,), "rb") as vFile:
        lArguments = vFile.read().split(b"\x00")
    except OSError:
      # The process ended between listing it and reading it.
      continue
    lText = [vArgument.decode("utf-8", "replace") for vArgument in lArguments]
    if "runner.py" not in " ".join(lText):
      continue
    if vNeedle in lText and lText.index(vNeedle) + 1 < len(lText):
      sAgentIds.add(lText[lText.index(vNeedle) + 1])
  return sorted(sAgentIds)


def fIsAgentRunning(pAgentId):
  """Return whether a run of this agent is already in flight."""
  return pAgentId in fListRunningAgentIds()


def fVerbListRunningAgents(pParams):
  """Return which agents are working right now.

  Read-only and unprivileged in spirit, but it lives here because reading
  every process's command line needs root. The sidebar uses it to spin the
  ring around an agent that is busy, so it is asked for often and must stay
  one sweep of /proc and nothing more.
  """
  return {"agent_ids": fListRunningAgentIds()}


def fVerbRunNow(pParams):
  """Start one agent run immediately, as that agent's own user.

  Returns as soon as the process is started: an agent run can take minutes and
  the web request that asked for it must not wait for it.

  With `only_if_idle`, a run already in flight means this one is not started
  and `started` comes back false. The check and the start happen here, in one
  place, so two callers cannot both look, both see an idle agent, and both
  start a run.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (vAgentId,))

  if pParams.get("only_if_idle") and fIsAgentRunning(vAgentId):
    fLogLine("Agent %s is already running; not starting another." % (vAgentId,))
    return {"agent_id": vAgentId, "started": False, "reason": "busy"}

  vRunnerPath = os.path.join(paths.fGetWebAppDir(), "backend", "core", "runner.py")
  vPythonPath = os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3")

  lCommand = [vPythonPath, vRunnerPath, "--agent-id", vAgentId]
  vPrompt = str(pParams.get("prompt") or "")
  if vPrompt:
    lCommand.extend(["--prompt", vPrompt])

  # A run that a card asked for is announced in the agent's chat, so the
  # conversation shows the work it was given as well as the work it was asked
  # for by hand. Written here and not in the buzzer for the same reason the
  # process is started here: the chat file lives in a 0700 home and only this
  # daemon can drop into it.
  dCard = pParams.get("card")
  vTurnId = ""
  if isinstance(dCard, dict) and dCard.get("id") is not None:
    vTurnId = os.urandom(8).hex()
    try:
      fRunAsAgent(
        vAgentId, vPasswordEntry,
        lambda: chat.fAppendCardMessage(vAgentId, dCard, vTurnId)
      )
      lCommand.extend(["--turn-id", vTurnId])
    except Exception as vError:
      # The announcement is the record of the work, not the work. A home that
      # cannot be written to is worth a line in the log, not a card that never
      # runs.
      fLogLine("Cannot announce card #%s in the chat of agent %s: %s"
               % (dCard.get("id"), vAgentId, vError))
      vTurnId = ""

  fLogLine("Starting a run for agent %s" % (vAgentId,))
  try:
    vProcess = subprocess.Popen(
      lCommand,
      user=vPasswordEntry.pw_uid,
      group=vPasswordEntry.pw_gid,
      extra_groups=[],
      cwd=vPasswordEntry.pw_dir,
      env=fBuildAgentEnvironment(vSystemUser, vPasswordEntry),
      stdin=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      start_new_session=True,
    )
  except Exception as vError:
    # The turn was opened a moment ago and the process that would have closed
    # it does not exist. Left open, the conversation waits for an answer for
    # ever and the composer stays shut: the card would not merely have gone
    # unanswered, it would have jammed the chat.
    fCloseTurnAfterAFailedStart(vAgentId, vPasswordEntry, vTurnId, vError)
    raise

  return {"agent_id": vAgentId, "pid": vProcess.pid, "started": True}


def fCloseTurnAfterAFailedStart(pAgentId, pPasswordEntry, pTurnId, pError):
  """Write the failure into a chat turn nothing else is going to close."""
  if not pTurnId:
    return
  try:
    fRunAsAgent(
      pAgentId, pPasswordEntry,
      lambda: chat.fAppendMessage(
        pAgentId, chat.cRoleError,
        "The run could not be started: %s" % (pError,), pTurnId,
        pMetadata={"reason": cReasonCannotStart}
      )
    )
  except Exception as vError:
    fLogLine("Cannot close the chat turn of agent %s: %s" % (pAgentId, vError))


def fVerbReadAgentInfo(pParams):
  """Return one agent's info.json.

  The web application cannot read it directly, because agent homes are 0700 and
  owned by the agent. This verb is that door, and it is read-only.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  return {"agent_id": vAgentId, "info": agents.fReadAgentInfo(vAgentId)}


def fVerbWriteAgentInfo(pParams):
  """Replace one agent's info.json with a validated version.

  The incoming object is never written as received: every field is rebuilt from
  the current file, so a malformed or hostile payload cannot change the agent's
  identity, its home directory or its system user.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  dIncoming = pParams.get("info") or {}
  if not isinstance(dIncoming, dict):
    raise ValueError("info must be an object")

  dCurrent = agents.fReadAgentInfo(vAgentId)
  dProvider = dIncoming.get("provider") or {}
  dLimits = dIncoming.get("limits") or {}

  dCurrent["name"] = agents.fValidateAgentName(
    dIncoming.get("name", dCurrent.get("name"))
  )
  dCurrent["description"] = str(dIncoming.get("description", dCurrent.get("description", "")))
  dCurrent["enabled"] = bool(dIncoming.get("enabled", dCurrent.get("enabled", True)))
  dCurrent["kanban_enabled"] = bool(
    dIncoming.get("kanban_enabled", dCurrent.get("kanban_enabled", True))
  )
  dCurrent["tools"] = [str(vTool) for vTool in (dIncoming.get("tools") or dCurrent.get("tools", []))]
  dCurrent["channels"] = [
    str(vChannel) for vChannel in (dIncoming.get("channels") or dCurrent.get("channels", []))
  ]

  # Skills are read with `in` rather than with `or`, so that unticking the last
  # one empties the list instead of quietly restoring what was there before.
  # A name that is not a name is refused outright - it can only be a bug or an
  # attempt at a path - while a name that is simply not installed any more is
  # dropped, so deleting a skill from the server never breaks the Save button
  # of an agent that happened to have it.
  lSkills = dCurrent.get("skills", [])
  if "skills" in dIncoming:
    lSkills = dIncoming.get("skills") or []
    if not isinstance(lSkills, list):
      raise ValueError("skills must be a list of skill names")
    for vSkill in lSkills:
      if not skills.fIsValidSkillName(vSkill):
        raise ValueError("%r is not a skill name" % (vSkill,))
  dCurrent["skills"] = skills.fSelectInstalledSkills(lSkills)

  dCurrent["provider"] = {
    "name": agents.fValidateProvider(
      dProvider.get("name", dCurrent.get("provider", {}).get("name", "ollama"))
    ),
    "model": str(dProvider.get("model", dCurrent.get("provider", {}).get("model", ""))),
    "base_url": str(dProvider.get("base_url", dCurrent.get("provider", {}).get("base_url", ""))),
    "api_key_ref": dProvider.get("api_key_ref", dCurrent.get("provider", {}).get("api_key_ref")),
  }

  # The backup model. An empty name is a valid answer and means there is none,
  # so it is not run through fValidateProvider, which insists on a real one.
  dFallback = dIncoming.get("fallback_provider")
  dCurrentFallback = dCurrent.get("fallback_provider") or {}
  if dFallback is None:
    dFallback = dCurrentFallback
  vFallbackName = str(dFallback.get("name", dCurrentFallback.get("name", ""))).strip()
  if vFallbackName:
    vFallbackName = agents.fValidateProvider(vFallbackName)
  dCurrent["fallback_provider"] = {
    "name": vFallbackName,
    "model": str(dFallback.get("model", dCurrentFallback.get("model", ""))),
    "base_url": str(dFallback.get("base_url", dCurrentFallback.get("base_url", ""))),
    "api_key_ref": dFallback.get("api_key_ref",
                                 dCurrentFallback.get("api_key_ref")),
  }

  dNewLimits = dict(dCurrent.get("limits") or agents.dDefaultLimits)
  for vKey in agents.dDefaultLimits:
    if vKey in dLimits:
      try:
        vValue = int(dLimits[vKey])
      except (TypeError, ValueError):
        raise ValueError("Limit %s must be an integer" % (vKey,))
      if vValue <= 0:
        raise ValueError("Limit %s must be greater than zero" % (vKey,))
      dNewLimits[vKey] = vValue
  dCurrent["limits"] = dNewLimits

  agents.fWriteAgentInfo(vAgentId, dCurrent)
  agents.fIndexAgent(vAgentId, dCurrent)
  return {"agent_id": vAgentId, "info": dCurrent}


def fVerbReadSystemPrompt(pParams):
  """Return one agent's system-prompt.md."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vPromptPath = paths.fGetAgentSystemPromptPath(vAgentId)
  try:
    with open(vPromptPath, "r", encoding="utf-8") as vFile:
      vContent = vFile.read()
  except FileNotFoundError:
    vContent = ""
  except OSError as vError:
    raise RuntimeError("Cannot read %s: %s" % (vPromptPath, vError))
  return {"agent_id": vAgentId, "system_prompt": vContent}


def fVerbWriteSystemPrompt(pParams):
  """Replace one agent's system-prompt.md."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vContent = str(pParams.get("system_prompt") or "")
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (vAgentId,))
  fEnsureAgentConfigDir(vAgentId, vPasswordEntry.pw_gid)
  fWriteAgentFile(
    paths.fGetAgentSystemPromptPath(vAgentId), vContent,
    0, vPasswordEntry.pw_gid, 0o640
  )
  return {"agent_id": vAgentId, "written": True}


def fVerbReadRunJournal(pParams):
  """Return one agent's run journal.

  The journal lives inside the agent's 0700 home, so this verb is the web
  application's only way to see what an agent has been doing.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vLimit = pParams.get("limit")
  if vLimit is not None:
    try:
      vLimit = max(1, min(int(vLimit), run_journal.cMaxJournalLines))
    except (TypeError, ValueError):
      raise ValueError("limit must be an integer")
  return {
    "agent_id": vAgentId,
    "entries": run_journal.fReadEntries(vAgentId, vLimit),
  }


def fVerbReadUsageSummary(pParams):
  """Return run and token totals for one agent, or for every agent."""
  vAgentId = pParams.get("agent_id")
  if vAgentId is not None:
    vNormalizedId = paths.fNormalizeAgentId(vAgentId)
    return {"summaries": {vNormalizedId: run_journal.fSummarizeUsage(vNormalizedId)}}

  dSummaries = {}
  for vExistingId in agents.fListUsedAgentIds():
    dSummaries[vExistingId] = run_journal.fSummarizeUsage(vExistingId)
  return {"summaries": dSummaries}


def fVerbReadMemory(pParams):
  """Return one agent's memory."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  return {"agent_id": vAgentId, "memory": memory.fRead(vAgentId)}


def fVerbWriteMemory(pParams):
  """Replace one agent's memory, as the agent.

  The user can edit it from the interface: it is the agent's memory, but it is
  the user's installation, and a wrong fact an agent keeps acting on is
  something you want to be able to correct.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vContent = str(pParams.get("memory") or "")
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (vAgentId,))
  fRunAsAgent(vAgentId, vPasswordEntry,
              lambda: memory.fWrite(vAgentId, vContent))
  return {"agent_id": vAgentId, "written": True}


def fVerbReadChat(pParams):
  """Return one agent's chat history.

  It lives inside the agent's 0700 home, so this is the web application's only
  way to read the conversation.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vLimit = pParams.get("limit")
  if vLimit is not None:
    try:
      vLimit = max(1, min(int(vLimit), chat.cMaxChatLines))
    except (TypeError, ValueError):
      raise ValueError("limit must be an integer")
  return {
    "agent_id": vAgentId,
    "messages": chat.fReadMessages(vAgentId, vLimit),
    "pending": chat.fHasPendingTurn(vAgentId),
  }


def fVerbSendChatMessage(pParams):
  """Record a chat message and start the run that answers it.

  Both halves happen here because both are things the web application cannot
  do: writing into the agent's 0700 home, and starting a process as the agent.
  The message is written before the run starts, so the interface can show it
  immediately and a run that dies still leaves the question visible.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vMessage = str(pParams.get("message") or "").strip()
  if not vMessage:
    raise ValueError("The message is empty")
  if len(vMessage) > cMaxChatMessageBytes:
    raise ValueError(
      "The message is too long (limit is %d characters)" % (cMaxChatMessageBytes,)
    )

  if chat.fHasPendingTurn(vAgentId):
    raise ValueError(
      "This agent is still answering the previous message. Wait for it to "
      "finish before sending another."
    )

  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (vAgentId,))

  dInfo = agents.fReadAgentInfo(vAgentId)
  if not dInfo.get("enabled", True):
    raise ValueError(
      "Agent %s is disabled. Enable it before talking to it." % (vAgentId,)
    )

  # Where the message came in through, when it was not the web interface. It is
  # validated rather than cleaned - it ends up in a JSON line the browser reads
  # and turns into a label - and an unknown source is dropped rather than
  # refused: a message that arrived is worth recording even if we cannot say
  # where from.
  vSource = str(pParams.get("source") or "").strip().lower()
  if vSource not in lKnownChatSources:
    vSource = ""

  vTurnId = os.urandom(8).hex()
  dMetadata = {"source": vSource} if vSource else None
  dRecorded = fRunAsAgent(
    vAgentId, vPasswordEntry,
    lambda: chat.fAppendMessage(
      vAgentId, chat.cRoleUser, vMessage, vTurnId, pPending=True,
      pMetadata=dMetadata
    )
  )

  vRunnerPath = os.path.join(paths.fGetWebAppDir(), "backend", "core", "runner.py")
  vPythonPath = os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3")

  fLogLine("Chat turn %s for agent %s" % (vTurnId, vAgentId))
  vProcess = subprocess.Popen(
    [vPythonPath, vRunnerPath, "--agent-id", vAgentId,
     "--chat-message", vMessage, "--turn-id", vTurnId],
    user=vPasswordEntry.pw_uid,
    group=vPasswordEntry.pw_gid,
    extra_groups=[],
    cwd=vPasswordEntry.pw_dir,
    env=fBuildAgentEnvironment(vSystemUser, vPasswordEntry),
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
  )
  return {"agent_id": vAgentId, "turn_id": vTurnId, "pid": vProcess.pid}


def fVerbClearChat(pParams):
  """Delete one agent's chat history."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (vAgentId,))
  fRunAsAgent(vAgentId, vPasswordEntry, lambda: chat.fClearHistory(vAgentId))
  return {"agent_id": vAgentId, "cleared": True}


# Verb dispatch table. Adding a privileged operation means adding a row here
# and nowhere else, which keeps the privileged surface easy to audit.
dVerbHandlers = {
  exec_protocol.cVerbPing: fVerbPing,
  exec_protocol.cVerbCreateAgent: fVerbCreateAgent,
  exec_protocol.cVerbDeleteAgent: fVerbDeleteAgent,
  exec_protocol.cVerbWriteCrontab: fVerbWriteCrontab,
  exec_protocol.cVerbReadCrontab: fVerbReadCrontab,
  exec_protocol.cVerbRunNow: fVerbRunNow,
  exec_protocol.cVerbListRunningAgents: fVerbListRunningAgents,
  exec_protocol.cVerbReadAgentInfo: fVerbReadAgentInfo,
  exec_protocol.cVerbWriteAgentInfo: fVerbWriteAgentInfo,
  exec_protocol.cVerbReadSystemPrompt: fVerbReadSystemPrompt,
  exec_protocol.cVerbWriteSystemPrompt: fVerbWriteSystemPrompt,
  exec_protocol.cVerbReadRunJournal: fVerbReadRunJournal,
  exec_protocol.cVerbReadUsageSummary: fVerbReadUsageSummary,
  exec_protocol.cVerbReadChat: fVerbReadChat,
  exec_protocol.cVerbSendChatMessage: fVerbSendChatMessage,
  exec_protocol.cVerbClearChat: fVerbClearChat,
  exec_protocol.cVerbReadMemory: fVerbReadMemory,
  exec_protocol.cVerbWriteMemory: fVerbWriteMemory,
}


class ExecRequestHandler(socketserver.StreamRequestHandler):
  """Handle one request on the executor socket."""

  def handle(self):
    try:
      vPid, vUid, vGid = fGetPeerCredentials(self.request)
    except OSError as vError:
      fLogLine("Cannot read peer credentials: %s" % (vError,))
      return

    if not fIsPeerAllowed(vUid):
      fLogLine("Refused connection from uid %d (pid %d)" % (vUid, vPid))
      try:
        self.wfile.write(
          exec_protocol.fEncodeMessage(
            exec_protocol.fBuildFailure("Not allowed")
          )
        )
      except OSError:
        pass
      return

    try:
      vRawRequest = self.rfile.readline(exec_protocol.cMaxRequestBytes)
    except OSError as vError:
      fLogLine("Cannot read request: %s" % (vError,))
      return

    dResponse = self.fProcessRequest(vRawRequest, vUid)

    try:
      self.wfile.write(exec_protocol.fEncodeMessage(dResponse))
    except OSError as vError:
      fLogLine("Cannot write response: %s" % (vError,))

  def fProcessRequest(self, pRawRequest, pUid):
    """Turn one raw request into a response payload."""
    try:
      dRequest = exec_protocol.fDecodeMessage(pRawRequest)
    except (ValueError, UnicodeDecodeError) as vError:
      return exec_protocol.fBuildFailure("Malformed request: %s" % (vError,))

    vVerb = dRequest.get("verb")
    dParams = dRequest.get("params") or {}
    if not isinstance(dParams, dict):
      return exec_protocol.fBuildFailure("params must be an object")

    fHandler = dVerbHandlers.get(vVerb)
    if fHandler is None:
      return exec_protocol.fBuildFailure("Unknown verb: %r" % (vVerb,))

    fLogLine("uid %d requested %s" % (pUid, vVerb))
    try:
      return exec_protocol.fBuildSuccess(fHandler(dParams))
    except ValueError as vError:
      return exec_protocol.fBuildFailure(vError)
    except Exception as vError:
      fLogLine("Verb %s failed: %s" % (vVerb, vError))
      return exec_protocol.fBuildFailure(vError)


class ExecServer(socketserver.ThreadingUnixStreamServer):
  """Unix socket server for the executor daemon."""

  daemon_threads = True
  allow_reuse_address = True


def fPrepareSocketPath():
  """Create the runtime directory and remove any stale socket file."""
  vSocketPath = paths.cExecSocketPath
  vRuntimeDir = os.path.dirname(vSocketPath)
  # 0755 root:root. The socket inside is 0660 root:boa, so an agent can see
  # that a socket exists and still cannot open it.
  os.makedirs(vRuntimeDir, mode=0o755, exist_ok=True)
  os.chmod(vRuntimeDir, 0o755)
  if os.path.exists(vSocketPath):
    os.unlink(vSocketPath)
  return vSocketPath


def fSecureSocket(pSocketPath):
  """Give the socket root:boa 0660, so no agent user can open it."""
  try:
    vAppGid = grp.getgrnam(paths.cAppGroup).gr_gid
  except KeyError:
    raise RuntimeError(
      "Group %s does not exist. Run the installer before starting the daemon."
      % (paths.cAppGroup,)
    )
  os.chown(pSocketPath, 0, vAppGid)
  os.chmod(pSocketPath, 0o660)


def fMain():
  """Run the daemon until it is stopped."""
  if os.getuid() != 0:
    fLogLine("The executor daemon must run as root.")
    return 1

  vSocketPath = fPrepareSocketPath()
  vServer = ExecServer(vSocketPath, ExecRequestHandler)
  try:
    fSecureSocket(vSocketPath)
  except RuntimeError as vError:
    fLogLine(str(vError))
    vServer.server_close()
    return 1

  fLogLine("Executor daemon listening on %s" % (vSocketPath,))
  try:
    vServer.serve_forever()
  except KeyboardInterrupt:
    fLogLine("Executor daemon stopping.")
  finally:
    vServer.server_close()
    if os.path.exists(vSocketPath):
      os.unlink(vSocketPath)
  return 0


if __name__ == "__main__":
  sys.exit(fMain())
