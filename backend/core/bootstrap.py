"""First-run initialization, called once by the Debian installer.

Creates both databases, stores the single administrator account and registers
the orchestrating agent that the installer has just created on the system.

The installer invokes this module as root, and the resulting files are handed
over to the `boa` user afterwards, so nothing here changes ownership itself.
"""

import json
import os

from argon2 import PasswordHasher

from backend.core import agents
from backend.core import db
from backend.core import paths

# Argon2id parameters. Generous for a LAN-only single-user login: the cost of a
# slow login once a day is nothing next to the cost of a guessable password.
cArgonTimeCost = 3
cArgonMemoryCost = 65536
cArgonParallelism = 4


def fHashPassword(pPassword):
  """Return an argon2id hash of a plaintext password."""
  vHasher = PasswordHasher(
    time_cost=cArgonTimeCost,
    memory_cost=cArgonMemoryCost,
    parallelism=cArgonParallelism,
  )
  return vHasher.hash(pPassword)


def fStoreAdministrator(pEmail, pPassword):
  """Store the single administrator account, replacing any previous one."""
  vHash = fHashPassword(pPassword)
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("DELETE FROM admin")
    vConnection.execute(
      "INSERT INTO admin (id, email, password_hash) VALUES (1, ?, ?)",
      (pEmail, vHash),
    )
    vConnection.commit()
  finally:
    vConnection.close()


def fRegisterAgent(pAgentId):
  """Add one agent to the agents index, reading its info.json.

  The info.json in the agent home directory is the source of truth. This table
  is only an index, so that listing the agents does not mean opening 999 files.

  The agent's API token is hashed into the index at the same time. The
  installer has already written the token file; this runs as root, which is the
  only moment the token can be read to hash it, because the file is 0600 and
  owned by the agent from here on.
  """
  vAgentId = paths.fNormalizeAgentId(pAgentId)
  vInfoPath = paths.fGetAgentInfoPath(vAgentId)
  try:
    with open(vInfoPath, "r", encoding="utf-8") as vFile:
      dInfo = json.load(vFile)
  except (OSError, ValueError) as vError:
    raise RuntimeError("Cannot read %s: %s" % (vInfoPath, vError))

  vApiToken = ""
  try:
    with open(paths.fGetAgentApiTokenPath(vAgentId), "r", encoding="utf-8") as vFile:
      vApiToken = vFile.read().strip()
  except OSError:
    vApiToken = ""

  agents.fIndexAgent(vAgentId, dInfo, vApiToken)


def fSeedDefaultSettings():
  """Write the settings the web interface expects to find on first run."""
  dDefaults = {
    "language": "en-US",
    "theme": "system",
    "smtp_configured": "0",
  }
  vConnection = db.fOpenAppDb()
  try:
    for vKey, vValue in dDefaults.items():
      vConnection.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (vKey, vValue),
      )
    vConnection.commit()
  finally:
    vConnection.close()


def fInitializeInstallation():
  """Entry point used by the installer.

  Reads BOA_ADMIN_EMAIL and BOA_ADMIN_PASSWORD from the environment rather than
  from the command line, so the generated password never appears in the process
  list of the production server.
  """
  vEmail = os.environ.get("BOA_ADMIN_EMAIL", "").strip()
  vPassword = os.environ.get("BOA_ADMIN_PASSWORD", "")

  if not vEmail:
    raise RuntimeError("BOA_ADMIN_EMAIL is empty. The installer must provide it.")
  if not vPassword:
    raise RuntimeError("BOA_ADMIN_PASSWORD is empty. The installer must provide it.")

  db.fCreateAppSchema()
  db.fCreateKanbanSchema()
  fSeedDefaultSettings()
  fStoreAdministrator(vEmail, vPassword)

  # The installer creates its agents before calling us, so their info.json
  # files are already on disk. Indexing whatever is there, rather than a fixed
  # list, means a new shipped agent needs no change here.
  for vAgentId in agents.fListUsedAgentIds():
    if os.path.exists(paths.fGetAgentInfoPath(vAgentId)):
      fRegisterAgent(vAgentId)

  print("Bunch of AIgents initialized at %s" % (paths.fGetBaseDir(),))
