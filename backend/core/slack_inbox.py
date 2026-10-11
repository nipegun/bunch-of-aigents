"""Durable Slack input, per-user selection, threads and delivery checkpoints."""

import json
import time

from backend.core import db

cExpirySeconds = 3600
cRememberEventsSeconds = 86400


def fExecute(pSql, pValues=()):
  vConnection = db.fOpenAppDb()
  try:
    vCursor = vConnection.execute(pSql, pValues)
    vConnection.commit()
    return vCursor.rowcount
  finally:
    vConnection.close()


def fRows(pSql, pValues=()):
  vConnection = db.fOpenAppDb()
  try:
    return [dict(vRow) for vRow in vConnection.execute(pSql, pValues).fetchall()]
  finally:
    vConnection.close()


def fQueue(pEventKey, pAudience, pPayload):
  """Commit before ACK; repeated deliveries share the same primary key."""
  return fExecute(
    "INSERT OR IGNORE INTO slack_incoming (event_key, audience, payload, received_at) VALUES (?, ?, ?, ?)",
    (pEventKey, pAudience, json.dumps(pPayload, ensure_ascii=False), int(time.time()))) == 1


def fListIncoming(pAudience):
  return fRows("SELECT * FROM slack_incoming WHERE audience = ? AND done = 0 "
               "AND retry_at <= ? ORDER BY received_at, rowid LIMIT 50",
               (pAudience, int(time.time())))


def fCompleteIncoming(pEventKey):
  fExecute("UPDATE slack_incoming SET done = 1 WHERE event_key = ?", (pEventKey,))


def fDelayIncoming(pEventKey, pSeconds):
  fExecute("UPDATE slack_incoming SET retry_at = ? WHERE event_key = ?",
            (int(time.time() + max(1, pSeconds)), pEventKey))


def fRememberResolution(pEventKey, pInput, pAudience, pAgentId=""):
  """Freeze routing or a command reply before any external side effect."""
  vConnection = db.fOpenAppDb()
  try:
    vUpdated = vConnection.execute(
      "UPDATE slack_incoming SET payload = ? WHERE event_key = ? AND audience = ? AND done = 0",
      (json.dumps(pInput, ensure_ascii=False), pEventKey, pAudience)).rowcount
    if vUpdated != 1:
      raise ValueError("The Slack input is no longer queued for this audience.")
    if pAgentId:
      vConnection.execute(
        "INSERT OR REPLACE INTO slack_selected (audience, user_id, agent_id) VALUES (?, ?, ?)",
        (pAudience, pInput["user"], pAgentId))
      if pInput.get("thread_ts"):
        vConnection.execute(
          "INSERT OR REPLACE INTO slack_messages (audience, message_id, agent_id) VALUES (?, ?, ?)",
          (pAudience, pInput["thread_ts"], pAgentId))
        vConnection.execute("DELETE FROM slack_messages WHERE rowid NOT IN "
                            "(SELECT rowid FROM slack_messages ORDER BY rowid DESC LIMIT 1000)")
    vConnection.commit()
  finally:
    vConnection.close()


def fSelectAgent(pAudience, pUserId, pAgentId):
  fExecute("INSERT OR REPLACE INTO slack_selected (audience, user_id, agent_id) VALUES (?, ?, ?)",
            (pAudience, pUserId, pAgentId))


def fReadSelectedAgent(pAudience, pUserId):
  lRows = fRows("SELECT agent_id FROM slack_selected WHERE audience = ? AND user_id = ?",
                (pAudience, pUserId))
  return lRows[0]["agent_id"] if lRows else ""


def fRememberMessage(pAudience, pMessageId, pAgentId):
  if not pMessageId:
    return
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO slack_messages (audience, message_id, agent_id) VALUES (?, ?, ?)",
      (pAudience, str(pMessageId), str(pAgentId)))
    vConnection.execute("DELETE FROM slack_messages WHERE rowid NOT IN "
                         "(SELECT rowid FROM slack_messages ORDER BY rowid DESC LIMIT 1000)")
    vConnection.commit()
  finally:
    vConnection.close()


def fFindAgentForMessage(pAudience, pMessageId):
  lRows = fRows("SELECT agent_id FROM slack_messages WHERE audience = ? AND message_id = ?",
                (pAudience, str(pMessageId or "")))
  return lRows[0]["agent_id"] if lRows else ""


def fAddPending(pTurnId, pAgentId, pThreadTs, pAudience):
  # A repeated input must not replace its existing delivery checkpoints.
  fExecute("INSERT OR IGNORE INTO slack_pending "
            "(turn_id, agent_id, thread_ts, audience, asked_at) VALUES (?, ?, ?, ?, ?)",
            (pTurnId, pAgentId, pThreadTs, pAudience, int(time.time())))


def fListPending():
  return fRows("SELECT * FROM slack_pending ORDER BY asked_at, rowid")


def fRemovePending(pTurnId):
  fExecute("DELETE FROM slack_pending WHERE turn_id = ?", (pTurnId,))


def fDelayPending(pTurnId, pSeconds):
  fExecute("UPDATE slack_pending SET retry_at = ? WHERE turn_id = ?",
            (int(time.time() + max(1, pSeconds)), pTurnId))


def fSetPendingThread(pTurnId, pThreadTs):
  fExecute("UPDATE slack_pending SET thread_ts = ? WHERE turn_id = ?", (pThreadTs, pTurnId))


def fListDeliveredParts(pTurnId):
  return {vRow["part"]: vRow["result"] for vRow in fRows(
    "SELECT part, result FROM slack_deliveries WHERE turn_id = ?", (pTurnId,))}


def fRememberDeliveredPart(pTurnId, pPart, pResult):
  fExecute("INSERT OR REPLACE INTO slack_deliveries (turn_id, part, result) VALUES (?, ?, ?)",
            (pTurnId, pPart, str(pResult)))


def fPrune(pAudience):
  vNow = int(time.time())
  fExecute("UPDATE slack_incoming SET done = 1 WHERE audience != ? OR received_at < ?",
            (pAudience, vNow - cExpirySeconds))
  fExecute("DELETE FROM slack_incoming WHERE done = 1 AND received_at < ?",
            (vNow - cRememberEventsSeconds,))
  fExecute("DELETE FROM slack_selected WHERE audience != ?", (pAudience,))
