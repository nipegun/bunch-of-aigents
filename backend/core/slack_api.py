"""Slack bot HTTP calls, setup validation and private PNG uploads."""

import json
import hashlib
import math
import re
import threading
import time
import uuid
from urllib.parse import urlsplit

import requests

from backend.core import attachments, channels, slack_markdown

cApiBase = "https://slack.com/api"
cChannelPattern = re.compile(r"[CGD][A-Z0-9]+")
cTimestampPattern = re.compile(r"\d+\.\d+")
sTransientErrors = {"ratelimited", "internal_error", "fatal_error", "service_unavailable", "request_timeout"}
dRetryUntil = {}
vRetryLock = threading.Lock()


class SlackRetryLater(channels.ChannelError):
  def __init__(self, pMessage, pRetryAfter=5):
    super().__init__(pMessage)
    try:
      self.vRetryAfter = max(1, min(3600, int(float(pRetryAfter))))
    except (TypeError, ValueError, OverflowError):
      self.vRetryAfter = 5


def fCheckRateLimit(pToken, pMethod):
  """One 429 also delays other messages using the same token and API method."""
  vKey = hashlib.sha256(pToken.encode()).hexdigest() + ":" + pMethod
  with vRetryLock:
    vRemaining = dRetryUntil.get(vKey, 0) - time.monotonic()
    if vRemaining <= 0:
      dRetryUntil.pop(vKey, None)
  if vRemaining > 0:
    raise SlackRetryLater("Slack rate limit; delivery will resume later.", math.ceil(vRemaining))
  return vKey


def fRecordRateLimit(pKey, pSeconds):
  vError = SlackRetryLater("Slack rate limit; delivery will resume later.", pSeconds)
  with vRetryLock:
    dRetryUntil[pKey] = max(dRetryUntil.get(pKey, 0), time.monotonic() + vError.vRetryAfter)
  return vError


def fCall(pConfig, pMethod, pPayload=None, pAppToken=False):
  """Slack also reports failures in HTTP 200 bodies; check both layers."""
  vToken = str(pConfig.get("app_token" if pAppToken else "bot_token") or "").strip()
  if not vToken:
    raise channels.ChannelRejected("Slack needs %s." % ("app_token" if pAppToken else "bot_token"))
  vRateKey = fCheckRateLimit(vToken, pMethod)
  vUrl = str(pConfig.get("api_base") or cApiBase).rstrip("/") + "/" + pMethod
  # Several Slack read/upload methods accept form fields but not JSON bodies.
  # Structured parameters such as files are JSON strings inside that form.
  dForm = {vKey: json.dumps(vValue) if isinstance(vValue, (dict, list, bool)) else vValue
           for vKey, vValue in (pPayload or {}).items()}
  try:
    vResponse = requests.post(vUrl, data=dForm,
      headers={"Authorization": "Bearer " + vToken}, timeout=channels.cSendTimeoutSeconds)
  except requests.RequestException as vError:
    raise SlackRetryLater("Cannot reach Slack: " + channels.fRedactSecrets(vError, pConfig))
  if vResponse.status_code == 429:
    raise fRecordRateLimit(vRateKey, vResponse.headers.get("Retry-After", 5))
  if vResponse.status_code >= 500:
    raise SlackRetryLater("Slack is unavailable (HTTP %s)." % vResponse.status_code)
  if vResponse.status_code != 200:
    raise channels.ChannelRejected("Slack refused %s (HTTP %s)." % (pMethod, vResponse.status_code))
  try:
    dBody = vResponse.json()
  except ValueError:
    raise SlackRetryLater("Slack returned invalid JSON.")
  if not isinstance(dBody, dict):
    raise SlackRetryLater("Slack returned an invalid response.")
  if not dBody.get("ok"):
    vError = str(dBody.get("error") or "unknown_error")
    vMessage = channels.fRedactSecrets("Slack refused %s: %s" % (pMethod, vError), pConfig)
    if vError == "ratelimited":
      raise fRecordRateLimit(vRateKey, vResponse.headers.get("Retry-After", 5))
    if vError in sTransientErrors:
      raise SlackRetryLater(vMessage, vResponse.headers.get("Retry-After", 5))
    if vError == "missing_scope":
      vMessage += ". Required scopes: " + channels.fRedactSecrets(dBody.get("needed", ""), pConfig)
    raise channels.ChannelRejected(vMessage)
  return dBody


def fCheckConfig(pConfig, pListen=False, pCheckSocket=True):
  """Validate the bot's identity and membership of the selected conversation."""
  vChannel = str(pConfig.get("channel_id") or "").strip()
  if not cChannelPattern.fullmatch(vChannel):
    raise channels.ChannelRejected("Slack needs a channel_id such as C0123456789, not a channel name.")
  dAuth = fCall(pConfig, "auth.test")
  if not all(dAuth.get(vKey) for vKey in ("team_id", "user_id", "bot_id")):
    raise channels.ChannelRejected("Use Slack's Bot User OAuth Token, not a user or app token.")
  dChannel = fCall(pConfig, "conversations.info", {"channel": vChannel}).get("channel")
  if not isinstance(dChannel, dict) or dChannel.get("id") != vChannel:
    raise channels.ChannelRejected("Slack returned an invalid channel.")
  if dChannel.get("is_archived"):
    raise channels.ChannelRejected("The Slack channel is archived.")
  if dChannel.get("is_mpim"):
    raise channels.ChannelRejected("Choose a Slack channel or a direct message with the bot.")
  if not dChannel.get("is_im") and not dChannel.get("is_member"):
    raise channels.ChannelRejected("Invite BoA to the Slack channel with /invite @BoA.")
  if pListen:
    if not str(pConfig.get("app_token") or "").strip():
      raise channels.ChannelRejected("Slack listening needs an app_token with connections:write and Socket Mode enabled.")
    if pCheckSocket:
      dSocket = fCall(pConfig, "apps.connections.open", pAppToken=True)
      if not str(dSocket.get("url") or "").startswith("wss://"):
        raise channels.ChannelRejected("Slack did not provide a Socket Mode connection.")
  return {"team_id": str(dAuth["team_id"]), "user_id": str(dAuth["user_id"]),
          "bot_id": str(dAuth["bot_id"]), "channel_id": vChannel}


def fSendMessage(pConfig, pMarkdown, pThreadTs=None, pdDelivered=None,
                  pOnPartSent=None, pDeliveryId=""):
  lParts = slack_markdown.fRenderToMessages(pMarkdown)
  if not lParts:
    raise channels.ChannelRejected("There is nothing to send: the Slack message is empty.")
  lIds = []
  vThread = pThreadTs
  for vIndex, vText in enumerate(lParts):
    vPart = "text:%d" % vIndex
    if (pdDelivered or {}).get(vPart):
      lIds.append(pdDelivered[vPart])
      if not vThread:
        vThread = pdDelivered[vPart]
      continue
    dPayload = {"channel": str(pConfig.get("channel_id") or "").strip(),
                "text": vText, "mrkdwn": True, "parse": "none", "link_names": False,
                "unfurl_links": False, "unfurl_media": False}
    if vThread:
      dPayload["thread_ts"] = str(vThread)
    if pDeliveryId:
      dPayload["client_msg_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, str(pDeliveryId) + ":" + vPart))
    dResult = fCall(pConfig, "chat.postMessage", dPayload)
    vTs = str(dResult.get("ts") or "")
    if not cTimestampPattern.fullmatch(vTs):
      raise SlackRetryLater("Slack did not confirm the sent message timestamp.")
    lIds.append(vTs)
    if pOnPartSent:
      pOnPartSent(vPart, vTs)
    if not vThread:
      vThread = vTs
  return {"channel": "slack", "sent": True, "message_id": lIds[-1], "message_ids": lIds,
          "_audience": channels.fAudienceKey("slack", pConfig)}


def fUploadImage(pConfig, pPng, pName):
  """Upload bytes without sharing them yet; never send the token to an upload URL."""
  try:
    attachments.fReadPngDimensions(pPng)
  except ValueError as vError:
    raise channels.ChannelRejected(str(vError))
  if len(pPng) > attachments.cMaxImageBytes:
    raise channels.ChannelRejected("The image is too large to send.")
  vRateKey = fCheckRateLimit(str(pConfig.get("bot_token") or "").strip(), "files.upload-data")
  dUpload = fCall(pConfig, "files.getUploadURLExternal", {"filename": pName, "length": len(pPng)})
  vFileId = str(dUpload.get("file_id") or "")
  vUrl = str(dUpload.get("upload_url") or "")
  dUrl = urlsplit(vUrl)
  dApi = urlsplit(str(pConfig.get("api_base") or cApiBase))
  vSameCustomOrigin = bool(pConfig.get("api_base")) and (dUrl.scheme, dUrl.netloc) == (dApi.scheme, dApi.netloc)
  if (not vFileId or dUrl.username or dUrl.password
      or not ((dUrl.scheme == "https" and dUrl.hostname == "files.slack.com") or vSameCustomOrigin)):
    raise channels.ChannelRejected("Slack returned an invalid file upload destination.")
  try:
    vResponse = requests.post(vUrl, data=pPng,
      headers={"Content-Type": "application/octet-stream"}, timeout=120, allow_redirects=False)
  except requests.RequestException:
    raise SlackRetryLater("Cannot upload the image to Slack.")
  if vResponse.status_code == 429:
    raise fRecordRateLimit(vRateKey, vResponse.headers.get("Retry-After", 5))
  if vResponse.status_code >= 500:
    raise SlackRetryLater("Slack could not accept the image yet.")
  if vResponse.status_code != 200:
    raise channels.ChannelRejected("Slack refused the image upload (HTTP %s)." % vResponse.status_code)
  return vFileId


def fShareImage(pConfig, pFileId, pName, pThreadTs=None, pConfirmExisting=False):
  """Complete one upload, or recognize a share whose confirmation was lost."""
  vChannelId = str(pConfig["channel_id"]).strip()
  if pConfirmExisting:
    try:
      dFile = fCall(pConfig, "files.info", {"file": pFileId}).get("file") or {}
    except channels.ChannelRejected as vError:
      if "file_not_found" not in str(vError):
        raise
      dFile = {}
    lShares = []
    for dGroup in (dFile.get("shares") or {}).values():
      lShares.extend(dGroup.get(vChannelId) or [])
    if any(str(dShare.get("thread_ts") or "") == str(pThreadTs or "") for dShare in lShares):
      return pFileId
  dPayload = {"files": [{"id": pFileId, "title": pName}], "channel_id": vChannelId}
  if pThreadTs:
    dPayload["thread_ts"] = str(pThreadTs)
  dResult = fCall(pConfig, "files.completeUploadExternal", dPayload)
  if not any(dFile.get("id") == pFileId for dFile in dResult.get("files", [])):
    raise SlackRetryLater("Slack did not confirm the shared file.")
  return pFileId
