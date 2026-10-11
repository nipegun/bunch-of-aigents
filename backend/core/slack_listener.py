#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Slack Socket Mode: persist incoming events, ACK, then run and reply in threads.

The SDK owns reconnects and heartbeats. Its callback only commits input and
acknowledges the envelope; agent runs and uploads happen in the main loop.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import agent_routing, attachments, channels, db, exec_client
from backend.core import slack_api, slack_inbox, slack_markdown, slack_texts

cRetrySeconds = 30
cPollSeconds = 2
sCommands = {"agents", "status", "help", "start"}


def fLogLine(pText, pConfig=None):
  agent_routing.fLogLine(channels.fRedactSecrets(pText, pConfig))


def fAudience(pConfig):
  return channels.fAudienceKey("slack", pConfig)


def fReadListeningConfig():
  try:
    dConfig = channels.fReadChannelConfig("slack")
  except channels.ChannelError:
    return None
  if not dConfig.get("listen"):
    return None
  return dConfig


def fExtractInput(pRequest, pConfig):
  """Whitelist event fields. Tokens, response URLs and triggers are never stored."""
  dPayload = pRequest.payload
  if not isinstance(dPayload, dict) or dPayload.get("team_id") != pConfig.get("_team_id"):
    return None
  if pRequest.type == "events_api":
    if dPayload.get("type") != "event_callback":
      return None
    lAuthorizations = dPayload.get("authorizations") or []
    if lAuthorizations and not any(dAuth.get("user_id") == pConfig.get("_bot_user_id")
                                   for dAuth in lAuthorizations):
      fLogLine("Slack app_token and bot_token do not identify the same installed bot.")
      return None
    dEvent = dPayload.get("event") or {}
    if (dEvent.get("type") not in ("message", "app_mention")
        or dEvent.get("subtype") not in (None, "", "file_share", "thread_broadcast")
        or dEvent.get("bot_id") or dEvent.get("bot_profile")
        or dEvent.get("user") == pConfig.get("_bot_user_id")):
      return None
    vTs = str(dEvent.get("ts") or "")
    if not slack_api.cTimestampPattern.fullmatch(vTs):
      return None
    dInput = {"kind": "message", "channel": str(dEvent.get("channel") or ""),
              "user": str(dEvent.get("user") or ""), "text": str(dEvent.get("text") or ""),
              "ts": vTs, "thread_ts": str(dEvent.get("thread_ts") or vTs)}
    vIdentity = "message:" + vTs
  elif pRequest.type == "slash_commands" and dPayload.get("command") == "/boa":
    dInput = {"kind": "command", "channel": str(dPayload.get("channel_id") or ""),
              "user": str(dPayload.get("user_id") or ""), "text": str(dPayload.get("text") or ""),
              "ts": "", "thread_ts": ""}
    vIdentity = "command:" + str(dPayload.get("trigger_id") or pRequest.envelope_id)
  else:
    return None
  if dInput["channel"] != str(pConfig.get("channel_id") or "").strip() or not dInput["user"]:
    return None
  if dInput["thread_ts"] and not slack_api.cTimestampPattern.fullmatch(dInput["thread_ts"]):
    return None
  vKey = hashlib.sha256((fAudience(pConfig) + ":" + vIdentity).encode()).hexdigest()[:32]
  return vKey, dInput


def fReceiveEnvelope(pClient, pRequest, pConfig):
  from slack_sdk.socket_mode.response import SocketModeResponse
  try:
    vInput = fExtractInput(pRequest, pConfig)
    if vInput:
      vKey, dInput = vInput
      slack_inbox.fQueue(vKey, fAudience(pConfig), dInput)
    pClient.send_socket_mode_response(SocketModeResponse(envelope_id=pRequest.envelope_id))
  except Exception as vError:
    # Withholding ACK makes Slack retry when a database write failed.
    fLogLine("Cannot acknowledge Slack event: %s" % vError, pConfig)


def fSay(pConfig, pText, pThreadTs=None, pAgentId="", pDeliveryId=""):
  dResult = slack_api.fSendMessage(pConfig, pText, pThreadTs, pDeliveryId=pDeliveryId)
  if pAgentId:
    for vId in dResult["message_ids"]:
      slack_inbox.fRememberMessage(fAudience(pConfig), vId, pAgentId)
  return dResult


def fBuildAgentsMessage():
  lAgents = agent_routing.fListAgentNames()
  if not lAgents:
    return slack_texts.fText("agentsNone")
  return "\n".join([slack_texts.fText("agentsHeading"), ""] + [
    "- **@%s** — `%s`" % (vName or vId, vId) for vId, vName in lAgents])


def fRouteMessage(pInput, pConfig):
  vText = slack_markdown.fReadMessageText(pInput["text"], pConfig.get("_bot_user_id"))
  vAudience = fAudience(pConfig)
  vAgentId = slack_inbox.fFindAgentForMessage(vAudience, pInput.get("thread_ts"))
  vNamedId, vRest = agent_routing.fMatchNamedAgent(vText, agent_routing.lDiscordNamePrefixes)
  if vAgentId:
    return vAgentId, vRest if vNamedId == vAgentId else vText
  if vNamedId:
    return vNamedId, vRest
  vSelected = slack_inbox.fReadSelectedAgent(vAudience, pInput["user"])
  if any(vId == vSelected for vId, vName in agent_routing.fListAgentNames()):
    return vSelected, vText
  return "", vText


def fHandleInput(pKey, pInput, pConfig):
  vAudience = fAudience(pConfig)
  vThread = pInput.get("thread_ts") or None
  if "_reply" in pInput:
    fSay(pConfig, pInput["_reply"], vThread, pInput.get("_reply_agent", ""), pKey)
    return

  def fReply(pText, pAgentId=""):
    pInput.update({"_reply": pText, "_reply_agent": pAgentId})
    slack_inbox.fRememberResolution(pKey, pInput, vAudience)
    fSay(pConfig, pText, vThread, pAgentId, pKey)

  vText = slack_markdown.fReadMessageText(pInput["text"], pConfig.get("_bot_user_id"))
  vFirst = vText.split()[0].lower() if vText else ""
  vCommand = vFirst.lstrip("!/") if vFirst.startswith(("!", "/")) else ""
  if pInput["kind"] == "command":
    vCommand = vFirst.lstrip("!/") or "help"
  if vCommand in sCommands:
    if vCommand in ("agents", "start"):
      vAnswer = fBuildAgentsMessage()
    elif vCommand == "status":
      vAnswer = agent_routing.fBuildStatusReport(slack_texts.fText, "boa-channel-slack")
    else:
      vAnswer = slack_texts.fText("helpText")
    fReply(vAnswer)
    return
  if not vText:
    return
  if "_agent_id" in pInput:
    vAgentId, vText = pInput["_agent_id"], pInput["_message"]
  else:
    vAgentId, vText = fRouteMessage(pInput, pConfig)
    if not vAgentId:
      fReply(slack_texts.fText("noAgent"))
      return
    pInput.update({"_agent_id": vAgentId, "_message": vText})
    slack_inbox.fRememberResolution(pKey, pInput, vAudience, vAgentId)
  if not vText:
    fReply(slack_texts.fText("whatShouldItDo", name=agent_routing.fGetAgentName(vAgentId)), vAgentId)
    return
  try:
    dResult = exec_client.fSendChatMessage(vAgentId, vText, pSource="slack",
      pTurnId=pKey[:16], pChannelEventId=pKey)
  except exec_client.ExecError as vError:
    vReason = str(vError)
    if "still answering" in vReason:
      vReply = slack_texts.fText("busy", name=agent_routing.fGetAgentName(vAgentId))
    elif "disabled" in vReason or "too long" in vReason or "reserved" in vReason:
      vReply = slack_texts.fText("cannotStart", name=agent_routing.fGetAgentName(vAgentId), reason=vReason)
    else:
      raise slack_api.SlackRetryLater(vReason)
    fReply(vReply)
    return
  slack_inbox.fAddPending(dResult["turn_id"], vAgentId, vThread, vAudience)
  slack_inbox.fRememberMessage(vAudience, vThread, vAgentId)
  fLogLine("Agent %s started Slack turn %s." % (vAgentId, dResult["turn_id"]))


def fProcessIncoming(pConfig):
  vAudience = fAudience(pConfig)
  slack_inbox.fPrune(vAudience)
  for dIncoming in slack_inbox.fListIncoming(vAudience):
    try:
      fHandleInput(dIncoming["event_key"], json.loads(dIncoming["payload"]), pConfig)
      slack_inbox.fCompleteIncoming(dIncoming["event_key"])
    except channels.ChannelRejected as vError:
      fLogLine("Slack rejected the input response: %s" % vError, pConfig)
      slack_inbox.fCompleteIncoming(dIncoming["event_key"])
    except Exception as vError:
      fLogLine("Slack input will be retried: %s" % vError, pConfig)
      slack_inbox.fDelayIncoming(dIncoming["event_key"], getattr(vError, "vRetryAfter", 5))
      break


def fDeliverParts(pConfig, pPending, pAnswer):
  vTurn = pPending["turn_id"]
  vAgent = pPending["agent_id"]
  vThread = pPending["thread_ts"]
  dDelivered = slack_inbox.fListDeliveredParts(vTurn)
  def fRememberPart(pPart, pMessageId):
    nonlocal vThread
    slack_inbox.fRememberMessage(pPending["audience"], pMessageId, vAgent)
    slack_inbox.fRememberDeliveredPart(vTurn, pPart, pMessageId)
    if not vThread:
      vThread = pMessageId
      slack_inbox.fSetPendingThread(vTurn, vThread)
  vText = str(pAnswer.get("text") or "")
  if vText or not vThread:
    slack_api.fSendMessage(pConfig, "**%s:**\n%s" % (agent_routing.fGetAgentName(vAgent), vText),
      vThread, dDelivered, fRememberPart, vTurn)
  for dImage in attachments.fListMessageAttachments(pAnswer):
    vPart = "image:" + dImage["id"]
    if vPart in dDelivered:
      continue
    try:
      vFileId = dDelivered.get("upload:" + vPart)
      if not vFileId:
        dFirst = exec_client.fReadChatAttachment(vAgent, dImage["id"])
        vBytes = b"".join(exec_client.fIterChatAttachment(vAgent, dImage["id"], dFirst))
        vFileId = slack_api.fUploadImage(pConfig, vBytes, dFirst["attachment"]["name"])
        slack_inbox.fRememberDeliveredPart(vTurn, "upload:" + vPart, vFileId)
      vConfirm = "sharing:" + vPart in dDelivered
      slack_inbox.fRememberDeliveredPart(vTurn, "sharing:" + vPart, vFileId)
      slack_api.fShareImage(pConfig, vFileId, str(dImage.get("caption") or dImage.get("name") or "image.png"),
                            vThread, vConfirm)
      slack_inbox.fRememberDeliveredPart(vTurn, vPart, vFileId)
    except (exec_client.AttachmentUnavailable, channels.ChannelRejected) as vError:
      fLogLine("Cannot deliver Slack image: %s" % vError, pConfig)
      fSay(pConfig, slack_texts.fText("imageFailed", name=str(dImage.get("name") or "image.png")[:128]),
            vThread, vAgent, vTurn + ":" + vPart)
      slack_inbox.fRememberDeliveredPart(vTurn, vPart, "unavailable")


def fDeliverAnswers(pConfig):
  vNow = time.time()
  for dPending in slack_inbox.fListPending():
    vTurn = dPending["turn_id"]
    if dPending["audience"] != fAudience(pConfig):
      slack_inbox.fRemovePending(vTurn)
      continue
    if dPending["retry_at"] > vNow:
      continue
    vExpired = vNow - dPending["asked_at"] > slack_inbox.cExpirySeconds
    try:
      dAnswer = agent_routing.fFindClosedMessage(dPending["agent_id"], vTurn)
      if dAnswer is None and not vExpired:
        continue
      if dAnswer is None:
        dAnswer = {"text": slack_texts.fText("neverFinished")}
      fDeliverParts(pConfig, dPending, dAnswer)
      slack_inbox.fRemovePending(vTurn)
      fLogLine("Answered turn %s on Slack." % vTurn)
    except channels.ChannelRejected as vError:
      fLogLine("Slack rejected turn %s; its answer remains in the web chat: %s" % (vTurn, vError), pConfig)
      slack_inbox.fRemovePending(vTurn)
    except Exception as vError:
      fLogLine("Slack answer will be retried: %s" % vError, pConfig)
      if vExpired:
        slack_inbox.fRemovePending(vTurn)
      else:
        slack_inbox.fDelayPending(vTurn, getattr(vError, "vRetryAfter", 5))
      break


def fOpenSocket(pConfig):
  from slack_sdk.socket_mode import SocketModeClient
  from slack_sdk.web import WebClient
  class RedactedHandler(logging.Handler):
    def emit(self, pRecord):
      fLogLine(pRecord.getMessage(), pConfig)
  vLogger = logging.Logger("boa.slack.socket", level=logging.WARNING)
  vLogger.propagate = False
  vLogger.addHandler(RedactedHandler())
  vWeb = WebClient(token=pConfig["bot_token"],
    base_url=str(pConfig.get("api_base") or slack_api.cApiBase).rstrip("/") + "/",
    logger=vLogger, retry_handlers=[])
  vClient = SocketModeClient(app_token=pConfig["app_token"], web_client=vWeb,
                            logger=vLogger, concurrency=1)
  vClient.socket_mode_request_listeners.append(
    lambda pClient, pRequest: fReceiveEnvelope(pClient, pRequest, pConfig))
  try:
    vClient.connect()
  except Exception:
    vClient.close()
    raise
  return vClient


def fMain():
  vParser = argparse.ArgumentParser(description="Receive Slack messages over Socket Mode.")
  vParser.add_argument("--once", action="store_true", help="Process queued input and answers once without opening a socket.")
  dArguments = vParser.parse_args()
  db.fCreateAppSchema()
  vClient = None
  vActiveKey = ""
  dActive = None
  vWasDisabled = False
  fLogLine("Slack listener started.")
  try:
    while True:
      dConfig = fReadListeningConfig()
      vKey = hashlib.sha256(json.dumps(dConfig, sort_keys=True).encode()).hexdigest() if dConfig else ""
      if vKey != vActiveKey and vClient:
        vClient.close()
        vClient = None
      if not dConfig:
        vActiveKey, dActive = "", None
        if not vWasDisabled:
          fLogLine("Slack is not set up to listen. Waiting for it to be.")
          vWasDisabled = True
        if dArguments.once:
          return 0
        time.sleep(cRetrySeconds)
        continue
      vWasDisabled = False
      try:
        if vKey != vActiveKey or (not dArguments.once and vClient is None):
          dIdentity = slack_api.fCheckConfig(dConfig, pListen=True, pCheckSocket=False)
          dActive = dict(dConfig, _team_id=dIdentity["team_id"], _bot_user_id=dIdentity["user_id"])
          if not dArguments.once:
            vClient = fOpenSocket(dActive)
          vActiveKey = vKey
          fLogLine("Listening to Slack as %s in workspace %s, channel %s only." % (
            dIdentity["user_id"], dIdentity["team_id"], dIdentity["channel_id"]))
        # Recover unacknowledged starts before delivering their pending turns.
        fProcessIncoming(dActive)
        fDeliverAnswers(dActive)
      except Exception as vError:
        fLogLine("Slack listener will retry: %s" % vError, dConfig)
        if dArguments.once:
          return 1
        time.sleep(getattr(vError, "vRetryAfter", cRetrySeconds))
        continue
      if dArguments.once:
        return 0
      time.sleep(cPollSeconds)
  finally:
    if vClient:
      vClient.close()


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("Slack listener stopping.")
