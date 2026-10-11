"""Posts on the X profile, each one approved by the person in the private conversation.

An agent with x.post does not publish. It asks: the request is stored with the
exact text, bound to the authorized account and to the person BoA talks to
(the audience), and that person receives the text in a direct message with a
one-time code. Only `!post <code>`, sent by that person in that conversation
within the hour, publishes it; `!discard <code>` drops it. Whatever the model
decides, a public post needs a human who said yes to that text.

It used to be an argument of channel.write, x_destination=post, guarded by a
sentence in the tool's description asking the model to post only when it was
told to. A page the agent read, or a message in the conversation, could tell it
otherwise, and nothing between the model and the profile asked anybody.

The code is not a secret from the agent - it is in the request it made - and
does not need to be: only messages from the configured interlocutor reach the
listener (x_listener.fExtractInput), and the agent writes from the account,
never as that person.
"""

import secrets
import time

from backend.core import channels, db, x_api, x_inbox, x_texts

# No 0/O or 1/I: the code is read on a phone and typed back by hand.
cCodeAlphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
cCodeLength = 8
cExpirySeconds = 3600
# Requests waiting at once. An agent asking again and again fills the
# conversation; past this many it is told to wait for an answer.
cMaxPending = 10
# Below the 10,000 characters of a direct message, so that the request -
# the text and the lines around it - still fits in one.
cMaxPostLength = 9000
cKeepSeconds = 172800


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


def fAudience(pConfig):
  return channels.fAudienceKey(channels.cChannelX, pConfig)


def fNewCode():
  return "".join(secrets.choice(cCodeAlphabet) for _vIndex in range(cCodeLength))


def fNormalizeCode(pCode):
  """The code as stored: spaces and dashes a phone may add are ignored."""
  return "".join(str(pCode or "").split()).replace("-", "").upper()[:64]


def fPrune():
  vNow = int(time.time())
  fExecute("UPDATE x_post_requests SET state = 'expired' WHERE state = 'pending' AND created_at < ?",
    (vNow - cExpirySeconds,))
  fExecute("DELETE FROM x_post_requests WHERE created_at < ?", (vNow - cKeepSeconds,))


def fCheckCanRequest(pConfig):
  """Raise ChannelRejected unless a post could be approved and published."""
  x_api.fCheckConfig(pConfig)
  if not pConfig.get("allow_posts"):
    raise channels.ChannelRejected("Publishing on X is disabled. Enable it in Settings → Channels first.")
  if "tweet.write" not in (pConfig.get("scopes") or []):
    raise channels.ChannelRejected("Authorize X again after enabling profile posts.")
  if not pConfig.get("listen"):
    raise channels.ChannelRejected(
      "X reception is off, so the approval could not arrive. Turn on reception "
      "in Settings → Channels → X before asking to publish.")


def fRequestPost(pAgentId, pAgentName, pText):
  """Store one post request and send its approval message to the person."""
  vText = str(pText or "").strip()
  if not vText:
    raise channels.ChannelRejected("There is nothing to publish: the text is empty.")
  if len(vText) > cMaxPostLength:
    raise channels.ChannelRejected(
      "The requested X post is too long (limit is %d characters). Shorten it." % (cMaxPostLength,))
  dConfig = channels.fReadChannelConfig(channels.cChannelX)
  fCheckCanRequest(dConfig)
  vAudience = fAudience(dConfig)
  fPrune()
  lPending = fRows("SELECT COUNT(*) AS total FROM x_post_requests WHERE audience = ? AND state = 'pending'",
    (vAudience,))
  if lPending and lPending[0]["total"] >= cMaxPending:
    raise channels.ChannelRejected(
      "%d posts are already waiting for approval. Wait for the person to answer them." % (cMaxPending,))

  vCode = fNewCode()
  fExecute("INSERT INTO x_post_requests (code, audience, agent_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
    (vCode, vAudience, str(pAgentId), vText, int(time.time())))
  vMessage = x_texts.fText("postRequest", name=str(pAgentName), account=str(dConfig.get("account_username") or ""),
    text=vText, code=vCode, minutes=cExpirySeconds // 60)
  vKey = "post-request:" + vCode
  x_inbox.fReserveSend(vAudience, vKey)
  try:
    vId = x_api.fSendDm(dConfig, vMessage)
  except x_api.XDeliveryUncertain:
    # The message may have arrived, so the request stays: the person can still
    # approve what they received.
    raise
  except channels.ChannelError:
    x_inbox.fReleaseSend(vAudience, vKey)
    fExecute("DELETE FROM x_post_requests WHERE code = ?", (vCode,))
    raise
  x_inbox.fConfirmSend(vAudience, vKey, vId)
  return {"requested": True, "expires_in_minutes": cExpirySeconds // 60}


def fFindRequest(pConfig, pCode):
  lRows = fRows("SELECT * FROM x_post_requests WHERE code = ? AND audience = ?",
    (fNormalizeCode(pCode), fAudience(pConfig)))
  return lRows[0] if lRows else None


def fApprove(pConfig, pCode):
  """Publish the text a code stands for. Returns the sentence to answer with."""
  fPrune()
  dRequest = fFindRequest(pConfig, pCode)
  if dRequest is None or dRequest["state"] in ("discarded", "expired"):
    return x_texts.fText("postUnknownCode", minutes=cExpirySeconds // 60)
  if dRequest["state"] == "published":
    return x_texts.fText("postPublished", url="https://x.com/i/status/" + dRequest["post_id"])
  if dRequest["state"] != "pending":
    # Publishing or uncertain: a POST that may have gone through is never
    # sent twice.
    return x_texts.fText("postUncertain")
  vClaimed = fExecute("UPDATE x_post_requests SET state = 'publishing' WHERE code = ? AND audience = ? "
    "AND state = 'pending'", (dRequest["code"], dRequest["audience"]))
  if vClaimed != 1:
    return x_texts.fText("postUnknownCode", minutes=cExpirySeconds // 60)
  try:
    dResult = x_api.fPublishPost(pConfig, dRequest["text"])
  except x_api.XDeliveryUncertain:
    fExecute("UPDATE x_post_requests SET state = 'uncertain' WHERE code = ?", (dRequest["code"],))
    return x_texts.fText("postUncertain")
  except x_api.XRetryLater:
    # A rate limit: nothing was published. The same command is tried again.
    fExecute("UPDATE x_post_requests SET state = 'pending' WHERE code = ?", (dRequest["code"],))
    raise
  except channels.ChannelError as vError:
    fExecute("UPDATE x_post_requests SET state = 'pending' WHERE code = ?", (dRequest["code"],))
    return x_texts.fText("postFailed", reason=str(vError))
  fExecute("UPDATE x_post_requests SET state = 'published', post_id = ? WHERE code = ?",
    (dResult["message_id"], dRequest["code"]))
  return x_texts.fText("postPublished", url=dResult["url"])


def fDiscard(pConfig, pCode):
  """Drop the request a code stands for. Returns the sentence to answer with."""
  fPrune()
  vDropped = fExecute("UPDATE x_post_requests SET state = 'discarded' WHERE code = ? AND audience = ? "
    "AND state = 'pending'", (fNormalizeCode(pCode), fAudience(pConfig)))
  if not vDropped:
    return x_texts.fText("postUnknownCode", minutes=cExpirySeconds // 60)
  return x_texts.fText("postDiscarded")
