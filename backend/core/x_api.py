"""X user-context API: private conversations, and posts approved one by one (x_posts)."""

from datetime import datetime
import re
import time

import requests

from backend.core import attachments, channels, x_auth

cApiUrl = "https://api.x.com/2"
cPollSeconds = 65
cMaxDmLength = 10000
cMaxImageBytes = 5 * 1024 * 1024
dRetryUntil = {}


class XRetryLater(channels.ChannelError):
  def __init__(self, pMessage, pSeconds=65):
    super().__init__(pMessage)
    self.vRetryAfter = max(1, pSeconds)


class XDeliveryUncertain(channels.ChannelRejected):
  """The write may have succeeded. Retrying it could send a duplicate."""


def fId(pValue, pLabel="ID"):
  vValue = str(pValue or "")
  if not re.fullmatch(r"[0-9]{1,19}", vValue):
    raise channels.ChannelRejected("X requires a numeric %s." % pLabel)
  return vValue


def fCall(pConfig, pMethod, pPath, **pdArguments):
  vKey = (pConfig.get("auth_generation"), pMethod, re.sub(r"/[0-9]+", "/:id", pPath))
  vUntil = dRetryUntil.get(vKey, 0)
  if vUntil > time.monotonic():
    raise XRetryLater("Waiting for X's rate-limit window.", vUntil - time.monotonic())
  vToken = x_auth.fAccessToken(pConfig)
  try:
    vResponse = requests.request(pMethod, cApiUrl + pPath,
      headers={"Authorization": "Bearer " + vToken}, timeout=30,
      allow_redirects=False, **pdArguments)
  except requests.RequestException:
    if pMethod != "GET":
      raise XDeliveryUncertain("X did not confirm the send. Check X before sending it again; BoA will not automatically repeat it.") from None
    raise XRetryLater("Cannot reach X. Reading will resume later.") from None
  if vResponse.status_code == 429:
    try:
      vWait = max(float(vResponse.headers.get("Retry-After", 0)),
        float(vResponse.headers.get("x-rate-limit-reset", 0)) - time.time() + 2, cPollSeconds)
    except (ValueError, TypeError):
      vWait = 900
    vWait = min(vWait, 86400)
    dRetryUntil[vKey] = time.monotonic() + vWait
    raise XRetryLater("X's rate limit was reached; waiting for the next window.", vWait)
  if vResponse.status_code >= 500:
    if pMethod != "GET":
      raise XDeliveryUncertain("X returned a server error without confirming the send. Check X before sending it again.")
    raise XRetryLater("X is temporarily unavailable.")
  if vResponse.status_code not in (200, 201):
    dReasons = {401: "Authorize X again in Settings → Channels.",
      402: "Check your API credits and spending limit in the X Developer Console.",
      403: "Check the granted permissions and whether the recipient accepts direct messages.",
      404: "Check the recipient ID and access to this conversation."}
    raise channels.ChannelRejected("X refused the request (HTTP %s). %s" % (
      vResponse.status_code, dReasons.get(vResponse.status_code, "Check the message and X channel settings.")))
  try:
    dBody = vResponse.json()
    if not isinstance(dBody, dict):
      raise ValueError()
    return dBody
  except (ValueError, TypeError):
    if pMethod != "GET":
      raise XDeliveryUncertain("X returned an unreadable send confirmation. Check X before sending it again.") from None
    raise XRetryLater("X returned an unreadable response.") from None


def fRecipient(pConfig):
  vRecipient = fId(pConfig.get("recipient_id"), "recipient_id")
  if vRecipient == str(pConfig.get("account_id")):
    raise channels.ChannelRejected("X direct messages require a different recipient account.")
  return vRecipient


def fCheckConfig(pConfig):
  fRecipient(pConfig)
  fId(pConfig.get("account_id"), "authorized account ID")
  if not pConfig.get("auth_generation"):
    raise channels.ChannelRejected("Authorize X in Settings → Channels first.")
  if not set(x_auth.lBaseScopes).issubset(set(pConfig.get("scopes") or [])):
    raise channels.ChannelRejected("Authorize X again to grant direct-message and image access.")


def fReadEvents(pConfig, pPaginationToken=""):
  dParams = {"max_results": 100, "event_types": "MessageCreate",
    "dm_event.fields": "id,text,created_at,dm_conversation_id,event_type",
    "expansions": "sender_id"}
  if pPaginationToken:
    dParams["pagination_token"] = pPaginationToken
  dBody = fCall(pConfig, "GET", "/dm_conversations/with/" + fRecipient(pConfig) + "/dm_events", params=dParams)
  lEvents = dBody.get("data", [])
  if not isinstance(lEvents, list) or dBody.get("errors"):
    raise XRetryLater("X did not return a complete direct-message page.")
  for dEvent in lEvents:
    if not isinstance(dEvent, dict):
      raise XRetryLater("X returned an invalid direct-message event.")
    fId(dEvent.get("id"), "event ID")
  return lEvents, str((dBody.get("meta") or {}).get("next_token") or "")


def fCreatedAt(pEvent):
  try:
    vDate = datetime.fromisoformat(str(pEvent.get("created_at") or "").replace("Z", "+00:00"))
    if vDate.tzinfo is None:
      raise ValueError()
    return int(vDate.timestamp())
  except (ValueError, TypeError, OverflowError):
    raise XRetryLater("X did not provide a valid timestamp for a direct message.") from None


def fSendDm(pConfig, pText, pMediaId=""):
  dBody = {}
  if pText:
    if len(pText) > cMaxDmLength:
      raise channels.ChannelRejected("An X direct message cannot exceed 10,000 characters.")
    dBody["text"] = pText
  if pMediaId:
    dBody["attachments"] = [{"media_id": fId(pMediaId, "media ID")}]
  if not dBody:
    raise channels.ChannelRejected("The X direct message is empty.")
  dResult = fCall(pConfig, "POST", "/dm_conversations/with/" + fRecipient(pConfig) + "/messages", json=dBody)
  try:
    return fId(dResult["data"]["dm_event_id"], "sent event ID")
  except (KeyError, TypeError, channels.ChannelError):
    raise XDeliveryUncertain("X did not return a direct-message ID. Check X before sending it again.") from None


def fUploadImage(pConfig, pPng, pName):
  try:
    attachments.fReadPngDimensions(pPng)
  except ValueError:
    raise channels.ChannelRejected("X requires a valid PNG image.") from None
  if len(pPng) > cMaxImageBytes:
    raise channels.ChannelRejected("X images must be no larger than 5 MiB.")
  dBody = fCall(pConfig, "POST", "/media/upload",
    data={"media_category": "dm_image"}, files={"media": (pName, pPng, "image/png")})
  try:
    dMedia = dBody["data"]
    if dMedia.get("processing_info", {}).get("state") not in (None, "succeeded"):
      raise ValueError()
    return fId(dMedia["id"], "media ID")
  except (KeyError, TypeError, ValueError):
    raise channels.ChannelRejected("X did not finish processing the PNG upload.") from None


def fPublishPost(pConfig, pText):
  if not pConfig.get("allow_posts"):
    raise channels.ChannelRejected("Publishing on X is disabled. Enable it in Settings → Channels first.")
  if "tweet.write" not in (pConfig.get("scopes") or []):
    raise channels.ChannelRejected("Authorize X again after enabling profile posts.")
  # Let X apply its weighted character/URL rules. A local len(text) <= 280
  # rejects valid URLs and miscounts CJK and emoji. Never truncate or thread.
  if len(pText) > 10000:
    raise channels.ChannelRejected("The requested X post is too long. Shorten it before publishing.")
  dBody = fCall(pConfig, "POST", "/tweets", json={"text": pText})
  try:
    vId = fId(dBody["data"]["id"], "post ID")
  except (KeyError, TypeError, channels.ChannelError):
    raise XDeliveryUncertain("X did not return a post ID. Check the profile before publishing again.") from None
  return {"channel": "x", "sent": True, "destination": "post", "message_id": vId,
          "url": "https://x.com/i/status/" + vId}


def fSendMessage(pConfig, pText, pDestination="dm"):
  # A post is published only by x_posts.fApprove, when the person in the
  # conversation has answered its code. Nothing that sends a message can
  # publish one.
  if pDestination == "post":
    raise channels.ChannelRejected(
      "Publishing on X needs the x.post tool, and the person's approval of each post by direct message.")
  if pDestination != "dm":
    raise channels.ChannelRejected("X destination must be dm.")
  vId = fSendDm(pConfig, pText)
  return {"channel": "x", "sent": True, "destination": "dm", "message_id": vId}
