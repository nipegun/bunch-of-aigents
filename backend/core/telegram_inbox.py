"""What a Telegram conversation needs to remember between messages.

Two small tables in the application database, both written and read by
processes running as `boa` - the agent API when an agent sends something, and
the listener when somebody answers.

  telegram_messages : which agent said what. A person replying to a message in
                      Telegram is replying to the agent that sent it, and the
                      id Telegram gave that message is the only thing tying the
                      two together.

  telegram_pending  : a question asked over Telegram that the agent has not
                      finished answering, so the answer can be sent back when
                      the run closes the turn.

The second one is on disk rather than in the listener's memory on purpose. The
service restarts on every update, and a person who asked something twenty
seconds earlier should not be left waiting for an answer that was written into
the chat and never came back to them.

Neither table is history. The first is pruned to the last few hundred rows -
nobody replies to a message from last month - and the second empties itself as
runs finish.
"""

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


# Which agent Telegram messages go to when nothing in them says otherwise.
# In the settings table rather than in memory for the usual reason: the
# service restarts on every update, and somebody who picked an agent a minute
# ago has not changed their mind about who they are talking to.
cSelectedAgentSetting = "telegram_selected_agent"


def fSetSelectedAgent(pAgentId):
  """Remember who the conversation is with."""
  return db.fWriteSetting(cSelectedAgentSetting, str(pAgentId or ""))


def fGetSelectedAgent():
  """Return who the conversation is with, or "" if nobody has been picked."""
  return db.fReadSetting(cSelectedAgentSetting, "")


def fRememberMessage(pMessageId, pAgentId):
  """Record that this Telegram message came from this agent."""
  if not pMessageId:
    return False
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO telegram_messages (message_id, agent_id) "
      "VALUES (?, ?)",
      (int(pMessageId), str(pAgentId)),
    )
    # Keep the newest, drop the rest. Done here rather than on a timer because
    # this is the only thing that makes the table grow.
    vConnection.execute(
      "DELETE FROM telegram_messages WHERE message_id NOT IN ("
      "  SELECT message_id FROM telegram_messages "
      "  ORDER BY message_id DESC LIMIT ?)",
      (cMaxRememberedMessages,),
    )
    vConnection.commit()
  finally:
    vConnection.close()
  return True


def fFindAgentForMessage(pMessageId):
  """Return the agent that sent this Telegram message, or "" if unknown."""
  if not pMessageId:
    return ""
  vConnection = db.fOpenAppDb()
  try:
    vRow = vConnection.execute(
      "SELECT agent_id FROM telegram_messages WHERE message_id = ?",
      (int(pMessageId),),
    ).fetchone()
  finally:
    vConnection.close()
  return str(vRow["agent_id"]) if vRow else ""


def fAddPending(pTurnId, pAgentId, pReplyToMessageId=None):
  """Record a question asked over Telegram that is still being answered."""
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO telegram_pending "
      "(turn_id, agent_id, reply_to) VALUES (?, ?, ?)",
      (str(pTurnId), str(pAgentId),
       int(pReplyToMessageId) if pReplyToMessageId else None),
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
      "SELECT turn_id, agent_id, reply_to, asked_at FROM telegram_pending "
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
      "DELETE FROM telegram_pending WHERE turn_id = ?", (str(pTurnId),)
    )
    vConnection.commit()
  finally:
    vConnection.close()
  return True


def fIsExpired(dPending, pNow=None):
  """Return whether this question has been waiting longer than it should.

  A run that died without closing its turn leaves a row nothing will ever come
  back for. Unparseable timestamps count as expired: a row whose age cannot be
  read is a row that would otherwise be asked about for ever.
  """
  vAskedAt = str(dPending.get("asked_at") or "")
  if not vAskedAt:
    return True
  try:
    vAskedSeconds = time.mktime(time.strptime(vAskedAt, "%Y-%m-%d %H:%M:%S"))
  except (ValueError, TypeError):
    return True
  vNow = pNow if pNow is not None else time.mktime(time.gmtime())
  return (vNow - vAskedSeconds) > cPendingExpirySeconds
