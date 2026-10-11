"""Durable Mattermost input, per-user selection, threads and delivery checkpoints."""

import hashlib
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
  """Commit input before advancing the polling checkpoint; deduplicate by post ID."""
  return fExecute(
    "INSERT OR IGNORE INTO mattermost_incoming (event_key, audience, payload, received_at) VALUES (?, ?, ?, ?)",
    (pEventKey, pAudience, json.dumps(pPayload, ensure_ascii=False), int(time.time()))) == 1


def fListIncoming(pAudience):
  return fRows("SELECT * FROM mattermost_incoming WHERE audience = ? AND done = 0 "
               "AND retry_at <= ? ORDER BY received_at, rowid LIMIT 50",
               (pAudience, int(time.time())))


def fCompleteIncoming(pEventKey):
  fExecute("UPDATE mattermost_incoming SET done = 1 WHERE event_key = ?", (pEventKey,))


def fDelayIncoming(pEventKey, pSeconds):
  fExecute("UPDATE mattermost_incoming SET retry_at = ? WHERE event_key = ?",
            (int(time.time() + max(1, pSeconds)), pEventKey))


def fRememberResolution(pEventKey, pInput, pAudience, pAgentId=""):
  """Freeze routing or a command reply before any external side effect."""
  vConnection = db.fOpenAppDb()
  try:
    vUpdated = vConnection.execute(
      "UPDATE mattermost_incoming SET payload = ? WHERE event_key = ? AND audience = ? AND done = 0",
      (json.dumps(pInput, ensure_ascii=False), pEventKey, pAudience)).rowcount
    if vUpdated != 1:
      raise ValueError("The Mattermost input is no longer queued for this audience.")
    if pAgentId:
      vConnection.execute(
        "INSERT OR REPLACE INTO mattermost_selected (audience, user_id, agent_id) VALUES (?, ?, ?)",
        (pAudience, pInput["user"], pAgentId))
      if pInput.get("root_id"):
        vConnection.execute(
          "INSERT OR REPLACE INTO mattermost_messages (audience, message_id, agent_id) VALUES (?, ?, ?)",
          (pAudience, pInput["root_id"], pAgentId))
        vConnection.execute("DELETE FROM mattermost_messages WHERE rowid NOT IN "
                            "(SELECT rowid FROM mattermost_messages ORDER BY rowid DESC LIMIT 1000)")
    vConnection.commit()
  finally:
    vConnection.close()


def fSelectAgent(pAudience, pUserId, pAgentId):
  fExecute("INSERT OR REPLACE INTO mattermost_selected (audience, user_id, agent_id) VALUES (?, ?, ?)",
            (pAudience, pUserId, pAgentId))


def fReadSelectedAgent(pAudience, pUserId):
  lRows = fRows("SELECT agent_id FROM mattermost_selected WHERE audience = ? AND user_id = ?",
                (pAudience, pUserId))
  return lRows[0]["agent_id"] if lRows else ""


def fRememberMessage(pAudience, pMessageId, pAgentId):
  if not pMessageId:
    return
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute(
      "INSERT OR REPLACE INTO mattermost_messages (audience, message_id, agent_id) VALUES (?, ?, ?)",
      (pAudience, str(pMessageId), str(pAgentId)))
    vConnection.execute("DELETE FROM mattermost_messages WHERE rowid NOT IN "
                         "(SELECT rowid FROM mattermost_messages ORDER BY rowid DESC LIMIT 1000)")
    vConnection.commit()
  finally:
    vConnection.close()


def fFindAgentForMessage(pAudience, pMessageId):
  lRows = fRows("SELECT agent_id FROM mattermost_messages WHERE audience = ? AND message_id = ?",
                (pAudience, str(pMessageId or "")))
  return lRows[0]["agent_id"] if lRows else ""


def fAddPending(pTurnId, pAgentId, pRootId, pAudience):
  # A repeated input must not replace its existing delivery checkpoints.
  fExecute("INSERT OR IGNORE INTO mattermost_pending "
            "(turn_id, agent_id, root_id, audience, asked_at) VALUES (?, ?, ?, ?, ?)",
            (pTurnId, pAgentId, pRootId, pAudience, int(time.time())))


def fListPending():
  return fRows("SELECT * FROM mattermost_pending ORDER BY asked_at, rowid")


def fRemovePending(pTurnId):
  fExecute("DELETE FROM mattermost_pending WHERE turn_id = ?", (pTurnId,))


def fDelayPending(pTurnId, pSeconds):
  fExecute("UPDATE mattermost_pending SET retry_at = ? WHERE turn_id = ?",
            (int(time.time() + max(1, pSeconds)), pTurnId))


def fSetPendingThread(pTurnId, pRootId):
  fExecute("UPDATE mattermost_pending SET root_id = ? WHERE turn_id = ?", (pRootId, pTurnId))


def fListDeliveredParts(pTurnId):
  return {vRow["part"]: vRow["result"] for vRow in fRows(
    "SELECT part, result FROM mattermost_deliveries WHERE turn_id = ?", (pTurnId,))}


def fRememberDeliveredPart(pTurnId, pPart, pResult):
  fExecute("INSERT OR REPLACE INTO mattermost_deliveries (turn_id, part, result) VALUES (?, ?, ?)",
            (pTurnId, pPart, str(pResult)))


def fPrune(pAudience):
  vNow = int(time.time())
  fExecute("UPDATE mattermost_incoming SET done = 1 WHERE audience != ? OR received_at < ?",
            (pAudience, vNow - cExpirySeconds))
  fExecute("DELETE FROM mattermost_incoming WHERE done = 1 AND received_at < ?",
            (vNow - cRememberEventsSeconds,))
  fExecute("DELETE FROM mattermost_selected WHERE audience != ?", (pAudience,))
  fExecute("DELETE FROM mattermost_messages WHERE audience != ?", (pAudience,))
  fExecute("DELETE FROM mattermost_poll WHERE audience != ?", (pAudience,))


def fEventKey(pAudience, pPostId):
  return hashlib.sha256((pAudience + ":" + pPostId).encode()).hexdigest()[:32]


def fReadCursor(pAudience):
  lRows = fRows("SELECT * FROM mattermost_poll WHERE audience = ?", (pAudience,))
  return lRows[0] if lRows else None


def fInitializePolling(pAudience, pPosts, pGeneration=""):
  """Skip the startup snapshot, retaining its IDs for timestamp overlap."""
  vAt = max((int(dPost.get("create_at") or 0) for dPost in pPosts), default=0)
  vConnection = db.fOpenAppDb()
  try:
    vChanged = vConnection.execute(
      "INSERT INTO mattermost_poll (audience, generation, first_at, last_at) VALUES (?, ?, ?, ?) "
      "ON CONFLICT(audience) DO UPDATE SET generation = excluded.generation, "
      "first_at = excluded.first_at, last_at = excluded.last_at "
      "WHERE mattermost_poll.generation != excluded.generation",
      (pAudience, pGeneration, vAt, vAt)).rowcount
    if vChanged:
      for dPost in pPosts:
        vConnection.execute("INSERT OR IGNORE INTO mattermost_incoming "
          "(event_key, audience, payload, received_at, done) VALUES (?, ?, ?, ?, 1)",
          (fEventKey(pAudience, dPost["id"]), pAudience, "{}", int(time.time())))
    vConnection.commit()
  finally:
    vConnection.close()


def fCommitPoll(pAudience, pInputs, pLastAt):
  """A failed commit advances neither input nor the server timestamp."""
  vConnection = db.fOpenAppDb()
  try:
    for vKey, dInput in pInputs:
      vConnection.execute("INSERT OR IGNORE INTO mattermost_incoming "
        "(event_key, audience, payload, received_at) VALUES (?, ?, ?, ?)",
        (vKey, pAudience, json.dumps(dInput, ensure_ascii=False), int(dInput["create_at"] / 1000)))
    vConnection.execute("UPDATE mattermost_poll SET last_at = MAX(last_at, ?) WHERE audience = ?",
      (int(pLastAt), pAudience))
    vConnection.commit()
  finally:
    vConnection.close()
