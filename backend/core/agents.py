"""Agent model: identifiers, info.json and the agents index.

An agent is three things that must stay in sync:

  1. A system user, `agent-xxx`, owning a 0700 home directory.
  2. An `info.json` inside that home, which is the source of truth for its
     configuration.
  3. A row in the `agents` table of boa.sqlite, which is only an index so that
     drawing the sidebar does not mean opening 999 files.

Because agent homes are 0700 and owned by the agent, the web application user
cannot read them. Every function here that touches a home directory therefore
runs inside the privileged daemon, never inside the web process.
"""

import hashlib
import json
import os
import re
import time

from backend.core import db
from backend.core import paths
from backend.providers import factory

# Display names are shown in the sidebar and used to address agents in prompts.
cAgentNamePattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,38}[A-Za-z0-9]$")

# Providers with a shipped adapter. One adapter per provider, one file each.
# Read from the factory rather than written out again: two lists of the same
# thing drift, and the one that decides whether an agent can be saved is not
# the one that decides whether it can run.
lSupportedProviders = list(factory.dProviderRegistry.keys())

# Default limits for a brand new agent. Deliberately low: an agent on a cron
# schedule that nobody watches is the cheapest way to run up a bill.
dDefaultLimits = {
  "max_tokens_per_run": 16384,
  "max_steps_per_run": 25,
  "timeout_seconds": 300,
  "max_runs_per_day": 48,
}

# A new agent can see the board and nothing else until the user says otherwise.
lDefaultTools = [
  "kanban.add_card",
  "kanban.move_card",
  "kanban.delete_card",
  "kanban.list_cards",
]


def fValidateAgentName(pName):
  """Return the validated display name of an agent.

  Raises ValueError when the name would be unusable in a prompt or in the UI.
  """
  vName = str(pName or "").strip()
  if not cAgentNamePattern.match(vName):
    raise ValueError(
      "Agent name must be 2 to 40 characters long and contain only letters, "
      "digits, spaces, dots, dashes and underscores: %r" % (pName,)
    )
  return vName


def fValidateProvider(pProviderName):
  """Return the validated provider name.

  Aliases are resolved here, so that an agent configured with `gemini` is
  stored as `google` and everything downstream sees one name.
  """
  vProvider = factory.fResolveProviderName(pProviderName)
  if vProvider not in lSupportedProviders:
    raise ValueError(
      "Unsupported provider %r. Supported: %s"
      % (pProviderName, ", ".join(sorted(lSupportedProviders)))
    )
  return vProvider


def fListUsedAgentIds():
  """Return every agent id that currently exists on disk.

  Reads the filesystem rather than the database, because the filesystem is what
  decides whether `useradd` will collide.
  """
  lUsedIds = []
  vAgentsDir = paths.fGetAgentsDir()
  try:
    lEntries = os.listdir(vAgentsDir)
  except OSError:
    return lUsedIds
  for vEntry in lEntries:
    if len(vEntry) == paths.cAgentIdLength and vEntry.isdigit():
      lUsedIds.append(vEntry)
  return sorted(lUsedIds)


def fGetNextFreeAgentId():
  """Return the lowest free agent id, as a zero-padded string.

  Starts at 001: 000 is reserved for the orchestrator, created at install time.
  """
  sUsedIds = set(fListUsedAgentIds())
  for vCandidate in range(1, paths.cMaxAgentId + 1):
    vPaddedId = str(vCandidate).zfill(paths.cAgentIdLength)
    if vPaddedId not in sUsedIds:
      return vPaddedId
  raise RuntimeError("No free agent id left: all 999 slots are in use")


def fBuildAgentInfo(pAgentId, pName, pDescription="", pProvider="ollama",
                    pModel="", pBaseUrl="",
                    pIsOrchestrator=False):
  """Build the info.json content of a new agent.

  The model is empty unless one is given. Writing a plausible-looking default
  into it would mean an agent that appears configured and fails on its first
  run against a model nobody chose; an empty field asks the question.
  """
  vAgentId = paths.fNormalizeAgentId(pAgentId)
  return {
    "id": vAgentId,
    "name": fValidateAgentName(pName),
    "description": str(pDescription or ""),
    "system_user": paths.fGetAgentSystemUser(vAgentId),
    "home": paths.fGetAgentHome(vAgentId),
    "enabled": True,
    "is_orchestrator": bool(pIsOrchestrator),
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "provider": {
      "name": fValidateProvider(pProvider),
      "model": str(pModel or ""),
      "base_url": str(pBaseUrl or ""),
      "api_key_ref": None,
    },
    # What the run falls back to when the main provider will not answer at
    # all. An empty name means there is none and a failure ends the run, which
    # is the honest default: a backup nobody chose would bill an account the
    # user did not mean to use.
    "fallback_provider": {
      "name": "",
      "model": "",
      "base_url": "",
      "api_key_ref": None,
    },
    "limits": dict(dDefaultLimits),
    "tools": list(lDefaultTools),
    "channels": [],
    # Which shared procedures this agent has been given. Names only: the
    # skills themselves live in /opt/boa/skills/ and belong to root.
    "skills": [],
    "kanban_enabled": True,
  }


def fReadAgentInfo(pAgentId):
  """Read one agent's info.json. Runs as root inside the privileged daemon.

  Opened through fOpenProtectedAgentFile, which refuses anything that is not a
  regular file owned by root and unwritable by anybody else. This file decides
  which tools the agent has: reading a version of it the agent could have
  written is the same as letting the agent grant itself tools.
  """
  vInfoPath = paths.fGetAgentInfoPath(pAgentId)
  try:
    with paths.fOpenProtectedAgentFile(pAgentId, paths.cInfoFileName) as vFile:
      dInfo = json.load(vFile)
  except FileNotFoundError:
    raise ValueError("Agent %s does not exist" % (paths.fNormalizeAgentId(pAgentId),))
  except PermissionError as vError:
    raise RuntimeError("Refusing to read %s: %s" % (vInfoPath, vError))
  except (OSError, ValueError) as vError:
    raise RuntimeError("Cannot read %s: %s" % (vInfoPath, vError))
  return dInfo


def fWriteAgentInfo(pAgentId, pInfo):
  """Write one agent's info.json atomically, as root's file.

  Writes to a temporary file in the same directory and renames it, so that an
  agent reading its own configuration never sees a half-written file.

  root:agent-xxx 0640, and it lives in the agent's config directory, which is
  root's. This file says which tools the agent has been granted and what it
  may spend: an agent able to edit it grants itself tools, and that is not a
  theory - it was measured, and the privileged daemon then reported the tool
  as granted. Only root ever writes here; every path into this function comes
  through the daemon.
  """
  vAgentId = paths.fNormalizeAgentId(pAgentId)
  vInfoPath = paths.fGetAgentInfoPath(vAgentId)
  vTempPath = vInfoPath + ".tmp"
  vStat = os.stat(paths.fGetAgentHome(vAgentId))
  try:
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      json.dump(pInfo, vFile, ensure_ascii=False, indent=2)
      vFile.write("\n")
    try:
      os.chown(vTempPath, 0, vStat.st_gid)
      os.chmod(vTempPath, 0o640)
    except PermissionError:
      # Not root: a test, or a development tree. Leave it as it is rather
      # than fail - on the server this always runs inside the daemon.
      os.chmod(vTempPath, 0o600)
    os.replace(vTempPath, vInfoPath)
  except OSError as vError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    raise RuntimeError("Cannot write %s: %s" % (vInfoPath, vError))


def fHashApiToken(pToken):
  """Return the stored form of an agent's local API token.

  A plain SHA-256 is enough here, unlike for the login password: the token is
  32 random bytes, so there is no dictionary to run against it.
  """
  return hashlib.sha256(str(pToken or "").strip().encode("utf-8")).hexdigest()


def fIndexAgent(pAgentId, pInfo, pApiToken=None):
  """Insert or update one agent in the agents index.

  When pApiToken is given its hash is stored; when it is omitted an existing
  hash is kept, so editing an agent's configuration never invalidates the
  token its running processes already hold.
  """
  vAgentId = paths.fNormalizeAgentId(pAgentId)
  vConnection = db.fOpenAppDb()
  try:
    vTokenHash = None
    if pApiToken:
      vTokenHash = fHashApiToken(pApiToken)
    else:
      vRow = vConnection.execute(
        "SELECT api_token_hash FROM agents WHERE id = ?", (vAgentId,)
      ).fetchone()
      if vRow:
        vTokenHash = vRow["api_token_hash"]

    vConnection.execute(
      "INSERT OR REPLACE INTO agents (id, name, system_user, enabled, "
      "api_token_hash) VALUES (?, ?, ?, ?, ?)",
      (
        vAgentId,
        pInfo.get("name", vAgentId),
        pInfo.get("system_user", paths.fGetAgentSystemUser(vAgentId)),
        1 if pInfo.get("enabled", True) else 0,
        vTokenHash,
      ),
    )
    vConnection.commit()
  finally:
    vConnection.close()


def fFindAgentByApiToken(pToken):
  """Return the agent row matching one API token, or None.

  This is what the agent API uses to turn a token into an identity.
  """
  if not str(pToken or "").strip():
    return None
  vConnection = db.fOpenAppDb()
  try:
    vRow = vConnection.execute(
      "SELECT id, name, system_user, enabled FROM agents WHERE api_token_hash = ?",
      (fHashApiToken(pToken),),
    ).fetchone()
  finally:
    vConnection.close()
  return dict(vRow) if vRow else None


def fUnindexAgent(pAgentId):
  """Remove one agent from the agents index."""
  vAgentId = paths.fNormalizeAgentId(pAgentId)
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("DELETE FROM agents WHERE id = ?", (vAgentId,))
    vConnection.commit()
  finally:
    vConnection.close()


def fListIndexedAgents():
  """Return every agent in the index, ordered by id.

  This is what the web application calls to draw the sidebar: it needs no
  access to the agent home directories.
  """
  vConnection = db.fOpenAppDb()
  try:
    lRows = vConnection.execute(
      "SELECT id, name, system_user, enabled, created_at FROM agents ORDER BY id"
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]
