"""SQLite access for the application database and the kanban board.

Two separate databases on purpose:

  - boa.sqlite    : installation state, agents index, login, usage accounting.
  - kanban.sqlite : the board, written concurrently by every agent.

Keeping the board apart means a long agent transaction on the board never
blocks the user interface, and the board can be backed up or wiped on its own.

Both databases run in WAL mode with a busy timeout, which is what makes
concurrent writes from several agent processes safe.
"""

import sqlite3

from backend.core import paths

# Seconds a writer waits for a lock before giving up. Agent runs are short but
# several may land on the same second, so a generous timeout is cheaper than
# handling a retry loop in every caller.
cBusyTimeoutSeconds = 30

cAppSchema = """
CREATE TABLE IF NOT EXISTS settings (
  key           TEXT PRIMARY KEY,
  value         TEXT NOT NULL,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  email         TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  -- Bumped every time the password changes. A session carries the value it
  -- was granted under, so changing the password makes every session granted
  -- before it stop being accepted. A counter and not a timestamp:
  -- datetime('now') has one-second resolution, and a password changed in the
  -- same second as a login would be indistinguishable from one changed
  -- before it.
  session_epoch INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS login_attempts (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  remote_addr   TEXT NOT NULL,
  attempted_at  TEXT NOT NULL DEFAULT (datetime('now')),
  succeeded     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_addr
  ON login_attempts (remote_addr, attempted_at);

CREATE TABLE IF NOT EXISTS agents (
  id             TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  system_user    TEXT NOT NULL UNIQUE,
  enabled        INTEGER NOT NULL DEFAULT 1,
  -- SHA-256 of the agent's local API token. The token itself lives 0600 in
  -- the agent's own home, which the web user cannot read, so the hash is how
  -- the agent API recognises a caller.
  api_token_hash TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- There are deliberately no `runs` or `usage` tables here. An agent process
-- runs as `agent-xxx` and this database is 0700 owned by `boa`, so an agent
-- cannot write to it - and giving it write access would let any agent rewrite
-- another agent's history. Each agent keeps its own journal in its own home
-- instead, and the web application reads those through the privileged daemon.
-- See backend/core/run_journal.py.

-- What the bot has said on Telegram, and who said it. A person answering a
-- message there is answering the agent that sent it, and the id Telegram gave
-- that message is the only thing connecting the two. Pruned: it is a routing
-- table for recent conversation, not a history of anything.
CREATE TABLE IF NOT EXISTS telegram_messages (
  message_id    INTEGER PRIMARY KEY,
  agent_id      TEXT NOT NULL,
  sent_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Questions asked over Telegram that an agent has not finished answering. On
-- disk rather than in the listener's memory so that restarting the service -
-- which every update does - does not leave somebody waiting for an answer that
-- was written to the chat and never sent back to them.
CREATE TABLE IF NOT EXISTS telegram_pending (
  turn_id       TEXT PRIMARY KEY,
  agent_id      TEXT NOT NULL,
  reply_to      INTEGER,
  asked_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Remember each delivered part so a failed image upload does not repeat the
-- text or images that already arrived. Removing the pending turn clears it.
CREATE TABLE IF NOT EXISTS telegram_deliveries (
  turn_id       TEXT NOT NULL,
  part          TEXT NOT NULL,
  PRIMARY KEY (turn_id, part),
  FOREIGN KEY (turn_id) REFERENCES telegram_pending(turn_id) ON DELETE CASCADE
);

-- Voice notes keep their original destination and chosen engine across a
-- service restart. No API keys or bot tokens are stored in these jobs.
CREATE TABLE IF NOT EXISTS audio_jobs (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_chat TEXT NOT NULL,
  source_message TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  turn_id TEXT NOT NULL UNIQUE,
  settings TEXT NOT NULL,
  media TEXT NOT NULL,
  caption TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT 'queued',
  transcript TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '{}',
  error TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0,
  retry_at INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  UNIQUE (source, source_chat, source_message)
);
CREATE INDEX IF NOT EXISTS idx_audio_jobs_queue ON audio_jobs (state, retry_at);

-- Separate message and pending tables for Discord, rather than a `channel`
-- column on the pair above: a Discord id is a snowflake, which is a string of
-- nineteen digits and not the small integer Telegram counts with, and the two
-- listeners are two services that must not be able to answer each other's
-- questions. Splitting them also meant no migration of a table already in
-- every installation.
CREATE TABLE IF NOT EXISTS discord_messages (
  message_id    TEXT PRIMARY KEY,
  agent_id      TEXT NOT NULL,
  sent_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS discord_pending (
  turn_id       TEXT PRIMARY KEY,
  agent_id      TEXT NOT NULL,
  reply_to      TEXT,
  asked_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schema_version (
  version       INTEGER PRIMARY KEY
);
"""

cKanbanSchema = """
CREATE TABLE IF NOT EXISTS cards (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  body          TEXT NOT NULL DEFAULT '',
  state         TEXT NOT NULL DEFAULT 'todo'
                CHECK (state IN ('todo', 'doing', 'done')),
  owner_agent   TEXT,
  created_by    TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  -- When the owner should be woken up for this card, in UTC. NULL means the
  -- card is only waiting on the board: nobody is woken for it.
  run_at        TEXT,
  -- When the buzzer actually started a run for it. Set once, so a card wakes
  -- its agent once and not on every pass.
  buzzed_at     TEXT,
  -- Who put the card in its owner's hands: "user", or the id of the agent that
  -- assigned it. Not the same as `created_by`: the user can create a card that
  -- the orchestrator later hands to somebody else, and the agent it lands on
  -- is told who gave it the work.
  assigned_by   TEXT,
  -- Which of the two kinds of time this is: 'now' for "run it straight away"
  -- and 'at' for a moment somebody chose. Both end up as a `run_at` in the
  -- past by the time the agent is woken, so the two are indistinguishable
  -- afterwards - and being woken is exactly when the agent is told which it
  -- was. NULL for a card nobody is woken for, and for cards that predate this.
  run_mode      TEXT
);

CREATE INDEX IF NOT EXISTS idx_cards_state ON cards (state, updated_at);

CREATE TABLE IF NOT EXISTS card_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id       INTEGER NOT NULL,
  from_state    TEXT,
  to_state      TEXT NOT NULL,
  agent_id      TEXT NOT NULL,
  note          TEXT NOT NULL DEFAULT '',
  happened_at   TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_card_events_card ON card_events (card_id, happened_at);

-- Deleting a card removes it and its events, so what it was is recorded here
-- first. An agent may delete its own cards, and the user must still be able to
-- see that a card existed and who removed it.
CREATE TABLE IF NOT EXISTS deleted_cards (
  id            INTEGER PRIMARY KEY,
  title         TEXT NOT NULL,
  state         TEXT NOT NULL,
  owner_agent   TEXT,
  created_by    TEXT NOT NULL,
  deleted_by    TEXT NOT NULL,
  deleted_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schema_version (
  version       INTEGER PRIMARY KEY
);
"""


def fOpenConnection(pDbPath):
  """Open a SQLite connection configured for concurrent access."""
  vConnection = sqlite3.connect(pDbPath, timeout=cBusyTimeoutSeconds)
  try:
    vConnection.row_factory = sqlite3.Row
    vConnection.execute("PRAGMA journal_mode = WAL")
    vConnection.execute("PRAGMA foreign_keys = ON")
    vConnection.execute("PRAGMA busy_timeout = %d" % (cBusyTimeoutSeconds * 1000,))
    vConnection.execute("PRAGMA synchronous = NORMAL")
  except sqlite3.Error:
    vConnection.close()
    raise
  return vConnection


def fOpenAppDb():
  """Open the application database."""
  return fOpenConnection(paths.fGetDbPath())


def fOpenKanbanDb():
  """Open the kanban database."""
  return fOpenConnection(paths.fGetKanbanDbPath())


def fReadSetting(pKey, pDefault=""):
  """Return one value from the settings table, or pDefault.

  Never raises. Callers of this are background services deciding how to phrase
  something, and a database that is momentarily locked is not a reason for one
  of them to stop.
  """
  try:
    vConnection = fOpenAppDb()
  except Exception:
    return pDefault
  try:
    vRow = vConnection.execute(
      "SELECT value FROM settings WHERE key = ?", (str(pKey),)).fetchone()
  except Exception:
    return pDefault
  finally:
    vConnection.close()
  return str(vRow["value"]) if vRow and vRow["value"] else pDefault


def fWriteSetting(pKey, pValue):
  """Store one value in the settings table. Never raises, like fReadSetting."""
  try:
    vConnection = fOpenAppDb()
  except Exception:
    return False
  try:
    vConnection.execute(
      "INSERT INTO settings (key, value, updated_at) "
      "VALUES (?, ?, datetime('now')) "
      "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
      "updated_at = excluded.updated_at",
      (str(pKey), str(pValue)),
    )
    vConnection.commit()
  except Exception:
    return False
  finally:
    vConnection.close()
  return True


# Columns added to `admin` after the first release, for the same reason as the
# kanban ones below: CREATE TABLE IF NOT EXISTS leaves an existing table alone,
# so an installation that predates a column has to be altered rather than
# recreated - and this table holds the only account there is.
dAdminColumns = {
  "session_epoch": "INTEGER NOT NULL DEFAULT 0",
}


def fCreateAppSchema():
  """Create the application schema if it does not exist yet, and migrate it."""
  vConnection = fOpenAppDb()
  try:
    vConnection.executescript(cAppSchema)
    fAddMissingColumns(vConnection, "admin", dAdminColumns)
    vConnection.execute(
      "INSERT OR IGNORE INTO schema_version (version) VALUES (1)"
    )
    vConnection.commit()
  finally:
    vConnection.close()


# Columns added to `cards` after the first release. CREATE TABLE IF NOT EXISTS
# leaves an existing table exactly as it is, so a board that predates them has
# to be altered rather than recreated: the cards on it are the user's.
dKanbanCardColumns = {
  "run_at": "TEXT",
  "buzzed_at": "TEXT",
  "assigned_by": "TEXT",
  "run_mode": "TEXT",
}

# Indexes over those columns, created after they exist. They cannot live in the
# schema script above: that script runs before the migration, so on a board
# that predates the columns the index would be created over columns that are
# not there yet - and the error takes the whole application down with it.
lKanbanLateIndexes = [
  # The buzzer's own question, asked every few seconds: which cards are due?
  "CREATE INDEX IF NOT EXISTS idx_cards_due ON cards (run_at, buzzed_at)",
]


def fAddMissingColumns(pConnection, pTableName, pdColumns):
  """Add any of `dColumns` the table does not have yet.

  SQLite has no "ADD COLUMN IF NOT EXISTS", so the table is asked what it has.
  """
  sExisting = {
    vRow["name"] for vRow in
    pConnection.execute("PRAGMA table_info(%s)" % (pTableName,)).fetchall()
  }
  for vName, vType in pdColumns.items():
    if vName in sExisting:
      continue
    pConnection.execute(
      "ALTER TABLE %s ADD COLUMN %s %s" % (pTableName, vName, vType)
    )


def fCreateKanbanSchema():
  """Create the kanban schema if it does not exist yet, and bring it up to date."""
  vConnection = fOpenKanbanDb()
  try:
    vConnection.executescript(cKanbanSchema)
    fAddMissingColumns(vConnection, "cards", dKanbanCardColumns)
    for vStatement in lKanbanLateIndexes:
      vConnection.execute(vStatement)
    vConnection.execute(
      "INSERT OR IGNORE INTO schema_version (version) VALUES (1)"
    )
    vConnection.commit()
  finally:
    vConnection.close()
