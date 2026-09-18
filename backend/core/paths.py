"""Filesystem layout of a Bunch of AIgents installation.

Every path in the project is derived from here. Nothing else in the codebase
hardcodes a directory, so a change of layout is a change of this file only.

The base directory is read from the BOA_BASE_DIR environment variable, which
lets the test suite point the whole tree at a temporary directory without
touching the production installation.
"""

import os

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
# permission on the DIRECTORY is. So these live in a subdirectory owned by
# root that the agent may enter and read and cannot write. The home stays the
# agent's; this one drawer inside it is not.
cAgentConfigDirName = "config"


def fGetAgentConfigDir(pAgentId):
  """The root-owned directory inside an agent home, readable by the agent."""
  return os.path.join(fGetAgentHome(pAgentId), cAgentConfigDirName)


def fFindAgentFile(pAgentId, pFileName):
  """The config path of a file, or its old home path if that is what exists.

  Installations made before the config directory existed keep these files
  straight in the home. The installer moves them on update; until it has,
  reading has to work either way, or an update would be a service that stops
  answering until somebody notices.
  """
  vConfigPath = os.path.join(fGetAgentConfigDir(pAgentId), pFileName)
  if os.path.exists(vConfigPath):
    return vConfigPath
  vLegacyPath = os.path.join(fGetAgentHome(pAgentId), pFileName)
  if os.path.exists(vLegacyPath):
    return vLegacyPath
  return vConfigPath


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
