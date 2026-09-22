"""What a Discord conversation needs to remember between messages.

The Telegram half of this is `telegram_inbox`, and the two are deliberately
separate rather than one module with a channel column. Three reasons:

  - A Discord id is a snowflake: nineteen digits that arrive as a string and
    are handed back as a string. Telegram counts with small integers. Sharing
    a table would mean one of the two being converted on every read.
  - They are two services. A pending question belongs to the listener that
    took it, and a shared table is a way for one of them to answer the
    other's.
  - The Telegram tables are already in every installation. Adding two beside
    them needs no migration of anything anybody has.

  discord_messages : which agent said what. Somebody replying to a message in
                     Discord is replying to the agent that sent it, and the id
                     Discord gave that message is the only thing tying the two
                     together. An answer sent in several parts records every
                     part, because a person replies to whichever one is on
                     their screen.

  discord_pending  : a question asked over Discord that the agent has not
                     finished answering, so the answer can be sent back when
                     the run closes the turn. On disk rather than in the
                     listener's memory: the service restarts on every update,
                     and somebody who asked a question twenty seconds earlier
                     should not lose the answer because of that.

Neither table is history. The first is pruned to the last few hundred rows and
the second empties itself as runs finish.
"""

import calendar
import time

from backend.core import db

# How many sent messages stay routable. A reply to something older than this
# falls back to the ordinary rules, which is a fair trade for a table that
# never grows.
cMaxRememberedMessages = 500

# When a pending question is given up on. The run has ceilings of its own - the
# longest is `timeout_seconds` - so a turn still open long after that is one
# whose run died without closing it, and waiting for it for ever would mean the
# listener asking the executor about it on every pass until the end of time.
cPendingExpirySeconds = 3600

# Which agent Discord messages go to when nothing in them says otherwise. In
# the settings table rather than in memory for the usual reason: the service
# restarts on every update, and somebody who picked an agent a minute ago has
# not changed their mind about who they are talking to.
cSelectedAgentSetting = "discord_selected_agent"


def fSetSelectedAgent(pAgentId):
  """Remember who the conversation is with."""
  return db.fWriteSetting(cSelectedAgentSetting, str(pAgentId or ""))


def fGetSelectedAgent():
  """Return who the conversation is with, or "" if nobody has been picked."""
  return db.fReadSetting(cSelectedAgentSetting, "")


def fRememberMessage(pMessageId, pAgentId):
  """Record that this Discord message came from this agent."""
  if not pMessageId:
    return False
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO discord_messages (message_id, agent_id) "
      "VALUES (?, ?)",
      (str(pMessageId), str(pAgentId)),
    )
    # Keep the newest, drop the rest. By insertion order rather than by id:
    # a snowflake sorts correctly as a string today and would stop doing so
    # the day one of them is twenty digits long.
    vConnection.execute(
      "DELETE FROM discord_messages WHERE rowid NOT IN ("
      "  SELECT rowid FROM discord_messages ORDER BY rowid DESC LIMIT ?)",
      (cMaxRememberedMessages,),
    )
    vConnection.commit()
  finally:
    vConnection.close()
  return True


def fFindAgentForMessage(pMessageId):
  """Return the agent that sent this Discord message, or "" if unknown."""
  if not pMessageId:
    return ""
  vConnection = db.fOpenAppDb()
  try:
    vRow = vConnection.execute(
      "SELECT agent_id FROM discord_messages WHERE message_id = ?",
      (str(pMessageId),),
    ).fetchone()
  finally:
    vConnection.close()
  return str(vRow["agent_id"]) if vRow else ""


def fAddPending(pTurnId, pAgentId, pReplyToMessageId=None):
  """Record a question asked over Discord that is still being answered."""
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO discord_pending "
      "(turn_id, agent_id, reply_to) VALUES (?, ?, ?)",
      (str(pTurnId), str(pAgentId),
       str(pReplyToMessageId) if pReplyToMessageId else None),
    )
    vConnection.commit()
  finally:
    vConnection.close()
  return True


def fListPending():
  """Return every question still waiting for an answer, oldest first."""
  vConnection = db.fOpenAppDb()
  try:
    lRows = vConnection.execute(
      "SELECT turn_id, agent_id, reply_to, asked_at FROM discord_pending "
      "ORDER BY asked_at, turn_id"
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]


def fRemovePending(pTurnId):
  """Forget one question, because it has been answered or given up on."""
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "DELETE FROM discord_pending WHERE turn_id = ?", (str(pTurnId),)
    )
    vConnection.commit()
  finally:
    vConnection.close()
  return True


def fIsExpired(pdPending, pNow=None):
  """Return whether this question has been waiting longer than it should.

  A run that died without closing its turn leaves a row nothing will ever come
  back for. Unparseable timestamps count as expired: a row whose age cannot be
  read is a row that would otherwise be asked about for ever.
  """
  vAskedAt = str(pdPending.get("asked_at") or "")
  if not vAskedAt:
    return True
  try:
    vAskedSeconds = calendar.timegm(time.strptime(vAskedAt, "%Y-%m-%d %H:%M:%S"))
  except (ValueError, TypeError):
    return True
  # SQLite timestamps and the current instant must use the same UTC clock.
  vNow = pNow if pNow is not None else time.time()
  return (vNow - vAskedSeconds) > cPendingExpirySeconds
