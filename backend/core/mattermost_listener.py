#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Poll one Mattermost channel, persist input and return agent replies in threads."""

import argparse
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import agent_routing, attachments, channels, db, exec_client
from backend.core import mattermost_api, mattermost_inbox, mattermost_texts

cPollSeconds = 3
cRetrySeconds = 30
sCommands = {"agents", "status", "help", "start"}


def fLogLine(pText, pConfig=None):
  agent_routing.fLogLine(channels.fRedactSecrets(pText, pConfig))


def fAudience(pConfig):
  return channels.fAudienceKey("mattermost", pConfig)


def fReadListeningConfig():
  try:
    dConfig = channels.fReadChannelConfig("mattermost")
  except channels.ChannelError:
    return None
  return dConfig if dConfig.get("listen") else None


def fReadMessageText(pText, pConfig):
  vText = str(pText or "").strip()
  vBotName = str(pConfig.get("_bot_username") or "")
  if vBotName and not agent_routing.fMatchNamedAgent(vText, agent_routing.lDiscordNamePrefixes)[0]:
    vText = re.sub(r"^@" + re.escape(vBotName) + r"(?:\s+|$)", "", vText, flags=re.I).strip()
  return vText


def fIsHuman(pUserId, pConfig):
  dUsers = pConfig.setdefault("_users", {})
  vCached = dUsers.get(pUserId)
  if vCached and vCached[1] > time.monotonic():
    return vCached[0]
  dUser = mattermost_api.fCall(pConfig, "GET", "/users/" + pUserId, pAllowMissing=True)
  vHuman = bool(isinstance(dUser, dict) and dUser.get("id") == pUserId
                and not dUser.get("is_bot") and not dUser.get("delete_at"))
  dUsers[pUserId] = (vHuman, time.monotonic() + 300)
  if len(dUsers) > 1000:
    dUsers.pop(next(iter(dUsers)))
  return vHuman


def fExtractInput(pPost, pConfig):
  """Ignore bots, webhooks, edits and system events before routing any text."""
  if (pPost.get("channel_id") != str(pConfig.get("channel_id") or "").strip()
      or pPost.get("user_id") == pConfig.get("_bot_user_id")
      or pPost.get("type") or pPost.get("delete_at") or pPost.get("edit_at")):
    return None
  dProps = pPost.get("props") or {}
  if not isinstance(dProps, dict) or any(str(dProps.get(vKey)).lower() == "true"
                                       for vKey in ("from_webhook", "from_bot", "from_plugin")):
    return None
  vUser = mattermost_api.fId(pPost.get("user_id"), "user ID")
  vPost = mattermost_api.fId(pPost.get("id"), "post ID")
  vRoot = mattermost_api.fId(pPost.get("root_id") or vPost, "root_id")
  if not str(pPost.get("message") or "").strip() or not fIsHuman(vUser, pConfig):
    return None
  return mattermost_inbox.fEventKey(fAudience(pConfig), vPost), {
    "channel": str(pPost["channel_id"]), "user": vUser, "text": str(pPost["message"]),
    "post_id": vPost, "root_id": vRoot, "create_at": int(pPost.get("create_at") or 0)}


def fPoll(pConfig):
  vAudience = fAudience(pConfig)
  dCursor = mattermost_inbox.fReadCursor(vAudience)
  vGeneration = str(pConfig.get("poll_generation") or "")
  if dCursor is None or dCursor["generation"] != vGeneration:
    mattermost_inbox.fInitializePolling(vAudience, mattermost_api.fReadPosts(pConfig), vGeneration)
    fLogLine("Mattermost checkpoint initialized; earlier channel messages will not be replayed.")
    return
  lPosts = mattermost_api.fReadNewPosts(pConfig, dCursor["last_at"])
  lInputs = []
  vLastAt = dCursor["last_at"]
  vOldest = max(dCursor["first_at"], int((time.time() - mattermost_inbox.cExpirySeconds) * 1000))
  for dPost in sorted(lPosts, key=lambda pPost: (int(pPost.get("create_at") or 0), pPost["id"])):
    vAt = int(dPost.get("create_at") or 0)
    vLastAt = max(vLastAt, vAt)
    if vAt < vOldest:
      continue
    vInput = fExtractInput(dPost, pConfig)
    if vInput:
      lInputs.append(vInput)
  mattermost_inbox.fCommitPoll(vAudience, lInputs, vLastAt)


def fSay(pConfig, pText, pRootId, pAgentId="", pDeliveryId=""):
  dResult = mattermost_api.fSendMessage(pConfig, pText, pRootId, pDeliveryId=pDeliveryId)
  if pAgentId:
    for vId in dResult["message_ids"]:
      mattermost_inbox.fRememberMessage(fAudience(pConfig), vId, pAgentId)
  return dResult


def fBuildAgentsMessage():
  lAgents = agent_routing.fListAgentNames()
  if not lAgents:
    return mattermost_texts.fText("agentsNone")
  return "\n".join([mattermost_texts.fText("agentsHeading"), ""] + [
    "- **@%s** — `%s`" % (vName or vId, vId) for vId, vName in lAgents])


def fRouteMessage(pInput, pConfig):
  vText = fReadMessageText(pInput["text"], pConfig)
  vAudience = fAudience(pConfig)
  vAgentId = mattermost_inbox.fFindAgentForMessage(vAudience, pInput["root_id"])
  vNamedId, vRest = agent_routing.fMatchNamedAgent(vText, agent_routing.lDiscordNamePrefixes)
  if vAgentId:
    return vAgentId, vRest if vNamedId == vAgentId else vText
  if vNamedId:
    return vNamedId, vRest
  vSelected = mattermost_inbox.fReadSelectedAgent(vAudience, pInput["user"])
  if any(vId == vSelected for vId, vName in agent_routing.fListAgentNames()):
    return vSelected, vText
  return "", vText


def fHandleInput(pKey, pInput, pConfig):
  vAudience = fAudience(pConfig)
  vRoot = pInput["root_id"]
  if "_reply" in pInput:
    fSay(pConfig, pInput["_reply"], vRoot, pInput.get("_reply_agent", ""), pKey)
    return

  def fReply(pText, pAgentId=""):
    pInput.update({"_reply": pText, "_reply_agent": pAgentId})
    mattermost_inbox.fRememberResolution(pKey, pInput, vAudience)
    fSay(pConfig, pText, vRoot, pAgentId, pKey)

  vText = fReadMessageText(pInput["text"], pConfig)
  vFirst = vText.split()[0].lower() if vText else ""
  vCommand = vFirst[1:] if vFirst.startswith("!") else ""
  if vCommand in sCommands:
    if vCommand in ("agents", "start"):
      vAnswer = fBuildAgentsMessage()
    elif vCommand == "status":
      vAnswer = agent_routing.fBuildStatusReport(mattermost_texts.fText, "boa-channel-mattermost")
    else:
      vAnswer = mattermost_texts.fText("helpText")
    fReply(vAnswer)
    return
  if not vText:
    return
  if "_agent_id" in pInput:
    vAgentId, vText = pInput["_agent_id"], pInput["_message"]
  else:
    vAgentId, vText = fRouteMessage(pInput, pConfig)
    if not vAgentId:
      fReply(mattermost_texts.fText("noAgent"))
      return
    pInput.update({"_agent_id": vAgentId, "_message": vText})
    mattermost_inbox.fRememberResolution(pKey, pInput, vAudience, vAgentId)
  if not vText:
    fReply(mattermost_texts.fText("whatShouldItDo", name=agent_routing.fGetAgentName(vAgentId)), vAgentId)
    return
  try:
    dResult = exec_client.fSendChatMessage(vAgentId, vText, pSource="mattermost",
      pTurnId=pKey[:16], pChannelEventId=pKey)
  except exec_client.ExecError as vError:
    vReason = str(vError)
    if "still answering" in vReason:
      vReply = mattermost_texts.fText("busy", name=agent_routing.fGetAgentName(vAgentId))
    elif "disabled" in vReason or "too long" in vReason or "reserved" in vReason:
      vReply = mattermost_texts.fText("cannotStart", name=agent_routing.fGetAgentName(vAgentId), reason=vReason)
    else:
      raise mattermost_api.MattermostRetryLater(vReason)
    fReply(vReply)
    return
  mattermost_inbox.fAddPending(dResult["turn_id"], vAgentId, vRoot, vAudience)
  mattermost_inbox.fRememberMessage(vAudience, vRoot, vAgentId)
  fLogLine("Agent %s started Mattermost turn %s." % (vAgentId, dResult["turn_id"]))


def fProcessIncoming(pConfig):
  vAudience = fAudience(pConfig)
  mattermost_inbox.fPrune(vAudience)
  for dIncoming in mattermost_inbox.fListIncoming(vAudience):
    try:
      fHandleInput(dIncoming["event_key"], json.loads(dIncoming["payload"]), pConfig)
      mattermost_inbox.fCompleteIncoming(dIncoming["event_key"])
    except channels.ChannelRejected as vError:
      fLogLine("Mattermost rejected the input response: %s" % vError, pConfig)
      mattermost_inbox.fCompleteIncoming(dIncoming["event_key"])
    except Exception as vError:
      fLogLine("Mattermost input will be retried: %s" % vError, pConfig)
      mattermost_inbox.fDelayIncoming(dIncoming["event_key"], getattr(vError, "vRetryAfter", 5))
      break


def fDeliverParts(pConfig, pPending, pAnswer):
  vTurn = pPending["turn_id"]
  vAgent = pPending["agent_id"]
  vRoot = pPending["root_id"]
  dDelivered = mattermost_inbox.fListDeliveredParts(vTurn)
  if not vRoot and dDelivered.get("text:0"):
    vRoot = dDelivered["text:0"]
    mattermost_inbox.fSetPendingThread(vTurn, vRoot)

  def fRememberPart(pPart, pMessageId):
    nonlocal vRoot
    mattermost_inbox.fRememberMessage(pPending["audience"], pMessageId, vAgent)
    mattermost_inbox.fRememberDeliveredPart(vTurn, pPart, pMessageId)
    if not vRoot:
      vRoot = pMessageId
      mattermost_inbox.fSetPendingThread(vTurn, vRoot)

  vText = str(pAnswer.get("text") or "")
  if vText or not vRoot:
    mattermost_api.fSendMessage(pConfig, "**%s:**\n%s" % (agent_routing.fGetAgentName(vAgent), vText),
      vRoot, dDelivered, fRememberPart, vTurn)
  for dImage in attachments.fListMessageAttachments(pAnswer):
    vPart = "image:" + dImage["id"]
    if vPart in dDelivered:
      continue
    try:
      vFileId = dDelivered.get("upload:" + vPart)
      if not vFileId:
        dFirst = exec_client.fReadChatAttachment(vAgent, dImage["id"])
        vBytes = b"".join(exec_client.fIterChatAttachment(vAgent, dImage["id"], dFirst))
        vFileId = mattermost_api.fUploadImage(pConfig, vBytes, dFirst["attachment"]["name"])
        mattermost_inbox.fRememberDeliveredPart(vTurn, "upload:" + vPart, vFileId)
      vPostId = mattermost_api.fCreatePost(pConfig, str(dImage.get("caption") or dImage.get("name") or "image.png")[:1000],
        vRoot, [vFileId], vTurn + ":" + vPart)
      fRememberPart(vPart, vPostId)
    except (exec_client.AttachmentUnavailable, channels.ChannelRejected) as vError:
      fLogLine("Cannot deliver Mattermost image: %s" % vError, pConfig)
      fSay(pConfig, mattermost_texts.fText("imageFailed", name=str(dImage.get("name") or "image.png")[:128]),
            vRoot, vAgent, vTurn + ":failed:" + vPart)
      mattermost_inbox.fRememberDeliveredPart(vTurn, vPart, "unavailable")


def fDeliverAnswers(pConfig):
  vNow = time.time()
  for dPending in mattermost_inbox.fListPending():
    vTurn = dPending["turn_id"]
    if dPending["audience"] != fAudience(pConfig):
      mattermost_inbox.fRemovePending(vTurn)
      continue
    if dPending["retry_at"] > vNow:
      continue
    vExpired = vNow - dPending["asked_at"] > mattermost_inbox.cExpirySeconds
    try:
      dAnswer = agent_routing.fFindClosedMessage(dPending["agent_id"], vTurn)
      if dAnswer is None and not vExpired:
        continue
      if dAnswer is None:
        dAnswer = {"text": mattermost_texts.fText("neverFinished")}
      fDeliverParts(pConfig, dPending, dAnswer)
      mattermost_inbox.fRemovePending(vTurn)
      fLogLine("Answered turn %s on Mattermost." % vTurn)
    except channels.ChannelRejected as vError:
      fLogLine("Mattermost rejected turn %s; its answer remains in the web chat: %s" % (vTurn, vError), pConfig)
      mattermost_inbox.fRemovePending(vTurn)
    except Exception as vError:
      fLogLine("Mattermost answer will be retried: %s" % vError, pConfig)
      if vExpired:
        mattermost_inbox.fRemovePending(vTurn)
      else:
        mattermost_inbox.fDelayPending(vTurn, getattr(vError, "vRetryAfter", 5))
      break


def fMain():
  vParser = argparse.ArgumentParser(description="Receive Mattermost messages through its REST API.")
  vParser.add_argument("--once", action="store_true", help="Poll and process input and answers once.")
  dArguments = vParser.parse_args()
  db.fCreateAppSchema()
  vActiveKey = ""
  dActive = None
  vWasDisabled = False
  fLogLine("Mattermost listener started.")
  while True:
    dConfig = fReadListeningConfig()
    if not dConfig:
      vActiveKey, dActive = "", None
      if not vWasDisabled:
        fLogLine("Mattermost is not set up to listen. Waiting for it to be.")
        vWasDisabled = True
      if dArguments.once:
        return 0
      time.sleep(cRetrySeconds)
      continue
    vWasDisabled = False
    vKey = hashlib.sha256(json.dumps(dConfig, sort_keys=True).encode()).hexdigest()
    try:
      if vKey != vActiveKey:
        dIdentity = mattermost_api.fCheckConfig(dConfig)
        dActive = dict(dConfig, _bot_user_id=dIdentity["user_id"], _bot_username=dIdentity["username"])
        vActiveKey = vKey
        fLogLine("Listening to Mattermost as %s on %s, channel %s only." % (
          dIdentity["username"], dIdentity["server_url"], dIdentity["channel_id"]))
      fPoll(dActive)
      fProcessIncoming(dActive)
      fDeliverAnswers(dActive)
    except Exception as vError:
      fLogLine("Mattermost listener will retry: %s" % vError, dConfig)
      if dArguments.once:
        return 1
      time.sleep(getattr(vError, "vRetryAfter", cRetrySeconds))
      continue
    if dArguments.once:
      return 0
    time.sleep(cPollSeconds)


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("Mattermost listener stopping.")
