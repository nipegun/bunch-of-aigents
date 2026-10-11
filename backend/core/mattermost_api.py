"""Mattermost REST bot conversations, uploads and legacy outgoing webhooks."""

import hashlib
import math
import re
import threading
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import requests

from backend.core import attachments, channels, discord_markdown

cIdPattern = re.compile(r"[a-z0-9]{26}")
cMessageLength = 4000
cPageSize = 200
dRetryUntil = {}
vRetryLock = threading.Lock()


class MattermostRetryLater(channels.ChannelError):
  def __init__(self, pMessage, pRetryAfter=5):
    super().__init__(pMessage)
    try:
      self.vRetryAfter = max(1, min(3600, int(float(pRetryAfter))))
    except (ValueError, TypeError, OverflowError):
      self.vRetryAfter = 5


def fServerUrl(pConfig):
  """Accept self-hosted HTTP or HTTPS, including a reverse proxy subpath."""
  vValue = str(pConfig.get("server_url") or "").strip().rstrip("/")
  try:
    dUrl = urlsplit(vValue)
    vPort = dUrl.port
  except ValueError:
    raise channels.ChannelRejected("Mattermost needs a valid server_url.")
  if (dUrl.scheme not in ("http", "https") or not dUrl.hostname
      or dUrl.username or dUrl.password or dUrl.query or dUrl.fragment
      or any(vChar.isspace() for vChar in vValue)):
    raise channels.ChannelRejected("Mattermost needs a server_url such as https://chat.example.org, without credentials or query parameters.")
  vPath = dUrl.path.rstrip("/")
  if vPath.endswith("/api/v4"):
    vPath = vPath[:-7]
  return urlunsplit((dUrl.scheme, dUrl.netloc.lower(), vPath, "", ""))


def fId(pValue, pField):
  vValue = str(pValue or "").strip()
  if not cIdPattern.fullmatch(vValue):
    raise channels.ChannelRejected("Mattermost needs a 26-character %s, not a channel name or URL." % pField)
  return vValue


def fCall(pConfig, pMethod, pPath, pPayload=None, pParams=None, pFiles=None, pAllowMissing=False):
  vToken = str(pConfig.get("bot_token") or "").strip()
  if not vToken:
    raise channels.ChannelRejected("Mattermost needs a bot_token from a bot account.")
  if any(vCharacter.isspace() for vCharacter in vToken):
    raise channels.ChannelRejected("The Mattermost bot_token must not contain whitespace.")
  vServer = fServerUrl(pConfig)
  vRateKey = hashlib.sha256((vServer + ":" + vToken).encode()).hexdigest()
  with vRetryLock:
    vRemaining = dRetryUntil.get(vRateKey, 0) - time.monotonic()
  if vRemaining > 0:
    raise MattermostRetryLater("Mattermost rate limit; delivery will resume later.", math.ceil(vRemaining))
  dArguments = {"headers": {"Authorization": "Bearer " + vToken},
    "params": pParams, "timeout": channels.cSendTimeoutSeconds, "allow_redirects": False}
  if pFiles:
    dArguments.update(data=pPayload, files=pFiles)
  elif pPayload is not None:
    dArguments["json"] = pPayload
  try:
    vResponse = requests.request(pMethod, vServer + "/api/v4" + pPath, **dArguments)
  except requests.RequestException as vError:
    raise MattermostRetryLater("Cannot reach Mattermost: " + channels.fRedactSecrets(vError, pConfig))
  if vResponse.status_code == 429:
    vDelay = vResponse.headers.get("Retry-After")
    if vDelay is None:
      try:
        vDelay = max(1, float(vResponse.headers.get("X-RateLimit-Reset", 0)) - time.time())
      except (TypeError, ValueError):
        vDelay = 5
    vError = MattermostRetryLater("Mattermost rate limit; delivery will resume later.", vDelay)
    with vRetryLock:
      dRetryUntil[vRateKey] = time.monotonic() + vError.vRetryAfter
    raise vError
  if vResponse.status_code >= 500 or vResponse.status_code in (408, 425):
    raise MattermostRetryLater("Mattermost is unavailable (HTTP %s)." % vResponse.status_code)
  if vResponse.status_code == 404 and pAllowMissing:
    return None
  if vResponse.status_code not in (200, 201):
    vDetail = ""
    try:
      dError = vResponse.json()
      if isinstance(dError, dict):
        vDetail = ": " + str(dError.get("message") or dError.get("id") or "")[:300]
    except ValueError:
      pass
    raise channels.ChannelRejected(channels.fRedactSecrets(
      "Mattermost refused %s %s (HTTP %s)%s" % (pMethod, pPath, vResponse.status_code, vDetail), pConfig))
  try:
    dBody = vResponse.json()
  except ValueError:
    raise MattermostRetryLater("Mattermost returned invalid JSON.")
  if not isinstance(dBody, (dict, list)):
    raise MattermostRetryLater("Mattermost returned an invalid response.")
  return dBody


def fPostList(pBody, pChannelId):
  """The posts map can also contain old thread parents; only order is the page."""
  if not isinstance(pBody, dict) or not isinstance(pBody.get("order"), list) or not isinstance(pBody.get("posts"), dict):
    raise MattermostRetryLater("Mattermost returned an invalid post list.")
  lPosts = []
  for vId in pBody["order"]:
    dPost = pBody["posts"].get(vId)
    if not isinstance(dPost, dict) or dPost.get("id") != vId or not cIdPattern.fullmatch(str(vId)):
      raise MattermostRetryLater("Mattermost returned an invalid post.")
    if dPost.get("channel_id") == pChannelId:
      lPosts.append(dPost)
  return lPosts


def fReadPosts(pConfig, pSince=None, pPage=0, pLimit=cPageSize):
  vChannel = fId(pConfig.get("channel_id"), "channel_id")
  dParams = {"skipFetchThreads": "true", "collapsedThreads": "false"}
  if pSince is not None and pSince > 0:
    dParams["since"] = int(pSince)
  else:
    dParams.update(page=pPage, per_page=pLimit)
  return fPostList(fCall(pConfig, "GET", "/channels/" + vChannel + "/posts", pParams=dParams), vChannel)


def fReadNewPosts(pConfig, pSince):
  """Overlap timestamps for ties; paginate when since hits its 1000-post cap."""
  lPosts = fReadPosts(pConfig, max(1, pSince - 1000))
  if len(lPosts) < 1000:
    return lPosts
  dPosts = {}
  for vPage in range(100):
    lPage = fReadPosts(pConfig, pPage=vPage)
    for dPost in lPage:
      if int(dPost.get("create_at") or 0) >= pSince - 1000:
        dPosts[dPost["id"]] = dPost
    if len(lPage) < cPageSize or any(int(dPost.get("create_at") or 0) < pSince - 1000 for dPost in lPage):
      return list(dPosts.values())
  raise MattermostRetryLater("Mattermost catch-up exceeded 20000 posts; the polling checkpoint was retained.", 30)


def fCheckConfig(pConfig):
  vChannel = fId(pConfig.get("channel_id"), "channel_id")
  dUser = fCall(pConfig, "GET", "/users/me")
  if not isinstance(dUser, dict) or not dUser.get("is_bot") or dUser.get("delete_at"):
    raise channels.ChannelRejected("Use the access token of an enabled Mattermost bot account.")
  vBotId = fId(dUser.get("id"), "bot user ID")
  dChannel = fCall(pConfig, "GET", "/channels/" + vChannel)
  if (not isinstance(dChannel, dict) or dChannel.get("id") != vChannel
      or dChannel.get("delete_at") or dChannel.get("type") not in ("O", "P", "D", "G")):
    raise channels.ChannelRejected("Choose an active Mattermost channel or direct conversation.")
  dMember = fCall(pConfig, "GET", "/channels/" + vChannel + "/members/" + vBotId)
  if not isinstance(dMember, dict) or dMember.get("user_id") != vBotId:
    raise channels.ChannelRejected("Add the Mattermost bot to the selected channel.")
  fReadPosts(pConfig, pLimit=1)
  return {"user_id": vBotId, "username": str(dUser.get("username") or ""),
          "channel_id": vChannel, "server_url": fServerUrl(pConfig)}


def fFindDeliveredPost(pConfig, pRootId, pDeliveryId):
  """Recover a lost acknowledgement beyond Mattermost's short pending-ID cache."""
  if not pRootId or not pDeliveryId:
    return None
  vRoot = fId(pRootId, "root_id")
  dThread = fCall(pConfig, "GET", "/posts/" + vRoot + "/thread")
  vBot = pConfig.get("_bot_user_id")
  if not vBot:
    vBot = fCall(pConfig, "GET", "/users/me").get("id")
  for dPost in fPostList(dThread, fId(pConfig.get("channel_id"), "channel_id")):
    if (dPost.get("user_id") == vBot and not dPost.get("delete_at")
        and dPost.get("root_id") == vRoot
        and (dPost.get("props") or {}).get("boa_delivery_id") == pDeliveryId):
      return dPost
  return None


def fCreatePost(pConfig, pText, pRootId=None, pFileIds=None, pDeliveryId=""):
  vChannel = fId(pConfig.get("channel_id"), "channel_id")
  vDelivery = hashlib.sha256((channels.fAudienceKey("mattermost", pConfig) + ":" + pDeliveryId).encode()).hexdigest() if pDeliveryId else ""
  dExisting = fFindDeliveredPost(pConfig, pRootId, vDelivery)
  if dExisting:
    return fId(dExisting.get("id"), "post ID")
  dPost = {"channel_id": vChannel, "message": pText}
  if pRootId:
    dPost["root_id"] = fId(pRootId, "root_id")
  if pFileIds:
    dPost["file_ids"] = [fId(vId, "file ID") for vId in pFileIds]
  if vDelivery:
    dPost.update(pending_post_id=vDelivery, props={"boa_delivery_id": vDelivery})
  dResult = fCall(pConfig, "POST", "/posts", dPost)
  if not isinstance(dResult, dict) or dResult.get("channel_id") != vChannel:
    raise MattermostRetryLater("Mattermost did not confirm the posted message.")
  return fId(dResult.get("id"), "post ID")


def fSendMessage(pConfig, pMarkdown, pRootId=None, pdDelivered=None, pOnPartSent=None, pDeliveryId=""):
  lParts = discord_markdown.fSplit(str(pMarkdown or "").replace("\r\n", "\n"), cMessageLength, 4)
  if not lParts:
    raise channels.ChannelRejected("There is nothing to send: the Mattermost message is empty.")
  lIds = []
  vRoot = pRootId
  vDelivery = pDeliveryId or uuid.uuid4().hex
  for vIndex, vText in enumerate(lParts):
    vPart = "text:%d" % vIndex
    vId = (pdDelivered or {}).get(vPart)
    if not vId:
      vId = fCreatePost(pConfig, vText, vRoot, pDeliveryId=vDelivery + ":" + vPart)
      if pOnPartSent:
        pOnPartSent(vPart, vId)
    lIds.append(vId)
    if not vRoot:
      vRoot = vId
  return {"channel": "mattermost", "sent": True, "message_id": lIds[-1], "message_ids": lIds,
          "_audience": channels.fAudienceKey("mattermost", pConfig)}


def fUploadImage(pConfig, pPng, pName):
  try:
    attachments.fReadPngDimensions(pPng)
  except ValueError as vError:
    raise channels.ChannelRejected(str(vError))
  if len(pPng) > attachments.cMaxImageBytes:
    raise channels.ChannelRejected("The image is too large to send.")
  dResult = fCall(pConfig, "POST", "/files", {"channel_id": fId(pConfig.get("channel_id"), "channel_id")},
    pFiles={"files": (pName, pPng, "image/png")})
  lFiles = dResult.get("file_infos") if isinstance(dResult, dict) else None
  if not isinstance(lFiles, list) or len(lFiles) != 1 or not isinstance(lFiles[0], dict):
    raise MattermostRetryLater("Mattermost did not confirm the uploaded PNG.")
  return fId(lFiles[0].get("id"), "file ID")
