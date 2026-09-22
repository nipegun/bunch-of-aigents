#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

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

import base64
import grp
import json
import os
import pwd
import re
import shutil
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import tempfile

from backend.core import agents
from backend.core import attachments
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

# Seconds a caller has to send its request line before the connection is
# dropped. socketserver's default is None, which is "wait for ever": a
# connection that opens and says nothing held a thread of a threading server
# until the process restarted.
cRequestTimeoutSeconds = 30

# Where a chat message can have come in through, other than the web interface
# it was typed into. A closed list because the value ends up in the chat file
# and then in the browser as a label: anything not on it is dropped.
lKnownChatSources = ["telegram", "discord"]


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


# Longest text handed to the runner on its standard input: a chat message, or
# the prompt a due card builds. Below a Linux pipe's 64 KiB buffer on purpose,
# so that the daemon's write completes whether or not the child has started
# reading yet - a write larger than the buffer waits for the child, and this
# daemon does not wait for runners. Both callers are far below it: a chat
# message is cMaxChatMessageBytes characters, and a card's prompt is bounded
# by the board's own limits on a title and a body.
cMaxStdinPayloadBytes = 60000


# Per-run limits on Debian, where systemd can put a run into a transient scope
# of its own: tasks - threads included, which is why the number is not
# smaller, a browser being a few hundred of them - and memory. The scope is
# also what ends whatever a run left behind: bash.run only signals its own
# process group, so a command that called setsid, or a background child of
# one that finished in time, outlived the run; `systemctl stop` on the scope
# reaches everything the run started, wherever it moved itself. And it takes
# the run out of this daemon's own cgroup, where a runaway agent used to
# spend the daemon's TasksMax and leave it unable to fork.
#
# On Alpine there is no systemd and no scope. What a run may do there is what
# the runner sets on itself: see runner.fApplyResourceLimits.
cRunTasksMax = 1024
cRunMemoryMax = "2G"
cRunSlice = "boa-agents.slice"


def fSystemdCanScope():
  """Whether a run can be started in a transient systemd scope here."""
  return (os.path.isdir("/run/systemd/system")
          and shutil.which("systemd-run") is not None
          and shutil.which("setpriv") is not None)


def fStopScope(pUnit):
  """End whatever is still running in one run's scope."""
  try:
    subprocess.run(["systemctl", "stop", "--quiet", pUnit],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=60, check=False)
  except (OSError, subprocess.SubprocessError) as vError:
    fLogLine("Cannot stop %s: %s" % (pUnit, vError))


def fWatchRunner(pAgentId, pPasswordEntry, pProcess, pTurnId, pUnit):
  """Wait for one run to end, and do what a run cannot do for itself.

  Two things. What the run left behind: with a scope, `systemctl stop` on it
  reaches every process the run started, wherever it moved itself; without
  one, nothing does. And a run that was killed - by the memory limit of its
  scope, by an operator, by anything that sends a signal - wrote nothing on
  the way out: no run_finished in its journal, and no error under the
  question that started it, so the turn stayed open and the composer stayed
  shut. A run that exited on its own has done both already, whatever its
  code; the turn is checked rather than assumed, because a crash before the
  runner's own handlers leaves it open with an exit code and not a signal.

  Waiting here also reaps the process: without it every finished run stayed
  a zombie until this daemon's garbage collector got round to it.
  """
  vCode = pProcess.wait()
  if pUnit:
    fStopScope(pUnit)
  if vCode == 0:
    return
  if vCode < 0:
    vReason = ("The run was killed by signal %d before it could answer."
               % (-vCode,))
  else:
    vReason = ("The run ended with exit code %d before it could answer."
               % (vCode,))
  try:
    vTurnOpen = bool(pTurnId) and chat.fTurnIsOpen(pAgentId, pTurnId)
  except Exception as vError:
    fLogLine("Cannot read the chat of agent %s: %s" % (pAgentId, vError))
    vTurnOpen = False
  if vCode > 0 and not vTurnOpen:
    # An ordinary failure: the runner wrote its own account of it.
    return
  fLogLine("Agent %s: %s" % (pAgentId, vReason))

  def fRecord():
    if vCode < 0:
      run_journal.fRecordRunFinished(pAgentId, "", "failed", 0, 0, vReason, "")
    if vTurnOpen:
      chat.fAppendMessage(pAgentId, chat.cRoleError, vReason, pTurnId)

  try:
    fRunAsAgent(pAgentId, pPasswordEntry, fRecord)
  except Exception as vError:
    fLogLine("Cannot record the end of agent %s's run: %s" % (pAgentId, vError))


def fStartRunner(pAgentId, pPasswordEntry, pSystemUser, pArguments, pPayload="",
                 pTurnId=""):
  """Start runner.py as the agent, handing it pPayload on standard input.

  What the user typed, and what a card says, used to travel on the command
  line: `--chat-message <text>`, `--prompt <text>`. The command line of a
  process is readable by every user of the machine through /proc, and an
  agent with bash.run is a user of the machine. Measured on a real install:
  `ps` run as agent-001 showed the message the owner had just sent to
  agent-000, for as long as that run lived. Standard input is read by the
  child and by nobody else, so the text goes there and the command line
  carries only the flag that says so.

  The size is checked before the process exists, so a text too long to hand
  over does not leave a runner waiting for input that is not coming. The
  child may already be gone by the time the write happens - an interpreter
  that fails at import exits at once - and then the pipe is broken, which is
  not this function's failure: the runner writes its own reasons to the
  journal.

  Where systemd is PID 1 the run goes into a transient scope of its own,
  `boa-agent-<id>-<random>.scope` under boa-agents.slice, with the task and
  memory limits above; `systemd-run --scope` execs into the command, so the
  pid is still the runner's and /proc still shows its command line.
  `setpriv` is what drops to the agent there, because systemd-run has to be
  root to create the scope. Elsewhere Popen drops to the agent itself. Either
  way a thread waits for the run, to end its scope and to close what it
  could not close: see fWatchRunner.
  """
  vPayload = pPayload.encode("utf-8") if pPayload else b""
  if len(vPayload) > cMaxStdinPayloadBytes:
    raise ValueError(
      "The text for the runner is too long (limit is %d bytes)"
      % (cMaxStdinPayloadBytes,))

  vRunnerPath = os.path.join(paths.fGetWebAppDir(), "backend", "core", "runner.py")
  vPythonPath = os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3")
  lRunner = [vPythonPath, vRunnerPath, "--agent-id", pAgentId] + list(pArguments)
  dKeywords = {
    "cwd": pPasswordEntry.pw_dir,
    "env": fBuildAgentEnvironment(pSystemUser, pPasswordEntry),
    "stdin": subprocess.PIPE if vPayload else subprocess.DEVNULL,
    "stdout": subprocess.DEVNULL,
    "stderr": subprocess.DEVNULL,
    "start_new_session": True,
  }
  vUnit = ""
  if fSystemdCanScope():
    vUnit = "boa-agent-%s-%s.scope" % (pAgentId, os.urandom(4).hex())
    lCommand = [
      "systemd-run", "--scope", "--quiet", "--collect",
      "--slice=%s" % (cRunSlice,), "--unit=%s" % (vUnit,),
      "-p", "TasksMax=%d" % (cRunTasksMax,),
      "-p", "MemoryMax=%s" % (cRunMemoryMax,),
      "--", "setpriv",
      "--reuid=%d" % (pPasswordEntry.pw_uid,),
      "--regid=%d" % (pPasswordEntry.pw_gid,),
      "--clear-groups", "--",
    ] + lRunner
  else:
    lCommand = lRunner
    dKeywords["user"] = pPasswordEntry.pw_uid
    dKeywords["group"] = pPasswordEntry.pw_gid
    dKeywords["extra_groups"] = []
  vProcess = subprocess.Popen(lCommand, **dKeywords)
  if vPayload:
    try:
      vProcess.stdin.write(vPayload)
      vProcess.stdin.close()
    except OSError as vError:
      fLogLine("Could not hand the text to the runner of agent %s: %s"
               % (pAgentId, vError))
      try:
        vProcess.stdin.close()
      except OSError:
        pass
  vWatcher = threading.Thread(
    target=fWatchRunner,
    args=(pAgentId, pPasswordEntry, vProcess, pTurnId, vUnit),
    daemon=True)
  vWatcher.start()
  # Kept on the process so that whoever started it can wait for the watcher
  # too - the tests do.
  vProcess.vWatcher = vWatcher
  return vProcess


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


def fEnsureAgentsConfigDir():
  """Create the root-owned parent of every agent's configuration directory.

  root:root 0711: an agent may traverse it to reach its own and cannot list
  what else is in it, which is the same reason /opt/boa/agents is 0711.
  """
  vDirectory = paths.fGetAgentsConfigDir()
  os.makedirs(vDirectory, exist_ok=True)
  os.chown(vDirectory, 0, 0)
  os.chmod(vDirectory, 0o711)
  return vDirectory


def fEnsureAgentConfigDir(pAgentId, pGid):
  """Create one agent's root-owned configuration directory, and return it.

  root:agent-xxx 0750: the agent may enter it and read what is in it, and
  cannot create, rename or delete anything there.

  It lives OUTSIDE the agent home. Inside it, the mode above bought nothing:
  renaming a directory needs write permission on its parent, the parent was
  the agent's own 0700 home, and so the agent could move the whole drawer
  aside and put its own in its place. The mode on the drawer was never
  consulted. Out here every directory on the way belongs to root.
  """
  fEnsureAgentsConfigDir()
  vDirectory = paths.fGetAgentConfigDir(pAgentId)
  os.makedirs(vDirectory, exist_ok=True)
  os.chown(vDirectory, 0, pGid)
  os.chmod(vDirectory, 0o750)
  return vDirectory


def fProtectAgentFiles(pAgentId, pGid):
  """Move an existing agent's protected files out of its home, as root.

  Called on every update and at daemon startup, for agents created under
  either older layout: straight in the home, or in the `config/` drawer that
  used to sit inside it. Moving is what takes the file out of the agent's
  reach - a file in a directory the agent can write is a file the agent can
  replace, whatever its own mode says.

  A file already in the new place wins over anything found in the old ones: on
  a machine where the agent DID substitute its drawer, the authoritative copy
  is the one root put there, not the one that was found in the home.
  """
  vDirectory = fEnsureAgentConfigDir(pAgentId, pGid)
  lSources = [
    paths.fGetLegacyAgentConfigDir(pAgentId),
    paths.fGetAgentHome(pAgentId),
  ]

  lMoved = []
  for vFileName in paths.lProtectedAgentFiles:
    vNewPath = os.path.join(vDirectory, vFileName)
    for vSourceDir in lSources:
      vOldPath = os.path.join(vSourceDir, vFileName)
      if os.path.exists(vNewPath):
        break
      # Never follow a link out of the home: an agent that left a symlink
      # called info.json pointing at a file of its own would otherwise have
      # that file promoted into the protected directory.
      if os.path.islink(vOldPath) or not os.path.isfile(vOldPath):
        continue
      os.replace(vOldPath, vNewPath)
      lMoved.append(vFileName)
      break
    if os.path.exists(vNewPath):
      # root owns it, the agent's group reads it.
      os.chown(vNewPath, 0, pGid)
      os.chmod(vNewPath, 0o640)

  # Whatever is left of the old drawer is the agent's problem, not a place
  # anything is read from any more. It is emptied of the three names so that a
  # stale copy cannot be mistaken for the real one by a human reading the
  # tree, and left otherwise alone: it is inside the agent's own home.
  vLegacyDir = paths.fGetLegacyAgentConfigDir(pAgentId)
  for vFileName in paths.lProtectedAgentFiles:
    for vStalePath in (os.path.join(vLegacyDir, vFileName),
                       os.path.join(paths.fGetAgentHome(pAgentId), vFileName)):
      try:
        if os.path.islink(vStalePath) or os.path.isfile(vStalePath):
          os.unlink(vStalePath)
      except OSError:
        pass
  return lMoved


def fProtectEveryAgent():
  """Run the migration for every agent on this machine. Returns how many.

  At startup as well as from the installer. The reader has no fallback to the
  old locations any more - the fallback WAS the bypass, since an agent could
  hide the authoritative file and have its own read instead - so something has
  to guarantee the files are in the new place before the first request is
  served. The daemon is root, it starts before anything asks it anything, and
  it is the only component that can move them.
  """
  vMoved = 0
  try:
    lAgentIds = sorted(os.listdir(paths.fGetAgentsDir()))
  except OSError:
    return 0

  for vEntry in lAgentIds:
    try:
      vAgentId = paths.fNormalizeAgentId(vEntry)
    except ValueError:
      continue
    try:
      vGid = pwd.getpwnam(paths.fGetAgentSystemUser(vAgentId)).pw_gid
    except KeyError:
      continue
    try:
      lMoved = fProtectAgentFiles(vAgentId, vGid)
    except OSError as vError:
      fLogLine("Cannot protect the files of agent %s: %s" % (vAgentId, vError))
      continue
    if lMoved:
      fLogLine("Agent %s: moved %s out of the home."
               % (vAgentId, ", ".join(lMoved)))
      vMoved += len(lMoved)
  return vMoved


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
  """Delete an agent completely: user, crontab, home, configuration and index.

  The configuration is now outside the home, so removing the home no longer
  removes it. Left behind, it would be handed to the next agent that got this
  id: its tools, its ceilings and its API token, belonging to somebody else.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  if vAgentId == paths.cOrchestratorId:
    raise ValueError("The orchestrating agent cannot be deleted")
  vSystemUser = paths.fGetAgentSystemUser(vAgentId)
  vHome = paths.fGetAgentHome(vAgentId)
  fLogLine("Deleting agent %s (%s)" % (vAgentId, vSystemUser))
  fRemoveAgentUser(vSystemUser, vHome)

  vConfigDir = paths.fGetAgentConfigDir(vAgentId)
  if os.path.isdir(vConfigDir):
    shutil.rmtree(vConfigDir, ignore_errors=True)

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


# One lock per agent, held from the moment this daemon asks whether an agent is
# running to the moment the process is started.
#
# The daemon serves every request on its own thread. So two `run_now` calls
# with `only_if_idle` could both sweep /proc, both find the agent idle, and
# both start a run - and the sweep cannot see a process that has not been
# forked yet, so even a small overlap is enough. The comment at fVerbRunNow
# used to say two callers could not both look and both start, which was true
# of two PROCESSES and never of this daemon's own threads.
#
# It is a lock inside one process, so it covers what this daemon starts: the
# run button, a due card, and a chat message. A crontab starts the runner
# directly and never comes through here, which is why the runner takes a file
# lock of its own - that one is the authority, this one is what lets the
# daemon answer "busy" instead of starting a process that immediately exits.
dAgentStartLocks = {}
vAgentStartLocksGuard = threading.Lock()


def fGetAgentStartLock(pAgentId):
  """Return the start lock of one agent, creating it once."""
  with vAgentStartLocksGuard:
    if pAgentId not in dAgentStartLocks:
      dAgentStartLocks[pAgentId] = threading.Lock()
    return dAgentStartLocks[pAgentId]


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
  and `started` comes back false. The check and the start are done holding
  this agent's start lock, so two callers cannot both look, both see an idle
  agent, and both start a run.

  That used to be claimed and not done. The daemon serves every request on its
  own thread, so the two callers were two threads of this process and there
  was nothing between them; measured, two simultaneous calls with
  only_if_idle=True produced two runs.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  with fGetAgentStartLock(vAgentId):
    return fStartRunLocked(vAgentId, pParams)


def fStartRunLocked(pvAgentId, pParams):
  """The body of fVerbRunNow, run with this agent's start lock held."""
  vSystemUser = paths.fGetAgentSystemUser(pvAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (pvAgentId,))

  if pParams.get("only_if_idle") and fIsAgentRunning(pvAgentId):
    fLogLine("Agent %s is already running; not starting another." % (pvAgentId,))
    return {"agent_id": pvAgentId, "started": False, "reason": "busy"}

  lArguments = []
  vPrompt = str(pParams.get("prompt") or "")
  if vPrompt:
    # The text itself goes on standard input, never on the command line: see
    # fStartRunner.
    lArguments.append("--prompt-on-stdin")

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
        pvAgentId, vPasswordEntry,
        lambda: chat.fAppendCardMessage(pvAgentId, dCard, vTurnId)
      )
      lArguments.extend(["--turn-id", vTurnId])
    except Exception as vError:
      # The announcement is the record of the work, not the work. A home that
      # cannot be written to is worth a line in the log, not a card that never
      # runs.
      fLogLine("Cannot announce card #%s in the chat of agent %s: %s"
               % (dCard.get("id"), pvAgentId, vError))
      vTurnId = ""

  fLogLine("Starting a run for agent %s" % (pvAgentId,))
  try:
    vProcess = fStartRunner(
      pvAgentId, vPasswordEntry, vSystemUser, lArguments, vPrompt, vTurnId)
  except Exception as vError:
    # The turn was opened a moment ago and the process that would have closed
    # it does not exist. Left open, the conversation waits for an answer for
    # ever and the composer stays shut: the card would not merely have gone
    # unanswered, it would have jammed the chat.
    fCloseTurnAfterAFailedStart(pvAgentId, vPasswordEntry, vTurnId, vError)
    raise

  return {"agent_id": pvAgentId, "pid": vProcess.pid, "started": True}


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


def fReadNameList(pIncoming, pKey, pCurrent):
  """Return a list of names from a payload, telling "empty" from "absent".

  The distinction is the whole point. A key that is not there means the caller
  is not changing it; a key holding an empty list means the caller is taking
  every one of them away, and that is a revocation the daemon must carry out
  rather than quietly undo.

  A value that is not a list is refused: it can only be a bug or an attempt at
  something, and neither should end up written into info.json.
  """
  if pKey not in pIncoming:
    return [str(vName) for vName in pCurrent or []]

  lIncoming = pIncoming.get(pKey)
  if lIncoming is None:
    return []
  if not isinstance(lIncoming, list):
    raise ValueError("%s must be a list of names" % (pKey,))
  return [str(vName) for vName in lIncoming]


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
  # Tools and channels are read with `in` rather than with `or`, for the same
  # reason skills are just below: `or` treats an empty list as an absent key,
  # so unticking the last tool restored the whole previous list. The interface
  # then reported a revocation it had not made - measured: two empty lists
  # went in, and bash.run and telegram were still granted afterwards.
  #
  # An omitted key still means "leave this alone", which is what lets a caller
  # send only the fields it wants changed.
  dCurrent["tools"] = fReadNameList(dIncoming, "tools", dCurrent.get("tools", []))
  dCurrent["channels"] = fReadNameList(dIncoming, "channels",
                                       dCurrent.get("channels", []))

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
  # Same byte budget as the chat, for the same reason: 2000 journal lines with
  # no cap on any one of them is a number of lines, not a size.
  lEntries, vDropped = exec_protocol.fTrimToByteBudget(
    run_journal.fReadEntries(vAgentId, vLimit))
  return {
    "agent_id": vAgentId,
    "entries": lEntries,
    "dropped": vDropped,
  }


def fVerbReadUsageSummary(pParams):
  """Return run and token totals for one agent, or for every agent."""
  vAgentId = pParams.get("agent_id")
  if vAgentId is not None:
    vNormalizedId = paths.fNormalizeAgentId(vAgentId)
    return {"summaries": {vNormalizedId: run_journal.fSummarizeUsage(vNormalizedId)}}

  dSummaries = {}
  for vExistingId in agents.fListUsedAgentIds():
    try:
      dSummaries[vExistingId] = run_journal.fSummarizeUsage(vExistingId)
    except Exception as vError:
      # One journal that cannot be read - a FIFO or a link left where
      # runs.jsonl should be - must not take the whole list down with it: the
      # sidebar draws every agent from this answer. That agent gets empty
      # totals and the reason; the log gets a line.
      fLogLine("Cannot summarize the journal of agent %s: %s"
               % (vExistingId, vError))
      dSummaries[vExistingId] = run_journal.fEmptyUsageSummary()
      dSummaries[vExistingId]["error"] = str(vError)
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
  # Trimmed by BYTES before the reply is built, not by line count.
  # Retention allows 500 lines and caps the length of none of them, so a
  # perfectly ordinary conversation went past what the client would read and
  # the chat stopped opening at all - in the web interface and in Telegram,
  # with nothing saying why.
  #
  # `dropped` travels so the interface can say "older messages are not shown"
  # rather than presenting a truncated history as the whole of it.
  lMessages, vDropped = exec_protocol.fTrimToByteBudget(
    chat.fReadMessages(vAgentId, vLimit))
  return {
    "agent_id": vAgentId,
    "messages": lMessages,
    "dropped": vDropped,
    "pending": chat.fHasPendingTurn(vAgentId),
  }


def fVerbReadChatAttachment(pParams):
  """Read only an owned PNG referenced by this agent's recorded conversation."""
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  vId = pParams.get("attachment_id")
  vOffset = pParams.get("offset", 0)
  if not attachments.fIsValidId(vId):
    return {"available": False}
  try:
    dImage = next((dImage for dMessage in chat.fReadMessages(vAgentId)
                   for dImage in attachments.fListMessageAttachments(dMessage)
                   if dImage["id"] == vId), None)
    if dImage is None:
      return {"available": False}
    vData, vSize = attachments.fReadImageChunk(vAgentId, vId, vOffset)
  except (OSError, ValueError):
    return {"available": False}
  vName = re.sub(r"[^A-Za-z0-9._-]", "_", str(dImage.get("name") or "image.png"))[:128]
  return {"available": True, "attachment": {
    "id": vId, "name": vName, "media_type": "image/png",
    "caption": str(dImage.get("caption") or "")[:1000],
  }, "offset": vOffset, "size": vSize,
    "data": base64.b64encode(vData).decode("ascii")}


def fVerbSendChatMessage(pParams):
  """Record a chat message and start the run that answers it.

  Both halves happen here because both are things the web application cannot
  do: writing into the agent's 0700 home, and starting a process as the agent.
  The message is written before the run starts, so the interface can show it
  immediately and a run that dies still leaves the question visible.
  """
  vAgentId = paths.fNormalizeAgentId(pParams.get("agent_id"))
  # The same lock the run button takes: "is this agent still answering" and
  # "write the question and start the run" have to be one step, or two
  # messages sent together both pass the pending check and both start a run.
  with fGetAgentStartLock(vAgentId):
    return fSendChatMessageLocked(vAgentId, pParams)


def fSendChatMessageLocked(pvAgentId, pParams):
  """The body of fVerbSendChatMessage, with this agent's start lock held."""
  vMessage = str(pParams.get("message") or "").strip()
  if not vMessage:
    raise ValueError("The message is empty")
  vAudioId = str(pParams.get("audio_id") or "")
  vRequestedTurn = str(pParams.get("turn_id") or "")
  if vAudioId and not re.fullmatch(r"[a-f0-9]{32}", vAudioId):
    raise ValueError("Invalid audio identifier.")
  if vRequestedTurn:
    if not vAudioId or vRequestedTurn != vAudioId[:16]:
      raise ValueError("An audio turn must use its reserved identifier.")
    for dMessage in chat.fReadMessages(pvAgentId):
      if dMessage.get("role") == chat.cRoleUser and dMessage.get("turn_id") == vRequestedTurn:
        return {"agent_id": pvAgentId, "turn_id": vRequestedTurn, "pid": 0}
  vLimit = 30000 if vAudioId else cMaxChatMessageBytes
  if len(vMessage) > vLimit:
    raise ValueError(
      "The message is too long (limit is %d characters)" % (vLimit,)
    )

  if chat.fHasPendingTurn(pvAgentId):
    raise ValueError(
      "This agent is still answering the previous message. Wait for it to "
      "finish before sending another."
    )

  vSystemUser = paths.fGetAgentSystemUser(pvAgentId)
  try:
    vPasswordEntry = pwd.getpwnam(vSystemUser)
  except KeyError:
    raise ValueError("Agent %s has no system user" % (pvAgentId,))

  dInfo = agents.fReadAgentInfo(pvAgentId)
  if not dInfo.get("enabled", True):
    raise ValueError(
      "Agent %s is disabled. Enable it before talking to it." % (pvAgentId,)
    )

  # Where the message came in through, when it was not the web interface. It is
  # validated rather than cleaned - it ends up in a JSON line the browser reads
  # and turns into a label - and an unknown source is dropped rather than
  # refused: a message that arrived is worth recording even if we cannot say
  # where from.
  vSource = str(pParams.get("source") or "").strip().lower()
  if vSource not in lKnownChatSources:
    vSource = ""

  vTurnId = vRequestedTurn or os.urandom(8).hex()
  dMetadata = {"source": vSource} if vSource else {}
  if vAudioId:
    dMetadata["audio_id"] = vAudioId
  dRecorded = fRunAsAgent(
    pvAgentId, vPasswordEntry,
    lambda: chat.fAppendMessage(
      pvAgentId, chat.cRoleUser, vMessage, vTurnId, pPending=True,
      pMetadata=dMetadata
    )
  )

  fLogLine("Chat turn %s for agent %s" % (vTurnId, pvAgentId))
  try:
    # The message goes on standard input, never on the command line: see
    # fStartRunner.
    vProcess = fStartRunner(
      pvAgentId, vPasswordEntry, vSystemUser,
      ["--chat-message-on-stdin", "--turn-id", vTurnId], vMessage, vTurnId)
  except Exception as vError:
    # The same repair the card path above already makes, for the same reason.
    # The question was written a moment ago with pending=True, and the process
    # that would have answered it does not exist. Left open, fHasPendingTurn
    # refuses every later message with "this agent is still answering the
    # previous one" - so a missing interpreter or a bad mode did not cost one
    # answer, it shut the conversation for good.
    fCloseTurnAfterAFailedStart(pvAgentId, vPasswordEntry, vTurnId, vError)
    raise

  return {"agent_id": pvAgentId, "turn_id": vTurnId, "pid": vProcess.pid}


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


def fVerbInstallWhisperModel(pParams):
  from backend.core import whisper_runtime
  return whisper_runtime.fStartModelDownload(pParams.get("model"))


# Verb dispatch table. Adding a privileged operation means adding a row here
# and nowhere else, which keeps the privileged surface easy to audit.
dVerbHandlers = {
  exec_protocol.cVerbInstallWhisperModel: fVerbInstallWhisperModel,
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
  exec_protocol.cVerbReadChatAttachment: fVerbReadChatAttachment,
  exec_protocol.cVerbSendChatMessage: fVerbSendChatMessage,
  exec_protocol.cVerbClearChat: fVerbClearChat,
  exec_protocol.cVerbReadMemory: fVerbReadMemory,
  exec_protocol.cVerbWriteMemory: fVerbWriteMemory,
}


class ExecRequestHandler(socketserver.StreamRequestHandler):
  """Handle one request on the executor socket."""

  # Seconds this handler waits for a caller to send its line.
  #
  # socketserver leaves `timeout` as None, so `self.rfile.readline` blocks for
  # ever on a connection that opens and never sends a newline. The server is a
  # threading one, so each of those holds a thread and a file descriptor until
  # the process restarts: opening a few hundred connections and saying nothing
  # is a local denial of service that needs no permission at all.
  timeout = cRequestTimeoutSeconds

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

  # Before the socket exists, so that no request is ever served against an
  # agent whose configuration is still somewhere the agent can rewrite.
  try:
    fProtectEveryAgent()
  except Exception as vError:
    fLogLine("Could not migrate the agent configuration: %s" % (vError,))

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
