"""Filesystem layout of a Bunch of AIgents installation.

Every path in the project is derived from here. Nothing else in the codebase
hardcodes a directory, so a change of layout is a change of this file only.

The base directory is read from the BOA_BASE_DIR environment variable, which
lets the test suite point the whole tree at a temporary directory without
touching the production installation.
"""

import errno
import os
import pwd
import stat

# Base directory. Production installations always use /opt/boa.
cDefaultBaseDir = "/opt/boa"

# System users
cAppUser = "boa"
cAppGroup = "boa"
cAgentUserPrefix = "agent-"
cOrchestratorId = "000"
cOrchestratorName = "manager"

# Network. These two ports are served by the application's own HAProxy, not by
# gunicorn: the machine's HAProxy prefixes a PROXY header before the TLS
# handshake, and only a proxy can read it there. Both listen on loopback only.
cHttpPort = 11080
cHttpsPort = 11443
cBindAddress = "127.0.0.1"

# Where gunicorn actually listens. Nothing on the network can reach it, so the
# only way into the application is through the proxy.
cWebSocketPath = "/run/boa-web/web.sock"

# Privileged executor daemon. Its runtime directory belongs to root; the agent
# API has a separate one because it runs as `boa` and has to create its socket
# itself.
cExecSocketPath = "/run/boa/exec.sock"

# Agent identifiers are three digits, 000 to 999.
cAgentIdLength = 3
cMinAgentId = 0
cMaxAgentId = 999


def fGetBaseDir():
  """Return the installation base directory."""
  return os.environ.get("BOA_BASE_DIR", cDefaultBaseDir)


def fGetWebAppDir():
  """Return the directory holding the deployed application code."""
  return os.path.join(fGetBaseDir(), "webapp")


def fGetToolsDir():
  """Return the directory holding the tool modules, one .py per tool."""
  return os.path.join(fGetBaseDir(), "tools")


def fGetSkillsDir():
  """Return the directory holding the skills, one directory per skill.

  Beside the tools and outside the deployed code, for the same reason: an
  update replaces webapp/ wholesale, and a procedure somebody wrote on this
  server is not something an update is entitled to delete.
  """
  return os.path.join(fGetBaseDir(), "skills")


def fGetAgentsDir():
  """Return the directory holding every agent home directory."""
  return os.path.join(fGetBaseDir(), "agents")


def fGetPlaywrightDir():
  """Return the directory holding the browser Playwright downloads.

  One copy for the whole installation, root-owned and read-only to everybody
  else. The browser is a binary: there is nothing to isolate about it, and a
  copy per agent would be 600 MB each and an update to do N times. What does
  have to be isolated is the profile - the cookies, the sessions - and that
  lives in each agent's own 0700 home.
  """
  return os.path.join(fGetBaseDir(), "playwright")


def fGetConfigDir():
  """Return the configuration directory."""
  return os.path.join(fGetBaseDir(), "config")


def fGetChannelsDir():
  """Return the directory holding one JSON file per messaging channel."""
  return os.path.join(fGetConfigDir(), "channels")


def fGetTelegramOffsetPath():
  """Return the file holding the last Telegram update the listener dealt with.

  Beside the configuration rather than in the database: it is one number, it is
  written on every pass, and losing it should mean re-reading a few messages -
  not a migration.
  """
  return os.path.join(fGetConfigDir(), "telegram-offset")


def fGetDiscordAfterPath():
  """Return the file holding the last Discord message the listener dealt with.

  Beside the Telegram offset and for the same reasons. What it holds is a
  snowflake - the id of a message - rather than a counter, because that is
  what Discord's `after` parameter takes.
  """
  return os.path.join(fGetConfigDir(), "discord-after")


def fGetDbDir():
  """Return the directory holding the application database."""
  return os.path.join(fGetBaseDir(), "db")


def fGetDbPath():
  """Return the path of the application SQLite database."""
  return os.path.join(fGetDbDir(), "boa.sqlite")


def fGetKanbanDir():
  """Return the directory holding the kanban board."""
  return os.path.join(fGetBaseDir(), "kanban")


def fGetKanbanDbPath():
  """Return the path of the kanban SQLite database.

  The board is a database and not a set of JSON files because several agents
  write to it concurrently, and only a transaction prevents two simultaneous
  card additions from overwriting each other.
  """
  return os.path.join(fGetKanbanDir(), "kanban.sqlite")


def fGetCertificatesDir():
  """Return the directory holding the TLS certificate and private key."""
  return os.path.join(fGetBaseDir(), "certificates")


def fGetLogsDir():
  """Return the directory holding the application logs."""
  return os.path.join(fGetBaseDir(), "logs")


def fNormalizeAgentId(pAgentId):
  """Return a validated, zero-padded three digit agent identifier.

  Raises ValueError when the identifier is not a number between 0 and 999, so
  that no caller can ever build a path out of arbitrary user input.
  """
  try:
    vNumericId = int(str(pAgentId).strip())
  except (TypeError, ValueError):
    raise ValueError("Agent id must be a number between 0 and 999: %r" % (pAgentId,))
  if vNumericId < cMinAgentId or vNumericId > cMaxAgentId:
    raise ValueError("Agent id out of range (0-999): %r" % (pAgentId,))
  return str(vNumericId).zfill(cAgentIdLength)


def fGetAgentHome(pAgentId):
  """Return the home directory of one agent."""
  return os.path.join(fGetAgentsDir(), fNormalizeAgentId(pAgentId))


def fGetAgentSystemUser(pAgentId):
  """Return the system user name of one agent."""
  return cAgentUserPrefix + fNormalizeAgentId(pAgentId)


# What an agent may read but must not write --------------------------------
#
# The home is the agent's own, 0700, and that is the point: it is where it
# keeps its memory, its journal, its conversation and any script it writes.
# But three of the files in it are not the agent's business to change:
#
#   info.json        which tools it has been granted, and its spending
#                    ceilings. An agent that can edit this grants itself
#                    tools - measured: it added mail.read to its own list and
#                    the privileged daemon then reported it as granted.
#   system-prompt.md the definition of what it is supposed to do. An agent
#                    talked into rewriting it stays rewritten, on every run
#                    from then on.
#   api-token        what it identifies itself to the agent API with.
#
# Owning a file is not what decides whether it can be replaced: the write
# permission on its DIRECTORY is.
#
# That sentence is why these files used to live in `<home>/config/`, owned by
# root - and why that was not enough. The rule applies to the drawer as well
# as to what is in it. `<home>/config` is an entry in the HOME, the home
# belongs to the agent at 0700, and renaming an entry needs write permission
# on the parent and nothing else. So the agent could not edit info.json, and
# could do this:
#
#     mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json
#
# and the daemon would read the substitute. Measured on a temporary tree: the
# rename succeeds against a directory with no write permission at all,
# because the kernel is not asked about that directory.
#
# So the drawer moved out of the home entirely, to a sibling of it under
# `/opt/boa/agents-config/`, whose whole parent chain is root's. The agent can
# reach its own and read what is in it; it cannot rename it, replace it or
# create one, because it can write to none of the directories on the way.
cAgentsConfigDirName = "agents-config"

# The old in-home drawer, and the older bare-home layout. Kept so the
# migration knows where to look, never read from.
cLegacyAgentConfigDirName = "config"


def fGetAgentsConfigDir():
  """The root-owned directory holding every agent's protected configuration."""
  return os.path.join(fGetBaseDir(), cAgentsConfigDirName)


def fGetAgentConfigDir(pAgentId):
  """Where one agent's protected files live: root's, outside the agent home."""
  return os.path.join(fGetAgentsConfigDir(), fNormalizeAgentId(pAgentId))


def fGetLegacyAgentConfigDir(pAgentId):
  """The pre-move drawer inside the home, for the installer's migration."""
  return os.path.join(fGetAgentHome(pAgentId), cLegacyAgentConfigDirName)


def fFindAgentFile(pAgentId, pFileName):
  """The path of one protected file. One place, with no fallback.

  There was a fallback: if the file was not in the drawer, the copy in the
  home was read instead, so that an update was not a service that stopped
  answering before the migration had run. It also meant an agent could delete
  the authoritative file's directory and have its own copy read - the fallback
  WAS the bypass. The migration now runs when the daemon starts as well as
  from the installer, so there is no window left for it to cover.
  """
  return os.path.join(fGetAgentConfigDir(pAgentId), pFileName)


def fOpenProtectedAgentFile(pAgentId, pFileName):
  """Open one protected file, refusing anything that is not root's own.

  The location is already out of the agent's reach, so this is the second
  answer to the same question rather than the only one - and it is the answer
  that survives a mistaken chmod during an update, or a directory restored
  from a backup with the wrong owner.

  Three things are checked, on the OPEN FILE rather than on its path, so that
  nothing can be swapped between the check and the read:

    it is a regular file   not a symlink into the home, not a fifo that makes
                           the daemon wait for an agent to feed it
    the owner may say so   root, in a real installation
    nobody else may write  0640 at the loosest

  The owner test is "root, or this process's own user when this process is not
  root". The second half is not a loosening of the first: an installation
  running entirely as one unprivileged user - the test tree, a developer's
  checkout - has no root to own anything, and there is no agent to keep out
  either, because there are no separate agent users. Where the check matters
  is the privileged daemon and the agent API, and the daemon refuses to start
  unless it is root, so there the first half is the only half that applies.

  Returns an open file object in text mode; the caller closes it.
  """
  vPath = os.path.join(fGetAgentConfigDir(pAgentId), pFileName)
  # O_NOFOLLOW refuses a symlink AT THE LAST component. The directories above
  # are root's, so there is nothing to point a link from.
  vDescriptor = os.open(vPath, os.O_RDONLY | os.O_NOFOLLOW)
  try:
    dStat = os.fstat(vDescriptor)
    if not stat.S_ISREG(dStat.st_mode):
      raise PermissionError(
        "%s is not a regular file, so it is not the configuration this agent "
        "was given." % (vPath,))

    sAllowedOwners = {0}
    if os.geteuid() != 0:
      sAllowedOwners.add(os.geteuid())
    if dStat.st_uid not in sAllowedOwners:
      raise PermissionError(
        "%s is owned by uid %d, which may not decide what it says."
        % (vPath, dStat.st_uid))

    if dStat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
      raise PermissionError(
        "%s is writable by somebody other than its owner (mode %o)."
        % (vPath, stat.S_IMODE(dStat.st_mode)))
    return os.fdopen(vDescriptor, "r", encoding="utf-8")
  except Exception:
    os.close(vDescriptor)
    raise


# What root reads from the home ---------------------------------------------
#
# The journal, the memory and the chat are the agent's own files, in its own
# 0700 home, written by its own processes. The privileged daemon reads all
# three as root, and root reads whatever it is pointed at: a FIFO named
# runs.jsonl makes the daemon thread wait for ever for an agent to feed it,
# and a link named memory.md pointing at a huge file has root read the whole
# thing into memory. Measured on the code before this existed: the request
# for the agents list, which reads every agent's journal, blocked on a FIFO
# and every later request leaked one more thread.
#
# So the daemon opens these the way it opens the protected files - on the OPEN
# FILE, so nothing can be swapped between the check and the read - and it
# bounds what it reads, so a file can be as large as its owner likes without
# the daemon having to hold it.

# Longest file of each kind the daemon will take. Well above what a legitimate
# one can reach: the journal is trimmed to 2000 lines with the answer in each
# capped at 4000 characters, the chat to 500 lines, and the memory is written
# at 8000 characters. A file past this is not the application's doing.
cMaxJournalBytes = 32 * 1024 * 1024
cMaxChatBytes = 32 * 1024 * 1024
cMaxMemoryBytes = 1024 * 1024

# Read in pieces of this size, so that the bound is on what is read and not
# only on what fstat said before reading began: an agent can append while its
# file is being read.
cReadChunkBytes = 64 * 1024


def fListAllowedAgentFileOwners(pAgentId):
  """The uids a file of this agent's home may be owned by.

  The agent's own user, when the system has one. This process's own user as
  well when it is not root: the test tree and a developer's checkout have no
  agent users, so there the files are whoever is running this. Root never
  gets that second half - the daemon refuses to start unless it is root, so
  for the daemon the agent's uid is the only answer, and an installation with
  no such user has nothing to read.
  """
  sOwners = set()
  try:
    sOwners.add(pwd.getpwnam(fGetAgentSystemUser(pAgentId)).pw_uid)
  except KeyError:
    pass
  if os.geteuid() != 0:
    sOwners.add(os.geteuid())
  return sOwners


def fOpenAgentOwnedFile(pAgentId, pPath):
  """Open one file of an agent's home for reading, or raise PermissionError.

  Refused, on the open descriptor rather than on the path: anything that is
  not a regular file, and a regular file owned by anybody but the agent. A
  symbolic link is refused at the open itself, with O_NOFOLLOW; O_NONBLOCK is
  what stops a FIFO from holding the open until somebody writes to it, so the
  fstat that follows can see what it is and say no.

  Returns the descriptor and the size fstat reported. The caller closes it.
  """
  try:
    vDescriptor = os.open(
      pPath, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY)
  except OSError as vError:
    if vError.errno == errno.ELOOP:
      raise PermissionError(
        "%s is a symbolic link, and a file of an agent's home is read only "
        "where it is." % (pPath,))
    raise
  try:
    dStat = os.fstat(vDescriptor)
    if not stat.S_ISREG(dStat.st_mode):
      raise PermissionError(
        "%s is not a regular file, so it is not something the application "
        "wrote." % (pPath,))
    sOwners = fListAllowedAgentFileOwners(pAgentId)
    if dStat.st_uid not in sOwners:
      raise PermissionError(
        "%s is owned by uid %d, which is not agent %s."
        % (pPath, dStat.st_uid, pAgentId))
    return vDescriptor, dStat.st_size
  except Exception:
    os.close(vDescriptor)
    raise


def fReadAgentOwnedFile(pAgentId, pPath, pMaxBytes, pKeepEnd=False):
  """Read one file of an agent's home, never more than pMaxBytes of it.

  Returns the text and whether it was cut. A file larger than the bound is
  read from its END when pKeepEnd is set, which is what a journal or a chat
  wants - the newest lines are the ones that get shown - and the partial line
  the cut lands in is dropped; otherwise from its start. The bound holds even
  when the file grows while it is being read.

  Decoded with replacement rather than strictly: one bad byte in a file the
  agent controls must not turn into an exception in the process reading it.

  Raises PermissionError for what fOpenAgentOwnedFile refuses, and the OSError
  of the open for anything else - FileNotFoundError included, which every
  caller treats as "nothing written yet".
  """
  vDescriptor, vSize = fOpenAgentOwnedFile(pAgentId, pPath)
  try:
    vTruncated = vSize > pMaxBytes
    if vTruncated and pKeepEnd:
      os.lseek(vDescriptor, vSize - pMaxBytes, os.SEEK_SET)
    lChunks = []
    vRemaining = pMaxBytes
    while vRemaining > 0:
      vChunk = os.read(vDescriptor, min(cReadChunkBytes, vRemaining))
      if not vChunk:
        break
      lChunks.append(vChunk)
      vRemaining -= len(vChunk)
    if not vTruncated and vRemaining == 0 and os.read(vDescriptor, 1):
      # It grew past the bound between the fstat and the end of the read.
      vTruncated = True
  finally:
    os.close(vDescriptor)

  vText = b"".join(lChunks).decode("utf-8", errors="replace")
  if vTruncated and pKeepEnd:
    vFirstNewline = vText.find("\n")
    vText = vText[vFirstNewline + 1:] if vFirstNewline >= 0 else ""
  return vText, vTruncated


cInfoFileName = "info.json"


def fGetAgentInfoPath(pAgentId):
  """Return the path of one agent's info.json."""
  return fFindAgentFile(pAgentId, cInfoFileName)


# Name of the system prompt file inside each agent home. Installations made
# before this was renamed have the old name; the installer renames them.
cSystemPromptFileName = "system-prompt.md"
cLegacySystemPromptFileName = "SystemPrompt.md"


def fGetAgentSystemPromptPath(pAgentId):
  """Return the path of one agent's system-prompt.md."""
  return fFindAgentFile(pAgentId, cSystemPromptFileName)


def fGetLegacySystemPromptPath(pAgentId):
  """Return the pre-rename path, for the installer's migration."""
  return os.path.join(fGetAgentHome(pAgentId), cLegacySystemPromptFileName)


cRunLockFileName = "run.lock"


def fGetAgentRunLockPath(pAgentId):
  """The file one agent's runs take an exclusive lock on.

  In the agent's own home, because every run of an agent is that agent's own
  process - the one the daemon starts and the one its crontab starts - and
  both have to be able to open the same file. It is not a permission boundary:
  an agent with bash.run can start whatever it likes, and this exists to stop
  the APPLICATION starting the same agent twice, not to stop the agent.
  """
  return os.path.join(fGetAgentHome(pAgentId), cRunLockFileName)


cApiTokenFileName = "api-token"


def fGetAgentApiTokenPath(pAgentId):
  """Return the path of one agent's local API token.

  The token identifies the agent against the local API. It is what lets an
  agent post to a channel without ever being able to read that channel's
  credentials.
  """
  return fFindAgentFile(pAgentId, cApiTokenFileName)


# The three files that move into the root-owned drawer, in one place so the
# installer's migration and the daemon that creates an agent cannot disagree
# about which they are.
lProtectedAgentFiles = [cInfoFileName, cSystemPromptFileName, cApiTokenFileName]
