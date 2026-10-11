"""Durable X input, selected agent, pagination and delivery reservations."""

import hashlib
import json
import time

from backend.core import db

cExpirySeconds = 3600


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


def fEventKey(pAudience, pEventId):
  return hashlib.sha256((pAudience + ":" + pEventId).encode()).hexdigest()[:32]


def fReadCursor(pAudience):
  lRows = fRows("SELECT * FROM x_poll WHERE audience = ?", (pAudience,))
  return lRows[0] if lRows else None


def fInitializePolling(pAudience, pLastId, pGeneration):
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("INSERT INTO x_poll (audience, generation, first_at, last_id) VALUES (?, ?, ?, ?) "
      "ON CONFLICT(audience) DO UPDATE SET generation = excluded.generation, first_at = excluded.first_at, "
      "last_id = excluded.last_id, scan_last_id = '', page_token = ''",
      (pAudience, pGeneration, int(time.time()), pLastId))
    vConnection.execute("UPDATE x_incoming SET done = 1 WHERE audience = ?", (pAudience,))
    vConnection.commit()
  finally:
    vConnection.close()


def fCommitPoll(pAudience, pInputs, pLastId, pPageToken):
  """Publish input and its pagination checkpoint in the same transaction."""
  vConnection = db.fOpenAppDb()
  try:
    for vKey, dInput in pInputs:
      vConnection.execute("INSERT OR IGNORE INTO x_incoming "
        "(event_key, audience, payload, received_at) VALUES (?, ?, ?, ?)",
        (vKey, pAudience, json.dumps(dInput, ensure_ascii=False), dInput["created_at"]))
    if pPageToken:
      vConnection.execute("UPDATE x_poll SET scan_last_id = ?, page_token = ? WHERE audience = ?",
        (pLastId, pPageToken, pAudience))
    else:
      vConnection.execute("UPDATE x_poll SET last_id = ?, scan_last_id = '', page_token = '' WHERE audience = ?",
        (pLastId, pAudience))
    vConnection.commit()
  finally:
    vConnection.close()


def fListIncoming(pAudience):
  return fRows("SELECT * FROM x_incoming WHERE audience = ? AND done = 0 AND retry_at <= ? "
               "ORDER BY received_at, length(json_extract(payload, '$.event_id')), "
               "json_extract(payload, '$.event_id') LIMIT 50", (pAudience, int(time.time())))


def fCompleteIncoming(pKey):
  fExecute("UPDATE x_incoming SET done = 1 WHERE event_key = ?", (pKey,))


def fDelayIncoming(pKey, pSeconds):
  fExecute("UPDATE x_incoming SET retry_at = ? WHERE event_key = ?", (int(time.time() + pSeconds), pKey))


def fRememberResolution(pKey, pInput, pAudience, pAgentId=""):
  vConnection = db.fOpenAppDb()
  try:
    vUpdated = vConnection.execute("UPDATE x_incoming SET payload = ? WHERE event_key = ? AND audience = ? AND done = 0",
      (json.dumps(pInput, ensure_ascii=False), pKey, pAudience)).rowcount
    if vUpdated != 1:
      raise ValueError("The X message is no longer queued for this conversation.")
    if pAgentId:
      vConnection.execute("INSERT OR REPLACE INTO x_selected (audience, agent_id) VALUES (?, ?)",
        (pAudience, pAgentId))
    vConnection.commit()
  finally:
    vConnection.close()


def fReadSelectedAgent(pAudience):
  lRows = fRows("SELECT agent_id FROM x_selected WHERE audience = ?", (pAudience,))
  return lRows[0]["agent_id"] if lRows else ""


def fAddPending(pTurnId, pAgentId, pAudience):
  fExecute("INSERT OR IGNORE INTO x_pending (turn_id, agent_id, audience, asked_at) VALUES (?, ?, ?, ?)",
    (pTurnId, pAgentId, pAudience, int(time.time())))


def fListPending():
  return fRows("SELECT * FROM x_pending ORDER BY asked_at, rowid")


def fRemovePending(pTurnId):
  fExecute("DELETE FROM x_pending WHERE turn_id = ?", (pTurnId,))


def fDelayPending(pTurnId, pSeconds):
  fExecute("UPDATE x_pending SET retry_at = ? WHERE turn_id = ?", (int(time.time() + pSeconds), pTurnId))


def fListDeliveredParts(pTurnId):
  return {dRow["part"]: dRow["result"] for dRow in fRows(
    "SELECT part, result FROM x_deliveries WHERE turn_id = ?", (pTurnId,))}


def fRememberDeliveredPart(pTurnId, pPart, pResult):
  fExecute("INSERT OR REPLACE INTO x_deliveries (turn_id, part, result) VALUES (?, ?, ?)",
    (pTurnId, pPart, str(pResult)))


def fReserveSend(pAudience, pKey):
  """Return new/sent/uncertain; a crash after POST must not duplicate a DM."""
  vConnection = db.fOpenAppDb()
  try:
    vInserted = vConnection.execute("INSERT OR IGNORE INTO x_outgoing "
      "(audience, delivery_key, created_at) VALUES (?, ?, ?)", (pAudience, pKey, int(time.time()))).rowcount
    vRow = vConnection.execute("SELECT message_id FROM x_outgoing WHERE audience = ? AND delivery_key = ?",
      (pAudience, pKey)).fetchone()
    vConnection.commit()
    return ("new", "") if vInserted else (("sent", vRow["message_id"]) if vRow["message_id"] else ("uncertain", ""))
  finally:
    vConnection.close()


def fConfirmSend(pAudience, pKey, pId):
  fExecute("UPDATE x_outgoing SET message_id = ? WHERE audience = ? AND delivery_key = ?", (pId, pAudience, pKey))


def fReleaseSend(pAudience, pKey):
  fExecute("DELETE FROM x_outgoing WHERE audience = ? AND delivery_key = ? AND message_id = ''", (pAudience, pKey))


def fPrune(pAudience):
  vNow = int(time.time())
  fExecute("UPDATE x_incoming SET done = 1 WHERE audience != ? OR received_at < ?", (pAudience, vNow - cExpirySeconds))
  fExecute("DELETE FROM x_incoming WHERE done = 1 AND received_at < ?", (vNow - 86400,))
  fExecute("DELETE FROM x_selected WHERE audience != ?", (pAudience,))
  fExecute("DELETE FROM x_poll WHERE audience != ?", (pAudience,))
  fExecute("DELETE FROM x_outgoing WHERE created_at < ?", (vNow - 172800,))
